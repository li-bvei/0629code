"""DRF への BusinessAccessPolicy の接続（ViewSet Mixin・権限クラス・関数ビュー用デコレータ）。

ViewSet は access_resource を宣言するだけ。範囲・オブジェクト判定・作成時の帰属は
access_rules の規則が決める。ViewSet 側で is_superuser や has_perm を見てはならない。
"""
from functools import wraps

from django.http import Http404
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.routers import APIRootView, DefaultRouter

from .access_policy import ALLOW, NOT_FOUND, BusinessAccessPolicy


def _audit_denied(request, resource, action, obj=None, reason=''):
    from apps.audit.services import record

    record(
        module='access',
        action='access_denied',
        request=request,
        obj=obj,
        object_type='' if obj is not None else resource,
        result='denied',
        reason=reason,
        extra={'resource': resource, 'access_action': action, 'method': request.method},
    )


def default_access_action(view, request):
    name = getattr(view, 'action', None)
    mapping = getattr(view, 'access_action_map', None) or {}
    if name in mapping:
        return mapping[name]
    if name == 'list':
        return 'list'
    if name == 'retrieve':
        return 'view'
    if name == 'create':
        return 'create'
    if name in ('update', 'partial_update', 'destroy'):
        return 'change'
    return 'view' if request.method in SAFE_METHODS else 'change'


def flush_link_events(request, policy, instance=None):
    """受控関連規則のイベントを AuditLog に書く。拒否は即時、許可は保存成功後に呼ぶ。"""
    from apps.audit.services import record

    events, policy.link_events = policy.link_events, []
    for event in events:
        denied = event['action'].endswith('_denied')
        record(
            module='access', action=event['action'], request=request, obj=event['obj'],
            result='denied' if denied else 'success', via_permission=event.get('via_permission', ''),
            extra={
                'field': event.get('field', ''),
                'target': f'{instance._meta.label_lower}:{instance.pk}' if instance is not None else '',
            },
        )


class BusinessAccessPermission(BasePermission):
    """モジュール権限（has_permission）とオブジェクト判定（has_object_permission）。"""

    message = 'この操作を行う権限がありません。'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        resource = getattr(view, 'access_resource', None)
        if resource is None:
            return False
        action = view.get_access_action()
        policy = BusinessAccessPolicy.for_request(request)
        if not policy.module_allowed(resource, action):
            _audit_denied(request, resource, action, reason='module')
            return False
        return True

    def has_object_permission(self, request, view, obj):
        resource = view.access_resource
        action = view.get_access_action()
        decision = BusinessAccessPolicy.for_request(request).decide(resource, obj, action)
        if decision == ALLOW:
            return True
        if decision == NOT_FOUND:
            raise Http404
        _audit_denied(request, resource, action, obj=obj, reason='object')
        return False


class BusinessAccessMixin:
    """APIView / ViewSet 共通：access_resource と権限クラスを与える。"""

    access_resource = None
    access_action_map = {}
    permission_classes = [BusinessAccessPermission]

    def get_access_action(self):
        return default_access_action(self, self.request)

    @property
    def business_policy(self):
        return BusinessAccessPolicy.for_request(self.request)

    @property
    def access_rule(self):
        return self.business_policy.rule(self.access_resource)


class BusinessScopedViewSetMixin(BusinessAccessMixin):
    """ModelViewSet 用：queryset の範囲限定・作成/更新時の帰属チェックを自動で行う。

    クラス定義では必ず ModelViewSet より前に置くこと（MRO で get_queryset を包むため）。
    """

    def get_scope_action(self):
        # 対象の検索は「見える範囲」で行う（範囲外は 404）。見えるが書けない対象は
        # has_object_permission の判定で 403 になる。出力（export）だけは出力範囲で絞る。
        action = self.get_access_action()
        if action in ('change', 'download', 'create'):
            return 'view'
        return action

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.business_policy.scope(self.access_resource, queryset, self.get_scope_action())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['policy'] = self.business_policy
        return context

    def perform_create(self, serializer):
        policy = self.business_policy
        try:
            extra = self.access_rule.prepare_create(policy, serializer.validated_data)
        except Exception:
            flush_link_events(self.request, policy)
            raise
        instance = serializer.save(**extra)
        flush_link_events(self.request, policy, instance)
        self.after_create(instance)

    def perform_update(self, serializer):
        policy = self.business_policy
        before = serializer.instance
        try:
            extra = self.access_rule.prepare_update(policy, before, serializer.validated_data)
        except Exception:
            flush_link_events(self.request, policy)
            raise
        instance = serializer.save(**extra)
        flush_link_events(self.request, policy, instance)
        self.after_update(instance)

    def after_create(self, instance):
        pass

    def after_update(self, instance):
        pass


def business_api_view(methods, resource, action=None):
    """関数ビュー用：@api_view に BusinessAccessPolicy のモジュール判定を組み合わせる。

    action を省略した場合、安全なメソッドは view、それ以外は change として判定する。
    ビュー本体では request.business_policy を使って範囲を絞ること。
    """

    def decorator(func):
        @wraps(func)
        def inner(request, *args, **kwargs):
            policy = BusinessAccessPolicy.for_request(request)
            if not policy.authenticated:
                raise NotAuthenticated()
            access_action = action or ('view' if request.method in SAFE_METHODS else 'change')
            if not policy.module_allowed(resource, access_action):
                _audit_denied(request, resource, access_action, reason='module')
                raise PermissionDenied()
            request.business_policy = policy
            if resource == 'diagnostics':
                from apps.audit.services import record

                record(module='system', action='diagnostic_run', request=request,
                       via_permission='authentication.use_diagnostics',
                       extra={'view': func.__name__, 'method': request.method})
            return func(request, *args, **kwargs)

        view = api_view(methods)(inner)
        view.access_resource = resource
        view.cls.access_resource = resource
        return view

    return decorator


def exempt_api_view(methods, reason):
    """業務データを扱わない関数ビュー（ログイン等）用。理由の明記を必須とする。"""

    def decorator(func):
        view = api_view(methods)(func)
        view.access_exempt = reason
        view.cls.access_exempt = reason
        return view

    return decorator


class ExemptAPIRootView(APIRootView):
    access_exempt = 'DRF の API ルート一覧（エンドポイント名のみで業務データを返さない）'


class BusinessRouter(DefaultRouter):
    """API ルート一覧に access_exempt を明示した DefaultRouter。"""

    APIRootView = ExemptAPIRootView
