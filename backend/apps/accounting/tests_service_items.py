"""P4：サービス価格マスタ・委託底価の権限・帳票明細のスナップショット・発行版の底価・新規受付の参考項目。

すべて合成データ。底価は「33333」など他の金額と重ならない値にして、応答・スナップショット・履歴・
PDF・監査に漏れていないかを文字列で確認する。
"""
import json
from datetime import date

import fitz
from django.test import TestCase

from apps.accounting.models import AccountingVoucher, Estimate, IssuedLineCostSnapshot, ServiceItem
from apps.accounting.tests_vouchers import VoucherFixture, grant
from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case

ITEMS = '/api/accounting/service-items/'
ESTIMATES = '/api/accounting/estimates/'
VOUCHERS = '/api/accounting/vouchers/'
FLOOR = 33333
FLOOR_2 = 27777
NOTE = '社内メモ：外部委託先の条件'


def line(item_id=None, **extra):
    base = {'item_name': '手入力の項目', 'quantity': 1, 'unit_price': 1000, 'tax_category': 'tax_10',
            'price_type': 'tax_included'}
    if item_id is not None:
        base['service_item_id'] = item_id
    base.update(extra)
    return base


class ServiceItemFixture(VoucherFixture):
    def setUp(self):
        super().setUp()
        self.accountant = make_user('accountant', roles=[ACCOUNTING_ADMIN], employee_name='会計')
        # 帳票は使えるが底価権限の無い人（実運用には無い組み合わせ。serializer の出し分けを確認する）
        self.clerk = grant(make_user('clerk', employee_name='事務'), 'use_estimate', 'use_voucher', 'use_service_item')
        self.su_only = make_user('su_only_sv', superuser=True)
        self.item = ServiceItem.objects.create(
            category='入管', name='試験用サービスA', default_price=55000, floor_price=FLOOR, professional_type='gyousei',
            tax_category='tax_10', unit='件', note=NOTE,
        )
        self.item_b = ServiceItem.objects.create(
            category='翻訳', name='試験用サービスB', default_price=8000, floor_price=FLOOR_2, professional_type='',
            tax_category='tax_10', unit='頁',
        )

    def get(self, user, url, params=None):
        self.client.force_login(user)
        return self.client.get(url, params or {})

    def delete(self, user, url):
        self.client.force_login(user)
        return self.client.delete(url)

    def estimate_with(self, user, lines, **extra):
        response = self.post(user, ESTIMATES, {'issue_date': '2026-10-06', 'recipient_name': '合成株式会社',
                                               'line_items': lines, **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def invoice_with(self, user, lines):
        response = self.post(user, VOUCHERS, {'voucher_type': 'invoice', 'issue_date': '2026-10-06',
                                              'recipient_name': '合成株式会社', 'amount': 0, 'line_items': lines})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def assertNoFloor(self, payload):
        text = json.dumps(payload, ensure_ascii=False, default=str)
        self.assertNotIn('floor', text)
        self.assertNotIn(str(FLOOR), text)
        self.assertNotIn(str(FLOOR_2), text)


class ServiceItemMasterTests(ServiceItemFixture, TestCase):
    def test_staff_can_list_active_items_without_floor_and_cannot_change(self):
        response = self.get(self.staff_a, ITEMS, {'active': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertNoFloor(response.json())
        self.assertEqual(self.get(self.staff_a, f'{ITEMS}{self.item.id}/').json().get('floor_price', 'none'), 'none')
        self.assertEqual(self.post(self.staff_a, ITEMS, {'name': 'x'}).status_code, 403)
        self.assertEqual(self.patch(self.staff_a, f'{ITEMS}{self.item.id}/', {'name': 'x'}).status_code, 403)
        self.assertEqual(self.delete(self.staff_a, f'{ITEMS}{self.item.id}/').status_code, 403)

    def test_superuser_without_business_roles_is_refused(self):
        self.assertEqual(self.get(self.su_only, ITEMS).status_code, 403)
        self.assertEqual(self.post(self.su_only, ITEMS, {'name': 'x'}).status_code, 403)

    def test_accounting_and_system_admin_see_and_manage_floor_price_with_audit(self):
        for user in (self.accountant, self.li):
            self.assertEqual(self.get(user, f'{ITEMS}{self.item.id}/').json()['floor_price'], str(FLOOR))
        response = self.post(self.accountant, ITEMS, {
            'category': '税務', 'name': '試験用サービスC', 'default_price': 30000, 'price_type': 'tax_excluded',
            'floor_price': 12000, 'professional_type': 'tax_accountant', 'tax_category': 'tax_10', 'unit': '件',
        })
        self.assertEqual(response.status_code, 201, response.content)
        created = response.json()
        self.assertEqual((created['floor_price'], created['professional_type_display']), ('12000', '税理士'))
        log = AuditLog.objects.get(action='service_item_created', object_id=str(created['id']))
        self.assertEqual(log.changes['floor_price'], {'from': None, 'to': 12000})
        self.assertEqual(log.user, self.accountant)

    def test_floor_price_cannot_be_written_without_floor_permission(self):
        manager = grant(make_user('manager_only'), 'use_service_item', 'manage_service_item')
        response = self.post(manager, ITEMS, {'name': '試験用サービスD', 'floor_price': 1})
        self.assertEqual(response.status_code, 400)
        self.assertIn('floor_price', response.json())
        item = self.get(manager, f'{ITEMS}{self.item.id}/').json()
        response = self.patch(manager, f'{ITEMS}{self.item.id}/', {'floor_price': 1, 'version': item['updated_at']})
        self.assertEqual(response.status_code, 400)
        ok = self.patch(manager, f'{ITEMS}{self.item.id}/', {'name': '試験用サービスA2', 'version': item['updated_at']})
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertNoFloor(ok.json())
        self.item.refresh_from_db()
        self.assertEqual(self.item.floor_price, FLOOR)

    def test_update_requires_version_and_rejects_stale_version_with_409(self):
        url = f'{ITEMS}{self.item.id}/'
        self.assertEqual(self.patch(self.accountant, url, {'default_price': 60000}).status_code, 400)
        version = self.get(self.accountant, url).json()['updated_at']
        first = self.patch(self.accountant, url, {'default_price': 60000, 'floor_price': 40000, 'version': version})
        self.assertEqual(first.status_code, 200, first.content)
        stale = self.patch(self.li, url, {'default_price': 70000, 'version': version})
        self.assertEqual(stale.status_code, 409)
        self.item.refresh_from_db()
        self.assertEqual((self.item.default_price, self.item.floor_price), (60000, 40000))
        log = AuditLog.objects.get(action='service_item_updated')
        self.assertEqual(log.changes['floor_price'], {'from': FLOOR, 'to': 40000})
        self.assertEqual(log.changes['default_price'], {'from': 55000, 'to': 60000})
        version = first.json()['updated_at']
        off = self.patch(self.accountant, url, {'is_active': False, 'version': version})
        self.assertEqual(off.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='service_item_deactivated').exists())
        self.assertNotIn(self.item.id, [r['id'] for r in self.rows(self.get(self.staff_a, ITEMS, {'active': '1'}))])

    def test_search_matches_name_and_category_but_not_floor_or_note(self):
        rows = lambda q: [r['id'] for r in self.rows(self.get(self.staff_a, ITEMS, {'search': q}))]  # noqa: E731
        self.assertIn(self.item.id, rows('サービスA'))
        self.assertIn(self.item_b.id, rows('翻訳'))
        self.assertEqual(rows(str(FLOOR)), [])
        self.assertEqual(rows('外部委託先'), [])

    def test_unused_item_can_be_deleted_used_item_cannot(self):
        response = self.delete(self.accountant, f'{ITEMS}{self.item_b.id}/')
        self.assertEqual(response.status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action='service_item_deleted').exists())
        self.estimate_with(self.accountant, [line(self.item.id)])
        response = self.delete(self.accountant, f'{ITEMS}{self.item.id}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(ServiceItem.objects.filter(pk=self.item.id).exists())

    def rows(self, response):
        data = response.json()
        return data['results'] if isinstance(data, dict) and 'results' in data else data


class DocumentServiceLineTests(ServiceItemFixture, TestCase):
    def test_selected_item_snapshot_and_floor_are_generated_by_backend(self):
        forged = line(self.item.id, item_name='名前を変更', unit_price=50000, line_key='forged',
                      service={'id': self.item.id, 'name': '偽', 'default_price': 1}, floor_price=1, internal_cost=1)
        doc = self.estimate_with(self.accountant, [forged, line()])
        first, manual = doc['line_items']
        self.assertEqual(first['service']['name'], '試験用サービスA')
        self.assertEqual(first['service']['default_price'], 55000)
        self.assertEqual((first['item_name'], first['unit_price']), ('名前を変更', 50000))  # 実際の値は編集可
        self.assertNotEqual(first['line_key'], 'forged')
        self.assertNotIn('floor_price', first)
        self.assertNotIn('internal_cost', first)
        self.assertNotIn('service', manual)
        self.assertNotEqual(manual['line_key'], first['line_key'])
        self.assertEqual(doc['internal_line_costs'], [
            {**doc['internal_line_costs'][0], 'line_key': first['line_key'], 'service_item_id': self.item.id,
             'floor_price': FLOOR, 'professional_type': 'gyousei'},
        ])
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.first_used_at)

    def test_users_without_floor_permission_never_receive_floor(self):
        doc = self.estimate_with(self.clerk, [line(self.item.id)])
        self.assertNoFloor(doc)
        self.assertNoFloor(self.get(self.clerk, f'{ESTIMATES}{doc["id"]}/').json())
        self.assertNoFloor(self.get(self.clerk, ESTIMATES).json())
        self.assertEqual(self.get(self.clerk, f'{ESTIMATES}{doc["id"]}/internal-costs/').status_code, 403)
        # 保存はされている（底価権限者からは見える）
        self.assertEqual(self.get(self.accountant, f'{ESTIMATES}{doc["id"]}/').json()['internal_line_costs'][0]['floor_price'], FLOOR)

    def test_master_changes_do_not_rewrite_saved_lines_or_floor(self):
        doc = self.estimate_with(self.accountant, [line(self.item.id)])
        ServiceItem.objects.filter(pk=self.item.id).update(name='改名後', default_price=99000, floor_price=11111, is_active=False)
        url = f'{ESTIMATES}{doc["id"]}/'
        resend = self.patch(self.accountant, url, {'line_items': doc['line_items'], 'version': doc['updated_at']})
        self.assertEqual(resend.status_code, 200, resend.content)
        saved = resend.json()
        self.assertEqual(saved['line_items'][0]['service']['name'], '試験用サービスA')
        self.assertEqual(saved['line_items'][0]['service']['default_price'], 55000)
        self.assertEqual(saved['internal_line_costs'][0]['floor_price'], FLOOR)
        # 無効になった項目は新しい行としては選べない（行番号つきで返す）
        again = self.patch(self.accountant, url, {'line_items': saved['line_items'] + [line(self.item.id)],
                                                  'version': saved['updated_at']})
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.json()['line_item_row'], ['2'])  # 既存の行エラーと同じ形

    def test_swapping_line_keys_does_not_move_floor_records(self):
        doc = self.estimate_with(self.accountant, [line(self.item.id), line(self.item_b.id)])
        a, b = doc['line_items']
        ServiceItem.objects.filter(pk=self.item.id).update(floor_price=44444)
        swapped = [dict(a, line_key=b['line_key']), dict(b, line_key=a['line_key'])]
        response = self.patch(self.accountant, f'{ESTIMATES}{doc["id"]}/', {'line_items': swapped, 'version': doc['updated_at']})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        costs = {c['line_key']: c for c in data['internal_line_costs']}
        for row in data['line_items']:
            self.assertEqual(costs[row['line_key']]['service_item_id'], row['service_item_id'])
        floors = {row['service_item_id']: costs[row['line_key']]['floor_price'] for row in data['line_items']}
        # 項目が一致しない行は新しい選択として扱い、別の行の底価を引き継がない
        self.assertEqual(floors, {self.item.id: 44444, self.item_b.id: FLOOR_2})
        # 同じ line_key を 2 行に送っても一意になる
        dup = self.patch(self.accountant, f'{ESTIMATES}{doc["id"]}/', {
            'line_items': [data['line_items'][0], dict(data['line_items'][0])], 'version': data['updated_at']})
        keys = [row['line_key'] for row in dup.json()['line_items']]
        self.assertEqual(len(set(keys)), 2)

    def test_old_documents_without_keys_keep_working(self):
        legacy = Estimate.objects.create(issue_date=date(2026, 9, 1), recipient_name='旧データ',
                                         line_items=[{'item_name': '旧明細', 'quantity': 1, 'unit_price': 2000}])
        url = f'{ESTIMATES}{legacy.pk}/'
        detail = self.get(self.accountant, url).json()
        self.assertEqual(detail['internal_line_costs'], [])
        response = self.patch(self.accountant, url, {'note': '備考だけ変更'})
        self.assertEqual(response.status_code, 200, response.content)
        response = self.patch(self.accountant, url, {'line_items': detail['line_items'], 'version': response.json()['updated_at']})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['line_items'][0]['line_key'])

    def test_concurrent_draft_edit_returns_409(self):
        doc = self.estimate_with(self.accountant, [line()])
        url = f'{ESTIMATES}{doc["id"]}/'
        self.assertEqual(self.patch(self.accountant, url, {'title': 'A', 'version': doc['updated_at']}).status_code, 200)
        stale = self.patch(self.li, url, {'title': 'B', 'version': doc['updated_at']})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(Estimate.objects.get(pk=doc['id']).title, 'A')

    def test_estimate_issue_keeps_floor_out_of_issued_snapshot_and_records_version(self):
        doc = self.estimate_with(self.accountant, [line(self.item.id)])
        response = self.move(self.accountant, 'estimates', doc['id'], 'submitted', confirm_provisional=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNoFloor(response.json()['issued_snapshot'])
        snapshot = IssuedLineCostSnapshot.objects.get(document_kind='estimate', document_id=doc['id'])
        self.assertEqual((snapshot.version, snapshot.line_costs[0]['floor_price']), (1, FLOOR))
        self.assertNoFloor(self.get(self.clerk, f'{ESTIMATES}{doc["id"]}/').json())
        update_logs = AuditLog.objects.filter(module='voucher', object_id=str(doc['id']))
        self.assertNoFloor([log.changes for log in update_logs] + [log.extra for log in update_logs])

    def test_invoice_reissue_keeps_each_issued_version_of_floor(self):
        doc = self.invoice_with(self.accountant, [line(self.item.id, unit_price=55000)])
        url = f'{VOUCHERS}{doc["id"]}/'
        self.assertEqual(self.move(self.accountant, 'vouchers', doc['id'], 'issued', confirm_provisional=True).status_code, 200)
        self.assertEqual(self.move(self.accountant, 'vouchers', doc['id'], 'draft').status_code, 200)
        current = self.get(self.accountant, url).json()
        changed = self.patch(self.accountant, url, {
            'line_items': [dict(current['line_items'][0], unit_price=60000), line(self.item_b.id)],
            'version': current['updated_at'],
        })
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(self.move(self.accountant, 'vouchers', doc['id'], 'issued', confirm_provisional=True).status_code, 200)
        costs = self.get(self.accountant, f'{url}internal-costs/').json()
        self.assertEqual([v['version'] for v in costs['issued_versions']], [1, 2])
        self.assertEqual([c['floor_price'] for c in costs['issued_versions'][0]['line_costs']], [FLOOR])
        self.assertEqual([c['floor_price'] for c in costs['issued_versions'][1]['line_costs']], [FLOOR, FLOOR_2])
        # 状態履歴・発行スナップショットには底価が無い（底価権限者が読んでも）
        history = self.get(self.accountant, f'{url}status-history/')
        self.assertEqual(history.status_code, 200)
        self.assertNoFloor(history.json())
        self.assertNoFloor(self.get(self.accountant, url).json()['issued_snapshot'])
        self.assertEqual(self.get(self.clerk, f'{url}internal-costs/').status_code, 403)

    def test_copy_rules_estimate_to_invoice_keeps_costs_contract_and_receipt_drop_service_keys(self):
        doc = self.estimate_with(self.li, [line(self.item.id)])
        invoice = self.post(self.li, f'{ESTIMATES}{doc["id"]}/create-invoice/').json()
        self.assertEqual(invoice['line_items'][0]['service']['name'], '試験用サービスA')
        self.assertEqual(invoice['internal_line_costs'], doc['internal_line_costs'])
        contract = self.post(self.li, f'{ESTIMATES}{doc["id"]}/create-contract/').json()
        self.assertNotIn('service', contract['line_items'][0])
        self.assertNotIn('internal_line_costs', contract)
        receipt = self.post(self.li, f'{VOUCHERS}{invoice["id"]}/create-receipt/').json()
        self.assertNotIn('service', receipt['line_items'][0])
        self.assertEqual(AccountingVoucher.objects.get(pk=receipt['id']).internal_line_costs, [])
        # 契約書・領収書に客户端からサービス項目を送っても使われない
        response = self.patch(self.li, f'/api/accounting/contracts/{contract["id"]}/',
                              {'line_items': [line(self.item.id)], 'version': contract['updated_at']})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn('service_item_id', response.json()['line_items'][0])

    def test_pdf_prints_neither_floor_nor_internal_note(self):
        doc = self.estimate_with(self.accountant, [line(self.item.id, unit_price=55000, note='PDF に出す備考')])
        response = self.get(self.accountant, f'{ESTIMATES}{doc["id"]}/pdf/')
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content) if response.streaming else response.content
        with fitz.open(stream=content, filetype='pdf') as pdf:
            text = ''.join(page.get_text() for page in pdf)
        self.assertIn('PDF に出す備考', text)
        self.assertNotIn('33,333', text)
        self.assertNotIn(str(FLOOR), text)
        self.assertNotIn('外部委託先', text)


class ReceptionServiceItemTests(ServiceItemFixture, TestCase):
    def reception(self, user, case_extra):
        from apps.cases.models import CaseApplicationCategory, CaseTypeMaster

        case_type = CaseTypeMaster.objects.get(code='ac')
        category = CaseApplicationCategory.objects.get(code='ac')
        self.client.force_login(user)
        return self.client.post('/api/receptions/', {
            'existing_customer_id': self.customer.id,
            'case': {'case_type_master': case_type.id, 'application_category': category.id, **case_extra},
        }, content_type='application/json')

    def test_optional_multiple_items_are_snapshotted_without_floor(self):
        response = self.reception(self.staff_a, {'service_items': [
            {'service_item': self.item.id, 'quantity': 1}, {'service_item': self.item_b.id, 'quantity': 3},
        ]})
        self.assertEqual(response.status_code, 201, response.content)
        case = Case.objects.get(pk=response.json()['case'])
        self.assertEqual([i['name'] for i in case.service_items], ['試験用サービスA', '試験用サービスB'])
        self.assertEqual(case.service_items[1]['quantity'], 3)
        self.assertNoFloor(case.service_items)
        ServiceItem.objects.filter(pk=self.item.id).update(name='改名後', default_price=1)
        detail = self.get(self.staff_a, f'/api/cases/{case.id}/').json()
        self.assertEqual(detail['service_items'][0]['name'], '試験用サービスA')
        self.assertNoFloor(detail)
        # 選ばなくても作成できる
        none = self.reception(self.staff_a, {})
        self.assertEqual(none.status_code, 201, none.content)
        self.assertEqual(Case.objects.get(pk=none.json()['case']).service_items, [])

    def test_inactive_item_and_missing_permission_are_refused(self):
        before = Case.objects.count()
        ServiceItem.objects.filter(pk=self.item_b.id).update(is_active=False)
        response = self.reception(self.staff_a, {'service_items': [{'service_item': self.item_b.id}]})
        self.assertEqual(response.status_code, 400)
        no_perm = make_user('case_only', employee_name='案件のみ')
        from django.contrib.auth.models import Permission

        no_perm.user_permissions.add(Permission.objects.get(content_type__app_label='cases', codename='use_cases'))
        response = self.reception(no_perm, {'service_items': [{'service_item': self.item.id}]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Case.objects.count(), before)
