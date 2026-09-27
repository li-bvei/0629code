"""部署前のアクセス制御構成チェック。問題があれば非ゼロで終了する（部署スクリプトで利用）。"""
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.authentication.access_policy import BusinessAccessPolicy
from apps.authentication.models import ProtectedAccount


class Command(BaseCommand):
    help = 'ProtectedAccount・localdev・開発用ツール・受保護ダウンロード設定を検査する。'

    def handle(self, *args, **options):
        errors, warnings = [], []
        production = settings.IS_PRODUCTION

        if production and settings.ENABLE_DEV_TOOLS:
            errors.append('本番で ENABLE_DEV_TOOLS が有効です。')
        if production and settings.DEBUG:
            errors.append('本番で DEBUG が有効です。')
        if production and not settings.PROTECTED_MEDIA_X_ACCEL:
            warnings.append('本番で PROTECTED_MEDIA_X_ACCEL が無効です（FileResponse で送信されます）。')

        protected = list(ProtectedAccount.objects.select_related('user'))
        valid = [
            row for row in protected
            if row.user.is_active and row.user.is_superuser
        ]
        if not valid:
            message = '有効な保護アカウント（active かつ superuser）がありません。protect_account で登録してください。'
            if production and settings.PROTECTED_ADMIN_ENFORCEMENT:
                errors.append(message)
            else:
                warnings.append(message + '（段階A：警告のみ）')
        elif not any(BusinessAccessPolicy(row.user).has('authentication.manage_users') for row in valid):
            message = '保護アカウントに authentication.manage_users が明示付与されていません。'
            (errors if production and settings.PROTECTED_ADMIN_ENFORCEMENT else warnings).append(message)

        User = get_user_model()
        active_localdev = list(User.objects.filter(username__in=settings.LOCALDEV_USERNAMES, is_active=True))
        if production and active_localdev:
            message = f'本番に有効な開発用アカウントがあります: {[u.username for u in active_localdev]}'
            if settings.LOCALDEV_CHECK_MODE == 'enforce':
                errors.append(message)
            else:
                warnings.append(message + '（warn モード：承認後に停止し、enforce へ切り替えてください）')

        for message in warnings:
            self.stdout.write(self.style.WARNING(f'WARNING: {message}'))
        for message in errors:
            self.stdout.write(self.style.ERROR(f'ERROR: {message}'))
        if errors:
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(
            f'OK（APP_ENV={settings.APP_ENV}, PROTECTED_ADMIN_ENFORCEMENT={settings.PROTECTED_ADMIN_ENFORCEMENT}, '
            f'LOCALDEV_CHECK_MODE={settings.LOCALDEV_CHECK_MODE}）'
        ))
