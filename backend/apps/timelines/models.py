from django.conf import settings
from django.db import models


class Timeline(models.Model):
    # 自動記録される主なイベント種別（record_case_event で使用）。手入力の記録は空文字。
    EVENT_MANUAL = ''
    EVENT_CASE_CREATED = 'case_created'
    EVENT_CUSTOMER_CREATED = 'customer_created'
    EVENT_ASSIGNEE_CHANGED = 'assignee_changed'
    EVENT_STATUS_CHANGED = 'status_changed'
    EVENT_REGISTRATION_STATUS_CHANGED = 'registration_status_changed'
    EVENT_WAITING_STARTED = 'waiting_started'
    EVENT_WAITING_ENDED = 'waiting_ended'
    EVENT_CHECKLIST_COMPLETED = 'checklist_completed'
    EVENT_DOCUMENT_UPLOADED = 'document_uploaded'
    EVENT_ACTION_CREATED = 'action_created'
    EVENT_ACTION_COMPLETED = 'action_completed'
    EVENT_DEADLINE_COMPLETED = 'deadline_completed'
    EVENT_PAYMENT_RECEIVED = 'payment_received'
    EVENT_EXPENSE_RECORDED = 'expense_recorded'
    EVENT_PDF_GENERATED = 'pdf_generated'
    EVENT_CASE_COMPLETED = 'case_completed'
    EVENT_CASE_REOPENED = 'case_reopened'
    EVENT_DOCUMENT_REQUEST = 'document_request'
    EVENT_DOCUMENT_RECEIVED = 'document_received'
    EVENT_DOCUMENT_ARCHIVED = 'document_archived'
    EVENT_DOCUMENT_RESTORED = 'document_restored'
    EVENT_ACCOUNTING_LINKED = 'accounting_linked'

    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='timelines',
    )
    occurred_at = models.DateField('発生日', null=True, blank=True)
    title = models.CharField(max_length=150)
    content = models.TextField(blank=True)
    event_type = models.CharField(max_length=40, blank=True, default='')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timeline_events',
    )
    metadata = models.JSONField(default=dict, blank=True)
    is_visible_to_client = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_timelines'
        ordering = ['-occurred_at', '-created_at']

    def __str__(self):
        return self.title
