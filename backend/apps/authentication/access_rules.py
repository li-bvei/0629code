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


# --- 会計：顧客・会社・案件への任意関連（P2） -----------------------------------------

def check_accounting_links(policy, data, instance=None):
    """会計記録（支出・収入）の顧客・会社・案件への関連付けを検査し、補完値を返す。

    - 案件：その案件を「変更」できること（案件の Timeline に記録を残すため）。
    - 顧客・会社：利用者が見られる範囲（最小識別情報のみの対象は不可）。
    - 案件だけ指定された場合は、案件の顧客・会社を補完する。
    会計記録そのものの所有者分離（owner）は各規則が別途行う。
    """
    extra = {}

    def changed(field):
        if field not in data:
            return False
        obj = data[field]
        if instance is None:
            return obj is not None
        return (obj.pk if obj is not None else None) != getattr(instance, f'{field}_id')

    if changed('case'):
        case = data['case']
        if case is not None and CASE_RULE.object_decision(policy, case, 'change') != ALLOW:
            raise PermissionDenied('この案件に会計記録を関連付ける権限がありません。')
        if case is not None:
            if data.get('customer') is None and not (instance and instance.customer_id):
                extra['customer'] = case.customer
            if data.get('company') is None and not (instance and instance.company_id) and case.company_id:
                extra['company'] = case.company
    for field, rule, label in (('customer', CUSTOMER_RULE_REF, '顧客'), ('company', COMPANY_RULE_REF, '会社')):
        if changed(field) and data[field] is not None:
            if rule().level(policy, data[field]) not in VISIBLE_LEVELS:
                raise PermissionDenied(f'この{label}に会計記録を関連付ける権限がありません。')
    return extra


class IncomeRule(Rule):
    """収入（モジュール権限のみ。P0 では記録単位の所有者分離なし）＋任意関連の検査。"""

    view_code = 'accounting.use_income'
    model_label = 'accounting.IncomeSource'

    def prepare_create(self, policy, data):
        return check_accounting_links(policy, data)

    def prepare_update(self, policy, instance, data):
        return check_accounting_links(policy, data, instance)


# --- 帳票：見積書・契約書・請求書・領収書（P2-C11） ------------------------------------

class BusinessDocumentRule(ModuleRule):
    """帳票はモジュール権限のみ（帳票ごとに別の権限）。関連付けと元帳票の参照を検査する。

    - 顧客・会社・案件への関連付けは会計記録と同じ規則（案件は「変更」できること）。
    - 元の見積書・契約書・請求書を指定する場合は、その帳票の閲覧権限も必要。
    """

    SOURCE_RESOURCES = {'source_estimate': 'estimate', 'source_contract': 'contract', 'source_invoice': 'voucher'}

    def _check_sources(self, policy, data, instance=None):
        for field, resource in self.SOURCE_RESOURCES.items():
            obj = data.get(field)
            if obj is None or (instance is not None and getattr(instance, f'{field}_id', None) == obj.pk):
                continue
            if not policy.module_allowed(resource, 'view'):
                raise PermissionDenied('元の帳票を参照する権限がありません。')

    def prepare_create(self, policy, data):
        self._check_sources(policy, data)
        return {**check_accounting_links(policy, data), 'created_by': policy.user, 'updated_by': policy.user}

    def prepare_update(self, policy, instance, data):
        self._check_sources(policy, data, instance)
        return {**check_accounting_links(policy, data, instance), 'updated_by': policy.user}


class AnyBusinessDocumentRule(ModuleRule):
    """帳票明細の定型項目・帳票の関連要約：いずれかの帳票を使える人は読める。変更は請求書・領収書の権限者。"""

    READ_CODES = ('accounting.use_voucher', 'accounting.use_estimate', 'accounting.use_contract')

    def module_allowed(self, policy, action):
        if action in READ_ACTIONS:
            return any(policy.has(code) for code in self.READ_CODES)
        return policy.has('accounting.use_voucher')


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
        extra = check_accounting_links(policy, data)
        return {**extra, 'owner': policy.user, 'created_by': policy.user, 'updated_by': policy.user}

    def prepare_update(self, policy, instance, data):
        extra = check_accounting_links(policy, data, instance)
        return {**extra, 'updated_by': policy.user}

    def via_permission(self, policy, action, obj=None):
        if obj is not None and obj.owner_id == policy.user_id:
            return 'owner'
        # 全件権限が無い場合の一覧・出力は本人分に限られるため、監査には「owner」と記録する
        # （持っていない expense_export_all 等を根拠として残さない）
        if not policy.has(self._all_code(action)):
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

    def check_party_links(self, policy, data, instance=None):
        """案件に紐付ける顧客・会社は受控関連規則に従う（任意 ID で範囲を広げさせない）。"""
        for field, rule in (('customer', CUSTOMER_RULE_REF()), ('company', COMPANY_RULE_REF())):
            if field not in data:
                continue
            obj = data[field]
            if obj is None or (instance is not None and getattr(instance, f'{field}_id') == obj.pk):
                continue
            rule.check_link(policy, obj, via=f'case.{field}')

    def prepare_create(self, policy, data):
        responsible = data.get('responsible_employee')
        self.resolve_create_responsible_id(policy, responsible.pk if responsible else None)
        self.check_party_links(policy, data)
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
        self.check_party_links(policy, data, instance)
        return {}

    def via_permission(self, policy, action, obj=None):
        if obj is not None and self.is_assigned(policy, obj):
            return 'assigned'
        return self.VIEW_ALL if action in READ_ACTIONS else self.CHANGE_ALL


CASE_RULE = CaseRule()


def _is_archived_case(case):
    return getattr(case, 'registration_status', None) == 'archived'


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
        if case is not None and action not in READ_ACTIONS and _is_archived_case(case):
            return FORBIDDEN  # アーカイブ済み案件の子資源は変更できない（復元が必要）
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
        if _is_archived_case(case):
            raise PermissionDenied('アーカイブ済みの案件には追加・変更できません。先に復元してください。')

    def prepare_create(self, policy, data):
        self._check_parent_writable(policy, data.get(self.parent_field))
        return {}

    def prepare_update(self, policy, instance, data):
        if self.parent_field in data and data[self.parent_field] != self.parent(instance):
            self._check_parent_writable(policy, data[self.parent_field])
        return {}


class TaskRule(CaseChildRule):
    """案件タスク＋毎日の計画の項目（P3）。

    - 計画の項目（work_date あり）：本人（responsible_employee）だけが変更できる。全件閲覧権限
      （case_view_all／case_change_all）を持つ人は閲覧だけ（変更は 403）。それ以外の人には見えない（404）。
      案件を関連付けるときは、その案件の変更権限が必要（従来の案件タスクと同じ規則）。
    - 従来の案件タスク（work_date なし）：これまでどおり CaseChildRule（親の案件の権限）に従う。
    """

    OWN_ONLY_MESSAGE = '他の人の計画は変更できません。'

    @staticmethod
    def _own_q(policy):
        if policy.employee_id is None:
            return _none_q()
        return Q(responsible_employee_id=policy.employee_id)

    @staticmethod
    def _is_own(policy, obj):
        return policy.employee_id is not None and obj.responsible_employee_id == policy.employee_id

    def scope(self, policy, queryset, action):
        plan = Q(work_date__isnull=False)
        if action in READ_ACTIONS:
            if self.can_view_all(policy):
                return queryset
            legacy = CASE_RULE.assigned_q(policy, prefix='case__')
        else:
            legacy = Q() if policy.has(CaseRule.CHANGE_ALL) else CASE_RULE.assigned_q(policy, prefix='case__')
        return queryset.filter((~plan & legacy) | (plan & self._own_q(policy)))

    def object_decision(self, policy, obj, action):
        if obj.work_date is None:
            return super().object_decision(policy, obj, action)
        own = self._is_own(policy, obj)
        if not (own or self.can_view_all(policy)):
            return NOT_FOUND
        if action in READ_ACTIONS or own:
            return ALLOW
        return FORBIDDEN

    def prepare_create(self, policy, data):
        if data.get('work_date') is None:
            return super().prepare_create(policy, data)
        if policy.employee_id is None:
            raise PermissionDenied('担当者に関連付いていないアカウントは計画を作成できません。管理者に確認してください。')
        if data.get('case') is not None:
            self._check_parent_writable(policy, data['case'])
        from apps.employees.models import Employee

        # 計画は必ず本人のもの（画面から担当者を指定しても使わない）
        return {'responsible_employee': Employee.objects.get(pk=policy.employee_id), 'created_by': policy.user}

    def prepare_update(self, policy, instance, data):
        if instance.work_date is None:
            if data.get('work_date') is not None:
                raise ValidationError({'work_date': ['案件タスクを計画の項目に変えることはできません。']})
            return super().prepare_update(policy, instance, data)
        if 'work_date' in data and data['work_date'] is None:
            raise ValidationError({'work_date': ['計画の項目には作業日が必要です。']})
        if 'responsible_employee' in data and getattr(data['responsible_employee'], 'pk', None) != instance.responsible_employee_id:
            raise ValidationError({'responsible_employee': ['計画の担当者は変更できません。']})
        if 'case' in data and data['case'] is not None and data['case'].pk != instance.case_id:
            self._check_parent_writable(policy, data['case'])
        return {}

    def via_permission(self, policy, action, obj=None):
        if obj is not None and obj.work_date is not None:
            return 'own' if self._is_own(policy, obj) else CaseRule.VIEW_ALL
        return super().via_permission(policy, action, obj)


class DailyReportRule(Rule):
    """業務報告（P3）：本人だけが作成・編集。全件閲覧権限を持つ人は閲覧だけ。"""

    view_code = 'cases.use_cases'
    model_label = 'tasks.DailyWorkReport'

    def scope(self, policy, queryset, action):
        if action in READ_ACTIONS and CASE_RULE.can_view_all(policy):
            return queryset
        if policy.employee_id is None:
            return queryset.none()
        return queryset.filter(employee_id=policy.employee_id)

    def object_decision(self, policy, obj, action):
        own = policy.employee_id is not None and obj.employee_id == policy.employee_id
        if own:
            return ALLOW
        if CASE_RULE.can_view_all(policy):
            return ALLOW if action in READ_ACTIONS else FORBIDDEN
        return NOT_FOUND

    def via_permission(self, policy, action, obj=None):
        if obj is not None and policy.employee_id is not None and obj.employee_id == policy.employee_id:
            return 'own'
        return CaseRule.VIEW_ALL


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

    def prepare_create(self, policy, data):
        super().prepare_create(policy, data)
        # 登録者は後端が設定する（フロントからの指定は受け付けない）。
        return {'uploaded_by': policy.user}

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

    LINK_ALL = None  # 他担当の進行中案件がある対象を関連付けるための明示権限
    LINK_DENIED_MESSAGE = ''

    def _foreign_active_cases(self, policy, target):
        """他の担当者（または未割当）の進行中案件。target は対象（または OuterRef）。"""
        Case = self._case_model()
        qs = Case.objects.filter(
            **{self.case_fk: target}, registration_status=Case.REGISTRATION_STATUS_ACTIVE,
        ).exclude(status__in=[Case.STATUS_COMPLETED, Case.STATUS_WITHDRAWN, Case.STATUS_REJECTED])
        # 未割当（responsible_employee が NULL）の進行中案件も「他担当」として扱う（明示的に判定）。
        if policy.employee_id is not None:
            qs = qs.filter(Q(responsible_employee__isnull=True) | ~Q(responsible_employee_id=policy.employee_id))
        return qs

    def foreign_active_case_exists(self, policy, obj):
        """他の担当者（または未割当）の進行中案件が紐付いているか。"""
        return self._foreign_active_cases(policy, obj).exists()

    def linkable(self, policy, queryset):
        """check_link と同じ条件で、関連付けできる対象だけに絞る（選択候補の一覧用）。

        queryset は scope() を通したもの（_access_assigned 注釈付き）であること。最終判定は保存時の
        check_link が送られた実 ID で行う（候補一覧に依存しない）。
        """
        if self.LINK_ALL and policy.has(self.LINK_ALL):
            return queryset
        foreign = Exists(self._foreign_active_cases(policy, OuterRef('pk')))
        return queryset.annotate(_access_foreign_active=foreign).filter(
            Q(_access_assigned=True) | Q(_access_foreign_active=False),
        )

    def check_link(self, policy, obj, *, via=''):
        """既存の顧客・会社を案件・受付・家族・職員・代表者として関連付けてよいか（受控関連規則）。

        - 本人担当範囲内：可
        - 他担当（未割当を含む）の進行中案件が無い：可（範囲外なら監査用イベントを記録）
        - 他担当の進行中案件がある：LINK_ALL 明示付与者のみ可（cross_scope_link を監査）、それ以外は 403
        フロントの候補一覧に依存せず、送られてきた実 ID で判定する。
        """
        if obj is None:
            return
        assigned, _ = self._flags(policy, obj)
        if assigned:
            return
        if self.foreign_active_case_exists(policy, obj):
            if policy.has(self.LINK_ALL):
                policy.link_events.append({
                    'action': 'cross_scope_link', 'obj': obj, 'via_permission': self.LINK_ALL, 'field': via,
                })
                return
            policy.link_events.append({'action': 'cross_scope_link_denied', 'obj': obj, 'field': via})
            raise PermissionDenied(self.LINK_DENIED_MESSAGE)
        policy.link_events.append({'action': 'party_link_unassigned', 'obj': obj, 'via_permission': '', 'field': via})

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
    LINK_ALL = 'customers.customer_link_all'
    LINK_DENIED_MESSAGE = 'この顧客は他の担当者または未割当の進行中案件に紐付いているため、関連付けできません。管理者に依頼してください。'


class CompanyRule(PartyRule):
    case_fk = 'company'
    model_label = 'companies.Company'
    LINK_ALL = 'customers.company_link_all'
    LINK_DENIED_MESSAGE = 'この会社は他の担当者または未割当の進行中案件に紐付いているため、関連付けできません。管理者に依頼してください。'

    def prepare_create(self, policy, data):
        CUSTOMER_RULE_REF().check_link(policy, data.get('representative_customer'), via='representative_customer')
        return {}

    def prepare_update(self, policy, instance, data):
        new = data.get('representative_customer')
        if 'representative_customer' in data and new is not None and new.pk != instance.representative_customer_id:
            CUSTOMER_RULE_REF().check_link(policy, new, via='representative_customer')
        return {}


def CUSTOMER_RULE_REF():
    return CUSTOMER_RULE


CUSTOMER_RULE = CustomerRule()
COMPANY_RULE = CompanyRule()


def COMPANY_RULE_REF():
    return COMPANY_RULE


class PartyChildRule(Rule):
    """家族（Customer 配下）・会社職員（Company 配下）。親が詳細表示できる範囲だけ見える。"""

    view_code = 'cases.use_cases'

    def __init__(self, parent_rule, parent_field, model_label=None, link_field=None):
        self.parent_rule = parent_rule
        self.parent_field = parent_field
        self.model_label = model_label
        # 家族の family_customer・会社職員の customer（既存顧客の関連付け）
        self.link_field = link_field

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

    def _check_link(self, policy, data, instance=None):
        if not self.link_field or self.link_field not in data:
            return
        obj = data[self.link_field]
        if obj is None or (instance is not None and getattr(instance, f'{self.link_field}_id') == obj.pk):
            return
        CUSTOMER_RULE.check_link(policy, obj, via=f'{self.model_label}.{self.link_field}')

    def prepare_create(self, policy, data):
        self._check_parent_writable(policy, data.get(self.parent_field))
        self._check_link(policy, data)
        return {}

    def _check_person_edit(self, policy, data, instance):
        """家族の画面から関連付いている人物（Customer）を直接修正してよいか。

        その人物を自分で変更できる（本人担当・case_change_all）か、他の担当者（未割当を含む）の進行中案件が
        無い場合だけ許可する。他担当の進行中案件の顧客を、家族の関連を足掛かりに書き換えさせない。
        """
        if not data.get('person') or not self.link_field:
            return
        person = getattr(instance, self.link_field, None)
        if person is None:
            return
        if CUSTOMER_RULE.object_decision(policy, person, 'change') == ALLOW:
            return
        if CUSTOMER_RULE.foreign_active_case_exists(policy, person):
            raise PermissionDenied('この方は他の担当者の進行中案件の顧客のため、ここからは本人の情報を変更できません。担当者または管理者に依頼してください。')

    def prepare_update(self, policy, instance, data):
        if self.parent_field in data and data[self.parent_field] != self.parent(instance):
            self._check_parent_writable(policy, data[self.parent_field])
        self._check_link(policy, data, instance)
        self._check_person_edit(policy, data, instance)
        return {}


# --- 不動産（P3） ---------------------------------------------------------------

class RealEstateRule(Rule):
    """不動産は担当者で分離しない協同台帳。入口と各操作は明示権限で制御する。"""

    USE = 'real_estate.use_real_estate'
    VIEW = 'real_estate.view_real_estate'
    CREATE = 'real_estate.create_real_estate'
    CHANGE = 'real_estate.change_real_estate'
    BULK_CHANGE = 'real_estate.bulk_change_real_estate'
    ARCHIVE = 'real_estate.archive_real_estate'
    RESTORE = 'real_estate.restore_real_estate'
    EXPORT = 'real_estate.export_real_estate'
    model_label = 'real_estate.RealEstateTransaction'
    LEDGER_MANAGE = 'real_estate.manage_legal_ledger'
    LEDGER_CORRECT = 'real_estate.correct_legal_ledger'
    LEDGER_CLOSE_YEAR = 'real_estate.close_legal_ledger_year'
    PROFIT = 'real_estate.manage_profit_distribution'
    IMPORT = 'real_estate.import_real_estate'

    ACTION_CODES = {
        'list': VIEW, 'view': VIEW, 'detail': VIEW, 'download': VIEW,
        'create': CREATE, 'change': CHANGE, 'bulk_change': BULK_CHANGE, 'archive': ARCHIVE, 'restore': RESTORE,
        'export': EXPORT, 'ledger': LEDGER_MANAGE, 'correct': LEDGER_CORRECT,
        'close_year': LEDGER_CLOSE_YEAR,
    }

    def module_allowed(self, policy, action):
        code = self.ACTION_CODES.get(action, self.VIEW if action in READ_ACTIONS else self.CHANGE)
        if action == 'bulk_change' and not policy.has(self.CHANGE):
            return False  # 一括変更は単票編集の権限に加えて、専用の明示権限が必要
        return policy.has(self.USE) and policy.has(code)

    def scope(self, policy, queryset, action):
        return queryset

    def object_decision(self, policy, obj, action):
        return ALLOW if self.module_allowed(policy, action) else FORBIDDEN

    def can_manage_ledger(self, policy):
        return policy.has(self.LEDGER_MANAGE)

    def can_manage_profit(self, policy):
        return policy.has(self.USE) and policy.has(self.PROFIT)

    def _check_links(self, policy, data, instance=None):
        for field, rule, label in (('customer', CUSTOMER_RULE_REF(), 'customer'),
                                   ('management_company', COMPANY_RULE_REF(), 'management_company')):
            if field not in data:
                continue
            obj = data[field]
            if obj is None or (instance is not None and getattr(instance, f'{field}_id') == obj.pk):
                continue
            rule.check_link(policy, obj, via=f'real_estate.{label}')

    def prepare_create(self, policy, data):
        self._check_links(policy, data)
        return {'created_by': policy.user, 'updated_by': policy.user}

    def prepare_update(self, policy, instance, data):
        self._check_links(policy, data, instance)
        return {'updated_by': policy.user}

    def via_permission(self, policy, action, obj=None):
        return self.ACTION_CODES.get(action, self.VIEW if action in READ_ACTIONS else self.CHANGE)


REAL_ESTATE_RULE = RealEstateRule()


class RealEstateChildRule(Rule):
    """不動産取引の子資源。担当者では絞らず、親取引と明示操作権限に従う。"""

    def __init__(self, model_label, parent_field='transaction', extra_code=None):
        self.model_label = model_label
        self.parent_field = parent_field
        self.extra_code = extra_code  # 追加で必要な権限（利益配分など）

    def module_allowed(self, policy, action):
        if self.extra_code and not policy.has(self.extra_code):
            return False
        return REAL_ESTATE_RULE.module_allowed(policy, action)

    def module_code(self, action):
        return self.extra_code or REAL_ESTATE_RULE.ACTION_CODES.get(
            action, RealEstateRule.VIEW if action in READ_ACTIONS else RealEstateRule.CHANGE)

    def scope(self, policy, queryset, action):
        return queryset

    def object_decision(self, policy, obj, action):
        if self.extra_code and not policy.has(self.extra_code):
            return NOT_FOUND
        return REAL_ESTATE_RULE.object_decision(policy, getattr(obj, self.parent_field), action)

    def _check_parent(self, policy, tx):
        if tx is not None and tx.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        if tx is not None and REAL_ESTATE_RULE.object_decision(policy, tx, 'change') != ALLOW:
            raise PermissionDenied('この不動産記録への書き込み権限がありません。')

    def prepare_create(self, policy, data):
        self._check_parent(policy, data.get(self.parent_field))
        return {}

    def prepare_update(self, policy, instance, data):
        if self.parent_field in data and data[self.parent_field] != getattr(instance, self.parent_field):
            self._check_parent(policy, data[self.parent_field])
        return {}


class RealEstatePartyRule(RealEstateChildRule):
    def _links(self, policy, data, instance=None):
        for field, rule in (('customer', CUSTOMER_RULE_REF()), ('company', COMPANY_RULE_REF())):
            obj = data.get(field)
            if obj is None or (instance is not None and getattr(instance, f'{field}_id') == obj.pk):
                continue
            rule.check_link(policy, obj, via=f'real_estate_party.{field}')

    def prepare_create(self, policy, data):
        super().prepare_create(policy, data)
        self._links(policy, data)
        return {}

    def prepare_update(self, policy, instance, data):
        super().prepare_update(policy, instance, data)
        self._links(policy, data, instance)
        return {}


class RealEstateAccountingLinkRule(RealEstateChildRule):
    """会計参照：取引への書き込み権限に加え、参照先の会計モジュール権限が必要。"""

    def _check_accounting(self, policy, data):
        if data.get('income_source') is not None and not policy.module_allowed('income', 'view'):
            raise PermissionDenied('収入を参照する権限がありません。')
        if data.get('voucher') is not None and not policy.module_allowed('voucher', 'view'):
            raise PermissionDenied('請求書・領収書を参照する権限がありません。')

    def prepare_create(self, policy, data):
        super().prepare_create(policy, data)
        self._check_accounting(policy, data)
        return {'created_by': policy.user}


class RealEstateFileRule(RealEstateChildRule):
    def prepare_create(self, policy, data):
        super().prepare_create(policy, data)
        document = data.get('document')
        if document is not None and DOCUMENT_RULE_REF().object_decision(policy, document, 'view') != ALLOW:
            raise PermissionDenied('この案件書類を参照する権限がありません。')
        return {'uploaded_by': policy.user}


class RealEstateLedgerRule(RealEstateChildRule):
    def module_allowed(self, policy, action):
        allowed = REAL_ESTATE_RULE.module_allowed(policy, action)
        if action == 'export':
            return allowed and policy.has(RealEstateRule.LEDGER_MANAGE)
        return allowed


class RealEstateImportRule(Rule):
    model_label = 'real_estate.RealEstateImportRun'

    def module_allowed(self, policy, action):
        return policy.has(RealEstateRule.USE) and policy.has(RealEstateRule.IMPORT)

    def module_code(self, action):
        return RealEstateRule.IMPORT


def DOCUMENT_RULE_REF():
    return RULES['document']


# --- 規則表 -------------------------------------------------------------------

CASE_SETTINGS_RULE = ModuleRule('cases.use_cases', 'cases.manage_case_settings')

RULES = {
    # 会計
    'expense': ExpenseRule(),
    'expense_category': ExpenseCategoryRule(),
    # カテゴリ提案規則：一覧も含めて manage_expense_category の明示権限が必要
    'expense_category_rule': ModuleRule('accounting.manage_expense_category',
                                        model_label='accounting.ExpenseCategorySuggestionRule'),
    'income': IncomeRule(),
    'vehicle': ModuleRule('accounting.use_vehicle', model_label='accounting.VehicleUsage'),
    'project': ModuleRule('accounting.use_project'),
    'voucher': BusinessDocumentRule('accounting.use_voucher', model_label='accounting.AccountingVoucher'),
    'voucher_item_template': AnyBusinessDocumentRule('accounting.use_voucher', model_label='accounting.VoucherItemTemplate'),
    # P4 サービス価格マスタ：閲覧（受付・帳票で選ぶ）と管理は別の明示権限。委託底価は serializer が
    # accounting.view_service_floor_price で項目ごと出し分ける。
    'service_item': ModuleRule('accounting.use_service_item', 'accounting.manage_service_item',
                               model_label='accounting.ServiceItem'),
    'voucher_links': AnyBusinessDocumentRule('accounting.use_voucher'),
    'estimate': BusinessDocumentRule('accounting.use_estimate', model_label='accounting.Estimate'),
    'contract': BusinessDocumentRule('accounting.use_contract', model_label='accounting.Contract'),
    'visa': ModuleRule('accounting.use_visa'),
    'seifu': ModuleRule('accounting.use_seifu'),
    'tax_renewal': ModuleRule('accounting.use_tax_renewal', model_label='accounting.TaxRenewalVoucherRecord'),
    # 案件
    'case': CASE_RULE,
    'case_checklist_item': CaseChildRule('case'),
    'timeline': CaseChildRule('case'),
    'task': TaskRule('case', model_label='tasks.Task'),
    'daily_report': DailyReportRule(),
    'reminder': CaseChildRule('case'),
    'document': DocumentRule('case', model_label='documents.Document'),
    'case_settings': CASE_SETTINGS_RULE,
    'dismissed_deadline': ModuleRule('cases.use_cases', model_label='reminders.DismissedDeadline'),
    # 顧客・会社
    'customer': CUSTOMER_RULE,
    'family_member': PartyChildRule(CUSTOMER_RULE, 'customer', model_label='customers.FamilyMember',
                                    link_field='family_customer'),
    'company': COMPANY_RULE,
    'company_staff': PartyChildRule(COMPANY_RULE, 'company', model_label='companies.CompanyStaff',
                                    link_field='customer'),
    # 不動産（P3）
    'real_estate': REAL_ESTATE_RULE,
    'real_estate_party': RealEstatePartyRule('real_estate.TransactionParty'),
    'real_estate_ledger': RealEstateLedgerRule('real_estate.LegalLedger'),
    'real_estate_file': RealEstateFileRule('real_estate.RealEstateFile'),
    'real_estate_accounting_link': RealEstateAccountingLinkRule('real_estate.RealEstateAccountingLink'),
    'real_estate_profit': RealEstateChildRule('real_estate.InternalProfitDistribution',
                                              extra_code=RealEstateRule.PROFIT),
    # LIST.xlsx 等の dry-run：専用権限者のみ（取引は作らない）
    'real_estate_import': RealEstateImportRule(),
    # 全体検索：利用自体は業務利用者全員（中身は各資源の規則で絞る）
    'global_search': ModuleRule(None),
    # 事務所設定：参照は業務利用者全員、変更は system_admin の明示権限のみ
    'office_settings': ModuleRule(None, 'office.manage_office_settings'),
    # システム
    'diagnostics': DiagnosticsRule(),
}


def get_rule(resource):
    try:
        return RULES[resource]
    except KeyError as exc:
        raise LookupError(f'未登録の access_resource: {resource}') from exc
