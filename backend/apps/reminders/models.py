from django.conf import settings
from django.db import models


class DismissedDeadline(models.Model):
    """ダッシュボードの「期限提醒」で、個別に「非表示」にされた項目を記録する。

    案件が完了/取下げ/不許可になった場合は DashboardDeadlinesView 側で自動的に
    除外されるが、案件のステータス更新を忘れているケースや、そもそも案件に
    紐付いていない記録（家族情報だけ登録されていて業務上のやり取りが実質終わって
    いる等）を手動で個別に消せるようにするための、あくまで補助的な仕組み。

    どの期限項目かは (source_type, source_id, deadline_type, deadline_date) の
    組み合わせで一意に特定する。deadline_date まで含めるのは、期限日そのものが
    後から更新された場合（＝実質的に別の期限）には再度表示されるようにするため。
    """

    SOURCE_CUSTOMER = 'customer'
    SOURCE_FAMILY_MEMBER = 'family_member'
    SOURCE_COMPANY = 'company'
    SOURCE_CHOICES = [
        (SOURCE_CUSTOMER, '顧客'),
        (SOURCE_FAMILY_MEMBER, '家族（旧仕様）'),
        (SOURCE_COMPANY, '会社'),
    ]

    DEADLINE_RESIDENCE_EXPIRY = 'residence_expiry'
    DEADLINE_PASSPORT_EXPIRY = 'passport_expiry'
    DEADLINE_FISCAL_DECLARATION = 'fiscal_declaration'
    DEADLINE_TYPE_CHOICES = [
        (DEADLINE_RESIDENCE_EXPIRY, '在留期限'),
        (DEADLINE_PASSPORT_EXPIRY, 'パスポート期限'),
        (DEADLINE_FISCAL_DECLARATION, '決算申告期限'),
    ]

    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id = models.PositiveIntegerField()
    deadline_type = models.CharField(max_length=30, choices=DEADLINE_TYPE_CHOICES)
    deadline_date = models.DateField()
    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'dismissed_deadlines'
        unique_together = [('source_type', 'source_id', 'deadline_type', 'deadline_date')]

    def __str__(self):
        return f'{self.get_source_type_display()}#{self.source_id} - {self.get_deadline_type_display()}'


class Reminder(models.Model):
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='reminders',
    )
    title = models.CharField(max_length=150)
    remind_at = models.DateTimeField()
    note = models.TextField(blank=True)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_reminders'
        ordering = ['is_done', 'remind_at']

    def __str__(self):
        return self.title
