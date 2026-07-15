from django.db import IntegrityError, models, transaction


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

    case_number = models.CharField(max_length=120, unique=True)
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
    def generate_case_number(cls, case_type='', customer=None, created_at=None):
        from .utils import generate_case_number

        return generate_case_number(case_type, customer=customer, created_at=created_at)

    def save(self, *args, **kwargs):
        if self.case_number or self.pk:
            super().save(*args, **kwargs)
            return

        for attempt in range(3):
            self.case_number = self.generate_case_number(self.case_type, customer=self.customer)
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError:
                self.case_number = ''
                if attempt == 2:
                    raise


class CaseChecklistTemplate(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_checklist_templates'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class CaseChecklistTemplateItem(models.Model):
    ITEM_TYPE_TASK = 'task'
    ITEM_TYPE_DOCUMENT = 'document'
    ITEM_TYPE_CONFIRMATION = 'confirmation'

    ITEM_TYPE_CHOICES = [
        (ITEM_TYPE_TASK, '手続事項'),
        (ITEM_TYPE_DOCUMENT, '必要資料'),
        (ITEM_TYPE_CONFIRMATION, '確認事項'),
    ]

    template = models.ForeignKey(
        CaseChecklistTemplate,
        on_delete=models.CASCADE,
        related_name='items',
    )
    category = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=150)
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        default=ITEM_TYPE_DOCUMENT,
    )
    quantity = models.PositiveIntegerField(blank=True, null=True)
    unit = models.CharField(max_length=20, blank=True)
    is_required = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_with_template = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_checklist_template_items'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class CaseChecklistItem(models.Model):
    ITEM_TYPE_TASK = CaseChecklistTemplateItem.ITEM_TYPE_TASK
    ITEM_TYPE_DOCUMENT = CaseChecklistTemplateItem.ITEM_TYPE_DOCUMENT
    ITEM_TYPE_CONFIRMATION = CaseChecklistTemplateItem.ITEM_TYPE_CONFIRMATION
    ITEM_TYPE_CHOICES = CaseChecklistTemplateItem.ITEM_TYPE_CHOICES

    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='checklist_items',
    )
    source_template_item = models.ForeignKey(
        CaseChecklistTemplateItem,
        on_delete=models.SET_NULL,
        related_name='case_items',
        blank=True,
        null=True,
    )
    category = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=150)
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        default=ITEM_TYPE_DOCUMENT,
    )
    quantity = models.PositiveIntegerField(blank=True, null=True)
    unit = models.CharField(max_length=20, blank=True)
    is_required = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        related_name='completed_case_checklist_items',
        blank=True,
        null=True,
    )
    note = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_checklist_items'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name
