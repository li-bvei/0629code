"""BusinessAccessPolicy の防漏：全 API が access_resource/access_exempt を宣言しているか、
業務ビューが has_perm 等や受控モデルの直接参照で策略を迂回していないか。"""
import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver

from apps.authentication.access_policy import BusinessAccessPolicy
from apps.authentication.testing import make_user

BACKEND = Path(settings.BASE_DIR)

# 業務ビューとして走査するファイル。
VIEW_FILES = [
    'api/views.py',
    'api/workbench.py',
    'api/health.py',
    'apps/accounting/views.py',
    'apps/accounting/visa_import_views.py',
    'apps/accounting/seifu_notice_pdf.py',
    'apps/accounting/visa_form_fields.py',
    'apps/accounting/visa_position_debug.py',
    'apps/accounting/zei_pdf_diagnostics.py',
    'apps/accounting/zei_pdf_position_debug.py',
    'apps/cases/views.py',
    'apps/companies/views.py',
    'apps/customers/views.py',
    'apps/documents/views.py',
    'apps/employees/views.py',
    'apps/reminders/views.py',
    'apps/tasks/views.py',
    'apps/timelines/views.py',
]

# 受控モデル：ビューでは policy.queryset()/scope() を通す。直接参照が必要な行（権限確認済みの
# 書き込み・一意性確認・ID計算など）は同じ行に「# access-reviewed: 理由」を書く。
# ViewSet の class 属性 `queryset = Model.objects...` は Mixin が必ず範囲を掛けるため許可。
CONTROLLED_MODELS = {
    'Expense', 'Case', 'CaseChecklistItem', 'Timeline', 'Task', 'Reminder', 'Document',
    'Customer', 'FamilyMember', 'Company', 'CompanyStaff', 'IncomeSource', 'VehicleUsage',
}
FORBIDDEN_CALLS = {'has_perm', 'has_perms', 'get_all_permissions', 'get_group_permissions', 'get_user_permissions'}


def iter_patterns(patterns, prefix=''):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from iter_patterns(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            yield prefix + str(pattern.pattern), pattern.callback


class CoverageTests(SimpleTestCase):
    def test_every_api_endpoint_declares_access(self):
        missing = []
        for route, callback in iter_patterns(get_resolver().url_patterns):
            if not route.startswith('api/'):
                continue  # Django Admin 等は is_staff/ProtectedAccount で制御
            cls = getattr(callback, 'cls', None)
            declared = (
                getattr(callback, 'access_resource', None) or getattr(callback, 'access_exempt', None)
                or getattr(cls, 'access_resource', None) or getattr(cls, 'access_exempt', None)
            )
            if not declared:
                missing.append(route)
        self.assertEqual(missing, [], 'access_resource / access_exempt が未宣言の API')

    def test_declared_resources_exist_in_rule_table(self):
        from apps.authentication.access_rules import RULES

        unknown = set()
        for route, callback in iter_patterns(get_resolver().url_patterns):
            cls = getattr(callback, 'cls', None)
            resource = getattr(callback, 'access_resource', None) or getattr(cls, 'access_resource', None)
            if resource and resource not in RULES:
                unknown.add((route, resource))
        self.assertEqual(unknown, set())


class StaticConstraintTests(SimpleTestCase):
    def _violations(self, relpath):
        source = (BACKEND / relpath).read_text(encoding='utf-8')
        lines = source.split('\n')
        tree = ast.parse(source)
        allowed_class_attr_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id == 'queryset' for t in stmt.targets
                    ):
                        allowed_class_attr_lines.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
        problems = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_CALLS:
                problems.append(f'{relpath}:{node.lineno} {node.attr}')
            if isinstance(node, ast.Name) and node.id == 'DjangoModelPermissions':
                problems.append(f'{relpath}:{node.lineno} DjangoModelPermissions')
            if (
                isinstance(node, ast.Attribute)
                and node.attr in ('objects', '_default_manager')
                and isinstance(node.value, ast.Name)
                and node.value.id in CONTROLLED_MODELS
                and node.lineno not in allowed_class_attr_lines
                and 'access-reviewed' not in lines[node.lineno - 1]
            ):
                problems.append(f'{relpath}:{node.lineno} {node.value.id}.{node.attr}')
        return problems

    def test_business_views_do_not_bypass_policy(self):
        problems = []
        for relpath in VIEW_FILES:
            problems.extend(self._violations(relpath))
        self.assertEqual(problems, [])

    def test_policy_never_reads_is_superuser(self):
        source = (BACKEND / 'apps/authentication/access_policy.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        reads = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == 'is_superuser']
        self.assertEqual(reads, [])


class SuperuserIsNotBusinessAccessTests(TestCase):
    def test_superuser_without_groups_has_no_business_codes(self):
        su = make_user('su_only', superuser=True)
        self.assertTrue(su.has_perm('accounting.expense_view_all'))  # Django 既定の自動許可（使ってはならない理由）
        policy = BusinessAccessPolicy(su)
        self.assertEqual(policy.codes, frozenset())
        self.assertFalse(policy.module_allowed('expense'))
        self.assertFalse(policy.module_allowed('case'))

    def test_inactive_user_has_no_codes(self):
        from apps.authentication.roles import SYSTEM_ADMIN

        user = make_user('inactive', roles=[SYSTEM_ADMIN])
        user.is_active = False
        user.save()
        self.assertEqual(BusinessAccessPolicy(user).codes, frozenset())
