"""Case（担当者で制御）・子資源・Dashboard・受付・Customer/Company（最小検索・証件の伏せ字）の権限マトリクス。"""
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseChecklistItem, CaseTypeMaster
from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer, FamilyMember
from apps.employees.models import Employee
from apps.timelines.models import Timeline


class AccessFixtureMixin:
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=True)
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦', superuser=True)
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        self.su_only = make_user('su_only', superuser=True)
        self.unlinked = make_user('unlinked', roles=[STAFF])
        self.case_type, _ = CaseTypeMaster.objects.update_or_create(
            code='acc', defaults={'name': 'アクセス試験種別', 'number_abbreviation': '試験', 'sort_order': 1},
        )
        self.category, _ = CaseApplicationCategory.objects.update_or_create(
            code='acc-new', defaults={'name': 'アクセス試験区分', 'number_abbreviation': '試区', 'sort_order': 1},
        )
        self.cust_a = Customer.objects.create(name='顧客A', birth_date='1990-01-01', nationality='中国',
                                              residence_card_no='AB12345678CD', passport_no='E12345678',
                                              phone='090-1111-2222', address='東京都', my_number='123412341234')
        self.cust_b = Customer.objects.create(name='顧客B', birth_date='1991-01-01', residence_card_no='ZZ99998888YY')
        self.cust_new = Customer.objects.create(name='受付のみ', birth_date='1992-01-01', residence_card_no='NN11112222MM',
                                                phone='080-0000-0000')
        self.emp_a = Employee.objects.get(user=self.staff_a)
        self.emp_b = Employee.objects.get(user=self.staff_b)
        self.company_a = Company.objects.create(name='会社A', corporate_number='1234567890123', bank_account_number='7654321')
        self.case_a = self._case(self.cust_a, self.emp_a, company=self.company_a)
        self.case_b = self._case(self.cust_b, self.emp_b)
        self.case_unassigned = self._case(self.cust_b, None)
        self.item_a = CaseChecklistItem.objects.create(case=self.case_a, name='資料A')
        self.timeline_a = Timeline.objects.create(case=self.case_a, title='受付')
        FamilyMember.objects.create(customer=self.cust_a, name='家族A', relationship='spouse', birth_date='1990-05-05',
                                    residence_card_no='FM00001111XX')
        CompanyStaff.objects.create(company=self.company_a, customer=self.cust_b, position='社員')

    def _case(self, customer, employee, company=None):
        return Case.objects.create(
            case_type='経営・管理', case_type_master=self.case_type, application_category=self.category,
            status=Case.STATUS_OPEN, customer=customer, responsible_employee=employee, company=company,
        )

    def as_user(self, user):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)

    def rows(self, response):
        data = response.json()
        return data['results'] if isinstance(data, dict) and 'results' in data else data


class CaseAccessTests(AccessFixtureMixin, TestCase):
    def test_list_scope(self):
        self.as_user(self.staff_a)
        self.assertEqual({r['id'] for r in self.rows(self.client.get('/api/cases/'))}, {self.case_a.id})
        self.as_user(self.jiao)
        self.assertEqual({r['id'] for r in self.rows(self.client.get('/api/cases/'))},
                         {self.case_a.id, self.case_b.id, self.case_unassigned.id})
        self.as_user(self.su_only)
        self.assertEqual(self.client.get('/api/cases/').status_code, 403)
        self.as_user(None)
        self.assertIn(self.client.get('/api/cases/').status_code, (401, 403))

    def test_staff_cannot_see_or_change_other(self):
        self.as_user(self.staff_b)
        self.assertEqual(self.client.get(f'/api/cases/{self.case_a.id}/').status_code, 404)
        response = self.client.post(f'/api/cases/{self.case_a.id}/change-status/', {'new_status': 'accepted'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_business_admin_views_but_cannot_change_others(self):
        self.as_user(self.jiao)
        self.assertEqual(self.client.get(f'/api/cases/{self.case_a.id}/').status_code, 200)
        response = self.client.patch(f'/api/cases/{self.case_a.id}/', {'next_action': 'x'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        response = self.client.post(f'/api/cases/{self.case_a.id}/change-status/', {'new_status': 'accepted'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)
        response = self.client.patch(f'/api/cases/{self.case_unassigned.id}/', {'next_action': 'x'},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_assignee_can_change_and_li_can_change_unassigned(self):
        self.as_user(self.staff_a)
        response = self.client.patch(f'/api/cases/{self.case_a.id}/', {'next_action': '電話'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.as_user(self.li)
        response = self.client.patch(f'/api/cases/{self.case_unassigned.id}/', {'next_action': '割当'},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='case_change_other', user=self.li).exists())

    def test_reassign_is_audited_and_restricted(self):
        self.as_user(self.jiao)
        response = self.client.patch(f'/api/cases/{self.case_b.id}/', {'responsible_employee': self.emp_a.id},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.as_user(self.li)
        response = self.client.patch(f'/api/cases/{self.case_b.id}/', {'responsible_employee': self.emp_a.id},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='case_reassign', object_id=str(self.case_b.id)).exists())

    def test_child_resources_follow_parent_case(self):
        self.as_user(self.staff_b)
        self.assertEqual(self.client.get(f'/api/case-checklist-items/{self.item_a.id}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/timelines/{self.timeline_a.id}/').status_code, 404)
        self.assertEqual(self.rows(self.client.get(f'/api/timelines/?case={self.case_a.id}')), [])
        response = self.client.post('/api/timelines/', {'case': self.case_a.id, 'title': '侵入'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.as_user(self.jiao)
        self.assertEqual(self.client.get(f'/api/timelines/{self.timeline_a.id}/').status_code, 200)
        response = self.client.patch(f'/api/case-checklist-items/{self.item_a.id}/', {'is_completed': True},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.as_user(self.staff_a)
        response = self.client.patch(f'/api/case-checklist-items/{self.item_a.id}/', {'is_completed': True},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_summary_scoped(self):
        self.as_user(self.staff_a)
        data = self.client.get('/api/dashboard/summary/').json()
        self.assertEqual(data['cases']['total'], 1)
        self.assertEqual([c['id'] for c in data['recent_cases']], [self.case_a.id])
        self.as_user(self.jiao)
        self.assertEqual(self.client.get('/api/dashboard/summary/').json()['cases']['total'], 3)
        self.as_user(self.su_only)
        self.assertEqual(self.client.get('/api/dashboard/summary/').status_code, 403)

    def test_deadlines_scoped(self):
        from datetime import timedelta

        from django.utils import timezone

        Customer.objects.filter(pk__in=[self.cust_a.pk, self.cust_b.pk]).update(
            residence_expiry=timezone.localdate() + timedelta(days=10),
        )
        self.as_user(self.staff_a)
        names = {row['target_name'] for row in self.client.get('/api/dashboard/deadlines/').json()}
        self.assertIn('顧客A', names)
        self.assertNotIn('顧客B', names)

    def test_case_create_defaults_to_own_employee_and_restricts_others(self):
        self.as_user(self.staff_a)
        payload = {'case_type_master': self.case_type.id, 'application_category': self.category.id,
                   'customer': self.cust_new.id, 'status': Case.STATUS_OPEN}
        response = self.client.post('/api/cases/', payload, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Case.objects.get(pk=response.json()['id']).responsible_employee, self.emp_a)
        response = self.client.post('/api/cases/', {**payload, 'responsible_employee': self.emp_b.id},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.as_user(self.unlinked)
        response = self.client.post('/api/cases/', payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_reception_default_responsible(self):
        body = {'existing_customer_id': self.cust_new.id,
                'case': {'case_type_master': self.case_type.id, 'application_category': self.category.id}}
        self.as_user(self.staff_a)
        response = self.client.post('/api/receptions/', body, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Case.objects.get(pk=response.json()['case']).responsible_employee, self.emp_a)
        self.as_user(self.unlinked)
        response = self.client.post('/api/receptions/', body, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('responsible_employee', response.json())


class PartyAccessTests(AccessFixtureMixin, TestCase):
    FORBIDDEN_SEARCH_KEYS = {'residence_card_no', 'passport_no', 'address', 'phone', 'email', 'my_number', 'postal_code'}

    def test_search_returns_minimal_for_out_of_scope(self):
        self.as_user(self.staff_b)
        rows = {r['id']: r for r in self.rows(self.client.get('/api/customers/?search=顧客'))}
        minimal = rows[self.cust_a.id]
        self.assertEqual(minimal['access_level'], 'minimal')
        self.assertFalse(self.FORBIDDEN_SEARCH_KEYS & set(minimal))
        self.assertTrue(minimal['has_active_case'])
        self.assertEqual(minimal['responsible_employee_names'], ['A'])
        self.assertEqual(rows[self.cust_b.id]['access_level'], 'full')

    def test_match_hides_contact_for_out_of_scope(self):
        self.as_user(self.staff_b)
        response = self.client.post('/api/customers/match/', {'name': '顧客A', 'birth_date': '1990-01-01'},
                                    content_type='application/json')
        candidate = next(c for c in response.json()['candidates'] if c['customer_id'] == self.cust_a.id)
        self.assertNotIn('phone', candidate)
        self.assertNotIn('email', candidate)

    def test_detail_scope_and_masking(self):
        self.as_user(self.staff_b)
        self.assertEqual(self.client.get(f'/api/customers/{self.cust_a.id}/').status_code, 404)
        self.as_user(self.staff_a)
        data = self.client.get(f'/api/customers/{self.cust_a.id}/').json()
        self.assertEqual(data['residence_card_no'], 'AB12345678CD')
        self.assertEqual(data['passport_no'], 'E12345678')
        self.assertNotIn('my_number', data)
        self.assertTrue(data['has_my_number'])
        self.as_user(self.jiao)
        data = self.client.get(f'/api/customers/{self.cust_a.id}/').json()
        self.assertEqual(data['access_level'], 'masked')
        self.assertEqual(data['residence_card_no'], '****78CD')
        self.assertEqual(data['passport_no'], '****5678')
        self.as_user(self.li)
        data = self.client.get(f'/api/customers/{self.cust_b.id}/').json()
        self.assertEqual(data['residence_card_no'], 'ZZ99998888YY')
        self.assertTrue(AuditLog.objects.filter(action='sensitive_identity_view', user=self.li).exists())

    def test_uncased_customer_basic_only(self):
        self.as_user(self.staff_a)
        data = self.client.get(f'/api/customers/{self.cust_new.id}/').json()
        self.assertEqual(data['access_level'], 'basic')
        self.assertEqual(set(data), {'id', 'name', 'name_kana', 'birth_date', 'nationality', 'created_at',
                                     'phone', 'email', 'access_level'})
        self.assertEqual(data['phone'], '****0000')
        self.assertNotIn('080-0000-0000', self.client.get(f'/api/customers/{self.cust_new.id}/').content.decode())
        self.assertEqual(self.rows(self.client.get(f'/api/family-members/?customer={self.cust_new.id}')), [])
        response = self.client.patch(f'/api/customers/{self.cust_new.id}/', {'name': 'x'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.as_user(self.li)
        data = self.client.get(f'/api/customers/{self.cust_new.id}/').json()
        self.assertEqual(data['residence_card_no'], 'NN11112222MM')

    def test_related_cases_limited_to_visible(self):
        Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                            status=Case.STATUS_OPEN, customer=self.cust_a, responsible_employee=self.emp_b)
        self.as_user(self.staff_a)
        data = self.client.get(f'/api/customers/{self.cust_a.id}/').json()
        self.assertEqual({c['id'] for c in data['related_cases']}, {self.case_a.id})

    def test_family_members_masked_for_business_admin(self):
        self.as_user(self.staff_b)
        self.assertEqual(self.rows(self.client.get(f'/api/family-members/?customer={self.cust_a.id}')), [])
        self.as_user(self.jiao)
        rows = self.rows(self.client.get(f'/api/family-members/?customer={self.cust_a.id}'))
        self.assertEqual(rows[0]['residence_card_no'], '****11XX')
        self.assertNotIn('my_number', rows[0])

    def test_company_minimal_bank_mask_and_staff_my_number(self):
        self.as_user(self.staff_b)
        rows = {r['id']: r for r in self.rows(self.client.get('/api/companies/?search=会社'))}
        self.assertEqual(set(rows[self.company_a.id]), {'id', 'name', 'name_kana', 'corporate_number', 'access_level'})
        self.assertEqual(self.client.get(f'/api/companies/{self.company_a.id}/').status_code, 404)
        self.as_user(self.jiao)
        data = self.client.get(f'/api/companies/{self.company_a.id}/').json()
        self.assertEqual(data['bank_account_number'], '****4321')
        self.as_user(self.staff_a)
        data = self.client.get(f'/api/companies/{self.company_a.id}/').json()
        self.assertEqual(data['bank_account_number'], '7654321')
        staff_rows = self.rows(self.client.get(f'/api/company-staff/?company={self.company_a.id}'))
        self.assertNotIn('my_number', staff_rows[0])
        self.assertIn('has_my_number', staff_rows[0])

    def test_no_response_contains_my_number_plaintext(self):
        self.as_user(self.li)
        for url in (f'/api/customers/{self.cust_a.id}/', '/api/customers/', f'/api/family-members/?customer={self.cust_a.id}',
                    f'/api/company-staff/?company={self.company_a.id}'):
            self.assertNotIn('123412341234', self.client.get(url).content.decode(), url)
