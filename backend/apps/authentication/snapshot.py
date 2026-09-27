"""アカウント権限スナップショット（エクスポート／差分／復元）。パスワードは扱わない。"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone

from .models import ProtectedAccount

FLAG_FIELDS = ('is_active', 'is_staff', 'is_superuser')


def _perm_codes(qs):
    return sorted(f'{a}.{c}' for a, c in qs.values_list('content_type__app_label', 'codename'))


def build_snapshot():
    User = get_user_model()
    protected = set(ProtectedAccount.objects.values_list('user__username', flat=True))
    users = []
    for u in User.objects.order_by('username'):
        employee = getattr(u, 'employee', None) if hasattr(u, 'employee') else None
        users.append({
            'username': u.username,
            **{f: getattr(u, f) for f in FLAG_FIELDS},
            'groups': sorted(u.groups.values_list('name', flat=True)),
            'user_permissions': _perm_codes(u.user_permissions.all()),
            'employee': employee.name if employee else None,
            'protected': u.username in protected,
        })
    return {'created_at': timezone.now().isoformat(), 'version': 1, 'users': users}


def diff_snapshot(snapshot, usernames=None):
    """スナップショットと現在の差分（username ごと）。"""
    current = {row['username']: row for row in build_snapshot()['users']}
    diffs = []
    for row in snapshot['users']:
        if usernames and row['username'] not in usernames:
            continue
        now = current.get(row['username'])
        if now is None:
            diffs.append({'username': row['username'], 'missing': True})
            continue
        changes = {}
        for key in (*FLAG_FIELDS, 'groups', 'user_permissions'):
            if row[key] != now[key]:
                changes[key] = {'current': now[key], 'snapshot': row[key]}
        if changes:
            diffs.append({'username': row['username'], 'changes': changes})
    return diffs


@transaction.atomic
def restore_snapshot(snapshot, usernames=None):
    User = get_user_model()
    restored = []
    for diff in diff_snapshot(snapshot, usernames):
        if diff.get('missing'):
            continue
        row = next(r for r in snapshot['users'] if r['username'] == diff['username'])
        user = User.objects.get(username=row['username'])
        for flag in FLAG_FIELDS:
            setattr(user, flag, row[flag])
        user.save(update_fields=list(FLAG_FIELDS))
        user.groups.set(Group.objects.filter(name__in=row['groups']))
        perms = []
        for code in row['user_permissions']:
            app, codename = code.split('.', 1)
            perms.extend(Permission.objects.filter(content_type__app_label=app, codename=codename))
        user.user_permissions.set(perms)
        restored.append(diff)
    return restored
