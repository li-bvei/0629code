"""P2 会計：支出・収入の顧客/会社/案件関連、案件の会計要約、カテゴリ入力支援、報銷の分離維持。"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.models import Expense, ExpenseCategory, IncomeSource
from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster
from apps.companies.models import Company
from apps.customers.models import Customer
from apps.employees.models import Employee
from apps.timelines.models import Timeline


class AccountingFixture:
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=True)
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦', superuser=True)
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        ct, _ = CaseTypeMaster.objects.update_or_create(code='ac', defaults={'name': '会計試験種別', 'number_abbreviation': '会試'})
        cat, _ = CaseApplicationCategory.objects.update_or_create(code='ac', defaults={'name': '会計試験区分', 'number_abbreviation': '会区'})
        self.customer = Customer.objects.create(name='会計顧客', birth_date='1990-01-01')
        self.company = Company.objects.create(name='会計会社')
        self.other_customer = Customer.objects.create(name='他担当顧客', birth_date='1991-01-01')
        self.case_a = Case.objects.create(case_type='x', case_type_master=ct, application_category=cat, status=Case.STATUS_OPEN,
                                          customer=self.customer, company=self.company,
                                          responsible_employee=Employee.objects.get(user=self.staff_a))
        self.case_b = Case.objects.create(case_type='x', case_type_master=ct, application_category=cat, status=Case.STATUS_OPEN,
                                          customer=self.other_customer, responsible_employee=Employee.objects.get(user=self.staff_b))

    def post_expense(self, user, **extra):
        self.client.force_login(user)
        body = {'expense_date': '2026-09-10', 'category': '交通費', 'amount': '1200', **extra}
        return self.client.post('/api/accounting/expenses/', body, content_type='application/json')


class ExpenseLinkTests(AccountingFixture, TestCase):
    def test_link_to_own_case_fills_customer_company_and_records_timeline_without_amount(self):
        response = self.post_expense(self.staff_a, case=self.case_a.id)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data['customer'], self.customer.id)
        self.assertEqual(data['company'], self.company.id)
        self.assertEqual(data['case_number'], self.case_a.case_number)
        event = Timeline.objects.get(case=self.case_a, event_type=Timeline.EVENT_EXPENSE_RECORDED)
        self.assertIn('交通費', event.content)
        self.assertNotIn('1200', event.content)
        self.assertNotIn('1,200', event.content)
        self.assertTrue(event.metadata['linked'])
        self.assertTrue(AuditLog.objects.filter(action='expense_case_linked', user=self.staff_a).exists())

    def test_cannot_link_to_case_or_party_outside_scope(self):
        self.assertEqual(self.post_expense(self.staff_a, case=self.case_b.id).status_code, 403)
        self.assertEqual(self.post_expense(self.staff_a, customer=self.other_customer.id).status_code, 403)
        # 業務管理者は他担当の案件を閲覧できても「変更」できないので関連付け不可
        self.assertEqual(self.post_expense(self.jiao, case=self.case_a.id).status_code, 403)
        self.assertEqual(Expense.objects.count(), 0)

    def test_relink_and_unlink_are_recorded_on_both_cases(self):
        expense_id = self.post_expense(self.li, case=self.case_a.id).json()['id']
        self.client.force_login(self.li)
        response = self.client.patch(f'/api/accounting/expenses/{expense_id}/', {'case': self.case_b.id},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Timeline.objects.filter(case=self.case_a, title='支出の関連付けを解除').exists())
        self.assertTrue(Timeline.objects.filter(case=self.case_b, title='支出を関連付け').exists())
        self.client.patch(f'/api/accounting/expenses/{expense_id}/', {'case': None}, content_type='application/json')
        self.assertTrue(Timeline.objects.filter(case=self.case_b, title='支出の関連付けを解除').exists())

    def test_owner_isolation_still_enforced_with_links(self):
        own_id = self.post_expense(self.staff_a, case=self.case_a.id).json()['id']
        self.client.force_login(self.jiao)
        self.assertEqual(self.client.get(f'/api/accounting/expenses/{own_id}/').status_code, 200)  # 閲覧のみ
        response = self.client.patch(f'/api/accounting/expenses/{own_id}/', {'note': 'x'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.staff_b)
        self.assertEqual(self.client.get(f'/api/accounting/expenses/{own_id}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/accounting/expenses/?case={self.case_a.id}').json()['count'], 0)
        # 報銷は簡単登録のまま：審査・承認などの状態項目は存在しない
        self.assertFalse({'status', 'approved_by', 'submitted_at'} & {f.name for f in Expense._meta.fields})

    def test_income_link_requires_income_module(self):
        self.client.force_login(self.li)
        response = self.client.post('/api/accounting/income-sources/', {
            'source_date': '2026-09-01', 'amount': '50000', 'case': self.case_a.id,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['customer'], self.customer.id)
        self.assertTrue(Timeline.objects.filter(case=self.case_a, event_type=Timeline.EVENT_ACCOUNTING_LINKED,
                                                title='収入を関連付け').exists())
        self.client.force_login(self.staff_a)
        self.assertEqual(self.client.post('/api/accounting/income-sources/', {
            'source_date': '2026-09-01', 'amount': '1', 'case': self.case_a.id,
        }, content_type='application/json').status_code, 403)


class CaseAccountingSummaryTests(AccountingFixture, TestCase):
    def setUp(self):
        super().setUp()
        Expense.objects.create(expense_date=date(2026, 9, 1), category='交通費', amount=Decimal('1000'),
                               owner=self.staff_a, case=self.case_a)
        Expense.objects.create(expense_date=date(2026, 9, 2), category='印紙代', amount=Decimal('4000'),
                               owner=self.li, case=self.case_a)
        IncomeSource.objects.create(source_date=date(2026, 9, 3), amount=Decimal('88000'), case=self.case_a)

    def summary(self, user, case=None):
        self.client.force_login(user)
        return self.client.get(f'/api/cases/{(case or self.case_a).id}/accounting-summary/')

    def test_assignee_sees_only_own_expenses_and_no_income(self):
        data = self.summary(self.staff_a).json()
        self.assertEqual(data['expense']['count'], 1)
        self.assertEqual(data['expense']['total'], 1000)
        self.assertEqual(data['expense']['scope'], 'own')
        self.assertFalse(data['income']['visible'])
        self.assertFalse(data['tax_renewal']['visible'])

    def test_business_admin_sees_all_expenses_read_only_and_li_sees_income(self):
        data = self.summary(self.jiao).json()
        self.assertEqual(data['expense']['count'], 2)
        self.assertEqual(data['expense']['scope'], 'all')
        self.assertFalse(data['income']['visible'])
        data = self.summary(self.li).json()
        self.assertEqual(data['income']['total'], 88000)

    def test_case_scope_still_applies(self):
        self.assertEqual(self.summary(self.staff_b).status_code, 404)


class CategorySuggestionTests(AccountingFixture, TestCase):
    def setUp(self):
        super().setUp()
        ExpenseCategory.objects.create(name='交通費')
        ExpenseCategory.objects.create(name='通信費')
        for _ in range(3):
            Expense.objects.create(expense_date=date(2026, 8, 1), category='証明書代', place='新宿区役所',
                                   amount=Decimal('300'), owner=self.staff_a)
        Expense.objects.create(expense_date=date(2026, 8, 2), category='交通費', place='新宿駅', amount=Decimal('200'),
                               owner=self.staff_a)
        # 他人の履歴（推薦に使ってはならない）
        for _ in range(5):
            Expense.objects.create(expense_date=date(2026, 8, 3), category='秘密の分類', place='新宿区役所',
                                   amount=Decimal('999'), owner=self.staff_b)

    def get(self, user, **params):
        self.client.force_login(user)
        return self.client.get('/api/accounting/expenses/category-suggestions/', params).json()

    def test_search_and_manual_input(self):
        data = self.get(self.staff_a, q='交通')
        self.assertEqual(data['matches'][0]['name'], '交通費')
        self.assertEqual(data['normalized']['suggestion'], '交通費')  # 「交通」は同義語
        self.assertIsNone(self.get(self.staff_a, q='交通費')['normalized'])  # 既存名そのものなら提案なし
        # 手入力の新しい分類もそのまま保存できる（自動で書き換えない）
        response = self.post_expense(self.staff_a, category='新しい分類')
        self.assertEqual(response.json()['category'], '新しい分類')

    def test_synonym_and_notation_normalization_is_only_a_suggestion(self):
        self.assertEqual(self.get(self.staff_a, q='交通費用')['normalized']['suggestion'], '交通費')
        self.assertEqual(self.get(self.staff_a, q='タクシー代')['normalized']['suggestion'], '交通費')
        self.assertEqual(self.get(self.staff_a, q='交通費 ')['normalized']['suggestion'], '交通費')
        response = self.post_expense(self.staff_a, category='交通費用')
        self.assertEqual(response.json()['category'], '交通費用')
        self.assertEqual(Expense.objects.filter(category='交通費用').count(), 1)

    def test_recommendation_uses_only_own_history(self):
        data = self.get(self.staff_a, place='新宿区役所')
        names = [r['name'] for r in data['recommendations']]
        self.assertEqual(names[0], '証明書代')
        self.assertNotIn('秘密の分類', names)
        self.assertEqual(data['source_scope'], 'own_history')
        # expense_view_all を持つ焦でも他人の履歴からは推薦されない
        self.assertEqual(self.get(self.jiao, place='新宿区役所')['recommendations'], [])
        self.assertNotIn('秘密の分類', [m['name'] for m in self.get(self.jiao, q='秘密')['matches']])

    def test_requires_expense_module(self):
        su = make_user('su_cat', superuser=True)
        self.client.force_login(su)
        self.assertEqual(self.client.get('/api/accounting/expenses/category-suggestions/').status_code, 403)

    def test_no_bulk_rewrite_of_existing_data(self):
        self.get(self.staff_a, q='交通費用')
        self.assertEqual(Expense.objects.filter(category='証明書代').count(), 3)
