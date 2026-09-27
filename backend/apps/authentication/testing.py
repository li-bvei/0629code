"""テスト用ヘルパー：明示的な業務ロールを持つユーザーを作る（本番データには使わない）。"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.employees.models import Employee

from .roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, SYSTEM_ADMIN, sync_roles

FULL_ACCESS_ROLES = (SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN)


def make_user(username, roles=(), employee_name=None, superuser=False, staff=None, password='pw'):
    sync_roles()
    User = get_user_model()
    if superuser:
        user = User.objects.create_superuser(username=username, password=password, email='')
        if staff is False:
            user.is_staff = False
            user.save(update_fields=['is_staff'])
    else:
        user = User.objects.create_user(username=username, password=password, is_staff=bool(staff))
    for name in roles:
        user.groups.add(Group.objects.get(name=name))
    if employee_name:
        Employee.objects.create(name=employee_name, user=user)
    return user


def grant_full_business_access(user, employee_name=None):
    """既存テストの前提（全データ操作可能な利用者）を明示ロールで再現する。"""
    sync_roles()
    for name in FULL_ACCESS_ROLES:
        user.groups.add(Group.objects.get(name=name))
    if employee_name and not Employee.objects.filter(user=user).exists():
        Employee.objects.create(name=employee_name, user=user)
    return user
