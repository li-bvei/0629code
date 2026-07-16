from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction


class CaseTypeMaster(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=80, unique=True)
    number_abbreviation = models.CharField(max_length=20, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_type_masters'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class CaseApplicationCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.SlugField(max_length=80, unique=True)
    number_abbreviation = models.CharField(max_length=20, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_application_categories'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class CaseStatusSetting(models.Model):
    code = models.CharField(max_length=40, unique=True)
    display_name = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_status_settings'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.display_name


class AcquisitionPlacePreset(models.Model):
    name = models.CharField(max_length=150, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_acquisition_place_presets'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class ResponsiblePartyPreset(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=40, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_responsible_party_presets'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class Case(models.Model):
    REGISTRATION_STATUS_ACTIVE = 'active'
    REGISTRATION_STATUS_INACTIVE = 'inactive'
    REGISTRATION_STATUS_ARCHIVED = 'archived'
    STATUS_CONSULTATION = 'consultation'
    STATUS_ACCEPTED = 'accepted'
    STATUS_COLLECTING_DOCUMENTS = 'collecting_documents'
    STATUS_PREPARING_DOCUMENTS = 'preparing_documents'
    STATUS_READY_TO_APPLY = 'ready_to_apply'
    STATUS_APPLIED = 'applied'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_ADDITIONAL_DOCUMENTS = 'additional_documents'
    STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED = 'additional_documents_submitted'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_COMPLETED = 'completed'
    STATUS_OPEN = STATUS_ACCEPTED
    STATUS_IN_PROGRESS = STATUS_COLLECTING_DOCUMENTS
    STATUS_CLOSED = STATUS_COMPLETED

    REGISTRATION_STATUS_CHOICES = [
        (REGISTRATION_STATUS_ACTIVE, '有効'),
        (REGISTRATION_STATUS_INACTIVE, '無効'),
        (REGISTRATION_STATUS_ARCHIVED, 'アーカイブ'),
    ]

    STATUS_CHOICES = [
        (STATUS_CONSULTATION, '相談中'),
        (STATUS_ACCEPTED, '受任済み'),
        (STATUS_COLLECTING_DOCUMENTS, '資料準備中'),
        (STATUS_PREPARING_DOCUMENTS, '書類作成中'),
        (STATUS_READY_TO_APPLY, '申請準備完了'),
        (STATUS_APPLIED, '申請済み'),
        (STATUS_UNDER_REVIEW, '審査中'),
        (STATUS_ADDITIONAL_DOCUMENTS, '追加資料対応中'),
        (STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED, '追加資料提出済み'),
        (STATUS_APPROVED, '許可'),
        (STATUS_REJECTED, '不許可'),
        (STATUS_WITHDRAWN, '取下げ'),
        (STATUS_COMPLETED, '完了'),
    ]

    case_number = models.CharField(max_length=120, unique=True)
    case_type = models.CharField(max_length=100)
    case_type_master = models.ForeignKey(
        CaseTypeMaster,
        on_delete=models.PROTECT,
        related_name='cases',
        blank=True,
        null=True,
    )
    application_category = models.ForeignKey(
        CaseApplicationCategory,
        on_delete=models.PROTECT,
        related_name='cases',
        blank=True,
        null=True,
    )
    registration_status = models.CharField(
        max_length=20,
        choices=REGISTRATION_STATUS_CHOICES,
        default=REGISTRATION_STATUS_ACTIVE,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_ACCEPTED,
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
    consulted_at = models.DateField('相談日', blank=True, null=True)
    accepted_at = models.DateField(blank=True, null=True)
    document_collection_started_at = models.DateField('資料待ち開始日', blank=True, null=True)
    documents_completed_at = models.DateField('必要資料完了日', blank=True, null=True)
    application_ready_at = models.DateField('申請準備完了日', blank=True, null=True)
    applied_at = models.DateField('申請日', blank=True, null=True)
    application_authority = models.CharField('申請先', max_length=150, blank=True)
    application_receipt_number = models.CharField('受付番号', max_length=100, blank=True)
    permission_number = models.CharField('許可番号', max_length=100, blank=True)
    review_started_at = models.DateField('審査開始日', blank=True, null=True)
    expected_result_at = models.DateField('結果予定日', blank=True, null=True)
    additional_documents_requested_at = models.DateField('追加資料依頼日', blank=True, null=True)
    additional_documents_due_at = models.DateField('追加資料期限', blank=True, null=True)
    additional_documents_submitted_at = models.DateField('追加資料提出日', blank=True, null=True)
    additional_documents_detail = models.TextField('追加資料内容', blank=True)
    result_notified_at = models.DateField('結果通知日', blank=True, null=True)
    result_received_at = models.DateField('結果受領日', blank=True, null=True)
    result_note = models.TextField('結果備考', blank=True)
    withdrawn_at = models.DateField('取下げ日', blank=True, null=True)
    completed_at = models.DateField('完了日', blank=True, null=True)
    archived_at = models.DateField('アーカイブ日', blank=True, null=True)
    status_changed_at = models.DateField('進捗変更日', blank=True, null=True)
    next_action = models.TextField('次の対応', blank=True)
    next_action_due_at = models.DateField('対応期限', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cases'
        ordering = ['-created_at']

    def __str__(self):
        return self.case_number

    @classmethod
    def generate_case_number(cls, case_type_master=None, application_category=None, customer=None, created_at=None):
        from .utils import generate_case_number

        return generate_case_number(
            case_type_master=case_type_master,
            application_category=application_category,
            customer=customer,
            created_at=created_at,
        )

    def save(self, *args, **kwargs):
        if self.case_number or self.pk:
            super().save(*args, **kwargs)
            return

        for attempt in range(3):
            if self.case_type_master and not self.case_type:
                self.case_type = self.case_type_master.name
            if not self.case_type_master or not self.application_category:
                raise ValidationError('案件種別と申請区分を選択してください。')
            self.case_number = self.generate_case_number(
                case_type_master=self.case_type_master,
                application_category=self.application_category,
                customer=self.customer,
            )
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
    RESPONSIBLE_PARTY_CUSTOMER = 'customer'
    RESPONSIBLE_PARTY_COMPANY = 'company'
    RESPONSIBLE_PARTY_OUR_COMPANY = 'our_company'
    RESPONSIBLE_PARTY_GYOUSEI = 'gyousei'
    RESPONSIBLE_PARTY_TAX_ACCOUNTANT = 'tax_accountant'
    RESPONSIBLE_PARTY_OTHER = 'other'
    IMPORTANCE_NORMAL = 'normal'
    IMPORTANCE_IMPORTANT = 'important'
    IMPORTANCE_WARNING = 'warning'

    ITEM_TYPE_CHOICES = [
        (ITEM_TYPE_TASK, '手続事項'),
        (ITEM_TYPE_DOCUMENT, '必要資料'),
        (ITEM_TYPE_CONFIRMATION, '確認事項'),
    ]
    RESPONSIBLE_PARTY_CHOICES = [
        (RESPONSIBLE_PARTY_CUSTOMER, '顧客本人'),
        (RESPONSIBLE_PARTY_COMPANY, '会社'),
        (RESPONSIBLE_PARTY_OUR_COMPANY, '本公司代办'),
        (RESPONSIBLE_PARTY_GYOUSEI, '行政書士'),
        (RESPONSIBLE_PARTY_TAX_ACCOUNTANT, '税理士'),
        (RESPONSIBLE_PARTY_OTHER, 'その他'),
    ]
    IMPORTANCE_LEVEL_CHOICES = [
        (IMPORTANCE_NORMAL, '通常'),
        (IMPORTANCE_IMPORTANT, '重要'),
        (IMPORTANCE_WARNING, '要注意'),
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
    responsible_party = models.CharField(max_length=30, choices=RESPONSIBLE_PARTY_CHOICES, blank=True)
    acquisition_place = models.CharField(max_length=255, blank=True)
    required_details = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)
    customer_note = models.TextField(blank=True)
    is_visible_to_customer = models.BooleanField(default=True)
    importance_level = models.CharField(
        max_length=20,
        choices=IMPORTANCE_LEVEL_CHOICES,
        default=IMPORTANCE_NORMAL,
    )
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
    RESPONSIBLE_PARTY_CHOICES = CaseChecklistTemplateItem.RESPONSIBLE_PARTY_CHOICES
    IMPORTANCE_LEVEL_CHOICES = CaseChecklistTemplateItem.IMPORTANCE_LEVEL_CHOICES

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
    responsible_party = models.CharField(max_length=30, choices=RESPONSIBLE_PARTY_CHOICES, blank=True)
    acquisition_place = models.CharField(max_length=255, blank=True)
    required_details = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)
    customer_note = models.TextField(blank=True)
    is_visible_to_customer = models.BooleanField(default=True)
    importance_level = models.CharField(
        max_length=20,
        choices=IMPORTANCE_LEVEL_CHOICES,
        default=CaseChecklistTemplateItem.IMPORTANCE_NORMAL,
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_checklist_items'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name
