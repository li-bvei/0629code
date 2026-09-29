"""事務所全体の設定（単一行）。汎用の key-value 設定表にはしない。項目は必要なものだけを列で持つ。"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class OfficeSettings(models.Model):
    SINGLETON_ID = 1

    # 事業年度の末月（1〜12）。行が無い間は環境変数（首回デプロイ用）→ 既定 3 月の順で補う。
    fiscal_year_end_month = models.PositiveSmallIntegerField(
        '事業年度末月', validators=[MinValueValidator(1), MaxValueValidator(12)])
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+', verbose_name='更新者')
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'office_settings'
        verbose_name = '事務所設定'
        verbose_name_plural = '事務所設定'
        permissions = [('manage_office_settings', '事務所設定の変更')]

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)
