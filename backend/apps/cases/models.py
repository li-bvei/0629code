from django.db import models
from django.utils import timezone


class Case(models.Model):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_OPEN, '受付'),
        (STATUS_IN_PROGRESS, '進行中'),
        (STATUS_COMPLETED, '完了'),
        (STATUS_CLOSED, '終了'),
    ]

    case_number = models.CharField(max_length=50, unique=True)
    case_type = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='cases',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        related_name='cases',
        blank=True,
        null=True,
    )
    responsible_employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        related_name='cases',
        blank=True,
        null=True,
    )
    accepted_at = models.DateField(blank=True, null=True)
    applied_at = models.DateField('申請日', blank=True, null=True)
    result_notified_at = models.DateField('結果通知日', blank=True, null=True)
    completed_at = models.DateField('完了日', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cases'
        ordering = ['-created_at']

    def __str__(self):
        return self.case_number

    @classmethod
    def generate_case_number(cls):
        year = timezone.localdate().year
        prefix = f'CASE-{year}-'
        latest_case = (
            cls.objects
            .filter(case_number__startswith=prefix)
            .order_by('-case_number')
            .first()
        )

        next_number = 1
        if latest_case:
            latest_number = latest_case.case_number.replace(prefix, '', 1)
            if latest_number.isdigit():
                next_number = int(latest_number) + 1

        while True:
            case_number = f'{prefix}{next_number:04d}'
            if not cls.objects.filter(case_number=case_number).exists():
                return case_number
            next_number += 1

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = self.generate_case_number()
        super().save(*args, **kwargs)
