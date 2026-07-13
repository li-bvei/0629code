from django.db import models


class Task(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_PAUSED = 'paused'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, '未開始'),
        (STATUS_IN_PROGRESS, '進行中'),
        (STATUS_COMPLETED, '完了'),
        (STATUS_PAUSED, '一時停止'),
        (STATUS_CANCELLED, '取消'),
    ]

    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    responsible_employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        related_name='tasks',
        blank=True,
        null=True,
    )
    sort_order = models.PositiveIntegerField(default=0)
    due_date = models.DateField(blank=True, null=True)
    completed_at = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_tasks'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title
