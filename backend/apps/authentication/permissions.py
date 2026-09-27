from rest_framework.permissions import BasePermission

from .access_policy import BusinessAccessPolicy


class IsSuperUser(BasePermission):
    """システム管理（Admin 等）の前提条件。業務データの判定には使わない。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class CanManageUsers(BasePermission):
    """アカウント管理：is_superuser かつ authentication.manage_users の明示付与が必要。"""

    message = 'アカウント管理の権限がありません。'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_superuser):
            return False
        return BusinessAccessPolicy.for_request(request).has('authentication.manage_users')
