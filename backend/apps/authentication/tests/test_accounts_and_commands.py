"""アカウント管理の保護、Admin 段階A/B、開発用ツールの無効化、診断、管理コマンド（dry-run・適用・回滚）。"""
import importlib
import json
import os
import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import clear_url_caches

from apps.accounting.models import Expense
from apps.audit.models import AuditLog
from apps.authentication.models import ProtectedAccount
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.employees.models import Employee
from apps.common.test_isolation import safe_rmtree


def run(*args, **kwargs):
    out = StringIO()
    call_command(*args, stdout=out, **kwargs)
    return out.getvalue()


class AccountProtectionTests(TestCase):
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=True)
        ProtectedAccount.objects.create(user=self.li)
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦', superuser=True)
        self.su_only = make_user('su_only', superuser=True)

    def test_account_management_requires_explicit_manage_users(self):
        for user in (self.jiao, self.su_only):
            self.client.force_login(user)
            self.assertEqual(self.client.get('/api/users/').status_code, 403)
            response = self.client.patch(f'/api/users/{self.li.id}/', {'is_superuser': False}, content_type='application/json')
            self.assertEqual(response.status_code, 403)
        self.li.refresh_from_db()
        self.assertTrue(self.li.is_superuser)
        self.client.force_login(self.li)
        self.assertEqual(self.client.get('/api/users/').status_code, 200)

    def test_protected_account_cannot_be_demoted_disabled_or_renamed(self):
        other_admin = make_user('other_admin', roles=[SYSTEM_ADMIN], superuser=True)
        self.client.force_login(other_admin)
        for payload in ({'is_superuser': False}, {'is_active': False}, {'username': 'hijack'}):
            response = self.client.patch(f'/api/users/{self.li.id}/', payload, content_type='application/json')
            self.assertEqual(response.status_code, 400, payload)
        response = self.client.post(f'/api/users/{self.li.id}/reset-password/', {'new_password': 'Complex-Pass-9x'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.li.refresh_from_db()
        self.assertTrue(self.li.is_active and self.li.is_superuser and self.li.username == 'li')
        self.assertTrue(AuditLog.objects.filter(action='user_update', result='denied').exists())
        self.assertTrue(AuditLog.objects.filter(action='password_reset', result='denied').exists())

    def test_protected_account_cannot_self_demote_or_rename(self):
        self.client.force_login(self.li)
        for payload in ({'is_superuser': False}, {'username': 'renamed'}):
            response = self.client.patch(f'/api/users/{self.li.id}/', payload, content_type='application/json')
            self.assertEqual(response.status_code, 400, payload)

    def test_li_can_manage_other_accounts_with_audit(self):
        self.client.force_login(self.li)
        response = self.client.patch(f'/api/users/{self.jiao.id}/', {'first_name': '焦'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='user_update', object_id=str(self.jiao.id), result='success').exists())

    def test_me_reports_explicit_business_permissions_only(self):
        self.client.force_login(self.su_only)
        data = self.client.get('/api/auth/me/').json()
        self.assertEqual(data['business_permissions'], [])
        self.assertEqual(data['permissions'], [])
        self.client.force_login(self.jiao)
        data = self.client.get('/api/auth/me/').json()
        self.assertIn('accounting.expense_view_all', data['business_permissions'])
        self.assertNotIn('accounting.expense_change_all', data['business_permissions'])
        self.assertEqual(data['employee_name'], '焦')

    def test_login_success_and_failure_are_audited(self):
        self.client.post('/api/auth/login/', {'username': 'li', 'password': 'wrong'}, content_type='application/json')
        self.client.post('/api/auth/login/', {'username': 'li', 'password': 'pw'}, content_type='application/json')
        self.assertTrue(AuditLog.objects.filter(action='login_failed').exists())
        self.assertTrue(AuditLog.objects.filter(action='login_success', user=self.li).exists())


class AdminGuardTests(TestCase):
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN], superuser=True)
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN], superuser=True)

    def test_phase_a_keeps_staff_access(self):
        with override_settings(PROTECTED_ADMIN_ENFORCEMENT=False):
            self.client.force_login(self.jiao)
            self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_phase_b_limits_admin_to_protected_account(self):
        ProtectedAccount.objects.create(user=self.li)
        with override_settings(PROTECTED_ADMIN_ENFORCEMENT=True):
            self.client.force_login(self.jiao)
            self.assertEqual(self.client.get('/admin/').status_code, 302)
            self.client.force_login(self.li)
            self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_phase_b_with_empty_table_denies_everyone_not_all_superusers(self):
        with override_settings(PROTECTED_ADMIN_ENFORCEMENT=True):
            self.client.force_login(self.li)
            self.assertEqual(self.client.get('/admin/').status_code, 302)
        run('protect_account', username='li', apply=True, yes=True)
        with override_settings(PROTECTED_ADMIN_ENFORCEMENT=True):
            self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_audit_admin_visible_only_to_protected_with_permission(self):
        ProtectedAccount.objects.create(user=self.li)
        self.client.force_login(self.jiao)
        self.assertEqual(self.client.get('/admin/audit/auditlog/').status_code, 403)
        self.client.force_login(self.li)
        self.assertEqual(self.client.get('/admin/audit/auditlog/').status_code, 200)
        self.assertEqual(self.client.get('/admin/audit/auditlog/add/').status_code, 403)


class DevToolsAndDiagnosticsTests(TestCase):
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], superuser=True, employee_name='李')
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], superuser=True, employee_name='焦')

    def _reload_urls(self):
        import api.urls
        import apps.accounting.urls
        import config.urls

        for module in (apps.accounting.urls, api.urls, config.urls):
            importlib.reload(module)
        clear_url_caches()

    def test_dev_tool_routes_absent_when_disabled(self):
        try:
            with override_settings(ENABLE_DEV_TOOLS=False):
                self._reload_urls()
                self.client.force_login(self.li)
                for url in ('/api/case-checklist-demo/seed/', '/api/accounting/zei-pdf-position-debug/templates/',
                            '/api/accounting/visa-form-fields/', '/api/accounting/visa-position-debug/config/',
                            '/api/accounting/tax-renewal-pdf-diagnostics/numbered_sample/',
                            '/api/accounting/tax-renewal-pdf-diagnostics/'):
                    response = self.client.post(url) if 'seed' in url or 'numbered' in url else self.client.get(url)
                    self.assertEqual(response.status_code, 404, url)
                self.assertEqual(self.client.post('/api/checklist-item-presets/seed-standard/').status_code, 404)
                self.assertEqual(self.client.post('/api/residence-status-masters/seed-standard/').status_code, 404)
                # 本番で残るのは health / readiness だけ（業務データを返さない・未ログイン可）
                self.client.logout()
                self.assertEqual(self.client.get('/api/health/').json(), {'status': 'ok'})
                self.assertEqual(self.client.get('/api/readiness/').json(), {'status': 'ready'})
        finally:
            self._reload_urls()

    def test_dev_only_diagnostic_requires_superuser_and_explicit_permission(self):
        # 開発環境（ENABLE_DEV_TOOLS=True）でのみ登録。そこでも superuser + use_diagnostics が必要。
        self.client.force_login(self.jiao)
        self.assertEqual(self.client.get('/api/accounting/tax-renewal-pdf-diagnostics/').status_code, 403)
        self.client.force_login(self.li)
        self.assertNotEqual(self.client.get('/api/accounting/tax-renewal-pdf-diagnostics/').status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action='diagnostic_run', user=self.li).exists())


class CommandTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        User = get_user_model()
        self.li = User.objects.create_superuser('zbry6947@gmail.com', '', 'pw', last_name='李')
        self.jiao = User.objects.create_superuser('jiao', '', 'pw', last_name='焦')
        self.zhou = User.objects.create_superuser('zywwind@gmail.com', '', 'pw', last_name='周')
        self.emp_li = Employee.objects.create(name='李')
        self.emp_zhou = Employee.objects.create(name='周')
        Employee.objects.create(name='NAING')

    def tearDown(self):
        safe_rmtree(self.tmp)

    def test_setup_roles_dry_run_then_apply(self):
        Group.objects.all().delete()
        run('setup_access_roles')
        self.assertFalse(Group.objects.exists())
        run('setup_access_roles', apply=True, yes=True)
        self.assertEqual(set(Group.objects.values_list('name', flat=True)),
                         {SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, 'staff'})
        self.assertTrue(AuditLog.objects.filter(action='roles_setup').exists())

    def test_link_user_employee_by_username_and_name(self):
        run('link_user_employee', map=['zbry6947@gmail.com:李', 'zywwind@gmail.com:周'], create_employee=['jiao:焦'])
        self.assertIsNone(Employee.objects.get(name='李').user)
        run('link_user_employee', map=['zbry6947@gmail.com:李', 'zywwind@gmail.com:周'], create_employee=['jiao:焦'],
            apply=True, yes=True)
        self.assertEqual(Employee.objects.get(name='李').user, self.li)
        self.assertEqual(Employee.objects.get(name='周').user, self.zhou)
        self.assertEqual(Employee.objects.get(name='焦').user, self.jiao)
        self.assertIsNone(Employee.objects.get(name='NAING').user)
        self.assertEqual(AuditLog.objects.filter(action='user_employee_link').count(), 3)
        with self.assertRaises(CommandError):
            run('link_user_employee', map=['jiao:李'], apply=True, yes=True)

    def test_assign_roles_and_snapshot_restore(self):
        run('setup_access_roles', apply=True, yes=True)
        snapshot = os.path.join(self.tmp, 'snap.json')
        run('export_access_snapshot', output=snapshot)
        run('assign_business_roles', username='jiao', roles=f'{BUSINESS_ADMIN},{EXPENSE_VIEWER}', apply=True, yes=True)
        self.jiao.is_superuser = False
        self.jiao.is_staff = False
        self.jiao.save()
        out = run('restore_access_snapshot', snapshot, user=['jiao'])
        self.assertIn('is_superuser', out)
        self.jiao.refresh_from_db()
        self.assertFalse(self.jiao.is_superuser)  # dry-run では変わらない
        run('restore_access_snapshot', snapshot, user=['jiao'], apply=True, yes=True)
        self.jiao.refresh_from_db()
        self.assertTrue(self.jiao.is_superuser and self.jiao.is_staff)
        self.assertEqual(list(self.jiao.groups.values_list('name', flat=True)), [])
        self.assertTrue(AuditLog.objects.filter(action='access_snapshot_restore').exists())

    def test_protect_and_rename_protected_account(self):
        run('protect_account', username='zbry6947@gmail.com')
        self.assertFalse(ProtectedAccount.objects.exists())
        run('protect_account', username='zbry6947@gmail.com', apply=True, yes=True)
        self.assertTrue(ProtectedAccount.objects.filter(user=self.li).exists())
        run('rename_protected_account', old='zbry6947@gmail.com', new='li@example.com', apply=True, yes=True)
        self.li.refresh_from_db()
        self.assertEqual(self.li.username, 'li@example.com')
        self.assertTrue(ProtectedAccount.objects.filter(user=self.li).exists())

    def test_backfill_expense_owner_flow(self):
        for i in range(3):
            Expense.objects.create(expense_date=date(2026, 7, 1), category='c', amount=Decimal('100'))
        Expense.objects.create(expense_date=date(2026, 7, 1), category='c', amount=Decimal('1'), owner=self.jiao)
        with self.assertRaises(CommandError):  # Employee 未関連
            run('backfill_expense_owner', username='zbry6947@gmail.com')
        self.emp_li.user = self.li
        self.emp_li.save()
        with self.assertRaises(CommandError):  # 保護アカウントでない
            run('backfill_expense_owner', username='zbry6947@gmail.com')
        ProtectedAccount.objects.create(user=self.li)
        out = run('backfill_expense_owner', username='zbry6947@gmail.com')
        self.assertIn('owner 未設定: 3 件', out)
        self.assertEqual(Expense.objects.filter(owner__isnull=True).count(), 3)
        with self.assertRaises(CommandError):  # expect-count 不一致
            run('backfill_expense_owner', username='zbry6947@gmail.com', apply=True, yes=True, expect_count=2)
        with self.assertRaises(CommandError):  # expect-count 無し
            run('backfill_expense_owner', username='zbry6947@gmail.com', apply=True, yes=True)
        run('backfill_expense_owner', username='zbry6947@gmail.com', apply=True, yes=True, expect_count=3,
            output_dir=self.tmp)
        self.assertEqual(Expense.objects.filter(owner=self.li).count(), 3)
        self.assertEqual(Expense.objects.filter(owner=self.jiao).count(), 1)
        csv_file = next(f for f in os.listdir(self.tmp) if f.startswith('expense_owner_backfill_'))
        run('backfill_expense_owner', rollback=os.path.join(self.tmp, csv_file), apply=True, yes=True)
        self.assertEqual(Expense.objects.filter(owner__isnull=True).count(), 3)
        self.assertEqual(Expense.objects.filter(owner=self.jiao).count(), 1)

    def test_check_access_config(self):
        with override_settings(IS_PRODUCTION=True, DEBUG=False, ENABLE_DEV_TOOLS=False,
                               PROTECTED_ADMIN_ENFORCEMENT=False, LOCALDEV_CHECK_MODE='warn'):
            User = get_user_model()
            User.objects.create_user('localdev', password='pw')
            out = run('check_access_config')  # 段階A：保護アカウント無し・localdev は警告のみ
            self.assertIn('WARNING', out)
            with override_settings(LOCALDEV_CHECK_MODE='enforce'):
                with self.assertRaises(SystemExit):
                    run('check_access_config')
            User.objects.filter(username='localdev').update(is_active=False)
            with override_settings(PROTECTED_ADMIN_ENFORCEMENT=True):
                with self.assertRaises(SystemExit):  # 段階B：保護アカウントが空なら失敗
                    run('check_access_config')
                ProtectedAccount.objects.create(user=self.li)
                with self.assertRaises(SystemExit):  # manage_users 未付与
                    run('check_access_config')
                run('setup_access_roles', apply=True, yes=True)
                self.li.groups.add(Group.objects.get(name=SYSTEM_ADMIN))
                self.assertIn('OK', run('check_access_config'))
            with override_settings(ENABLE_DEV_TOOLS=True):
                with self.assertRaises(SystemExit):
                    run('check_access_config')
