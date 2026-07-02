from django.db import models


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
