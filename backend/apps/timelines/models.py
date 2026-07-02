from django.db import models


class Timeline(models.Model):
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='timelines',
    )
    occurred_at = models.DateField('発生日', null=True, blank=True)
    title = models.CharField(max_length=150)
    content = models.TextField(blank=True)
    is_visible_to_client = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_timelines'
        ordering = ['-occurred_at', '-created_at']

    def __str__(self):
        return self.title
