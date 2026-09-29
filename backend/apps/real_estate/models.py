"""不動産（P3）：賃貸を主とする取引記録・法定台帳・内部利益配分。

- Case・Accounting とは独立したアプリ。顧客・会社・担当者・書類・会計は参照（FK）だけで、データを複製しない。
- 売買（sale）は種別と台帳の列だけ保持し、売買の業務フローは第 1 版では作らない。
- 法定台帳は物理削除しない（API に削除が無い）。ロック後の変更は「更正」として履歴と監査を残す。
- 内部利益配分は法定台帳に含めない。専用権限を持つ人だけが見られる。
"""
import os
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models


class RealEstateTransaction(models.Model):
    TYPE_RENTAL = 'rental'
    TYPE_SALE = 'sale'
    TYPE_CHOICES = ((TYPE_RENTAL, '賃貸'), (TYPE_SALE, '売買'))

    STAGE_INQUIRY = 'inquiry'
    STAGE_VIEWING = 'viewing'
    STAGE_APPLICATION = 'application'
    STAGE_SCREENING = 'screening'
    STAGE_CONTRACT = 'contract'
    STAGE_SETTLED = 'settled'
    STAGE_CANCELLED = 'cancelled'
    STAGE_CHOICES = (
        (STAGE_INQUIRY, '問い合わせ'),
        (STAGE_VIEWING, '内見'),
        (STAGE_APPLICATION, '申込'),
        (STAGE_SCREENING, '審査'),
        (STAGE_CONTRACT, '契約'),
        (STAGE_SETTLED, '完了'),
        (STAGE_CANCELLED, 'キャンセル'),
    )

    PAYMENT_UNSET = ''
    PAYMENT_UNPAID = 'unpaid'
    PAYMENT_PAID = 'paid'
    PAYMENT_OFFSET = 'offset'
    PAYMENT_CHOICES = ((PAYMENT_UNSET, '未設定'), (PAYMENT_UNPAID, '未払い'), (PAYMENT_PAID, '支払済み'), (PAYMENT_OFFSET, '相殺'))

    TRANSFER_UNSET = ''
    TRANSFER_PENDING = 'pending'
    TRANSFER_DONE = 'transferred'
    TRANSFER_CHOICES = ((TRANSFER_UNSET, '未設定'), (TRANSFER_PENDING, '振込待ち'), (TRANSFER_DONE, '振込済み'))

    transaction_number = models.CharField('番号', max_length=40, unique=True, blank=True)
    transaction_type = models.CharField('取引種別', max_length=10, choices=TYPE_CHOICES, default=TYPE_RENTAL)
    stage = models.CharField('段階', max_length=20, choices=STAGE_CHOICES, default=STAGE_INQUIRY)
    # 当事者（軽量入力）。主档の顧客は任意の参照で、自動では結び付けない。
    party_name = models.CharField('顧客・当事者名', max_length=200)
    customer = models.ForeignKey('customers.Customer', verbose_name='顧客（参照）', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='real_estate_transactions')
    # 物件
    property_name = models.CharField('物件名', max_length=200)
    room_number = models.CharField('部屋番号', max_length=50, blank=True)
    property_address = models.CharField('所在地', max_length=300, blank=True)
    property_kind = models.CharField('物件種類', max_length=50, blank=True)
    area_sqm = models.DecimalField('面積（㎡）', max_digits=9, decimal_places=2, null=True, blank=True)
    # 管理会社（名称は入力のまま、会社主档は任意の参照）
    management_company_name = models.CharField('管理会社', max_length=200, blank=True)
    management_company = models.ForeignKey('companies.Company', verbose_name='管理会社（参照）', on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='real_estate_managed_transactions')
    responsible_employee = models.ForeignKey('employees.Employee', verbose_name='担当', on_delete=models.PROTECT,
                                             null=True, blank=True, related_name='real_estate_transactions')
    transaction_date = models.DateField('取引日', null=True, blank=True)
    # 金額（円）。LIST.xlsx の近い 3 つの請求金額は意味が確定するまで別々の元金額として保持する。
    rent_or_price = models.DecimalField('賃料・価格', max_digits=12, decimal_places=0, null=True, blank=True)
    brokerage_fee = models.DecimalField('仲介手数料（報酬）', max_digits=12, decimal_places=0, null=True, blank=True)
    advertising_fee = models.DecimalField('広告料', max_digits=12, decimal_places=0, null=True, blank=True)
    handling_fee = models.DecimalField('手数料', max_digits=12, decimal_places=0, null=True, blank=True)
    source_billed_to_sunrise_amount = models.DecimalField('元：向SUNRISE請求書金額', max_digits=12, decimal_places=0, null=True, blank=True)
    source_billed_to_client_amount = models.DecimalField('元：向客人請求金額', max_digits=12, decimal_places=0, null=True, blank=True)
    source_sunrise_invoice_amount = models.DecimalField('元：SUNRISE請求書金額', max_digits=12, decimal_places=0, null=True, blank=True)
    payment_status = models.CharField('支払状態', max_length=20, choices=PAYMENT_CHOICES, blank=True, default=PAYMENT_UNSET)
    payment_date = models.DateField('支払日', null=True, blank=True)
    transfer_status = models.CharField('振込状態', max_length=20, choices=TRANSFER_CHOICES, blank=True, default=TRANSFER_UNSET)
    note = models.TextField('備考', blank=True)
    # 取込元（将来の本取込用。第 1 版は dry-run のみで、この列に書くのは手入力でない場合だけ）
    source_file = models.CharField('取込元ファイル', max_length=255, blank=True)
    source_sheet = models.CharField('取込元シート', max_length=100, blank=True)
    source_row = models.PositiveIntegerField('取込元の行番号', null=True, blank=True)
    source_values = models.JSONField('取込元の原値', default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+', verbose_name='作成者')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+', verbose_name='更新者')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'real_estate_transactions'
        verbose_name = '不動産取引'
        verbose_name_plural = '不動産取引'
        ordering = ['-created_at', '-id']
        permissions = [
            ('use_real_estate', '不動産の利用（本人担当）'),
            ('real_estate_view_all', '不動産：全件閲覧'),
            ('real_estate_change_all', '不動産：全件変更'),
            ('manage_legal_ledger', '不動産：法定台帳のロック・更正・年度締め・出力'),
            ('manage_profit_distribution', '不動産：内部利益配分の閲覧・編集'),
        ]

    def __str__(self):
        return f'{self.transaction_number} {self.property_name} {self.room_number}'.strip()

    def save(self, *args, **kwargs):
        if not self.transaction_number:
            from .numbering import allocate_transaction_number

            self.transaction_number = allocate_transaction_number()
        super().save(*args, **kwargs)


class RealEstateNumberSequence(models.Model):
    key = models.CharField(max_length=20, unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'real_estate_number_sequences'


class TransactionParty(models.Model):
    ROLE_LESSOR = 'lessor'
    ROLE_LESSEE = 'lessee'
    ROLE_SELLER = 'seller'
    ROLE_BUYER = 'buyer'
    ROLE_AGENT = 'agent'
    ROLE_BROKER = 'broker'
    ROLE_CO_BROKER = 'co_broker'
    ROLE_CHOICES = (
        (ROLE_LESSOR, '貸主'), (ROLE_LESSEE, '借主'), (ROLE_SELLER, '売主'), (ROLE_BUYER, '買主'),
        (ROLE_AGENT, '代理人'), (ROLE_BROKER, '媒介業者'), (ROLE_CO_BROKER, '共同の宅建業者'),
    )

    transaction = models.ForeignKey(RealEstateTransaction, on_delete=models.CASCADE, related_name='parties')
    role = models.CharField('立場', max_length=20, choices=ROLE_CHOICES)
    name = models.CharField('氏名・名称', max_length=200)
    address = models.CharField('住所', max_length=300, blank=True)
    license_number = models.CharField('免許番号', max_length=100, blank=True)
    customer = models.ForeignKey('customers.Customer', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='real_estate_parties', verbose_name='顧客（参照）')
    company = models.ForeignKey('companies.Company', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='real_estate_parties', verbose_name='会社（参照）')
    note = models.CharField('備考', max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'real_estate_transaction_parties'
        ordering = ['id']


class LegalLedger(models.Model):
    """宅建業法の帳簿（取引ごと）。ロック後は更正でのみ変更し、物理削除しない。"""

    FORM_AGENCY = 'agency'
    FORM_BROKERAGE = 'brokerage'
    FORM_OWN = 'own'
    FORM_CHOICES = ((FORM_BROKERAGE, '媒介'), (FORM_AGENCY, '代理'), (FORM_OWN, '自ら当事者'))

    DEFAULT_RETENTION_YEARS = {RealEstateTransaction.TYPE_RENTAL: 5, RealEstateTransaction.TYPE_SALE: 5}

    transaction = models.OneToOneField(RealEstateTransaction, on_delete=models.PROTECT, related_name='legal_ledger')
    transaction_form = models.CharField('取引態様', max_length=20, choices=FORM_CHOICES, default=FORM_BROKERAGE)
    transaction_type = models.CharField('取引種別', max_length=10, choices=RealEstateTransaction.TYPE_CHOICES)
    property_location = models.CharField('所在地', max_length=300, blank=True)
    property_name = models.CharField('物件名', max_length=200, blank=True)
    room_number = models.CharField('部屋番号', max_length=50, blank=True)
    area_sqm = models.DecimalField('面積（㎡）', max_digits=9, decimal_places=2, null=True, blank=True)
    building_outline = models.TextField('建物の概要', blank=True)
    rent_or_price = models.DecimalField('賃料・価格', max_digits=12, decimal_places=0, null=True, blank=True)
    remuneration = models.DecimalField('報酬', max_digits=12, decimal_places=0, null=True, blank=True)
    advertising_fee = models.DecimalField('広告料', max_digits=12, decimal_places=0, null=True, blank=True)
    handling_fee = models.DecimalField('手数料', max_digits=12, decimal_places=0, null=True, blank=True)
    special_terms = models.TextField('特約', blank=True)
    contract_date = models.DateField('取引（契約）日', null=True, blank=True)
    fiscal_year = models.PositiveIntegerField('事業年度', null=True, blank=True)
    fiscal_year_closed_at = models.DateTimeField('年度締め日時', null=True, blank=True)
    retention_years = models.PositiveSmallIntegerField('保存年数', default=5)
    retention_until = models.DateField('保存期限', null=True, blank=True)
    legal_hold = models.BooleanField('legal hold（保存延長）', default=False)
    legal_hold_reason = models.CharField('legal hold の理由', max_length=300, blank=True)
    is_locked = models.BooleanField('ロック', default=False)
    locked_at = models.DateTimeField('ロック日時', null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='+', verbose_name='ロック者')
    locked_snapshot = models.JSONField('ロック時の内容', default=dict, blank=True)
    version = models.PositiveIntegerField('版', default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_legal_ledgers'
        ordering = ['-contract_date', '-id']


class LegalLedgerCorrection(models.Model):
    ledger = models.ForeignKey(LegalLedger, on_delete=models.PROTECT, related_name='corrections')
    version = models.PositiveIntegerField('更正後の版')
    changes = models.JSONField('変更内容', default=dict)
    reason = models.CharField('更正理由', max_length=500)
    corrected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    corrected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'real_estate_legal_ledger_corrections'
        ordering = ['-corrected_at', '-id']


def real_estate_upload_to(instance, filename):
    # 保存名は推測できない UUID（元のファイル名は file_name に保持）
    from django.utils import timezone

    ext = os.path.splitext(filename or '')[1].lower()[:10]
    return f'{REAL_ESTATE_FILE_SUBDIR}/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}{ext}'


REAL_ESTATE_FILE_SUBDIR = 'real_estate_files'


class RealEstateFile(models.Model):
    KIND_CHOICES = (
        ('brokerage_contract', '媒介契約書'), ('important_matters', '重要事項説明書'), ('contract', '契約書'),
        ('identity', '本人確認書類'), ('other', 'その他'),
    )

    transaction = models.ForeignKey(RealEstateTransaction, on_delete=models.CASCADE, related_name='files')
    kind = models.CharField('種類', max_length=30, choices=KIND_CHOICES, default='other')
    title = models.CharField('タイトル', max_length=200)
    file = models.FileField('ファイル', upload_to=real_estate_upload_to, max_length=255, blank=True)
    file_name = models.CharField('元のファイル名', max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField('サイズ', null=True, blank=True)
    mime_type = models.CharField('MIME', max_length=100, blank=True)
    sha256 = models.CharField('SHA-256', max_length=64, blank=True)
    # 既に案件の書類として登録済みのファイルを参照する場合（複製しない）
    document = models.ForeignKey('documents.Document', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='real_estate_refs', verbose_name='案件書類（参照）')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'real_estate_files'
        ordering = ['-created_at', '-id']


class RealEstateAccountingLink(models.Model):
    """会計側の記録への参照（会計データは複製しない）。"""

    transaction = models.ForeignKey(RealEstateTransaction, on_delete=models.CASCADE, related_name='accounting_links')
    income_source = models.ForeignKey('accounting.IncomeSource', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='real_estate_links')
    voucher = models.ForeignKey('accounting.AccountingVoucher', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='real_estate_links')
    note = models.CharField('備考', max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'real_estate_accounting_links'
        ordering = ['-id']


class InternalProfitDistribution(models.Model):
    """内部利益配分（法定台帳ではない）。manage_profit_distribution を持つ人だけが扱う。"""

    METHOD_FIXED = 'fixed'
    METHOD_RATIO = 'ratio'
    METHOD_CHOICES = ((METHOD_FIXED, '固定金額'), (METHOD_RATIO, '比率'))
    STATUS_DRAFT = 'draft'
    STATUS_SETTLED = 'settled'
    STATUS_CHOICES = ((STATUS_DRAFT, '草稿'), (STATUS_SETTLED, '結算済み'))

    transaction = models.ForeignKey(RealEstateTransaction, on_delete=models.CASCADE, related_name='profit_distributions')
    recipient_name = models.CharField('配分先', max_length=200)
    recipient_employee = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='+', verbose_name='配分先（担当者）')
    method = models.CharField('計算方法', max_length=10, choices=METHOD_CHOICES, default=METHOD_RATIO)
    base_amount = models.DecimalField('基準額', max_digits=12, decimal_places=0, default=0)
    ratio_percent = models.DecimalField('比率（％）', max_digits=6, decimal_places=2, null=True, blank=True)
    fixed_amount = models.DecimalField('固定金額', max_digits=12, decimal_places=0, null=True, blank=True)
    amount = models.DecimalField('配分金額', max_digits=12, decimal_places=0, default=0)
    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    settled_at = models.DateTimeField('結算日時', null=True, blank=True)
    note = models.TextField('備考', blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_profit_distributions'
        ordering = ['id']

    def compute_amount(self):
        if self.method == self.METHOD_FIXED:
            return Decimal(self.fixed_amount or 0)
        ratio = Decimal(self.ratio_percent or 0) / Decimal('100')
        return (Decimal(self.base_amount or 0) * ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        self.amount = self.compute_amount()
        super().save(*args, **kwargs)
