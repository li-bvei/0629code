"""管理コマンド共通：既定 dry-run、--apply 時の確認、監査ログ記録。"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class SafeCommand(BaseCommand):
    """書き込み系コマンドの基底。--apply が無ければ何も書かない。"""

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='実際に書き込む（省略時は dry-run）')
        parser.add_argument('--yes', action='store_true', help='--apply 時の対話確認を省略する（自動テスト用）')

    def confirm(self, options, message):
        if not options.get('apply'):
            self.stdout.write(self.style.WARNING('dry-run：書き込みは行いません（--apply で実行）。'))
            return False
        if options.get('yes'):
            return True
        answer = input(f'{message} 実行するには yes と入力してください: ')
        if answer.strip() != 'yes':
            raise CommandError('確認が得られなかったため中止しました。')
        return True

    def get_user(self, username):
        User = get_user_model()
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'ユーザーが見つかりません: {username}') from exc

    def audit(self, action, *, user=None, obj=None, changes=None, extra=None, reason=''):
        from apps.audit.services import record

        record(
            module='command',
            action=action,
            user=user,
            obj=obj,
            changes=changes,
            extra={**(extra or {}), 'command': self.__module__.rsplit('.', 1)[-1]},
            reason=reason,
        )
