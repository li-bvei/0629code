from django.conf import settings
from django.db import models


class Employee(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    # ログインアカウントとの1対1関連（業務権限の「本人担当」判定に使う）。
    # 担当者はアカウントを持たなくてもよい（例：ログインしない担当者）。関連付けは
    # 管理コマンド link_user_employee で行い、migration ではデータを書かない。
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        ordering = ['name']

    def __str__(self):
        return self.name
