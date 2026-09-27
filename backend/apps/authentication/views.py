from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials, get_lockout_message
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import record, safe_changes

from .access_policy import BusinessAccessPolicy, is_protected_account
from .permissions import CanManageUsers
from .serializers import (
    ChangeOwnPasswordSerializer,
    ResetPasswordSerializer,
    SystemUserCreateSerializer,
    SystemUserSerializer,
    SystemUserUpdateSerializer,
)

AUTH_EXEMPT_REASON = '認証エンドポイント（業務データを扱わない）'


def serialize_user(user, request=None):
    policy = BusinessAccessPolicy.for_request(request) if request is not None else BusinessAccessPolicy(user)
    employee = policy.employee
    codes = policy.sorted_codes()
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'is_protected': is_protected_account(user),
        'groups': list(user.groups.values_list('name', flat=True)),
        # 表示制御専用。安全の根拠にはならない（判定は常に後端の BusinessAccessPolicy）。
        'permissions': codes,
        'business_permissions': codes,
        'employee_id': employee.pk if employee else None,
        'employee_name': employee.name if employee else '',
        'dev_tools_enabled': settings.ENABLE_DEV_TOOLS,
    }


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    return Response({'detail': 'CSRF cookie set'})


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username', '')
    password = request.data.get('password', '')

    credentials = get_credentials(username=username, password=password)
    if not AxesProxyHandler.is_allowed(request, credentials):
        record(module='auth', action='login_failed', request=request, result='denied',
               extra={'username': str(username)[:150], 'reason': 'locked'})
        return Response({'detail': get_lockout_message()}, status=status.HTTP_403_FORBIDDEN)

    user = authenticate(request, username=username, password=password)

    if user is None:
        record(module='auth', action='login_failed', request=request, result='denied',
               extra={'username': str(username)[:150]})
        return Response({'detail': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    record(module='auth', action='login_success', request=request, user=user)
    return Response(serialize_user(user, request))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    record(module='auth', action='logout', request=request)
    logout(request)
    return Response({'detail': '已退出登录'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(serialize_user(request.user, request))


for _view in (csrf, login_view, logout_view, me):
    _view.access_exempt = AUTH_EXEMPT_REASON
    _view.cls.access_exempt = AUTH_EXEMPT_REASON


def _user_state(user):
    return {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


class SystemUserViewSet(viewsets.ModelViewSet):
    """账号管理：一覧・新規追加・更新・強制パスワードリセットは
    is_superuser かつ authentication.manage_users の明示付与が必要（保護アカウント規則あり）。
    change-password のみ本人が使えるパスワード変更。"""

    access_exempt = 'アカウント管理（CanManageUsers + 保護アカウント規則で制御）'
    queryset = User.objects.all().order_by('username')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action == 'change_password':
            return [IsAuthenticated()]
        return [CanManageUsers()]

    def get_serializer_class(self):
        if self.action == 'create':
            return SystemUserCreateSerializer
        return SystemUserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        record(module='auth', action='user_create', request=self.request, obj=user,
               changes=safe_changes({}, _user_state(user)))

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        before = _user_state(instance)
        serializer = SystemUserUpdateSerializer(
            instance, data=request.data, partial=True, context={'request': request},
        )
        if not serializer.is_valid():
            record(module='auth', action='user_update', request=request, obj=instance, result='denied',
                   extra={'errors': list(serializer.errors.keys())})
            serializer.is_valid(raise_exception=True)
        serializer.save()
        record(module='auth', action='user_update', request=request, obj=instance,
               changes=safe_changes(before, _user_state(instance)))
        return Response(SystemUserSerializer(instance).data)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        if is_protected_account(user) and user.pk != request.user.pk:
            record(module='auth', action='password_reset', request=request, obj=user, result='denied',
                   reason='protected account')
            raise PermissionDenied('保護アカウントのパスワードは本人以外リセットできません。')
        serializer = ResetPasswordSerializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(module='auth', action='password_reset', request=request, obj=user)
        return Response({'detail': 'パスワードをリセットしました。'})

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        serializer = ChangeOwnPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(module='auth', action='password_change_own', request=request, obj=request.user)
        return Response({'detail': 'パスワードを変更しました。'})
