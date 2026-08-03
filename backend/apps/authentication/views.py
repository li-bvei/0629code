from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials, get_lockout_message
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .permissions import IsSuperUser
from .serializers import (
    ChangeOwnPasswordSerializer,
    ResetPasswordSerializer,
    SystemUserCreateSerializer,
    SystemUserSerializer,
)


def serialize_user(user):
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'groups': list(user.groups.values_list('name', flat=True)),
        'permissions': list(user.get_all_permissions()),
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
        return Response({'detail': get_lockout_message()}, status=status.HTTP_403_FORBIDDEN)

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({'detail': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    return Response(serialize_user(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({'detail': '已退出登录'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(serialize_user(request.user))


class SystemUserViewSet(viewsets.ModelViewSet):
    """账号管理：一覧・新規追加・強制パスワードリセットはroot(is_superuser)専用。
    change-password のみ本人が使えるパスワード変更。"""

    queryset = User.objects.all().order_by('username')
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action == 'change_password':
            return [IsAuthenticated()]
        return [IsSuperUser()]

    def get_serializer_class(self):
        if self.action == 'create':
            return SystemUserCreateSerializer
        return SystemUserSerializer

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        allowed_fields = {'is_active'}
        if set(request.data.keys()) - allowed_fields:
            return Response(
                {'detail': 'is_active のみ変更できます。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'is_active' in request.data:
            instance.is_active = bool(request.data['is_active'])
            instance.save(update_fields=['is_active'])
        return Response(SystemUserSerializer(instance).data)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        serializer = ResetPasswordSerializer(instance=user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'パスワードをリセットしました。'})

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        serializer = ChangeOwnPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'パスワードを変更しました。'})
