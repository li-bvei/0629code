"""P6：マイナンバーの表示（専用操作・明示権限・対象の閲覧範囲・監査）と、顧客詳細の関連会社の表示範囲。

マイナンバーはすべて合成値（実在しない番号）。応答・監査・ログに平文が出ないことを文字列で確認する。
"""
import json
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.authentication.tests.test_case_party_access import AccessFixtureMixin
from apps.cases.models import Case
from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer, FamilyMember

SYNTHETIC_A = '123412341234'      # フィクスチャの顧客 A（合成値）
SYNTHETIC_FAMILY = '987698769876'
SYNTHETIC_LINKED = '555566667777'
SYNTHETIC_STAFF = '444433332222'       # 旧形式（顧客に関連付いていない）会社職員
SYNTHETIC_B = '111122223333'


class MyNumberFixture(AccessFixtureMixin):
    def setUp(self):
        super().setUp()
        self.family = FamilyMember.objects.create(customer=self.cust_a, name='家族A2', relationship='child',
                                                  birth_date='2015-05-05', my_number=SYNTHETIC_FAMILY)
        self.linked_person = Customer.objects.create(name='関連人物', birth_date='1992-02-02', my_number=SYNTHETIC_LINKED)
        self.linked_family = FamilyMember.objects.create(customer=self.cust_a, relationship='spouse',
                                                         family_customer=self.linked_person)

    def reveal(self, user, kind, pk):
        self.as_user(user)
        base = {'customer': '/api/customers/', 'staff': '/api/company-staff/'}.get(kind, '/api/family-members/')
        return self.client.post(f'{base}{pk}/reveal-my-number/', content_type='application/json')

    def grant(self, username, revoke=False):
        args = ['grant_business_permission', '--username', username, '--permission', 'customers.reveal_my_number',
                '--apply', '--yes']
        if revoke:
            args.append('--revoke')
        call_command(*args, stdout=StringIO())

    def assertNoPlaintext(self, *payloads):
        text = json.dumps(payloads, ensure_ascii=False, default=str)
        for value in (SYNTHETIC_A, SYNTHETIC_FAMILY, SYNTHETIC_LINKED, SYNTHETIC_STAFF, SYNTHETIC_B):
            self.assertNotIn(value, text)


class MyNumberRevealTests(MyNumberFixture, TestCase):
    def test_system_admin_can_reveal_within_visible_scope_and_it_is_audited(self):
        response = self.reveal(self.li, 'customer', self.cust_a.id)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'registered': True, 'my_number': SYNTHETIC_A})
        self.assertIn('no-store', response['Cache-Control'])
        log = AuditLog.objects.get(action='my_number_reveal', object_id=str(self.cust_a.id))
        self.assertEqual((log.result, log.via_permission, log.user), ('success', 'customers.reveal_my_number', self.li))
        self.assertEqual(log.object_type, 'customers.customer')
        self.assertNoPlaintext(list(AuditLog.objects.values()))

    def test_individual_grant_and_revoke_via_command(self):
        denied = self.reveal(self.staff_a, 'customer', self.cust_a.id)  # 本人担当だが表示権限なし
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()['code'], 'my_number_permission_required')
        self.grant('staff_a')
        self.assertEqual(self.reveal(self.staff_a, 'customer', self.cust_a.id).json()['my_number'], SYNTHETIC_A)
        self.assertTrue(AuditLog.objects.filter(module='command', action='permission_grant').exists())
        self.grant('staff_a', revoke=True)
        self.assertEqual(self.reveal(self.staff_a, 'customer', self.cust_a.id).status_code, 403)
        self.assertTrue(AuditLog.objects.filter(module='command', action='permission_revoke').exists())
        denials = AuditLog.objects.filter(action='my_number_reveal_denied', result='denied', user=self.staff_a)
        self.assertEqual(denials.count(), 2)
        self.assertEqual(set(denials.values_list('reason', flat=True)), {'missing_permission'})

    def test_superuser_flag_or_other_roles_do_not_grant_reveal(self):
        self.assertEqual(self.reveal(self.su_only, 'customer', self.cust_a.id).status_code, 403)  # 業務権限なし
        self.assertEqual(self.reveal(self.jiao, 'customer', self.cust_a.id).status_code, 403)  # superuser＋業務管理者
        self.assertFalse(AuditLog.objects.filter(action='my_number_reveal').exists())

    def test_permission_does_not_widen_object_scope_404_for_invisible_targets(self):
        self.grant('staff_a')
        response = self.reveal(self.staff_a, 'customer', self.cust_b.id)  # 他担当の案件がある顧客
        self.assertEqual(response.status_code, 404)
        self.assertNoPlaintext(response.content.decode())
        missing = self.reveal(self.staff_a, 'customer', 999999)
        self.assertEqual(missing.status_code, 404)
        logs = AuditLog.objects.filter(action='my_number_reveal_denied', reason='not_visible')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.first().object_repr, '')

    def test_permission_does_not_reveal_for_basic_only_customers(self):
        # 案件の無い顧客は基本情報（BASIC）だけ見られる：表示権限があっても 403（範囲を広げない）
        self.cust_new.my_number = SYNTHETIC_A
        self.cust_new.save()
        self.grant('staff_a')
        self.as_user(self.staff_a)
        detail = self.client.get(f'/api/customers/{self.cust_new.id}/')
        self.assertEqual((detail.status_code, detail.json().get('access_level')), (200, 'basic'))
        response = self.reveal(self.staff_a, 'customer', self.cust_new.id)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'my_number_scope_required')
        self.assertNoPlaintext(response.content.decode(), list(AuditLog.objects.values()))
        self.assertTrue(AuditLog.objects.filter(action='my_number_reveal_denied', reason='detail_scope_required',
                                                object_id=str(self.cust_new.id)).exists())

    def test_list_detail_search_and_export_never_contain_plaintext(self):
        self.grant('staff_a')
        for user in (self.li, self.staff_a, self.jiao):
            self.as_user(user)
            payloads = [
                self.client.get('/api/customers/').json(),
                self.client.get(f'/api/customers/{self.cust_a.id}/').json(),
                self.client.get('/api/customers/', {'search': SYNTHETIC_A}).json(),
                self.client.get('/api/family-members/', {'customer': self.cust_a.id}).json(),
                self.client.get(f'/api/family-members/{self.family.id}/').json(),
            ]
            self.assertNoPlaintext(payloads)
        detail = self.client.get(f'/api/customers/{self.cust_a.id}/').json()
        self.assertTrue(detail['has_my_number'])
        self.assertEqual(self.client.get('/api/customers/', {'search': SYNTHETIC_A}).json()['results'], [])

    def test_family_members_follow_the_same_rules(self):
        response = self.reveal(self.li, 'family', self.family.id)
        self.assertEqual(response.json(), {'registered': True, 'my_number': SYNTHETIC_FAMILY})
        linked = self.reveal(self.li, 'family', self.linked_family.id)
        self.assertEqual(linked.json()['my_number'], SYNTHETIC_LINKED)  # 関連付いた人物の値
        self.assertEqual(self.reveal(self.staff_a, 'family', self.family.id).status_code, 403)
        self.grant('staff_b')
        self.assertEqual(self.reveal(self.staff_b, 'family', self.family.id).status_code, 404)
        log = AuditLog.objects.get(action='my_number_reveal', object_id=str(self.family.id))
        self.assertEqual(log.object_type, 'customers.familymember')
        self.assertNoPlaintext(list(AuditLog.objects.values()))

    def test_unregistered_and_unreadable_values_do_not_leak(self):
        empty = Customer.objects.create(name='未登録', birth_date='1993-03-03')
        Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                            customer=empty, responsible_employee=self.emp_a)
        self.assertEqual(self.reveal(self.li, 'customer', empty.id).json(), {'registered': False, 'my_number': ''})
        from apps.customers import my_number

        with mock.patch.dict(my_number.VALUE_READERS, {'customer': mock.Mock(side_effect=my_number.MyNumberUnavailable())}):
            with self.assertLogs('django.request', level='WARNING') as captured:
                response = self.reveal(self.li, 'customer', self.cust_a.id)
        self.assertEqual(response.status_code, 422)
        self.assertNoPlaintext(response.content.decode(), captured.output)
        self.assertEqual(AuditLog.objects.filter(action='my_number_reveal_denied', result='error').count(), 1)

    def test_command_only_grants_listed_permissions(self):
        with self.assertRaises(Exception):
            call_command('grant_business_permission', '--username', 'staff_a', '--permission',
                         'cases.case_change_all', '--apply', '--yes', stdout=StringIO())
        out = StringIO()
        call_command('grant_business_permission', '--username', 'staff_a', '--permission',
                     'customers.reveal_my_number', stdout=out)  # dry-run
        self.assertIn('dry-run', out.getvalue())
        self.assertEqual(self.reveal(self.staff_a, 'customer', self.cust_a.id).status_code, 403)


class CompanyStaffRevealTests(MyNumberFixture, TestCase):
    """会社職員のマイナンバー：顧客・家族と同じ権限（customers.reveal_my_number）と監査。"""

    def setUp(self):
        super().setUp()
        self.cust_b.my_number = SYNTHETIC_B
        self.cust_b.save()
        # 顧客 B に関連付いた職員（フィクスチャ）・顧客 A に関連付いた職員・旧形式の職員
        self.staff_linked_b = CompanyStaff.objects.get(company=self.company_a, customer=self.cust_b)
        self.staff_linked_a = CompanyStaff.objects.create(company=self.company_a, customer=self.cust_a, position='代表補佐')
        self.staff_legacy = CompanyStaff.objects.create(company=self.company_a, name='旧形式 職員', my_number=SYNTHETIC_STAFF)

    def test_system_admin_reveals_linked_customer_value_and_legacy_staff_value(self):
        linked = self.reveal(self.li, 'staff', self.staff_linked_b.id)
        self.assertEqual(linked.status_code, 200, linked.content)
        self.assertEqual(linked.json(), {'registered': True, 'my_number': SYNTHETIC_B})  # 関連付いた顧客の値
        self.assertIn('no-store', linked['Cache-Control'])
        legacy = self.reveal(self.li, 'staff', self.staff_legacy.id)
        self.assertEqual(legacy.json(), {'registered': True, 'my_number': SYNTHETIC_STAFF})
        logs = AuditLog.objects.filter(action='my_number_reveal', object_type='companies.companystaff')
        self.assertEqual(sorted(logs.values_list('extra__linked_customer', flat=True)), [False, True])
        self.assertNoPlaintext(list(AuditLog.objects.values()))

    def test_individual_grant_unauthorized_and_revoke(self):
        self.assertEqual(self.reveal(self.staff_a, 'staff', self.staff_legacy.id).status_code, 403)  # 担当範囲内・権限なし
        self.grant('staff_a')
        self.assertEqual(self.reveal(self.staff_a, 'staff', self.staff_legacy.id).json()['my_number'], SYNTHETIC_STAFF)
        self.assertEqual(self.reveal(self.staff_a, 'staff', self.staff_linked_a.id).json()['my_number'], SYNTHETIC_A)
        self.grant('staff_a', revoke=True)
        self.assertEqual(self.reveal(self.staff_a, 'staff', self.staff_legacy.id).status_code, 403)
        reasons = set(AuditLog.objects.filter(action='my_number_reveal_denied', user=self.staff_a).values_list('reason', flat=True))
        self.assertEqual(reasons, {'missing_permission'})
        self.assertNoPlaintext(list(AuditLog.objects.values()))

    def test_scope_404_superuser_only_403_and_linked_person_not_widened(self):
        self.grant('staff_b')
        response = self.reveal(self.staff_b, 'staff', self.staff_legacy.id)  # 会社 A は担当範囲外
        self.assertEqual(response.status_code, 404)
        self.assertNoPlaintext(response.content.decode())
        self.assertEqual(self.reveal(self.su_only, 'staff', self.staff_legacy.id).status_code, 403)  # superuser だけ
        self.assertEqual(self.reveal(self.jiao, 'staff', self.staff_legacy.id).status_code, 403)  # superuser＋業務管理者
        # staff_a は会社 A を見られるが、職員として関連付いた顧客 B（他担当の進行中案件）は見られない
        self.grant('staff_a')
        self.as_user(self.staff_a)
        from apps.authentication.access_rules import CUSTOMER_RULE, VISIBLE_LEVELS
        from apps.authentication.access_policy import BusinessAccessPolicy

        self.assertNotIn(CUSTOMER_RULE.level(BusinessAccessPolicy(self.staff_a), self.cust_b), VISIBLE_LEVELS)
        denied = self.reveal(self.staff_a, 'staff', self.staff_linked_b.id)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()['code'], 'my_number_scope_required')
        self.assertTrue(AuditLog.objects.filter(action='my_number_reveal_denied', reason='linked_person_not_visible').exists())
        self.assertNoPlaintext(denied.content.decode(), list(AuditLog.objects.values()))

    def test_unreadable_value_is_422_and_audited_without_plaintext(self):
        from apps.customers import my_number

        broken = mock.Mock(side_effect=my_number.MyNumberUnavailable())
        with mock.patch.dict(my_number.VALUE_READERS, {'company_staff': broken}):
            with self.assertLogs('django.request', level='WARNING') as captured:
                response = self.reveal(self.li, 'staff', self.staff_legacy.id)
        self.assertEqual(response.status_code, 422)
        self.assertNoPlaintext(response.content.decode(), captured.output, list(AuditLog.objects.values()))
        self.assertEqual(AuditLog.objects.filter(action='my_number_reveal_denied', result='error').count(), 1)

    def test_company_and_staff_apis_never_contain_plaintext(self):
        self.grant('staff_a')
        for user in (self.li, self.staff_a, self.jiao):
            self.as_user(user)
            payloads = [
                self.client.get(f'/api/companies/{self.company_a.id}/').json(),
                self.client.get('/api/companies/').json(),
                self.client.get('/api/company-staff/', {'company': self.company_a.id}).json(),
                self.client.get(f'/api/company-staff/{self.staff_legacy.id}/').json(),
                self.client.get('/api/customers/', {'search': '顧客'}).json(),
            ]
            self.assertNoPlaintext(payloads)
        self.as_user(self.li)
        rows = {row['id']: row for row in self.client.get('/api/company-staff/', {'company': self.company_a.id}).json()['results']}
        self.assertEqual((rows[self.staff_legacy.id]['has_my_number'], rows[self.staff_linked_b.id]['has_my_number']), (True, True))
        self.assertNotIn('my_number', rows[self.staff_legacy.id])


class RelatedCompanyScopeTests(MyNumberFixture, TestCase):
    def test_related_companies_only_link_to_visible_companies_and_hide_contact_otherwise(self):
        other = Company.objects.create(name='範囲外会社', phone='03-0000-0000', email='x@example.invalid')
        Case.objects.create(case_type='x', case_type_master=self.case_type, application_category=self.category,
                            customer=self.cust_b, company=other, responsible_employee=self.emp_b)
        CompanyStaff.objects.create(company=other, customer=self.cust_a, position='社員')
        CompanyStaff.objects.create(company=self.company_a, customer=self.cust_a, position='代表補佐')
        self.as_user(self.staff_a)
        rows = {row['id']: row for row in self.client.get(f'/api/customers/{self.cust_a.id}/').json()['related_companies']}
        self.assertEqual(len(rows), 2)  # 案件・職員で重複しても 1 行
        self.assertTrue(rows[self.company_a.id]['can_open'])
        self.assertEqual(set(rows[self.company_a.id]['relation_types']), {'staff', 'case'})
        self.assertFalse(rows[other.id]['can_open'])
        self.assertEqual((rows[other.id]['phone'], rows[other.id]['email']), ('', ''))
        self.assertNotIn('bank_account_number', json.dumps(rows))
        self.assertEqual(self.client.get(f'/api/companies/{other.id}/').status_code, 404)  # 直接 URL でも入れない
        self.assertEqual(self.client.get(f'/api/companies/{self.company_a.id}/').status_code, 200)
