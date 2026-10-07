from django.contrib.auth.models import Permission
from django.core.management.base import CommandError

from apps.authentication.management.base import SafeCommand
from apps.authentication.roles import BUSINESS_PERMISSION_CODES

# 個別付与を許す業務権限（ロールに入れず、特定の人にだけ付けることを想定したもの）
INDIVIDUAL_GRANTABLE = {'customers.reveal_my_number'}


class Command(SafeCommand):
    help = ('業務権限を指定ユーザーに個別付与・取り消しする（例：customers.reveal_my_number）。'
            '既定 dry-run。is_superuser は使わず、Permission 行を直接付与する。監査ログに残す。')

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--username', required=True)
        parser.add_argument('--permission', required=True, help='app_label.codename')
        parser.add_argument('--revoke', action='store_true', help='付与ではなく取り消す')

    def handle(self, *args, **options):
        code = options['permission'].strip()
        if code not in INDIVIDUAL_GRANTABLE or code not in BUSINESS_PERMISSION_CODES:
            raise CommandError(f'個別付与できない権限です: {code}（対象：{sorted(INDIVIDUAL_GRANTABLE)}）')
        app_label, codename = code.split('.', 1)
        try:
            permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
        except Permission.DoesNotExist as exc:
            raise CommandError(f'権限が未作成です（migrate を確認）: {code}') from exc
        user = self.get_user(options['username'])
        has_direct = user.user_permissions.filter(pk=permission.pk).exists()
        via_groups = sorted(user.groups.filter(permissions=permission).values_list('name', flat=True))
        revoke = options['revoke']
        self.stdout.write(f'{user.username}（id={user.pk}）{code}：個別付与={has_direct} ロール経由={via_groups}')
        if revoke and via_groups:
            self.stdout.write(self.style.WARNING(
                'ロール経由でも付与されています。ロールからの付与は assign_business_roles で変更してください。'))
        if (revoke and not has_direct) or (not revoke and has_direct):
            self.stdout.write('変更はありません。')
            return
        if not self.confirm(options, f'{code} を{"取り消し" if revoke else "付与"}します。'):
            return
        if revoke:
            user.user_permissions.remove(permission)
        else:
            user.user_permissions.add(permission)
        self.audit('permission_revoke' if revoke else 'permission_grant', obj=user,
                   changes={'user_permissions': {'from': has_direct, 'to': not revoke}}, extra={'permission': code})
        self.stdout.write(self.style.SUCCESS('変更しました。'))
