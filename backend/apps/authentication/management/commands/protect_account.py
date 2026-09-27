from django.core.management.base import CommandError

from apps.authentication.management.base import SafeCommand
from apps.authentication.models import ProtectedAccount


class Command(SafeCommand):
    help = (
        '保護アカウント（唯一のシステム管理者）を登録・解除する。username で指定。'
        'Web からは変更できないため、復旧時もこのコマンドを使う。既定 dry-run。'
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--username', required=False)
        parser.add_argument('--remove', action='store_true', help='登録を解除する')
        parser.add_argument('--reason', default='唯一のシステム管理者')
        parser.add_argument('--list', action='store_true')

    def handle(self, *args, **options):
        if options['list'] or not options['username']:
            rows = ProtectedAccount.objects.select_related('user')
            if not rows:
                self.stdout.write(self.style.WARNING('保護アカウントは未登録です。'))
            for row in rows:
                u = row.user
                self.stdout.write(f'{u.username}（id={u.pk}） active={u.is_active} superuser={u.is_superuser} reason={row.reason}')
            return
        user = self.get_user(options['username'])
        existing = ProtectedAccount.objects.filter(user=user).first()
        if options['remove']:
            if existing is None:
                raise CommandError('このユーザーは保護アカウントではありません。')
            if ProtectedAccount.objects.count() == 1:
                self.stdout.write(self.style.WARNING('最後の保護アカウントを解除します。段階B有効時は Admin に誰も入れなくなります。'))
            self.stdout.write(f'解除: {user.username}（id={user.pk}）')
            if not self.confirm(options, '保護アカウントを解除します。'):
                return
            existing.delete()
            self.audit('protected_account_change', user=None, obj=user, extra={'op': 'remove'})
        else:
            if existing is not None:
                self.stdout.write('既に保護アカウントです。変更はありません。')
                return
            if not (user.is_active and user.is_superuser):
                raise CommandError('保護アカウントは is_active かつ is_superuser である必要があります。')
            self.stdout.write(f'登録: {user.username}（id={user.pk}、氏名={user.last_name}{user.first_name}）')
            if not self.confirm(options, '保護アカウントとして登録します。'):
                return
            ProtectedAccount.objects.create(user=user, reason=options['reason'])
            self.audit('protected_account_change', user=None, obj=user, extra={'op': 'add'})
        self.stdout.write(self.style.SUCCESS('完了しました。'))
