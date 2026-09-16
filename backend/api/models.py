from django.db import models


class ReceptionIdempotencyRecord(models.Model):
    """POST /api/receptions/ の重複送信対策。

    フロントが送る request_id（1回の受付確定操作につき1つ）をキーに、
    同じ操作の再送（二重クリック・ネットワーク再試行）で顧客・案件を
    重複作成しないようにする。response が null の間は処理中を意味する。
    """

    request_id = models.CharField(max_length=100, unique=True)
    response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reception_idempotency_records'

    def __str__(self):
        return self.request_id
