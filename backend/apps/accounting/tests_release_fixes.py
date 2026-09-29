"""本地发布验证で見つかった不具合の回帰テスト。"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.models import Expense
from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, SYSTEM_ADMIN
from apps.authentication.testing import make_user


class ExpenseExportAuditTests(TestCase):
    def setUp(self):
        self.li = make_user('rf_li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李')
        self.jiao = make_user('rf_jiao', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦')
        Expense.objects.create(expense_date=date(2026, 9, 1), category='交通費', amount=Decimal('500'), owner=self.jiao)
        Expense.objects.create(expense_date=date(2026, 9, 2), category='交通費', amount=Decimal('800'), owner=self.li)

    def export(self, user):
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/accounting/expenses/excel/').status_code, 200)
        return AuditLog.objects.filter(action='expense_export', user=user).latest('id')

    def test_viewer_export_is_own_only_and_audited_as_owner(self):
        log = self.export(self.jiao)
        self.assertEqual(log.extra['count'], 1)
        # 持っていない expense_export_all を根拠として記録しない
        self.assertEqual(log.via_permission, 'owner')

    def test_export_all_holder_is_audited_with_permission(self):
        log = self.export(self.li)
        self.assertEqual(log.extra['count'], 2)
        self.assertEqual(log.via_permission, 'accounting.expense_export_all')
