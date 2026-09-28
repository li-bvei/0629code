"""P1：Next Action・待機・入金記録・完了/再開の Timeline/AuditLog と権限。"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster
from apps.customers.models import Customer
from apps.employees.models import Employee
from apps.timelines.models import Timeline


class WorkFixture:
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=True)
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦', superuser=True)
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        self.emp_a = Employee.objects.get(user=self.staff_a)
        self.emp_b = Employee.objects.get(user=self.staff_b)
        self.case_type, _ = CaseTypeMaster.objects.update_or_create(code='wk', defaults={'name': '作業試験種別', 'number_abbreviation': '作試'})
        self.category, _ = CaseApplicationCategory.objects.update_or_create(code='wk', defaults={'name': '作業試験区分', 'number_abbreviation': '作区'})
        self.customer = Customer.objects.create(name='作業顧客', birth_date='1990-01-01')
        self.case_a = Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                                          status=Case.STATUS_COLLECTING_DOCUMENTS, customer=self.customer,
                                          responsible_employee=self.emp_a)

    def post(self, user, path, body=None):
        self.client.force_login(user)
        return self.client.post(f'/api/cases/{self.case_a.id}/{path}', body or {}, content_type='application/json')


class NextActionTests(WorkFixture, TestCase):
    def test_set_and_complete_next_action_with_timeline_and_audit(self):
        due = (timezone.localdate() + timedelta(days=3)).isoformat()
        response = self.post(self.staff_a, 'next-action/', {'next_action': '在職証明を依頼', 'next_action_due_at': due,
                                                             'assignee': self.emp_a.id, 'blocked_reason': '会社の回答待ち'})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['next_action_state'], 'open')
        self.assertEqual(data['next_action_assignee_name'], 'A')
        self.assertEqual(data['next_action_blocked_reason'], '会社の回答待ち')
        self.assertTrue(Timeline.objects.filter(case=self.case_a, event_type=Timeline.EVENT_ACTION_CREATED).exists())
        self.assertTrue(AuditLog.objects.filter(action='case_next_action_set', user=self.staff_a).exists())
        response = self.post(self.staff_a, 'next-action/complete/', {'note': '受領済み'})
        self.assertEqual(response.json()['next_action_state'], 'done')
        self.assertTrue(Timeline.objects.filter(case=self.case_a, event_type=Timeline.EVENT_ACTION_COMPLETED).exists())
        self.assertTrue(AuditLog.objects.filter(action='case_next_action_completed').exists())
        self.assertEqual(self.post(self.staff_a, 'next-action/complete/').status_code, 400)

    def test_assignee_must_be_able_to_view_case(self):
        response = self.post(self.staff_a, 'next-action/', {'next_action': 'x', 'assignee': self.emp_b.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('assignee', response.json())
        # 焦（全件閲覧可）の担当者は指定できる
        response = self.post(self.staff_a, 'next-action/', {'next_action': 'x', 'assignee': self.jiao.employee.id})
        self.assertEqual(response.status_code, 200)

    def test_generic_patch_cannot_write_work_fields(self):
        self.client.force_login(self.staff_a)
        self.client.patch(f'/api/cases/{self.case_a.id}/', {'next_action': '直接', 'work_status': 'waiting',
                                                              'waiting_reason': 'other'}, content_type='application/json')
        self.case_a.refresh_from_db()
        self.assertEqual(self.case_a.next_action, '')
        self.assertEqual(self.case_a.work_status, Case.WORK_STATUS_ACTIVE)

    def test_permissions(self):
        self.assertEqual(self.post(self.staff_b, 'next-action/', {'next_action': 'x'}).status_code, 404)
        self.assertEqual(self.post(self.jiao, 'next-action/', {'next_action': 'x'}).status_code, 403)
        self.assertEqual(self.post(self.jiao, 'waiting/start/', {'waiting_reason': 'other'}).status_code, 403)
        self.assertEqual(self.post(self.li, 'next-action/', {'next_action': '李が設定'}).status_code, 200)

    def test_status_change_with_new_next_action_resets_completion(self):
        self.post(self.staff_a, 'next-action/', {'next_action': '一つ目'})
        self.post(self.staff_a, 'next-action/complete/')
        response = self.post(self.staff_a, 'change-status/', {'new_status': Case.STATUS_PREPARING_DOCUMENTS,
                                                               'next_action': '二つ目'})
        self.assertEqual(response.status_code, 200, response.content)
        self.case_a.refresh_from_db()
        self.assertIsNone(self.case_a.next_action_completed_at)


class WaitingTests(WorkFixture, TestCase):
    def test_start_and_end_waiting(self):
        until = (timezone.localdate() + timedelta(days=14)).isoformat()
        response = self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'customer_documents',
                                                               'waiting_note': '課税証明', 'waiting_until': until})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['work_status'], 'waiting')
        self.assertEqual(data['waiting_reason_display'], '顧客資料待ち')
        self.assertEqual(data['waiting_days'], 0)
        self.assertEqual(data['status'], Case.STATUS_COLLECTING_DOCUMENTS)  # 13 の進捗は変わらない
        self.assertEqual(self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'other'}).status_code, 400)
        response = self.post(self.staff_a, 'waiting/end/', {'note': '受領'})
        self.assertEqual(response.json()['work_status'], 'active')
        events = list(Timeline.objects.filter(case=self.case_a).values_list('event_type', flat=True))
        self.assertIn(Timeline.EVENT_WAITING_STARTED, events)
        self.assertIn(Timeline.EVENT_WAITING_ENDED, events)
        self.assertTrue(AuditLog.objects.filter(action='case_waiting_started').exists())
        self.assertTrue(AuditLog.objects.filter(action='case_waiting_ended').exists())

    def test_validation(self):
        self.assertEqual(self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'nope'}).status_code, 400)
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'other', 'waiting_until': past}).status_code, 400)
        self.assertEqual(self.post(self.staff_a, 'waiting/end/').status_code, 400)

    def test_dashboard_waiting_uses_work_status(self):
        self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'immigration_review'})
        data = self.client.get('/api/dashboard/summary/').json()
        self.assertEqual(data['cases']['waiting'], 1)

    def test_completing_case_clears_waiting_and_reopen_is_recorded(self):
        self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'other'})
        response = self.post(self.staff_a, 'change-status/', {'new_status': Case.STATUS_COMPLETED, 'force': True,
                                                               'note': '完了'})
        self.assertEqual(response.status_code, 200, response.content)
        self.case_a.refresh_from_db()
        self.assertEqual(self.case_a.work_status, Case.WORK_STATUS_ACTIVE)
        self.assertTrue(Timeline.objects.filter(case=self.case_a, event_type=Timeline.EVENT_CASE_COMPLETED).exists())
        response = self.post(self.staff_a, 'change-status/', {'new_status': Case.STATUS_COLLECTING_DOCUMENTS,
                                                               'force': True, 'note': '追加依頼'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Timeline.objects.filter(case=self.case_a, event_type=Timeline.EVENT_CASE_REOPENED).exists())
        self.assertEqual(AuditLog.objects.filter(action='case_status_changed', object_id=str(self.case_a.id)).count(), 2)
        self.assertEqual(self.post(self.staff_a, 'waiting/start/', {'waiting_reason': 'other'}).status_code, 200)


class PaymentNoteTests(WorkFixture, TestCase):
    def test_payment_note_records_timeline_only(self):
        from apps.accounting.models import AccountingVoucher, IncomeSource

        response = self.post(self.staff_a, 'payment-note/', {'amount': '55,000', 'received_on': '2026-09-01',
                                                              'reference': '請求書 INV-1'})
        self.assertEqual(response.status_code, 201, response.content)
        event = Timeline.objects.get(case=self.case_a, event_type=Timeline.EVENT_PAYMENT_RECEIVED)
        self.assertIn('55,000円', event.content)
        self.assertFalse(event.metadata['accounting_record_created'])
        self.assertEqual(IncomeSource.objects.count(), 0)
        self.assertEqual(AccountingVoucher.objects.count(), 0)
        self.assertTrue(AuditLog.objects.filter(action='case_payment_noted').exists())
        self.assertEqual(self.post(self.staff_a, 'payment-note/', {'amount': 'abc'}).status_code, 400)
        self.assertEqual(self.post(self.staff_b, 'payment-note/', {}).status_code, 404)


class TodayWorkbenchTests(WorkFixture, TestCase):
    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        self.case_b = Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                                          status=Case.STATUS_COLLECTING_DOCUMENTS, customer=self.customer,
                                          responsible_employee=self.emp_b)
        Case.objects.filter(pk=self.case_a.pk).update(next_action='a の対応', next_action_due_at=today - timedelta(days=1))
        Case.objects.filter(pk=self.case_b.pk).update(next_action='b の対応', next_action_due_at=today,
                                                       work_status=Case.WORK_STATUS_WAITING, waiting_reason='other',
                                                       waiting_since=today - timedelta(days=5))
        self.closed = Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                                          status=Case.STATUS_COMPLETED, customer=self.customer, responsible_employee=self.emp_a,
                                          next_action='終わった')

    def get(self, user, scope='mine'):
        self.client.force_login(user)
        return self.client.get(f'/api/workbench/today/?scope={scope}')

    def test_mine_is_limited_to_own_cases_and_actions(self):
        data = self.get(self.staff_a).json()
        self.assertEqual([c['id'] for c in data['cases']], [self.case_a.id])
        self.assertEqual([c['id'] for c in data['next_actions']], [self.case_a.id])
        self.assertEqual(data['next_actions'][0]['due_status'], 'overdue')
        self.assertEqual(data['summary']['overdue'], 1)
        self.assertEqual(data['waiting'], [])
        data = self.get(self.staff_b).json()
        self.assertEqual([c['id'] for c in data['waiting']], [self.case_b.id])
        self.assertEqual(data['waiting'][0]['waiting_days'], 5)

    def test_next_action_assigned_to_me_on_visible_case(self):
        Case.objects.filter(pk=self.case_b.pk).update(next_action_assignee=self.jiao.employee)
        data = self.get(self.jiao).json()
        self.assertEqual([c['id'] for c in data['next_actions']], [self.case_b.id])
        self.assertEqual(data['cases'], [])

    def test_all_scope_requires_view_all(self):
        self.assertEqual(self.get(self.staff_a, 'all').status_code, 403)
        data = self.get(self.jiao, 'all').json()
        self.assertEqual({c['id'] for c in data['cases']}, {self.case_a.id, self.case_b.id})
        self.assertEqual(data['summary']['waiting'], 1)

    def test_unlinked_user_and_superuser_only(self):
        unlinked = make_user('unlinked_wb', roles=[STAFF])
        data = self.get(unlinked).json()
        self.assertFalse(data['employee_linked'])
        self.assertEqual(data['cases'], [])
        su = make_user('su_wb', superuser=True)
        self.assertEqual(self.get(su).status_code, 403)


class ChecklistReceiveTests(WorkFixture, TestCase):
    def setUp(self):
        super().setUp()
        import shutil
        import tempfile

        from django.core.files.base import ContentFile
        from django.test import override_settings

        from apps.cases.models import CaseChecklistItem
        from apps.documents.models import Document

        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.item = CaseChecklistItem.objects.create(case=self.case_a, name='課税証明書')
        self.doc = Document(case=self.case_a, title='課税証明', file_name='kazei.pdf', file_path='')
        self.doc.file.save('kazei.pdf', ContentFile(b'%PDF'), save=True)
        other_case = Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                                         status=Case.STATUS_COLLECTING_DOCUMENTS, customer=self.customer,
                                         responsible_employee=self.emp_a)
        self.other_doc = Document.objects.create(case=other_case, title='別案件', file_name='x.pdf', file_path='')

    def receive(self, user, body):
        self.client.force_login(user)
        return self.client.post(f'/api/case-checklist-items/{self.item.id}/receive/', body, content_type='application/json')

    def test_receive_links_document_and_records_timeline(self):
        response = self.receive(self.staff_a, {'document': self.doc.id, 'received_on': '2026-09-20', 'complete': True})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['document'], self.doc.id)
        self.assertEqual(data['document_title'], '課税証明')
        self.assertEqual(data['received_at'], '2026-09-20')
        self.assertTrue(data['is_completed'])
        events = set(Timeline.objects.filter(case=self.case_a).values_list('event_type', flat=True))
        self.assertTrue({Timeline.EVENT_DOCUMENT_RECEIVED, Timeline.EVENT_CHECKLIST_COMPLETED} <= events)
        self.assertTrue(AuditLog.objects.filter(action='checklist_item_received').exists())

    def test_document_must_belong_to_same_case_and_be_visible(self):
        self.assertEqual(self.receive(self.staff_a, {'document': self.other_doc.id}).status_code, 400)
        self.assertEqual(self.receive(self.staff_b, {'document': self.doc.id}).status_code, 404)
        self.assertEqual(self.receive(self.jiao, {}).status_code, 403)

    def test_generic_patch_cannot_link_document(self):
        self.client.force_login(self.staff_a)
        self.client.patch(f'/api/case-checklist-items/{self.item.id}/', {'document': self.other_doc.id},
                          content_type='application/json')
        self.item.refresh_from_db()
        self.assertIsNone(self.item.document_id)

    def test_document_upload_records_timeline(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.staff_a)
        response = self.client.post('/api/documents/', {'case': self.case_a.id, 'title': '在職証明',
                                                        'file': SimpleUploadedFile('zaishoku.pdf', b'%PDF')})
        self.assertEqual(response.status_code, 201, response.content)
        event = Timeline.objects.get(case=self.case_a, event_type=Timeline.EVENT_DOCUMENT_UPLOADED)
        self.assertEqual(event.metadata['document_id'], response.json()['id'])


class AccountingLinkTimelineTests(WorkFixture, TestCase):
    def test_tax_renewal_record_linked_to_case_records_timeline_only(self):
        self.client.force_login(self.li)
        response = self.client.post('/api/accounting/tax-renewal-records/', {
            'title': '更新用', 'category': 'renewal', 'case': self.case_a.id,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        event = Timeline.objects.get(case=self.case_a, event_type=Timeline.EVENT_ACCOUNTING_LINKED)
        self.assertEqual(event.metadata['module'], 'accounting.tax_renewal')
