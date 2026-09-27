from django.contrib.auth.models import Group
from django.core.management.base import CommandError

from apps.authentication.management.base import SafeCommand
from apps.authentication.roles import ROLE_PERMISSIONS


class Command(SafeCommand):
    help = '指定ユーザーの業務ロール（Group）を設定する。username で指定。既定 dry-run。'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--username', required=True)
        parser.add_argument('--roles', required=True, help='カンマ区切り。空文字で全業務ロール解除')

    def handle(self, *args, **options):
        user = self.get_user(options['username'])
        wanted = [r.strip() for r in options['roles'].split(',') if r.strip()]
        unknown = [r for r in wanted if r not in ROLE_PERMISSIONS]
        if unknown:
            raise CommandError(f'未定義のロール: {unknown}')
        missing = [r for r in wanted if not Group.objects.filter(name=r).exists()]
        if missing:
            raise CommandError(f'Group が未作成です（先に setup_access_roles --apply）: {missing}')
        current = set(user.groups.filter(name__in=ROLE_PERMISSIONS).values_list('name', flat=True))
        add, remove = sorted(set(wanted) - current), sorted(current - set(wanted))
        self.stdout.write(f'{user.username}（id={user.pk}）現在={sorted(current)} 追加={add} 解除={remove}')
        if not add and not remove:
            self.stdout.write('変更はありません。')
            return
        if not self.confirm(options, 'ロールを変更します。'):
            return
        for name in add:
            user.groups.add(Group.objects.get(name=name))
        for name in remove:
            user.groups.remove(Group.objects.get(name=name))
        self.audit('group_change', obj=user, changes={'groups': {'from': sorted(current), 'to': sorted(wanted)}})
        self.stdout.write(self.style.SUCCESS('変更しました。'))
