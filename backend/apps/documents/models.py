from django.db import models


class Document(models.Model):
    SOURCE_INTERNAL = 'internal'
    SOURCE_CLIENT = 'client'
    SOURCE_SYSTEM = 'system'

    SOURCE_CHOICES = [
        (SOURCE_INTERNAL, '内部アップロード'),
        (SOURCE_CLIENT, '顧客アップロード'),
        (SOURCE_SYSTEM, 'システム生成'),
    ]

    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to='case_documents/', null=True, blank=True)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    content_type = models.CharField(max_length=100, blank=True)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_INTERNAL,
    )
    is_visible_to_client = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)
