"""資源ごとのアクセス規則（BusinessAccessPolicy の規則表）。

ここと access_policy.py 以外で業務権限を判定してはならない。各 ViewSet は
access_resource を宣言するだけで、範囲の絞り込み・オブジェクト判定・作成時の
帰属チェックはすべてここの規則が行う。モデルは循環 import を避けるため関数内で
遅延 import する。

アクション：list / view / create / change / export / download
"""
from django.db.models import BooleanField, Exists, OuterRef, Q, Value
from rest_framework.exceptions import PermissionDenied, ValidationError

from .access_policy import ALLOW, FORBIDDEN, NOT_FOUND

READ_ACTIONS = {'list', 'view', 'detail', 'export', 'download'}

# 顧客・会社の表現レベル
LEVEL_FULL = 'full'          # 担当範囲内、または機微項目閲覧権限あり：全項目
LEVEL_MASKED = 'masked'      # 全件閲覧権限（業務管理者）：証件番号・口座を伏せる
LEVEL_BASIC = 'basic'        # 案件の無い顧客・会社：非機微の基本情報のみ
LEVEL_MINIMAL = 'minimal'    # 範囲外：重複防止用の最小識別情報のみ（一覧・検索）

VISIBLE_LEVELS = {LEVEL_FULL, LEVEL_MASKED, LEVEL_BASIC}
DETAIL_LEVELS = {LEVEL_FULL, LEVEL_MASKED}


def _none_q(prefix=''):
    return Q(**{f'{prefix}pk__in': []})


class Rule:
    view_code = None
    write_code = None
    model_label = None  # policy.queryset() で使う 'app_label.ModelName'

    def module_code(self, action):
        if action in READ_ACTIONS:
            return self.view_code
        return self.write_code or self.view_code

    def module_allowed(self, policy, action):
        code = self.module_code(action)
        return code is None or policy.has(code)

    def scope(self, policy, queryset, action):
        return queryset

    def object_decision(self, policy, obj, action):
        return ALLOW

    def prepare_create(self, policy, data):
        return {}

    def prepare_update(self, policy, instance, data):
        return {}

    def via_permission(self, policy, action, obj=None):
        return self.module_code(action) or ''


class ModuleRule(Rule):
    """モジュール単位の権限のみ（P0 では記録単位の所有者分離を行わない資源）。"""

    def __init__(self, view_code, write_code=None, model_label=None):
        self.view_code = view_code
        self.write_code = write_code
        self.model_label = model_label


class DiagnosticsRule(Rule):
    """保持する診断機能：superuser かつ authentication.use_diagnostics の明示付与。"""

    view_code = 'authentication.use_diagnostics'

    def module_allowed(self, policy, action):
        return bool(getattr(policy.user, 'is_superuser', False)) and policy.has(self.view_code)


# --- 会計：支出（報銷） ---------------------------------------------------------

class ExpenseRule(Rule):
    view_code = 'accounting.use_expense'
    model_label = 'accounting.Expense'
    VIEW_ALL = 'accounting.expense_view_all'
    CHANGE_ALL = 'accounting.expense_change_all'
    EXPORT_ALL = 'accounting.expense_export_all'

    def _all_code(self, action):
        if action == 'export':
            return self.EXPORT_ALL
        if action in ('change', 'create'):
            return self.CHANGE_ALL
        return self.VIEW_ALL

    def scope(self, policy, queryset, action):
        if policy.has(self._all_code(action)):
            return queryset
        return queryset.filter(owner_id=policy.user_id)

    def object_decision(self, policy, obj, action):
        own = obj.owner_id is not None and obj.owner_id == policy.user_id
        visible = own or policy.has(self.VIEW_ALL)
        if not visible:
            return NOT_FOUND
        if action in READ_ACTIONS:
            return ALLOW
        if own or policy.has(self.CHANGE_ALL):
            return ALLOW
        return FORBIDDEN

    def prepare_create(self, policy, data):
        # 所有者は必ずリクエストしたユーザー。フロントから送られた owner は無視する。
        return {'owner': policy.user, 'created_by': policy.user, 'updated_by': policy.user}

    def prepare_update(self, policy, instance, data):
        return {'updated_by': policy.user}

    def via_permission(self, policy, action, obj=None):
        if obj is not None and obj.owner_id == policy.user_id:
            return 'owner'
        return self._all_code(action)

    def sees_others(self, policy, action='view'):
        return policy.has(self._all_code(action))


class ExpenseCategoryRule(ModuleRule):
    def __init__(self):
        super().__init__('accounting.use_expense', 'accounting.manage_expense_category')


# --- 案件 -------------------------------------------------------------------

class CaseRule(Rule):
    view_code = 'cases.use_cases'
    model_label = 'cases.Case'
    VIEW_ALL = 'cases.case_view_all'
    CHANGE_ALL = 'cases.case_change_all'

    def can_view_all(self, policy):
        return policy.has_any(self.VIEW_ALL, self.CHANGE_ALL)

    def assigned_q(self, policy, prefix=''):
        if policy.employee_id is None:
            return _none_q(prefix)
        return Q(**{f'{prefix}responsible_employee_id': policy.employee_id})

    def is_assigned(self, policy, case):
        return (
            case is not None
            and policy.employee_id is not None
            and case.responsible_employee_id == policy.employee_id
        )

    def scope(self, policy, queryset, action):
        if action in READ_ACTIONS and self.can_view_all(policy):
            return queryset
        if action not in READ_ACTIONS and policy.has(self.CHANGE_ALL):
            return queryset
        return queryset.filter(self.assigned_q(policy))

    def object_decision(self, policy, obj, action):
        assigned = self.is_assigned(policy, obj)
        if not (assigned or self.can_view_all(policy)):
            return NOT_FOUND
        if action in READ_ACTIONS:
            return ALLOW
        if assigned or policy.has(self.CHANGE_ALL):
            return ALLOW
        return FORBIDDEN

    def resolve_create_responsible_id(self, policy, responsible_id):
        """新規案件の担当者を決める。未指定なら本人（Employee 関連が無ければエラー）。
        case_change_all が無い利用者は自分以外を担当者にできない。"""
        if responsible_id in (None, ''):
            if policy.employee is None:
                raise ValidationError({'responsible_employee': ['担当者を選択してください。']})
            return policy.employee_id
        responsible_id = int(responsible_id)
        if not policy.has(self.CHANGE_ALL) and responsible_id != policy.employee_id:
            raise PermissionDenied('他の担当者の案件は作成できません。')
        return responsible_id

    def prepare_create(self, policy, data):
        responsible = data.get('responsible_employee')
        self.resolve_create_responsible_id(policy, responsible.pk if responsible else None)
        if responsible is None:
            return {'responsible_employee': policy.employee}
        return {}

    def prepare_update(self, policy, instance, data):
        if 'responsible_employee' in data:
            new = data['responsible_employee']
            new_id = new.pk if new is not None else None
            if new_id != instance.responsible_employee_id and not (
                policy.has(self.CHANGE_ALL) or self.is_assigned(policy, instance)
            ):
                raise PermissionDenied('担当者を変更する権限がありません。')
        return {}

    def via_permission(self, policy, action, obj=None):
        if obj is not None and self.is_assigned(policy, obj):
            return 'assigned'
        return self.VIEW_ALL if action in READ_ACTIONS else self.CHANGE_ALL


CASE_RULE = CaseRule()


class CaseChildRule(Rule):
    """Case にぶら下がる資源（Checklist・Timeline・Task・Reminder・Document）。"""

    view_code = 'cases.use_cases'
    extra_view_all_codes = ()

    def __init__(self, parent_field='case', nullable=False, model_label=None):
        self.parent_field = parent_field
        self.nullable = nullable
        self.model_label = model_label

    def can_view_all(self, policy):
        return CASE_RULE.can_view_all(policy) or policy.has_any(*self.extra_view_all_codes)

    def scope(self, policy, queryset, action):
        if action in READ_ACTIONS and self.can_view_all(policy):
            return queryset
        if action not in READ_ACTIONS and policy.has(CaseRule.CHANGE_ALL):
            return queryset
        return queryset.filter(CASE_RULE.assigned_q(policy, prefix=f'{self.parent_field}__'))

    def parent(self, obj):
        return getattr(obj, self.parent_field, None)

    def object_decision(self, policy, obj, action):
        case = self.parent(obj)
        if case is None:
            if not self.can_view_all(policy):
                return NOT_FOUND
            if action in READ_ACTIONS or policy.has(CaseRule.CHANGE_ALL):
                return ALLOW
            return FORBIDDEN
        if action in READ_ACTIONS and self.can_view_all(policy):
            return ALLOW
        return CASE_RULE.object_decision(policy, case, action)

    def _check_parent_writable(self, policy, case):
        if case is None:
            if self.nullable and policy.has(CaseRule.CHANGE_ALL):
                return
            if self.nullable:
                raise PermissionDenied('案件に紐付かない記録は作成できません。')
            return  # 必須チェックはシリアライザに任せる
        if CASE_RULE.object_decision(policy, case, 'change') != ALLOW:
            raise PermissionDenied('この案件への書き込み権限がありません。')

    def prepare_create(self, policy, data):
        self._check_parent_writable(policy, data.get(self.parent_field))
        return {}

    def prepare_update(self, policy, instance, data):
        if self.parent_field in data and data[self.parent_field] != self.parent(instance):
            self._check_parent_writable(policy, data[self.parent_field])
        return {}


class DocumentRule(CaseChildRule):
    VIEW_ALL = 'documents.document_view_all'
    DOWNLOAD_ALL = 'documents.document_download_all'
    extra_view_all_codes = (VIEW_ALL,)

    def object_decision(self, policy, obj, action):
        if action != 'download':
            return super().object_decision(policy, obj, action)
        visible = super().object_decision(policy, obj, 'view')
        if visible != ALLOW:
            return visible
        # 担当範囲外のダウンロードは機微操作：document_download_all が必要。
        if CASE_RULE.is_assigned(policy, obj.case) or policy.has(self.DOWNLOAD_ALL):
            return ALLOW
        return FORBIDDEN

    def via_permission(self, policy, action, obj=None):
        if obj is not None and CASE_RULE.is_assigned(policy, obj.case):
            return 'assigned'
        if action == 'download':
            return self.DOWNLOAD_ALL
        return self.VIEW_ALL if action in READ_ACTIONS else CaseRule.CHANGE_ALL


# --- 顧客・会社 ---------------------------------------------------------------

class PartyRule(Rule):
    """顧客・会社の共通規則。担当範囲は「本人担当の案件が紐付くか」で判定する。"""

    view_code = 'cases.use_cases'
    VIEW_ALL = 'customers.customer_view_all'
    SENSITIVE = 'customers.view_sensitive_identity'
    case_fk = None  # Case 上の FK 名（customer / company）

    def _case_model(self):
        from apps.cases.models import Case

        return Case

    def annotate(self, policy, queryset):
        Case = self._case_model()
        has_case = Exists(Case.objects.filter(**{self.case_fk: OuterRef('pk')}))
        if policy.employee_id is not None:
            assigned = Exists(Case.objects.filter(
                **{self.case_fk: OuterRef('pk'), 'responsible_employee_id': policy.employee_id}
            ))
        else:
            assigned = Value(False, output_field=BooleanField())
        return queryset.annotate(_access_assigned=assigned, _access_has_case=has_case)

    def _flags(self, policy, obj):
        assigned = getattr(obj, '_access_assigned', None)
        has_case = getattr(obj, '_access_has_case', None)
        if assigned is None or has_case is None:
            Case = self._case_model()
            cases = Case.objects.filter(**{self.case_fk: obj})
            has_case = cases.exists()
            assigned = (
                policy.employee_id is not None
                and cases.filter(responsible_employee_id=policy.employee_id).exists()
            )
        return bool(assigned), bool(has_case)

    def level(self, policy, obj):
        assigned, has_case = self._flags(policy, obj)
        if assigned or policy.has(self.SENSITIVE):
            return LEVEL_FULL
        if policy.has(self.VIEW_ALL):
            return LEVEL_MASKED
        if not has_case:
            return LEVEL_BASIC
        return LEVEL_MINIMAL

    def detail_scope(self, policy, queryset):
        """詳細（全項目または伏せ字付き）を表示できる範囲。期限一覧などの集計に使う。"""
        queryset = self.annotate(policy, queryset)
        if policy.has_any(self.VIEW_ALL, self.SENSITIVE):
            return queryset
        return queryset.filter(_access_assigned=True)

    def scope(self, policy, queryset, action):
        queryset = self.annotate(policy, queryset)
        if action == 'detail':
            return self.detail_scope(policy, queryset)
        if action == 'list':
            return queryset  # 一覧・検索は全件（範囲外は最小識別情報で表現する）
        if action in READ_ACTIONS:
            if policy.has_any(self.VIEW_ALL, self.SENSITIVE):
                return queryset
            return queryset.filter(Q(_access_assigned=True) | Q(_access_has_case=False))
        if policy.has(CaseRule.CHANGE_ALL):
            return queryset
        return queryset.filter(_access_assigned=True)

    def object_decision(self, policy, obj, action):
        level = self.level(policy, obj)
        if level not in VISIBLE_LEVELS:
            return NOT_FOUND
        if action in READ_ACTIONS:
            return ALLOW
        assigned, _ = self._flags(policy, obj)
        if assigned or policy.has(CaseRule.CHANGE_ALL):
            return ALLOW
        return FORBIDDEN

    def via_permission(self, policy, action, obj=None):
        if obj is not None and self._flags(policy, obj)[0]:
            return 'assigned'
        if action in READ_ACTIONS:
            return self.SENSITIVE if policy.has(self.SENSITIVE) else self.VIEW_ALL
        return CaseRule.CHANGE_ALL


class CustomerRule(PartyRule):
    case_fk = 'customer'
    model_label = 'customers.Customer'


class CompanyRule(PartyRule):
    case_fk = 'company'
    model_label = 'companies.Company'


CUSTOMER_RULE = CustomerRule()
COMPANY_RULE = CompanyRule()


class PartyChildRule(Rule):
    """家族（Customer 配下）・会社職員（Company 配下）。親が詳細表示できる範囲だけ見える。"""

    view_code = 'cases.use_cases'

    def __init__(self, parent_rule, parent_field, model_label=None):
        self.parent_rule = parent_rule
        self.parent_field = parent_field
        self.model_label = model_label

    def scope(self, policy, queryset, action):
        if action in READ_ACTIONS and policy.has_any(PartyRule.VIEW_ALL, PartyRule.SENSITIVE):
            return queryset
        if action not in READ_ACTIONS and policy.has(CaseRule.CHANGE_ALL):
            return queryset
        if policy.employee_id is None:
            return queryset.none()
        Case = self.parent_rule._case_model()
        assigned_parent_ids = Case.objects.filter(
            responsible_employee_id=policy.employee_id,
        ).exclude(**{f'{self.parent_rule.case_fk}__isnull': True}).values(self.parent_rule.case_fk)
        return queryset.filter(**{f'{self.parent_field}_id__in': assigned_parent_ids})

    def parent(self, obj):
        return getattr(obj, self.parent_field)

    def parent_level(self, policy, obj):
        return self.parent_rule.level(policy, self.parent(obj))

    def object_decision(self, policy, obj, action):
        if self.parent_level(policy, obj) not in DETAIL_LEVELS:
            return NOT_FOUND
        if action in READ_ACTIONS:
            return ALLOW
        return self.parent_rule.object_decision(policy, self.parent(obj), 'change')

    def _check_parent_writable(self, policy, parent):
        if parent is None:
            return
        if self.parent_rule.object_decision(policy, parent, 'change') != ALLOW:
            raise PermissionDenied('この顧客・会社への書き込み権限がありません。')

    def prepare_create(self, policy, data):
        self._check_parent_writable(policy, data.get(self.parent_field))
        return {}

    def prepare_update(self, policy, instance, data):
        if self.parent_field in data and data[self.parent_field] != self.parent(instance):
            self._check_parent_writable(policy, data[self.parent_field])
        return {}


# --- 規則表 -------------------------------------------------------------------

CASE_SETTINGS_RULE = ModuleRule('cases.use_cases', 'cases.manage_case_settings')

RULES = {
    # 会計
    'expense': ExpenseRule(),
    'expense_category': ExpenseCategoryRule(),
    'income': ModuleRule('accounting.use_income', model_label='accounting.IncomeSource'),
    'vehicle': ModuleRule('accounting.use_vehicle', model_label='accounting.VehicleUsage'),
    'project': ModuleRule('accounting.use_project'),
    'voucher': ModuleRule('accounting.use_voucher'),
    'visa': ModuleRule('accounting.use_visa'),
    'seifu': ModuleRule('accounting.use_seifu'),
    'tax_renewal': ModuleRule('accounting.use_tax_renewal'),
    # 案件
    'case': CASE_RULE,
    'case_checklist_item': CaseChildRule('case'),
    'timeline': CaseChildRule('case'),
    'task': CaseChildRule('case'),
    'reminder': CaseChildRule('case'),
    'document': DocumentRule('case', model_label='documents.Document'),
    'case_settings': CASE_SETTINGS_RULE,
    'dismissed_deadline': ModuleRule('cases.use_cases', model_label='reminders.DismissedDeadline'),
    # 顧客・会社
    'customer': CUSTOMER_RULE,
    'family_member': PartyChildRule(CUSTOMER_RULE, 'customer', model_label='customers.FamilyMember'),
    'company': COMPANY_RULE,
    'company_staff': PartyChildRule(COMPANY_RULE, 'company', model_label='companies.CompanyStaff'),
    # システム
    'diagnostics': DiagnosticsRule(),
}


def get_rule(resource):
    try:
        return RULES[resource]
    except KeyError as exc:
        raise LookupError(f'未登録の access_resource: {resource}') from exc
