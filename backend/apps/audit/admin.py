from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """読み取り専用。閲覧は保護アカウントかつ audit.view_auditlog を明示付与された者だけ。"""

    list_display = ('occurred_at', 'username_snapshot', 'module', 'action', 'result', 'object_type', 'object_id', 'ip')
    list_filter = ('module', 'action', 'result')
    search_fields = ('username_snapshot', 'object_repr', 'request_id', 'object_id')
    date_hierarchy = 'occurred_at'

    def _allowed(self, request):
        from apps.authentication.access_policy import BusinessAccessPolicy, is_protected_account

        user = request.user
        return (
            is_protected_account(user)
            and BusinessAccessPolicy(user).has('audit.view_auditlog')
        )

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
