from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """システムのアクセス・変更の記録（Timeline とは別物）。

    業務の進捗は Timeline、ログイン・権限変更・他人データ閲覧・出力・ダウンロード・
    拒否などのシステム操作はここに記録する。書き込みは apps.audit.services.record()
    だけから行い、API での作成・変更・削除は提供しない。
    """

    RESULT_SUCCESS = 'success'
    RESULT_DENIED = 'denied'
    RESULT_ERROR = 'error'
    RESULT_CHOICES = [
        (RESULT_SUCCESS, 'success'),
        (RESULT_DENIED, 'denied'),
        (RESULT_ERROR, 'error'),
    ]

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    module = models.CharField(max_length=40, db_index=True)
    action = models.CharField(max_length=60, db_index=True)
    object_type = models.CharField(max_length=60, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default=RESULT_SUCCESS)
    changes = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    via_permission = models.CharField(max_length=100, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-occurred_at', '-id']
        verbose_name = '監査ログ'
        verbose_name_plural = '監査ログ'

    def __str__(self):
        return f'{self.occurred_at:%Y-%m-%d %H:%M:%S} {self.module}.{self.action} {self.result}'
