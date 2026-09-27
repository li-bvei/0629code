from apps.authentication.management.base import SafeCommand
from apps.authentication.roles import plan_roles, sync_roles


class Command(SafeCommand):
    help = '業務ロール（Group）と明示権限を定義どおりに作成・同期する。既定 dry-run。'

    def handle(self, *args, **options):
        plan = plan_roles()
        for row in plan:
            status = '既存' if row['exists'] else '新規作成'
            self.stdout.write(f"[{row['group']}] {status} 追加={row['add']} 削除={row['remove']}")
        if not self.confirm(options, 'Group と権限を同期します。'):
            return
        result = sync_roles()
        self.audit('roles_setup', extra={'plan': plan})
        self.stdout.write(self.style.SUCCESS(f'同期しました（{len(result)} Group）。'))
