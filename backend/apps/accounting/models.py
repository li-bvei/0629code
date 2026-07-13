from django.conf import settings
from django.db import models
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.companies.models import Company
from apps.customers.models import Customer
from apps.employees.models import Employee


class ExpenseCategory(models.Model):
    name = models.CharField('カテゴリ名', max_length=50, unique=True)
    is_active = models.BooleanField('有効', default=True)
    sort_order = models.PositiveIntegerField('並び順', default=0)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_expense_categories'
        verbose_name = '支出カテゴリ'
        verbose_name_plural = '支出カテゴリ'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class Expense(models.Model):
    expense_date = models.DateField('日付')
    place = models.CharField('場所', max_length=255, blank=True)
    category = models.CharField('カテゴリ', max_length=50)
    amount = models.DecimalField('金額', max_digits=12, decimal_places=0)
    payment_method = models.CharField('支払方法', max_length=50, blank=True)
    expense_target = models.CharField('費用対象', max_length=150, blank=True)
    note = models.TextField('備考', blank=True)
    is_reimbursed = models.BooleanField('精算済み', default=False)
    is_exported = models.BooleanField('出力済み', default=False)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_expenses'
        verbose_name = '支出記録'
        verbose_name_plural = '支出記録'
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f'{self.expense_date} {self.category} {self.amount}'


class IncomeSource(models.Model):
    source_date = models.DateField('日付')
    source_target = models.CharField('対象', max_length=150, blank=True)
    amount = models.DecimalField('金額', max_digits=12, decimal_places=0)
    note = models.TextField('備考', blank=True)
    is_exported = models.BooleanField('出力済み', default=False)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_income_sources'
        verbose_name = '収入来源'
        verbose_name_plural = '収入来源'
        ordering = ['-source_date', '-created_at']

    def __str__(self):
        return f'{self.source_date} {self.source_target} {self.amount}'


class VehicleUsage(models.Model):
    usage_date = models.DateField('日付')
    place = models.CharField('場所', max_length=255, blank=True)
    distance_km = models.DecimalField('走行距離', max_digits=8, decimal_places=1)
    usage_target = models.CharField('利用対象', max_length=150, blank=True)
    purpose = models.CharField('用途', max_length=100, blank=True)
    note = models.TextField('備考', blank=True)
    is_exported = models.BooleanField('出力済み', default=False)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_vehicle_usages'
        verbose_name = '用車記録'
        verbose_name_plural = '用車記録'
        ordering = ['-usage_date', '-created_at']

    def __str__(self):
        return f'{self.usage_date} {self.purpose} {self.distance_km}km'


class AccountingProject(models.Model):
    name = models.CharField('项目名称', max_length=255)
    description = models.TextField('项目说明', blank=True)
    start_date = models.DateField('开始日期', null=True, blank=True)
    end_date = models.DateField('结束日期', null=True, blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    note = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'accounting_projects'
        verbose_name = '项目收支表'
        verbose_name_plural = '项目收支表'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class AccountingProjectIncome(models.Model):
    project = models.ForeignKey(
        AccountingProject,
        on_delete=models.CASCADE,
        related_name='project_incomes',
        verbose_name='项目',
    )
    income_date = models.DateField('收入日期')
    income_target = models.CharField('收入对象', max_length=255, blank=True)
    amount = models.DecimalField('金额', max_digits=12, decimal_places=2)
    note = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'accounting_project_incomes'
        verbose_name = '项目收入'
        verbose_name_plural = '项目收入'
        ordering = ['-income_date', '-id']

    def __str__(self):
        return f'{self.project.name} - {self.amount}'


class AccountingProjectExpense(models.Model):
    project = models.ForeignKey(
        AccountingProject,
        on_delete=models.CASCADE,
        related_name='project_expenses',
        verbose_name='项目',
    )
    expense_date = models.DateField('支出日期')
    place = models.CharField('地点', max_length=255, blank=True)
    category_name = models.CharField('类别', max_length=255, blank=True)
    amount = models.DecimalField('金额', max_digits=12, decimal_places=2)
    payment_method = models.CharField('支付方式', max_length=100, blank=True)
    expense_target = models.CharField('费用对象', max_length=255, blank=True)
    note = models.TextField('备注', blank=True)
    source_expense = models.ForeignKey(
        Expense,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='project_copies',
        verbose_name='来源支出记录',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'accounting_project_expenses'
        verbose_name = '项目支出'
        verbose_name_plural = '项目支出'
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return f'{self.project.name} - {self.amount}'


class VoucherItemTemplate(models.Model):
    name = models.CharField('項目名', max_length=255, unique=True)
    default_unit_price = models.DecimalField(
        '默认单价',
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField('有効', default=True)
    sort_order = models.PositiveIntegerField('並び順', default=0)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_voucher_item_templates'
        verbose_name = '帳票明細項目'
        verbose_name_plural = '帳票明細項目'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class AccountingVoucher(models.Model):
    VOUCHER_TYPE_INVOICE = 'invoice'
    VOUCHER_TYPE_RECEIPT = 'receipt'
    VOUCHER_TYPE_CHOICES = (
        (VOUCHER_TYPE_INVOICE, '請求書'),
        (VOUCHER_TYPE_RECEIPT, '領収書'),
    )

    voucher_type = models.CharField('帳票種別', max_length=20, choices=VOUCHER_TYPE_CHOICES)
    voucher_number = models.CharField('帳票番号', max_length=50, unique=True, blank=True)
    issue_date = models.DateField('発行日')
    recipient_name = models.CharField('宛先会社名', max_length=255, blank=True)
    recipient_postal_code = models.CharField('宛先郵便番号', max_length=20, blank=True)
    recipient_address = models.TextField('宛先住所', blank=True)
    title = models.CharField('件名 / 但し書き', max_length=255, blank=True)
    amount = models.DecimalField('金額', max_digits=12, decimal_places=0)
    tax_amount = models.DecimalField('消費税額', max_digits=12, decimal_places=0, default=0)
    total_amount = models.DecimalField('合計金額', max_digits=12, decimal_places=0, default=0)
    details = models.TextField('明細', blank=True)
    line_items = models.JSONField('明細行', default=list, blank=True)
    note = models.TextField('備考', blank=True)
    payment_due_date = models.DateField('支払期限', null=True, blank=True)
    payment_method = models.CharField('支払方法', max_length=100, blank=True)
    issuer_name = models.CharField('発行者名', max_length=255, default='SUNRISE日晟鴻達株式会社')
    issuer_postal_code = models.CharField('発行者郵便番号', max_length=20, blank=True)
    issuer_address = models.TextField('発行者住所', blank=True)
    issuer_tel = models.CharField('発行者電話番号', max_length=50, blank=True)
    issuer_registration_number = models.CharField('登録番号', max_length=100, blank=True)
    bank_info = models.TextField('振込先', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='accounting_vouchers',
        verbose_name='作成者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_vouchers'
        verbose_name = '帳票'
        verbose_name_plural = '帳票'
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return f'{self.get_voucher_type_display()} {self.voucher_number}'

    # def save(self, *args, **kwargs):
    #     self.line_items = self.normalize_line_items(self.line_items)
    #     if self.line_items:
    #         self.amount = sum(Decimal(str(item['line_total'])) for item in self.line_items)
    #         self.tax_amount = (self.amount * Decimal('0.10')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    #     else:
    #         self.tax_amount = self.tax_amount or 0
    #     self.total_amount = self.amount + self.tax_amount
    #     if not self.voucher_number:
    #         self.voucher_number = self.generate_voucher_number()
    #     super().save(*args, **kwargs)
    def save(self, *args, **kwargs):
        self.line_items = self.normalize_line_items(self.line_items)
        if self.line_items:
            total_amount = sum(Decimal(str(item['line_total'])) for item in self.line_items)
            self.amount = (total_amount / Decimal('1.1')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            self.tax_amount = total_amount - self.amount
            self.total_amount = total_amount
        else:
            self.tax_amount = self.tax_amount or 0
            self.total_amount = self.amount + self.tax_amount
        if not self.voucher_number:
            self.voucher_number = self.generate_voucher_number()
        super().save(*args, **kwargs)

    @staticmethod
    def to_decimal(value):
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0')

    @classmethod
    def normalize_line_items(cls, items):
        if not isinstance(items, list):
            return []

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_name = str(item.get('item_name') or '').strip()
            quantity = cls.to_decimal(item.get('quantity'))
            unit_price = cls.to_decimal(item.get('unit_price'))
            if not item_name and quantity == 0 and unit_price == 0:
                continue
            line_total = (quantity * unit_price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            normalized.append({
                'item_name': item_name,
                'quantity': float(quantity),
                'unit_price': int(unit_price.quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
                'line_total': int(line_total),
            })
        return normalized

    def generate_voucher_number(self):
        prefix = 'INV' if self.voucher_type == self.VOUCHER_TYPE_INVOICE else 'REC'
        date_part = self.issue_date.strftime('%Y%m%d')
        base = f'{prefix}-{date_part}'
        latest = (
            AccountingVoucher.objects
            .filter(voucher_number__startswith=base)
            .order_by('-voucher_number')
            .first()
        )
        next_number = 1
        if latest and latest.voucher_number:
            try:
                next_number = int(latest.voucher_number.split('-')[-1]) + 1
            except ValueError:
                next_number = 1
        return f'{base}-{next_number:04d}'


class VisaReturnApplication(models.Model):
    GENDER_CHOICES = (
        ('male', '男性'),
        ('female', '女性'),
    )
    MARITAL_STATUS_CHOICES = (
        ('single', '未婚'),
        ('married', '既婚'),
        ('divorced', '離婚'),
        ('widowed', '死別'),
    )

    applicant_name = models.CharField('申请人姓名', max_length=255, blank=True)
    nationality = models.CharField('国籍', max_length=100, blank=True)
    birth_date = models.DateField('生年月日', null=True, blank=True)
    gender = models.CharField('性別', max_length=20, blank=True, choices=GENDER_CHOICES)
    marital_status = models.CharField('婚姻状況', max_length=20, blank=True, choices=MARITAL_STATUS_CHOICES)
    passport_number = models.CharField('旅券番号', max_length=100, blank=True)
    passport_issue_date = models.DateField('旅券発行日', null=True, blank=True)
    passport_expiry_date = models.DateField('旅券期限', null=True, blank=True)
    residence_status = models.CharField('在留資格', max_length=100, blank=True)
    address = models.TextField('住所', blank=True)
    phone = models.CharField('電話番号', max_length=50, blank=True)
    email = models.EmailField('メール', blank=True)
    occupation = models.CharField('職業', max_length=100, blank=True)
    guarantor_name = models.CharField('保証人氏名', max_length=255, blank=True)
    guarantor_phone = models.CharField('保証人電話番号', max_length=50, blank=True)
    guarantor_address = models.TextField('保証人住所', blank=True)
    guarantor_relationship = models.CharField('申請人との関係', max_length=100, blank=True)
    guarantor_occupation = models.CharField('保証人職業', max_length=100, blank=True)
    guarantor_snapshot = models.JSONField('保証人スナップショット', default=dict, blank=True)
    form_data = models.JSONField('表单数据', default=dict, blank=True)
    note = models.TextField('備考', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visa_return_applications',
        verbose_name='作成者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_visa_return_applications'
        verbose_name = '返签visa表'
        verbose_name_plural = '返签visa表'
        ordering = ['-created_at']

    def __str__(self):
        return self.applicant_name or f'返签visa表 {self.pk}'


class VisaGuarantorTemplate(models.Model):
    name = models.CharField('模板名称', max_length=255)
    guarantor_name = models.CharField('在日担保人姓名', max_length=255, blank=True)
    guarantor_name_en = models.CharField('在日担保人英文姓名', max_length=255, blank=True)
    guarantor_phone = models.CharField('电话', max_length=50, blank=True)
    guarantor_address = models.TextField('日文地址', blank=True)
    guarantor_address_en = models.TextField('英文地址', blank=True)
    guarantor_birth_date = models.DateField('出生日期', null=True, blank=True)
    guarantor_nationality = models.CharField('国籍', max_length=100, blank=True)
    guarantor_visa_status = models.CharField('签证种类 / 在留资格', max_length=100, blank=True)
    guarantor_occupation = models.CharField('职业 / 职务', max_length=100, blank=True)
    guarantor_relationship = models.CharField('与申请人的关系', max_length=100, blank=True)
    guarantor_company_name = models.CharField('公司名', max_length=255, blank=True)
    note = models.TextField('备注', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'accounting_visa_guarantor_templates'
        verbose_name = '在日担保人模板'
        verbose_name_plural = '在日担保人模板'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class SeifuNoticePdfRecord(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '下書き'),
        (STATUS_COMPLETED, '完了'),
    )

    title = models.CharField('记录名称', max_length=255)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    text_items = models.JSONField('追加文字', default=list, blank=True)
    note = models.TextField('备注', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='seifu_notice_pdf_records',
        verbose_name='作成者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_seifu_notice_pdf_records'
        verbose_name = '清風合格通知書记录'
        verbose_name_plural = '清風合格通知書记录'
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return self.title


class TaxRenewalVoucherRecord(models.Model):
    CATEGORY_RENEWAL = 'renewal'
    CATEGORY_PENSION = 'pension'
    CATEGORY_CHOICES = (
        (CATEGORY_RENEWAL, '更新用'),
        (CATEGORY_PENSION, '年金加入'),
    )

    STATUS_DRAFT = 'draft'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '下書き'),
        (STATUS_COMPLETED, '完了'),
    )

    title = models.CharField('记录名称', max_length=255)
    category = models.CharField('分类', max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_RENEWAL)
    company = models.ForeignKey(
        Company,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tax_renewal_voucher_records',
        verbose_name='会社',
    )
    customer = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tax_renewal_voucher_records',
        verbose_name='顧客',
    )
    employee = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tax_renewal_voucher_records',
        verbose_name='担当者',
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    has_employees = models.BooleanField('是否有雇员', default=False)
    has_dependents = models.BooleanField('是否有抚养人', default=False)
    selected_templates = models.JSONField('选择模板', default=list, blank=True)
    form_data = models.JSONField('表单数据', default=dict, blank=True)
    generated_files = models.JSONField('生成文件', default=list, blank=True)
    note = models.TextField('备注', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tax_renewal_voucher_records',
        verbose_name='作成者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_tax_renewal_voucher_records'
        verbose_name = '税务证明更新用记录'
        verbose_name_plural = '税务证明更新用记录'
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return self.title


class TaxRenewalAgentTemplate(models.Model):
    name = models.CharField('模板名称', max_length=255)
    agent_name = models.CharField('代理人姓名', max_length=255)
    agent_kana = models.CharField('代理人假名', max_length=255, blank=True)
    agent_address = models.TextField('代理人地址', blank=True)
    agent_phone = models.CharField('代理人电话', max_length=50, blank=True)
    agent_company_name = models.CharField('代理公司名', max_length=255, blank=True)
    agent_position = models.CharField('职务', max_length=100, blank=True)
    note = models.TextField('备注', blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.IntegerField('排序', default=0)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_tax_renewal_agent_templates'
        verbose_name = '税务证明代理人模板'
        verbose_name_plural = '税务证明代理人模板'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name
