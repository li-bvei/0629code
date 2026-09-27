from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from apps.authentication.management.base import SafeCommand
from apps.authentication.models import ProtectedAccount


class Command(SafeCommand):
    help = '保護アカウントの username を変更する（Web からは変更不可）。保護関係は FK で維持される。既定 dry-run。'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--from', dest='old', required=True)
        parser.add_argument('--to', dest='new', required=True)

    def handle(self, *args, **options):
        user = self.get_user(options['old'])
        if not ProtectedAccount.objects.filter(user=user).exists():
            raise CommandError('保護アカウントではありません。通常の改名は画面から行ってください。')
        if get_user_model().objects.filter(username=options['new']).exists():
            raise CommandError('変更後の username は既に使われています。')
        self.stdout.write(f'改名: {user.username} → {options["new"]}（id={user.pk}）')
        self.stdout.write('注意：本番の運用手順書・部署設定に旧 username を記載している場合は合わせて更新してください。')
        if not self.confirm(options, '保護アカウントを改名します。'):
            return
        old = user.username
        user.username = options['new']
        user.save(update_fields=['username'])
        self.audit('protected_account_change', obj=user, changes={'username': {'from': old, 'to': user.username}}, extra={'op': 'rename'})
        self.stdout.write(self.style.SUCCESS('完了しました。'))
