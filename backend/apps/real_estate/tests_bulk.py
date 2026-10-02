"""不動産の絞り込み追加と一括変更（権限・原子性・選択の固定・履歴）の回帰テスト。"""
from datetime import date
from unittest import mock

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.authentication.roles import ROLE_PERMISSIONS, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.real_estate import bulk_service
from apps.real_estate.models import RealEstateTransaction

from .tests import RealEstateFixture

LIST_URL = '/api/real-estate/transactions/'
PREVIEW_URL = LIST_URL + 'bulk-preview/'
BULK_URL = LIST_URL + 'bulk-update/'


class BulkFixture(RealEstateFixture):
    def setUp(self):
        super().setUp()
        self.a = self.create_tx(responsible_name='焦', stage='contract', transaction_date='2026-10-05',
                                transfer_status='pending')
        self.b = self.create_tx(user=self.staff_b, responsible_name='周', stage='contract',
                                transaction_date='2026-10-20', transfer_status='transferred')
        self.c = self.create_tx(responsible_name='焦', stage='inquiry', transaction_date='2026-09-30')

    def items(self, ids):
        """一覧で見た時点の ID と updated_at（API が返す文字列そのまま）。"""
        rows = {tx.pk: tx for tx in RealEstateTransaction.objects.filter(pk__in=ids)}
        return [{'id': pk, 'updated_at': timezone.localtime(rows[pk].updated_at).isoformat()} if pk in rows
                else {'id': pk, 'updated_at': timezone.now().isoformat()} for pk in ids]

    def select(self, user, ids):
        """一覧で選択した記録を固定する（bulk-preview）。"""
        return self.api(user, 'post', PREVIEW_URL, {'selection': {'mode': 'ids', 'items': self.items(ids)}})

    def submit(self, user, token, count, changes=None, **extra):
        body = {'selection_token': token, 'changes': changes or {}, 'expected_count': count, **extra}
        return self.api(user, 'post', BULK_URL, body)

    def bulk(self, user, ids, changes=None, **extra):
        """選択 → 実行。選択の段階で拒否された場合はその応答を返す。"""
        selected = self.select(user, ids)
        if selected.status_code != 200:
            return selected
        return self.submit(user, selected.json()['selection_token'], extra.pop('expected_count', len(ids)), changes, **extra)

    def stage_of(self, tx):
        return RealEstateTransaction.objects.get(pk=tx['id']).stage

    def grant_bulk(self, user):
        user.user_permissions.add(Permission.objects.get(codename='bulk_change_real_estate'))


class FilterTests(BulkFixture, TestCase):
    def ids(self, **params):
        self.client.force_login(self.staff_a)
        response = self.client.get(LIST_URL, params)
        self.assertEqual(response.status_code, 200, response.content)
        return {row['id'] for row in response.json()['results']}

    def test_transaction_date_range_and_transfer_status(self):
        self.assertEqual(self.ids(transaction_date_from='2026-10-01', transaction_date_to='2026-10-31'),
                         {self.a['id'], self.b['id']})
        self.assertEqual(self.ids(transaction_date_to='2026-09-30'), {self.c['id']})
        self.assertEqual(self.ids(transfer_status='pending'), {self.a['id']})
        self.assertEqual(self.ids(transfer_status='unset'), {self.c['id']})

    def test_invalid_date_is_a_readable_400(self):
        self.client.force_login(self.staff_a)
        response = self.client.get(LIST_URL, {'transaction_date_from': '2026-13-99'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('transaction_date_from', response.json())


class BulkPermissionTests(BulkFixture, TestCase):
    def test_role_definition_grants_bulk_only_to_system_admin(self):
        code = 'real_estate.bulk_change_real_estate'
        self.assertEqual([name for name, codes in ROLE_PERMISSIONS.items() if code in codes], [SYSTEM_ADMIN])
        self.assertNotIn(code, ROLE_PERMISSIONS[STAFF])

    def test_ordinary_user_keeps_single_edit_but_bulk_is_forbidden(self):
        url = f"{LIST_URL}{self.b['id']}/"
        self.assertEqual(self.api(self.staff_a, 'patch', url, {'stage': 'screening'}).status_code, 200)
        self.assertEqual(self.bulk(self.staff_a, [self.a['id']], {'stage': 'settled'}).status_code, 403)
        self.assertEqual(self.api(self.staff_a, 'post', PREVIEW_URL, {'filters': {}}).status_code, 403)
        self.assertEqual(self.bulk(self.manager, [self.a['id']], {'stage': 'settled'}).status_code, 403)
        self.assertEqual(self.stage_of(self.a), 'contract')
        self.assertTrue(AuditLog.objects.filter(action='access_denied', user=self.staff_a).exists())

    def test_superuser_without_explicit_permission_is_not_a_bypass(self):
        outsider = make_user('re_bulk_su', superuser=True)
        self.assertEqual(self.bulk(outsider, [self.a['id']], {'stage': 'settled'}).status_code, 403)

    def test_bulk_permission_alone_without_single_edit_is_not_enough(self):
        viewer = make_user('re_bulk_viewer')
        for codename in ('use_real_estate', 'view_real_estate', 'bulk_change_real_estate'):
            viewer.user_permissions.add(Permission.objects.get(codename=codename))
        self.assertEqual(self.bulk(viewer, [self.a['id']], {'stage': 'settled'}).status_code, 403)

    def test_explicitly_granted_ordinary_user_can_bulk_change_records_of_any_assignee(self):
        self.grant_bulk(self.staff_a)
        response = self.bulk(self.staff_a, [self.a['id'], self.b['id']], {'responsible_name': '田中'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['updated'], 2)
        self.assertEqual(set(RealEstateTransaction.objects.filter(pk__in=[self.a['id'], self.b['id']])
                             .values_list('responsible_name', flat=True)), {'田中'})


class BulkUpdateTests(BulkFixture, TestCase):
    def test_li_bulk_settle_assignee_and_date_with_readable_history(self):
        self.assertFalse(self.li.is_superuser)
        ids = [self.a['id'], self.b['id']]
        response = self.bulk(self.li, ids, {'stage': 'settled', 'responsible_name': '田中',
                                            'transaction_date': '2026-10-31'})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['matched'], body['updated'], body['unchanged']), (2, 2, 0))
        for tx in RealEstateTransaction.objects.filter(pk__in=ids):
            self.assertEqual((tx.stage, tx.responsible_name, tx.transaction_date), ('settled', '田中', date(2026, 10, 31)))
            self.assertEqual(tx.updated_by, self.li)
        self.assertEqual(self.stage_of(self.c), 'inquiry')  # 対象外は変わらない

        history = self.api(self.staff_a, 'get', f"{LIST_URL}{self.b['id']}/audit-log/").json()
        row = next(r for r in history if '一括変更' in r['message'])
        self.assertEqual(row['actor'], '李')
        self.assertIn({'field': '段階', 'before': '契約', 'after': '完了'}, row['changes'])
        self.assertIn({'field': '担当者', 'before': '周', 'after': '田中'}, row['changes'])
        self.assertIn({'field': '取引日', 'before': '2026-10-20', 'after': '2026-10-31'}, row['changes'])
        self.assertNotIn('technical_details', row)  # 通常画面に項目 ID・JSON・権限名を出さない

        summary = AuditLog.objects.get(action='transaction_bulk_updated')
        self.assertEqual(summary.user, self.li)
        self.assertEqual(summary.via_permission, 'real_estate.bulk_change_real_estate')
        self.assertEqual((summary.extra['matched'], summary.extra['updated']), (2, 2))
        self.assertEqual(summary.extra['fields'], ['responsible_name', 'stage', 'transaction_date'])
        self.assertEqual(AuditLog.objects.filter(action='transaction_updated',
                                                 extra__batch_id=summary.extra['batch_id']).count(), 2)

    def test_only_checked_fields_change_and_same_value_rows_are_left_untouched(self):
        before = RealEstateTransaction.objects.get(pk=self.a['id'])
        response = self.bulk(self.li, [self.a['id'], self.c['id']], {'stage': 'contract'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['updated'], response.json()['unchanged']), (1, 1))
        after = RealEstateTransaction.objects.get(pk=self.a['id'])
        self.assertEqual((after.responsible_name, after.transaction_date, after.updated_at, after.updated_by),
                         (before.responsible_name, before.transaction_date, before.updated_at, before.updated_by))

    def test_clearing_requires_explicit_clear_fields(self):
        ids = [self.a['id']]
        self.assertEqual(self.bulk(self.li, ids, {'responsible_name': ''}).status_code, 400)
        self.assertEqual(self.bulk(self.li, ids, {'transaction_date': None}).status_code, 400)
        self.assertEqual(RealEstateTransaction.objects.get(pk=self.a['id']).responsible_name, '焦')
        self.assertEqual(self.bulk(self.li, ids, clear_fields=['stage']).status_code, 400)
        self.assertEqual(self.bulk(self.li, ids, {'responsible_name': 'x'}, clear_fields=['responsible_name']).status_code, 400)
        cleared = self.bulk(self.li, ids, clear_fields=['responsible_name', 'transaction_date'])
        self.assertEqual(cleared.status_code, 200, cleared.content)
        tx = RealEstateTransaction.objects.get(pk=self.a['id'])
        self.assertEqual((tx.responsible_name, tx.transaction_date), ('', None))

    def test_invalid_requests_change_nothing(self):
        ids = [self.a['id'], self.b['id']]
        archived = self.api(self.li, 'post', f"{LIST_URL}{self.c['id']}/archive/", {'reason': '確認済み'})
        self.assertEqual(archived.status_code, 200, archived.content)
        cases = [
            ('空の変更', self.bulk(self.li, ids), 400),
            ('未知の項目', self.bulk(self.li, ids, {'stage': 'settled', 'note': 'x'}), 400),
            ('対象外の項目', self.bulk(self.li, ids, {'is_archived': True}), 400),
            ('不正な段階', self.bulk(self.li, ids, {'stage': 'unknown'}), 400),
            ('不正な日付', self.bulk(self.li, ids, {'stage': 'settled', 'transaction_date': '2026-02-30'}), 400),
            ('重複 ID', self.bulk(self.li, ids + [self.a['id']], {'stage': 'settled'}), 400),
            ('空の選択', self.bulk(self.li, [], {'stage': 'settled'}, expected_count=1), 400),
            ('件数なし', self.api(self.li, 'post', BULK_URL, {'selection_token': self.select(self.li, ids).json()['selection_token'],
                                                           'changes': {'stage': 'settled'}}), 400),
            ('ID の直接指定（トークンなし）', self.api(self.li, 'post', BULK_URL, {
                'selection': {'mode': 'ids', 'ids': ids}, 'changes': {'stage': 'settled'}, 'expected_count': 2}), 400),
            ('ID と古い版の直接指定', self.api(self.li, 'post', BULK_URL, {
                'selection': {'mode': 'ids', 'items': self.items(ids)}, 'changes': {'stage': 'settled'},
                'expected_count': 2}), 400),
            ('更新日時なしの選択', self.api(self.li, 'post', PREVIEW_URL, {
                'selection': {'mode': 'ids', 'items': [{'id': self.a['id']}]}}), 400),
            ('件数不一致', self.bulk(self.li, ids, {'stage': 'settled'}, expected_count=3), 409),
            ('存在しない ID', self.bulk(self.li, ids + [999999], {'stage': 'settled'}), 409),
            ('アーカイブ済み', self.bulk(self.li, ids + [self.c['id']], {'stage': 'settled'}), 409),
            ('選択方法なし', self.api(self.li, 'post', BULK_URL, {'changes': {'stage': 'settled'}, 'expected_count': 2}), 400),
        ]
        for label, response, expected in cases:
            self.assertEqual(response.status_code, expected, f'{label}: {response.content}')
        self.assertEqual({self.stage_of(self.a), self.stage_of(self.b)}, {'contract'})
        self.assertFalse(AuditLog.objects.filter(action='transaction_bulk_updated').exists())
        self.assertFalse(AuditLog.objects.filter(action='transaction_updated', extra__bulk=True).exists())

    def test_failure_in_the_middle_rolls_back_every_record(self):
        original = RealEstateTransaction.save
        calls = {'n': 0}

        def failing_save(instance, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 2:
                raise bulk_service.BulkConflict('途中で失敗')
            return original(instance, *args, **kwargs)

        with mock.patch.object(RealEstateTransaction, 'save', failing_save):
            response = self.bulk(self.li, [self.a['id'], self.b['id']], {'stage': 'settled'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual({self.stage_of(self.a), self.stage_of(self.b)}, {'contract'})
        self.assertFalse(AuditLog.objects.filter(action='transaction_updated', extra__bulk=True).exists())

    def test_locked_ledger_is_not_overwritten(self):
        ledger = self.api(self.li, 'post', f"{LIST_URL}{self.a['id']}/ensure-ledger/").json()
        self.assertEqual(self.api(self.li, 'post', f"/api/real-estate/ledgers/{ledger['id']}/lock/").status_code, 200)
        response = self.bulk(self.li, [self.a['id']], {'transaction_date': '2026-10-31'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['locked_ledger_count'], 1)
        after = self.api(self.li, 'get', f"/api/real-estate/ledgers/{ledger['id']}/").json()
        self.assertEqual((after['contract_date'], after['version'], after['is_locked']), ('2026-10-05', 1, True))


class FilterSelectionTokenTests(BulkFixture, TestCase):
    FILTERS = {'stage': 'contract', 'transaction_date_from': '2026-10-01', 'transaction_date_to': '2026-10-31'}

    def preview(self, user=None, filters=None):
        response = self.api(user or self.li, 'post', PREVIEW_URL, {'filters': self.FILTERS if filters is None else filters})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def submit(self, token, count, user=None, changes=None):
        return super().submit(user or self.li, token, count, changes or {'stage': 'settled'})

    def test_month_end_settle_for_all_filtered_records(self):
        preview = self.preview()
        self.assertEqual(preview['count'], 2)
        self.assertIn('段階：契約', preview['filter_summary'])
        self.assertIn('取引日：2026-10-01 〜 2026-10-31', preview['filter_summary'])
        response = self.submit(preview['selection_token'], 2)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual({self.stage_of(self.a), self.stage_of(self.b)}, {'settled'})
        self.assertEqual(self.stage_of(self.c), 'inquiry')
        summary = AuditLog.objects.get(action='transaction_bulk_updated')
        self.assertEqual(summary.extra['mode'], 'filter')
        self.assertIn('段階：契約', summary.extra['filter_summary'])

    def test_preview_never_includes_archived_records(self):
        self.api(self.li, 'post', f"{LIST_URL}{self.b['id']}/archive/", {'reason': '確認済み'})
        self.assertEqual(self.preview(filters={'archive_status': 'all'})['count'], 2)
        self.assertEqual(self.preview()['count'], 1)

    def test_record_archived_after_preview_aborts_whole_batch(self):
        preview = self.preview()
        self.api(self.li, 'post', f"{LIST_URL}{self.b['id']}/archive/", {'reason': '確認済み'})
        self.assertEqual(self.submit(preview['selection_token'], 2).status_code, 409)
        self.assertEqual(self.stage_of(self.a), 'contract')

    def test_token_is_bound_to_count_user_signature_and_time(self):
        preview = self.preview()
        token = preview['selection_token']
        self.assertEqual(self.submit(token, 5).status_code, 409)  # ブラウザが名乗る件数は通らない
        self.assertEqual(self.submit(token + 'x', 2).status_code, 400)  # 改ざん
        self.assertEqual(self.submit('', 2).status_code, 400)
        self.grant_bulk(self.staff_a)
        self.assertEqual(self.submit(token, 2, user=self.staff_a).status_code, 400)  # 他人のトークン
        with mock.patch.object(bulk_service, 'TOKEN_MAX_AGE_SECONDS', -1):
            self.assertEqual(self.submit(token, 2).status_code, 400)  # 期限切れ
        self.assertEqual({self.stage_of(self.a), self.stage_of(self.b)}, {'contract'})
        # 対象はトークンに固定された記録だけ（余分な ID を送っても対象は増えない）
        response = self.api(self.li, 'post', BULK_URL, {
            'selection_token': token, 'ids': [self.c['id']], 'changes': {'stage': 'settled'}, 'expected_count': 2,
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.stage_of(self.c), 'inquiry')


class ConcurrencyTests(BulkFixture, TestCase):
    """プレビュー（選択の固定）後に対象が変わったら、絞り込み全選択でも手動選択でも 409 で全体を中止する。"""

    FILTERS = {'stage': 'contract'}

    def tokens(self):
        by_filter = self.api(self.li, 'post', PREVIEW_URL, {'filters': self.FILTERS}).json()
        by_ids = self.select(self.li, [self.a['id'], self.b['id']]).json()
        self.assertEqual((by_filter['count'], by_filter['mode'], by_ids['count'], by_ids['mode']), (2, 'filter', 2, 'ids'))
        return [by_filter['selection_token'], by_ids['selection_token']]

    def assert_all_rejected(self, tokens, untouched):
        for token in tokens:
            response = self.submit(self.li, token, 2, {'responsible_name': '一括後'})
            self.assertEqual(response.status_code, 409, response.content)
        for tx in untouched:
            self.assertNotEqual(RealEstateTransaction.objects.get(pk=tx['id']).responsible_name, '一括後')
        self.assertFalse(AuditLog.objects.filter(action='transaction_bulk_updated').exists())
        self.assertFalse(AuditLog.objects.filter(action='transaction_updated', extra__bulk=True).exists())

    def test_record_edited_after_preview_aborts_whole_batch(self):
        tokens = self.tokens()
        # 別の利用者が、一括変更の対象項目ではない備考を単票編集する（絞り込み条件には引き続き一致する）
        edited = self.api(self.staff_b, 'patch', f"{LIST_URL}{self.b['id']}/", {'note': '確認中'})
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assert_all_rejected(tokens, [self.a, self.b])

    def test_record_archived_or_restored_after_preview_aborts_whole_batch(self):
        tokens = self.tokens()
        self.api(self.li, 'post', f"{LIST_URL}{self.b['id']}/archive/", {'reason': '確認済み'})
        self.assert_all_rejected(tokens, [self.a])
        # 復元して利用中に戻っても、プレビュー時の版とは違うので古いトークンは通らない
        self.api(self.li, 'post', f"{LIST_URL}{self.b['id']}/restore/")
        self.assert_all_rejected(tokens, [self.a, self.b])

    def test_record_deleted_after_preview_aborts_whole_batch(self):
        tokens = self.tokens()
        RealEstateTransaction.objects.filter(pk=self.b['id']).delete()
        self.assert_all_rejected(tokens, [self.a])

    def test_other_bulk_change_after_preview_makes_old_token_stale(self):
        tokens = self.tokens()
        first = self.submit(self.li, tokens[0], 2, {'stage': 'settled'})
        self.assertEqual(first.status_code, 200, first.content)
        second = self.submit(self.li, tokens[1], 2, {'responsible_name': '一括後'})
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(AuditLog.objects.filter(action='transaction_bulk_updated').count(), 1)

    def test_manual_selection_with_version_seen_before_another_edit_is_rejected_at_preview(self):
        seen = self.items([self.a['id'], self.b['id']])  # 一覧を表示した時点
        self.api(self.staff_b, 'patch', f"{LIST_URL}{self.b['id']}/", {'note': '確認中'})
        response = self.api(self.li, 'post', PREVIEW_URL, {'selection': {'mode': 'ids', 'items': seen}})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertNotIn('selection_token', response.json())

    def test_unchanged_records_pass_and_token_cannot_be_replayed_after_success(self):
        token = self.tokens()[1]
        self.assertEqual(self.submit(self.li, token, 2, {'stage': 'settled'}).status_code, 200)
        self.assertEqual(self.submit(self.li, token, 2, {'stage': 'contract'}).status_code, 409)  # 版が進んだ
        self.assertEqual({self.stage_of(self.a), self.stage_of(self.b)}, {'settled'})
