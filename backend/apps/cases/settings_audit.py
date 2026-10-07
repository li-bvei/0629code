"""案件設置（案件種別・業務フロー・段階・必要資料テンプレート）の変更監査（P4）。

変更には cases.manage_case_settings が必要（case_settings 規則）。ここでは誰が・いつ・何を・
変更前後の値を監査ログに残すだけで、権限判定はしない。
"""
from apps.audit.services import record, safe_changes

AUDIT_MODULE = 'case_settings'
SKIPPED_FIELDS = {'created_at', 'updated_at'}


def setting_values(obj):
    values = {}
    for field in obj._meta.concrete_fields:
        if field.name in SKIPPED_FIELDS:
            continue
        value = getattr(obj, field.attname)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        values[field.attname] = value
    return values


def audit_setting(request, obj, action, before=None, after=None, **kwargs):
    """action：created / updated / deleted / restored / reordered など。"""
    if after is None and action != 'deleted':
        after = setting_values(obj)
    changes = safe_changes(before or {}, after or {})
    if action == 'updated' and not changes:
        return None
    return record(
        module=AUDIT_MODULE, action=f'{obj._meta.model_name}_{action}', request=request, obj=obj,
        object_repr=f'{obj._meta.verbose_name} {obj}', changes=changes, **kwargs,
    )


class SettingsAuditMixin:
    """ModelViewSet 用：作成・更新・削除を監査する（perform_* を上書きしない ViewSet 向け）。"""

    def perform_create(self, serializer):
        super().perform_create(serializer)
        audit_setting(self.request, serializer.instance, 'created')

    def perform_update(self, serializer):
        before = setting_values(serializer.instance)
        super().perform_update(serializer)
        audit_setting(self.request, serializer.instance, 'updated', before=before)

    def perform_destroy(self, instance):
        before, pk = setting_values(instance), instance.pk
        super().perform_destroy(instance)
        audit_setting(self.request, instance, 'deleted', before=before, object_id=str(pk))
