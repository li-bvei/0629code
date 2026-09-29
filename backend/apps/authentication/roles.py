"""業務ロール（Django Group）と明示的な業務権限の定義。

権限は各モデルの Meta.permissions で宣言し（migration で Permission 行が作られる）、
ここでは Group ごとの割り当てだけを定義する。Group の作成・同期は管理コマンド
setup_access_roles（既定 dry-run）で行う。is_superuser はここでは一切使わない。
"""
from django.contrib.auth.models import Group, Permission
from django.db import transaction

SYSTEM_ADMIN = 'system_admin'
ACCOUNTING_ADMIN = 'accounting_admin'
BUSINESS_ADMIN = 'business_admin'
EXPENSE_VIEWER = 'expense_viewer'
STAFF = 'staff'

ROLE_PERMISSIONS = {
    SYSTEM_ADMIN: [
        'authentication.manage_users',
        'authentication.use_diagnostics',
        'audit.view_auditlog',
        'cases.case_change_all',
        'cases.manage_case_settings',
        'customers.view_sensitive_identity',
        'customers.customer_link_all',
        'customers.company_link_all',
        'documents.document_download_all',
        'real_estate.real_estate_change_all',
        'real_estate.manage_legal_ledger',
        'office.manage_office_settings',
    ],
    ACCOUNTING_ADMIN: [
        'real_estate.manage_profit_distribution',
        'accounting.use_expense',
        'accounting.expense_view_all',
        'accounting.expense_change_all',
        'accounting.expense_export_all',
        'accounting.manage_expense_category',
        'accounting.use_income',
        'accounting.use_vehicle',
        'accounting.use_project',
        'accounting.use_voucher',
        'accounting.use_estimate',
        'accounting.use_contract',
        'accounting.use_visa',
        'accounting.use_tax_renewal',
        'accounting.use_seifu',
    ],
    BUSINESS_ADMIN: [
        'cases.use_cases',
        'cases.case_view_all',
        'customers.customer_view_all',
        'documents.document_view_all',
        'real_estate.use_real_estate',
        'real_estate.real_estate_view_all',
    ],
    EXPENSE_VIEWER: [
        'accounting.use_expense',
        'accounting.expense_view_all',
    ],
    STAFF: [
        'cases.use_cases',
        'accounting.use_expense',
        'real_estate.use_real_estate',
    ],
}

# 業務権限として扱う codename の全集合（BusinessAccessPolicy はこれ以外を見ない）。
BUSINESS_PERMISSION_CODES = frozenset(code for codes in ROLE_PERMISSIONS.values() for code in codes)

# 初期メンバー案（生産での割り当ては D7 として別途承認。username で指定する）。
INITIAL_ROLE_PLAN = {
    'zbry6947@gmail.com': [SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN],
    'jiao': [BUSINESS_ADMIN, EXPENSE_VIEWER],
    'zywwind@gmail.com': [BUSINESS_ADMIN, EXPENSE_VIEWER],
}


def resolve_permission(code):
    app_label, codename = code.split('.', 1)
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def plan_roles():
    """現在の Group 状態と定義との差分を返す（書き込みはしない）。"""
    plan = []
    for name, codes in ROLE_PERMISSIONS.items():
        group = Group.objects.filter(name=name).first()
        current = set()
        if group:
            current = {
                f'{app}.{code}'
                for app, code in group.permissions.values_list('content_type__app_label', 'codename')
            }
        wanted = set(codes)
        plan.append({
            'group': name,
            'exists': group is not None,
            'add': sorted(wanted - current),
            'remove': sorted(current - wanted),
        })
    return plan


@transaction.atomic
def sync_roles():
    """Group を作成し、権限を定義どおりに同期する（冪等）。"""
    for name, codes in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=name)
        group.permissions.set([resolve_permission(code) for code in codes])
    return plan_roles()
