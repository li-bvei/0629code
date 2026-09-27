"""BusinessAccessPolicy：業務データの権限とデータ範囲を判定する唯一の入口。

重要：Django の User.has_perm() は active な superuser に対して無条件に True を返し、
ModelBackend.get_all_permissions() も superuser には全権限を返す。そのため業務判定では
それらを一切使わず、Group と直接付与から得た Permission 行だけを読む。is_superuser は
業務判定に影響しない（Admin・サーバー保守・アカウント管理の前提条件にのみ使う）。
"""
from django.contrib.auth.models import Permission
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

ALLOW = 'allow'
NOT_FOUND = 'not_found'
FORBIDDEN = 'forbidden'


def get_user_employee(user):
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.employee
    except ObjectDoesNotExist:
        return None


def is_protected_account(user):
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    from .models import ProtectedAccount

    return ProtectedAccount.objects.filter(user_id=user.pk).exists()


class BusinessAccessPolicy:
    def __init__(self, user):
        self.user = user
        self.authenticated = bool(
            user is not None
            and getattr(user, 'is_authenticated', False)
            and getattr(user, 'is_active', False)
        )
        self.employee = get_user_employee(user) if self.authenticated else None
        self.codes = self._load_explicit_codes()

    # --- 権限の読み込み ---------------------------------------------------
    def _load_explicit_codes(self):
        if not self.authenticated:
            return frozenset()
        rows = (
            Permission.objects
            .filter(Q(user=self.user) | Q(group__user=self.user))
            .values_list('content_type__app_label', 'codename')
            .distinct()
        )
        # is_superuser は読まない。明示付与された権限だけ。
        return frozenset(f'{app}.{codename}' for app, codename in rows)

    @classmethod
    def for_request(cls, request):
        """同一リクエスト内では1回だけ権限を読み込む。"""
        raw = getattr(request, '_request', request)
        user = getattr(request, 'user', None)
        cached = getattr(raw, '_business_access_policy', None)
        if cached is not None and cached.user is user:
            return cached
        policy = cls(user)
        try:
            raw._business_access_policy = policy
        except AttributeError:
            pass
        return policy

    @property
    def employee_id(self):
        return self.employee.pk if self.employee is not None else None

    @property
    def user_id(self):
        return self.user.pk if self.authenticated else None

    def has(self, code):
        return code in self.codes

    def has_any(self, *codes):
        return any(code in self.codes for code in codes)

    # --- 規則への委譲 -----------------------------------------------------
    def rule(self, resource):
        from .access_rules import get_rule

        return get_rule(resource)

    def module_allowed(self, resource, action='view'):
        if not self.authenticated:
            return False
        return self.rule(resource).module_allowed(self, action)

    def scope(self, resource, queryset, action='view'):
        if not self.authenticated:
            return queryset.none()
        rule = self.rule(resource)
        if not rule.module_allowed(self, action):
            return queryset.none()
        return rule.scope(self, queryset, action)

    def queryset(self, resource, action='list'):
        """規則に登録されたモデルの全件 queryset を、この利用者の範囲に絞って返す。

        ビュー・Dashboard・集計・図表・出力は受控モデルを直接 .objects で読まず、必ずこれを使う。
        """
        from django.apps import apps

        rule = self.rule(resource)
        if not rule.model_label:
            raise LookupError(f'{resource} には model_label が未設定です。')
        model = apps.get_model(rule.model_label)
        return self.scope(resource, model._default_manager.all(), action)

    def decide(self, resource, obj, action='view'):
        if not self.authenticated:
            return NOT_FOUND
        return self.rule(resource).object_decision(self, obj, action)

    def via(self, resource, action='view', obj=None):
        return self.rule(resource).via_permission(self, action, obj)

    def sorted_codes(self):
        return sorted(self.codes)
