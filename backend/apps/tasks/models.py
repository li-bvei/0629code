from django.db import models


class Task(models.Model):
    STATUS_TODO = 'todo'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'

    STATUS_CHOICES = [
        (STATUS_TODO, '未対応'),
        (STATUS_IN_PROGRESS, '対応中'),
        (STATUS_DONE, '完了'),
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
        default=STATUS_TODO,
    )
    due_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_tasks'
        ordering = ['status', 'due_date', '-created_at']

    def __str__(self):
        return self.title
