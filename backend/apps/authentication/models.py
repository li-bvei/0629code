from django.conf import settings
from django.db import models


class ProtectedAccount(models.Model):
    """停止・降格・改名・パスワードリセットから保護されるアカウント（唯一のシステム管理者）。

    表示名やDB上のIDではなく、User への FK で識別する。行の追加・削除はサーバー上の
    管理コマンド protect_account だけで行い、API・Admin からは変更できない。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='protected_account',
    )
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'authentication_protected_accounts'
        verbose_name = '保護アカウント'
        verbose_name_plural = '保護アカウント'
        permissions = [
            ('manage_users', 'アカウント管理'),
            ('use_diagnostics', '診断機能の利用'),
        ]

    def __str__(self):
        return self.user.get_username()
