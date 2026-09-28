"""受控関連規則：既存の顧客・会社 ID を提出して担当範囲を自己拡大できないこと。

案件作成・更新、受付（既存顧客・既存会社・家族・代表者）、家族、会社職員、会社代表者の各入口で、
他担当の進行中案件がある対象は 403。李・link_all 明示付与者は可能で cross_scope_link を監査。
フロントの候補ではなく、提出された実 ID（画面に出ない対象の ID も含む）で判定されること。"""
from django.contrib.auth.models import Permission
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.cases.models import Case
from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer, FamilyMember

from .test_case_party_access import AccessFixtureMixin


class PartyLinkBypassTests(AccessFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        # staff_b 自身の範囲：cust_b（case_b）と、case_b に紐付けた company_b
        self.company_b = Company.objects.create(name='会社B')
        Case.objects.filter(pk=self.case_b.pk).update(company=self.company_b)
        self.case_payload = {'case_type_master': self.case_type.id, 'application_category': self.category.id,
                             'status': Case.STATUS_OPEN}

    def post(self, user, url, body):
        self.as_user(user)
        return self.client.post(url, body, content_type='application/json')

    def assertDenied(self, response, keyword):
        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn(keyword, response.json()['detail'])

    # --- 案件 -----------------------------------------------------------------
    def test_case_create_with_other_staffs_customer_is_denied(self):
        before = Case.objects.count()
        response = self.post(self.staff_b, '/api/cases/', {**self.case_payload, 'customer': self.cust_a.id})
        self.assertDenied(response, '他の担当者の進行中案件')
        self.assertEqual(Case.objects.count(), before)
        self.assertTrue(AuditLog.objects.filter(action='cross_scope_link_denied', user=self.staff_b,
                                                object_id=str(self.cust_a.id), result='denied').exists())

    def test_case_create_with_other_staffs_company_is_denied(self):
        response = self.post(self.staff_b, '/api/cases/',
                             {**self.case_payload, 'customer': self.cust_b.id, 'company': self.company_a.id})
        self.assertDenied(response, 'この会社')

    def test_case_update_to_other_staffs_customer_is_denied(self):
        self.as_user(self.staff_b)
        response = self.client.patch(f'/api/cases/{self.case_b.id}/', {'customer': self.cust_a.id},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.case_b.refresh_from_db()
        self.assertEqual(self.case_b.customer_id, self.cust_b.id)
        # 範囲が広がっていない
        self.assertEqual(self.client.get(f'/api/customers/{self.cust_a.id}/').status_code, 404)

    def test_only_knowing_the_id_is_not_enough(self):
        # staff_b には cust_a の詳細は 404（画面に出ない）が、ID 直接指定でも関連付けできない
        self.as_user(self.staff_b)
        self.assertEqual(self.client.get(f'/api/customers/{self.cust_a.id}/').status_code, 404)
        response = self.post(self.staff_b, '/api/cases/', {**self.case_payload, 'customer': self.cust_a.id})
        self.assertEqual(response.status_code, 403)

    # --- 家族・会社職員・会社代表者 ------------------------------------------------
    def test_family_link_bypass_is_denied(self):
        before = FamilyMember.objects.count()
        response = self.post(self.staff_b, '/api/family-members/',
                             {'customer': self.cust_b.id, 'family_customer': self.cust_a.id, 'relationship': 'spouse'})
        self.assertDenied(response, '他の担当者の進行中案件')
        self.assertEqual(FamilyMember.objects.count(), before)

    def test_company_staff_link_bypass_is_denied(self):
        before = CompanyStaff.objects.count()
        response = self.post(self.staff_b, '/api/company-staff/',
                             {'company': self.company_b.id, 'customer': self.cust_a.id, 'position': '社員'})
        self.assertDenied(response, '他の担当者の進行中案件')
        self.assertEqual(CompanyStaff.objects.count(), before)

    def test_company_representative_bypass_is_denied(self):
        response = self.post(self.staff_b, '/api/companies/', {'name': '新会社', 'representative_customer': self.cust_a.id})
        self.assertDenied(response, '他の担当者の進行中案件')

    # --- 受付 -------------------------------------------------------------------
    def test_reception_existing_customer_and_company_bypass_are_denied(self):
        case = {'case_type_master': self.case_type.id, 'application_category': self.category.id}
        before = Case.objects.count()
        for body, keyword in (
            ({'existing_customer_id': self.cust_a.id, 'case': case}, '他の担当者の進行中案件'),
            ({'existing_customer_id': self.cust_b.id, 'existing_company_id': self.company_a.id, 'case': case}, 'この会社'),
            ({'existing_customer_id': self.cust_b.id, 'family_members': [{'customer': self.cust_a.id, 'relationship': 'spouse'}]},
             '他の担当者の進行中案件'),
            ({'existing_customer_id': self.cust_b.id, 'company': {'name': '代表者経由', 'representative_customer': self.cust_a.id}},
             '他の担当者の進行中案件'),
        ):
            response = self.post(self.staff_b, '/api/receptions/', body)
            self.assertDenied(response, keyword)
        self.assertEqual(Case.objects.count(), before)
        self.assertFalse(Company.objects.filter(name='代表者経由').exists())

    # --- 許可されるケース -----------------------------------------------------------
    def test_own_scope_and_unassigned_objects_can_be_linked(self):
        response = self.post(self.staff_b, '/api/cases/', {**self.case_payload, 'customer': self.cust_b.id,
                                                            'company': self.company_b.id})
        self.assertEqual(response.status_code, 201, response.content)
        response = self.post(self.staff_b, '/api/cases/', {**self.case_payload, 'customer': self.cust_new.id})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AuditLog.objects.filter(action='party_link_unassigned', object_id=str(self.cust_new.id)).exists())

    def test_customer_with_only_closed_cases_can_be_linked(self):
        Case.objects.filter(pk=self.case_a.pk).update(status=Case.STATUS_COMPLETED)
        response = self.post(self.staff_b, '/api/cases/', {**self.case_payload, 'customer': self.cust_a.id})
        self.assertEqual(response.status_code, 201, response.content)

    def test_li_can_link_cross_scope_with_audit(self):
        response = self.post(self.li, '/api/cases/', {**self.case_payload, 'customer': self.cust_a.id,
                                                       'company': self.company_a.id,
                                                       'responsible_employee': self.emp_b.id})
        self.assertEqual(response.status_code, 201, response.content)
        logs = AuditLog.objects.filter(action='cross_scope_link', user=self.li, result='success')
        self.assertEqual({(log.object_type, log.object_id) for log in logs},
                         {('customers.customer', str(self.cust_a.id)), ('companies.company', str(self.company_a.id))})
        self.assertEqual({log.via_permission for log in logs}, {'customers.customer_link_all', 'customers.company_link_all'})
        self.assertTrue(all(log.extra['target'].startswith('cases.case:') for log in logs))

    def test_business_admin_needs_explicit_link_all(self):
        # 焦相当（業務管理者）は既定では他担当の顧客を家族として関連付けできない
        jiao_case = Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                                        status=Case.STATUS_OPEN, customer=self.cust_new,
                                        responsible_employee=self.jiao.employee)
        body = {'customer': jiao_case.customer_id, 'family_customer': self.cust_a.id, 'relationship': 'spouse'}
        self.assertEqual(self.post(self.jiao, '/api/family-members/', body).status_code, 403)
        self.jiao.user_permissions.add(Permission.objects.get(codename='customer_link_all'))
        response = self.post(self.jiao, '/api/family-members/', body)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AuditLog.objects.filter(action='cross_scope_link', user=self.jiao,
                                                via_permission='customers.customer_link_all').exists())

    def test_reception_cross_scope_by_li_is_audited(self):
        response = self.post(self.li, '/api/receptions/', {
            'existing_customer_id': self.cust_a.id,
            'case': {'case_type_master': self.case_type.id, 'application_category': self.category.id},
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AuditLog.objects.filter(action='cross_scope_link', user=self.li,
                                                object_id=str(self.cust_a.id)).exists())
