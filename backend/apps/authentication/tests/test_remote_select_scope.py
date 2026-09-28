"""RemoteSelect が呼ぶ検索 API（顧客・会社・担当者）が権限範囲内の結果だけを返すこと。"""
from django.test import TestCase

from apps.authentication.roles import EXPENSE_VIEWER
from apps.authentication.testing import make_user

from .test_case_party_access import AccessFixtureMixin


class RemoteSelectScopeTests(AccessFixtureMixin, TestCase):
    def rows(self, response):
        data = response.json()
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    def test_customer_search_minimal_outside_scope_and_detail_404(self):
        self.as_user(self.staff_b)
        rows = {r['id']: r for r in self.rows(self.client.get('/api/customers/?search=顧客A'))}
        self.assertEqual(rows[self.cust_a.id]['access_level'], 'minimal')
        self.assertNotIn('phone', rows[self.cust_a.id])
        # 初期値の取得（fetchOne 相当）は範囲外なら 404 → フロントは id のみ表示
        self.assertEqual(self.client.get(f'/api/customers/{self.cust_a.id}/').status_code, 404)

    def test_case_number_search_limited_to_visible_cases(self):
        self.as_user(self.staff_b)
        ids = {r['id'] for r in self.rows(self.client.get(f'/api/customers/?search={self.case_a.case_number}'))}
        self.assertNotIn(self.cust_a.id, ids)
        self.as_user(self.staff_a)
        ids = {r['id'] for r in self.rows(self.client.get(f'/api/customers/?search={self.case_a.case_number}'))}
        self.assertIn(self.cust_a.id, ids)

    def test_company_search_minimal_outside_scope(self):
        self.as_user(self.staff_b)
        row = next(r for r in self.rows(self.client.get('/api/companies/?search=会社A')) if r['id'] == self.company_a.id)
        self.assertEqual(set(row), {'id', 'name', 'name_kana', 'corporate_number', 'access_level'})

    def test_search_requires_case_module(self):
        expense_only = make_user('expense_only', roles=[EXPENSE_VIEWER], employee_name='経費のみ')
        self.as_user(expense_only)
        for url in ('/api/customers/?search=顧客', '/api/companies/?search=会社', '/api/employees/?search=A'):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.as_user(self.su_only)
        self.assertEqual(self.client.get('/api/employees/').status_code, 403)
        self.as_user(None)
        self.assertIn(self.client.get('/api/customers/?search=顧客').status_code, (401, 403))

    def test_employee_list_readable_but_not_writable_for_staff(self):
        self.as_user(self.staff_a)
        self.assertEqual(self.client.get('/api/employees/?search=B').status_code, 200)
        response = self.client.post('/api/employees/', {'name': '勝手に追加'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
