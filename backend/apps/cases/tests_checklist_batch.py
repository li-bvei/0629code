"""P2：案件内の必要資料の一括更新（同じ案件の中だけ・項目ごとの結果・部分成功・監査）。"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase

from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseChecklistItem, CaseTypeMaster
from apps.customers.models import Customer
from apps.employees.models import Employee
from apps.timelines.models import Timeline


class ChecklistBatchTests(TestCase):
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], superuser=True, employee_name='李')
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], superuser=True, employee_name='焦')
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        ct, _ = CaseTypeMaster.objects.update_or_create(code='cb', defaults={'name': '一括資料種別', 'number_abbreviation': '一資'})
        cat, _ = CaseApplicationCategory.objects.update_or_create(code='cb', defaults={'name': '一括資料区分', 'number_abbreviation': '資区'})
        customer = Customer.objects.create(name='資料顧客', birth_date='1990-01-01')

        def make_case(user):
            return Case.objects.create(case_type='x', case_type_master=ct, application_category=cat, status=Case.STATUS_OPEN,
                                       customer=customer, responsible_employee=Employee.objects.get(user=user))

        self.case = make_case(self.staff_a)
        self.other = make_case(self.staff_a)
        self.items = [CaseChecklistItem.objects.create(case=self.case, name=f'資料{i}', category='本人') for i in range(3)]
        self.task = CaseChecklistItem.objects.create(case=self.case, name='申請書作成', item_type='task', category='作業')
        self.foreign = CaseChecklistItem.objects.create(case=self.other, name='他案件の資料')

    def batch(self, user, ids, changes, case=None, **extra):
        self.client.force_login(user)
        return self.client.post(f'/api/cases/{(case or self.case).id}/checklist-batch/',
                                {'item_ids': ids, 'changes': changes, **extra}, content_type='application/json')

    def test_batch_complete_and_set_fields_success_with_item_and_batch_audit(self):
        ids = [item.id for item in self.items]
        response = self.batch(self.staff_a, ids, {
            'is_completed': True, 'received_at': '2026-10-01', 'responsible_party': 'customer',
            'acquisition_place': '区役所', 'note': '原本確認済み',
        })
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['requested'], body['succeeded'], body['failed']), (3, 3, 0))
        self.assertEqual(body['progress_summary']['required_items_completed'], 3)
        for item in CaseChecklistItem.objects.filter(pk__in=ids):
            self.assertTrue(item.is_completed)
            self.assertIsNotNone(item.completed_at)
            self.assertEqual(item.completed_by.user, self.staff_a)
            self.assertEqual((str(item.received_at), item.responsible_party, item.acquisition_place, item.note),
                             ('2026-10-01', 'customer', '区役所', '原本確認済み'))
        item_logs = AuditLog.objects.filter(action='checklist_item_batch_updated')
        self.assertEqual(item_logs.count(), 3)
        self.assertEqual(item_logs.first().changes['is_completed'], {'from': False, 'to': True})
        batch_log = AuditLog.objects.get(action='checklist_batch_update')
        self.assertEqual((batch_log.extra['requested'], batch_log.extra['succeeded'], batch_log.extra['failed']), (3, 3, 0))
        self.assertEqual({log.extra['batch_id'] for log in item_logs}, {batch_log.extra['batch_id']})
        self.assertEqual(Timeline.objects.filter(case=self.case, event_type=Timeline.EVENT_CHECKLIST_COMPLETED).count(), 3)

    def test_partial_success_does_not_roll_back_successful_items(self):
        stale = self.items[1]
        CaseChecklistItem.objects.filter(pk=stale.pk).update(note='他の人が先に変更',
                                                             updated_at=stale.updated_at + timedelta(seconds=5))
        versions = {str(item.id): item.updated_at.isoformat() for item in self.items + [self.task]}
        response = self.batch(self.staff_a, [self.items[0].id, stale.id, self.task.id, self.items[2].id],
                              {'received_at': '2026-10-02'}, versions=versions)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body['succeeded'], body['failed']), (2, 2))
        failures = {row['id']: row['code'] for row in body['results'] if row['status'] == 'failed'}
        self.assertEqual(failures, {stale.id: 'conflict', self.task.id: 'not_applicable'})
        self.assertTrue(all(row.get('detail') for row in body['results'] if row['status'] == 'failed'))
        refreshed = {item.id: item for item in CaseChecklistItem.objects.filter(case=self.case)}
        self.assertEqual(str(refreshed[self.items[0].id].received_at), '2026-10-02')
        self.assertEqual(str(refreshed[self.items[2].id].received_at), '2026-10-02')
        self.assertIsNone(refreshed[stale.id].received_at)
        self.assertEqual(AuditLog.objects.get(action='checklist_batch_update').result, 'error')

    def test_unexpected_error_on_one_item_keeps_others(self):
        from apps.cases import checklist_batch

        original = checklist_batch._apply
        target = self.items[1].id

        def flaky(item, changes, employee):
            if item.id == target:
                raise RuntimeError('boom')
            return original(item, changes, employee)

        with mock.patch.object(checklist_batch, '_apply', side_effect=flaky), \
                self.assertLogs('apps.cases.checklist_batch', 'ERROR'):
            body = self.batch(self.staff_a, [i.id for i in self.items], {'is_completed': True}).json()
        self.assertEqual((body['succeeded'], body['failed']), (2, 1))
        self.assertFalse(CaseChecklistItem.objects.get(pk=target).is_completed)

    def test_items_of_other_case_reject_the_whole_request(self):
        response = self.batch(self.staff_a, [self.items[0].id, self.foreign.id], {'is_completed': True})
        self.assertEqual(response.status_code, 400)
        self.assertIn('item_ids', response.json())
        self.assertFalse(CaseChecklistItem.objects.filter(is_completed=True).exists())  # 一部だけ実行しない
        self.assertTrue(AuditLog.objects.filter(action='checklist_batch_rejected', result='denied').exists())
        # 存在しない ID も同じ扱い
        self.assertEqual(self.batch(self.staff_a, [self.items[0].id, 999999], {'is_completed': True}).status_code, 400)

    def test_permissions_and_archived_case(self):
        ids = [self.items[0].id]
        self.assertEqual(self.batch(self.staff_b, ids, {'is_completed': True}).status_code, 404)  # 見えない
        self.assertEqual(self.batch(self.jiao, ids, {'is_completed': True}).status_code, 403)     # 見えるが変更不可
        self.assertEqual(self.batch(self.li, ids, {'is_completed': True}).status_code, 200)       # 全件変更権限
        Case.objects.filter(pk=self.case.pk).update(registration_status=Case.REGISTRATION_STATUS_ARCHIVED)
        self.assertEqual(self.batch(self.staff_a, ids, {'is_completed': False}).status_code, 400)
        self.assertTrue(CaseChecklistItem.objects.get(pk=ids[0]).is_completed)

    def test_validation_of_changes_and_ids(self):
        ids = [self.items[0].id]
        for changes in ({}, {'is_completed': 'yes'}, {'responsible_party': 'nobody'}, {'received_at': '2026/13/40'},
                        {'note': 'x', 'note_mode': 'merge'}):
            self.assertEqual(self.batch(self.staff_a, ids, changes).status_code, 400, changes)
        self.assertEqual(self.batch(self.staff_a, [], {'is_completed': True}).status_code, 400)
        self.assertEqual(self.batch(self.staff_a, ['a'], {'is_completed': True}).status_code, 400)
        self.assertFalse(AuditLog.objects.filter(action='checklist_batch_update').exists())

    def test_uncomplete_clears_completion_and_note_append(self):
        item = self.items[0]
        CaseChecklistItem.objects.filter(pk=item.pk).update(note='既存')
        self.batch(self.staff_a, [item.id], {'is_completed': True, 'note': '追記', 'note_mode': 'append'})
        item.refresh_from_db()
        self.assertEqual(item.note, '既存\n追記')
        self.batch(self.staff_a, [item.id], {'is_completed': False, 'received_at': None})
        item.refresh_from_db()
        self.assertEqual((item.is_completed, item.completed_at, item.completed_by, item.received_at), (False, None, None, None))
