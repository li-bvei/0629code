from django.conf import settings
from django.db import models
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from apps.cases.models import Case
from apps.companies.models import Company
from apps.customers.models import Customer
from apps.employees.models import Employee
from .voucher_calculations import calculate_voucher_amounts


class ExpenseCategory(models.Model):
    name = models.CharField('カテゴリ名', max_length=50, unique=True)
    is_active = models.BooleanField('有効', default=True)
    sort_order = models.PositiveIntegerField('並び順', default=0)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_expense_categories'
        permissions = [
            ('manage_expense_category', '支出カテゴリの登録・変更（業務権限）'),
        ]
        verbose_name = '支出カテゴリ'
        verbose_name_plural = '支出カテゴリ'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class ExpenseCategorySuggestionRule(models.Model):
    """場所などの文字からカテゴリを提案する規則（提案だけ。保存値は利用者が確定した文字列）。

    owner が空の規則は事務所共通、owner がある規則はその利用者本人の提案にだけ使う。
    規則の一覧・編集・削除・事務所共通への昇格は manage_expense_category を持つ人だけ。支出の入力者は、
    自分が確定した「場所 → カテゴリ」を明示的に記憶させた場合に限り、本人用の規則を 1 件追加できる
    （category_suggestions.remember_place_rule）。具体的な場所名を他の利用者の提案に混ぜない。
    """

    FIELD_PLACE = 'place'
    FIELD_TARGET = 'expense_target'
    FIELD_NOTE = 'note'
    FIELD_CHOICES = ((FIELD_PLACE, '場所'), (FIELD_TARGET, '費用対象'), (FIELD_NOTE, '備考'))

    SOURCE_SEED = 'seed'
    SOURCE_MANUAL = 'manual'
    SOURCE_CONFIRMED = 'user_confirmed'
    SOURCE_CHOICES = ((SOURCE_SEED, '初期規則'), (SOURCE_MANUAL, '管理者が登録'), (SOURCE_CONFIRMED, '入力時に記憶'))

    pattern = models.CharField('文字', max_length=100)
    # 表記ゆれを吸収した照合用キー（category_suggestions.normalize_key）。保存時に必ず再計算する。
    pattern_key = models.CharField('照合キー', max_length=100, editable=False)
    match_field = models.CharField('対象項目', max_length=20, choices=FIELD_CHOICES, default=FIELD_PLACE)
    expense_category = models.ForeignKey(ExpenseCategory, verbose_name='提案するカテゴリ', on_delete=models.CASCADE,
                                         related_name='suggestion_rules')
    priority = models.IntegerField('優先度', default=0)
    is_active = models.BooleanField('有効', default=True)
    source = models.CharField('登録元', max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    # 空＝事務所共通。値あり＝その利用者だけの規則（利用者を削除したら規則も消す。共通へは自動で広げない）
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='本人用の利用者', on_delete=models.CASCADE,
                              null=True, blank=True, related_name='expense_category_rules')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='作成者', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='最終更新者', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='+')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_expense_category_rules'
        verbose_name = '支出カテゴリの提案規則'
        verbose_name_plural = '支出カテゴリの提案規則'
        ordering = ['-priority', 'id']
        constraints = [
            # 同じ範囲（本人用は利用者ごと）で、同じ項目・同じ文字から別々のカテゴリを提案しない。
            # 事務所共通（owner が空）の重複は NULL が一意制約に掛からないため、シリアライザと昇格処理で防ぐ。
            models.UniqueConstraint(fields=['owner', 'match_field', 'pattern_key'],
                                    name='uniq_expense_category_rule_pattern'),
        ]

    def __str__(self):
        return f'{self.get_match_field_display()}「{self.pattern}」→ {self.expense_category}'

    def save(self, *args, **kwargs):
        from .category_suggestions import normalize_key

        self.pattern = (self.pattern or '').strip()
        self.pattern_key = normalize_key(self.pattern)
        super().save(*args, **kwargs)


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
    # データの所有者（報銷の本人）。業務データの分離はこの値で判定する。新規作成時は
    # 後端が必ずリクエストユーザーを設定し、フロントからの指定は受け付けない。
    # 既存データは管理コマンド backfill_expense_owner（既定 dry-run）で後から設定する。
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='所有者',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='owned_expenses',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='作成者',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_expenses',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='最終更新者',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_expenses',
    )
    # 任意の関連（P2）：顧客・会社・案件。関連付けは BusinessAccessPolicy で検査し、
    # 案件への関連付けは案件の Timeline に「関連付けた事実」だけを残す（会計データは会計側）。
    customer = models.ForeignKey(
        'customers.Customer', verbose_name='関連顧客', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    company = models.ForeignKey(
        'companies.Company', verbose_name='関連会社', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    case = models.ForeignKey(
        'cases.Case', verbose_name='関連案件', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_expenses'
        permissions = [
            ('use_expense', '支出記録（本人分）の利用'),
            ('expense_view_all', '他人の支出記録の閲覧（読み取り専用）'),
            ('expense_change_all', '他人の支出記録の変更・削除'),
            ('expense_export_all', '他人の支出記録を含むExcel出力'),
        ]
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
    # 任意の関連（P2）：顧客・会社・案件。関連付けは BusinessAccessPolicy で検査し、
    # 案件への関連付けは案件の Timeline に「関連付けた事実」だけを残す（会計データは会計側）。
    customer = models.ForeignKey(
        'customers.Customer', verbose_name='関連顧客', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    company = models.ForeignKey(
        'companies.Company', verbose_name='関連会社', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    case = models.ForeignKey(
        'cases.Case', verbose_name='関連案件', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_income_sources'
        permissions = [
            ('use_income', '収入元の利用'),
        ]
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
        permissions = [
            ('use_vehicle', '車両使用記録の利用'),
        ]
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
        permissions = [
            ('use_project', 'プロジェクト収支の利用'),
        ]
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


class ServiceItem(models.Model):
    """サービス価格マスタ（P4）。見積書・請求書の明細と新規受付で選ぶ。

    - 委託底価（floor_price）は外部専門家への基本費用で、対客報価とは別。閲覧・変更は
      accounting.view_service_floor_price を持つ人だけ（serializer が項目自体を出さない）。
    - 帳票・案件は選んだ時点の内容をスナップショットとして持つため、ここを変えても過去の帳票は変わらない。
    - 使われた項目は物理削除できない（first_used_at）。不要になったら無効化する。
    """

    PROFESSIONAL_GYOUSEI = 'gyousei'
    PROFESSIONAL_TAX_ACCOUNTANT = 'tax_accountant'
    PROFESSIONAL_JUDICIAL_SCRIVENER = 'judicial_scrivener'
    PROFESSIONAL_LABOR_CONSULTANT = 'labor_consultant'
    PROFESSIONAL_OTHER = 'other'
    PROFESSIONAL_TYPE_CHOICES = (
        ('', 'なし'),
        (PROFESSIONAL_GYOUSEI, '行政書士'),
        (PROFESSIONAL_TAX_ACCOUNTANT, '税理士'),
        (PROFESSIONAL_JUDICIAL_SCRIVENER, '司法書士'),
        (PROFESSIONAL_LABOR_CONSULTANT, '社会保険労務士'),
        (PROFESSIONAL_OTHER, 'その他'),
    )
    TAX_CATEGORY_CHOICES = (
        ('tax_10', '10％'),
        ('tax_8', '8％'),
        ('non_taxable', '非課税'),
    )
    PRICE_TYPE_CHOICES = (
        ('tax_included', '税込'),
        ('tax_excluded', '税抜'),
    )

    PRICE_PROVISIONAL = 'provisional'
    PRICE_CONFIRMED = 'confirmed'
    PRICE_STATUS_CHOICES = ((PRICE_PROVISIONAL, '暫定価格'), (PRICE_CONFIRMED, '確定価格'))

    # P6：初期登録などに使う安定した識別子（名称で同一判定しない）。手作業の項目は空でよい
    code = models.SlugField('コード', max_length=60, unique=True, null=True, blank=True)
    category = models.CharField('分類', max_length=100, blank=True)
    name = models.CharField('項目名', max_length=255)
    default_price = models.DecimalField('対客標準価格', max_digits=12, decimal_places=0, null=True, blank=True)
    # P6：価格の状態。暫定のまま帳票・受付に使えるが、画面に明示し、発行前に確認を求める
    price_status = models.CharField('価格の状態', max_length=20, choices=PRICE_STATUS_CHOICES, default=PRICE_PROVISIONAL)
    price_confirmed_at = models.DateTimeField('価格確定日時', null=True, blank=True)
    price_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='価格確定者',
    )
    price_type = models.CharField('価格の税区分', max_length=20, choices=PRICE_TYPE_CHOICES, default='tax_included')
    floor_price = models.DecimalField('委託底価', max_digits=12, decimal_places=0, null=True, blank=True)
    professional_type = models.CharField('委託専門家', max_length=30, choices=PROFESSIONAL_TYPE_CHOICES, blank=True)
    tax_category = models.CharField('税区分', max_length=20, choices=TAX_CATEGORY_CHOICES, default='tax_10')
    unit = models.CharField('単位', max_length=20, blank=True)
    is_active = models.BooleanField('有効', default=True)
    note = models.TextField('社内メモ', blank=True)
    sort_order = models.PositiveIntegerField('並び順', default=0)
    first_used_at = models.DateTimeField('初回使用日時', null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='作成者',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='更新者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_service_items'
        permissions = [
            ('use_service_item', 'サービス項目の閲覧・選択'),
            ('manage_service_item', 'サービス項目の登録・変更'),
            ('view_service_floor_price', '委託底価の閲覧・変更'),
        ]
        verbose_name = 'サービス項目'
        verbose_name_plural = 'サービス項目'
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

    HONORIFIC_ONCHU = '御中'
    HONORIFIC_SAMA = '様'
    HONORIFIC_NONE = ''
    HONORIFIC_CHOICES = (
        (HONORIFIC_ONCHU, '御中'),
        (HONORIFIC_SAMA, '様'),
        (HONORIFIC_NONE, 'なし'),
    )

    voucher_type = models.CharField('帳票種別', max_length=20, choices=VOUCHER_TYPE_CHOICES)
    voucher_number = models.CharField('帳票番号', max_length=50, unique=True, blank=True)
    issue_date = models.DateField('発行日')
    recipient_name = models.CharField('宛先会社名', max_length=255, blank=True)
    recipient_honorific = models.CharField(
        '敬称', max_length=10, choices=HONORIFIC_CHOICES, default=HONORIFIC_ONCHU, blank=True,
    )
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
    # P2-C11：請求書と領収書は状態を共有しない。列も選択肢も別に持ち、自分の種別の列だけを使う。
    # 既存行は空（状態未設定＝旧データ）のまま残し、一括で書き換えない。
    INVOICE_STATUS_DRAFT = 'draft'
    INVOICE_STATUS_ISSUED = 'issued'
    INVOICE_STATUS_SENT = 'sent'
    INVOICE_STATUS_PAID = 'paid'
    INVOICE_STATUS_CANCELLED = 'cancelled'
    INVOICE_STATUS_CHOICES = (
        (INVOICE_STATUS_DRAFT, '下書き'),
        (INVOICE_STATUS_ISSUED, '発行済み'),
        (INVOICE_STATUS_SENT, '送付済み'),
        (INVOICE_STATUS_PAID, '入金済み'),
        (INVOICE_STATUS_CANCELLED, '取消'),
    )
    RECEIPT_STATUS_DRAFT = 'draft'
    RECEIPT_STATUS_ISSUED = 'issued'
    RECEIPT_STATUS_VOIDED = 'voided'
    RECEIPT_STATUS_CHOICES = (
        (RECEIPT_STATUS_DRAFT, '下書き'),
        (RECEIPT_STATUS_ISSUED, '発行済み'),
        (RECEIPT_STATUS_VOIDED, '無効'),
    )
    invoice_status = models.CharField('請求書の状態', max_length=20, choices=INVOICE_STATUS_CHOICES, blank=True, default='')
    receipt_status = models.CharField('領収書の状態', max_length=20, choices=RECEIPT_STATUS_CHOICES, blank=True, default='')
    paid_date = models.DateField('入金日', null=True, blank=True)
    status_changed_at = models.DateTimeField('状態変更日時', null=True, blank=True)
    issued_snapshot = models.JSONField('発行時の金額スナップショット', default=dict, blank=True)
    # P4：サービス項目を選んだ明細行の委託底価スナップショット（line_key で行に対応）。社内用で、
    # serializer は底価権限者にだけ返す。発行スナップショット・状態履歴・PDF・検索には含めない。
    internal_line_costs = models.JSONField('明細の委託底価（社内）', default=list, blank=True)
    source_estimate = models.ForeignKey(
        'accounting.Estimate', verbose_name='元の見積書', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vouchers',
    )
    source_contract = models.ForeignKey(
        'accounting.Contract', verbose_name='元の契約書', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vouchers',
    )
    source_invoice = models.ForeignKey(
        'self', verbose_name='元の請求書', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='receipts',
    )
    customer = models.ForeignKey(
        'customers.Customer', verbose_name='関連顧客', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    company = models.ForeignKey(
        'companies.Company', verbose_name='関連会社', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    case = models.ForeignKey(
        'cases.Case', verbose_name='関連案件', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='accounting_vouchers',
        verbose_name='作成者',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='更新者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_vouchers'
        permissions = [
            ('use_voucher', '請求書・領収書の利用'),
        ]
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
            _, summary = calculate_voucher_amounts(self.line_items)
            self.amount = summary['subtotal']
            self.tax_amount = summary['tax_total']
            self.total_amount = summary['total']
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
        return calculate_voucher_amounts(items)[0]

    def generate_voucher_number(self):
        # 形式（INV/REC-YYYYMMDD-NNNN）は従来どおり。採番は共通の連番表で排他制御する。
        from .voucher_infra import allocate_number

        prefix = 'INV' if self.voucher_type == self.VOUCHER_TYPE_INVOICE else 'REC'
        return allocate_number(prefix, self.issue_date, AccountingVoucher, 'voucher_number')

    @property
    def status_field(self):
        return 'invoice_status' if self.voucher_type == self.VOUCHER_TYPE_INVOICE else 'receipt_status'

    @property
    def number(self):
        return self.voucher_number


class DocumentNumberSequence(models.Model):
    """帳票番号の連番（共通基盤）。キーは「接頭辞-発行日」。各帳票の番号規則は帳票ごとに別。"""

    key = models.CharField('キー', max_length=40, unique=True)
    last_number = models.PositiveIntegerField('最終番号', default=0)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_document_number_sequences'
        verbose_name = '帳票番号の連番'
        verbose_name_plural = '帳票番号の連番'

    def __str__(self):
        return f'{self.key}: {self.last_number}'


class BusinessDocumentFields(models.Model):
    """見積書・契約書が共有する「宛先・発行者・金額・関連」の列（抽象）。状態と番号規則は各帳票で定義する。"""

    HONORIFIC_CHOICES = AccountingVoucher.HONORIFIC_CHOICES

    issue_date = models.DateField('発行日')
    recipient_name = models.CharField('宛先', max_length=255, blank=True)
    recipient_honorific = models.CharField('敬称', max_length=10, choices=HONORIFIC_CHOICES, default='御中', blank=True)
    recipient_postal_code = models.CharField('宛先郵便番号', max_length=20, blank=True)
    recipient_address = models.TextField('宛先住所', blank=True)
    title = models.CharField('件名', max_length=255, blank=True)
    line_items = models.JSONField('明細行', default=list, blank=True)
    amount = models.DecimalField('小計（税抜）', max_digits=12, decimal_places=0, default=0)
    tax_amount = models.DecimalField('消費税額', max_digits=12, decimal_places=0, default=0)
    total_amount = models.DecimalField('合計金額', max_digits=12, decimal_places=0, default=0)
    note = models.TextField('備考', blank=True)
    issuer_name = models.CharField('発行者名', max_length=255, default='SUNRISE日晟鴻達株式会社')
    issuer_postal_code = models.CharField('発行者郵便番号', max_length=20, blank=True)
    issuer_address = models.TextField('発行者住所', blank=True)
    issuer_tel = models.CharField('発行者電話番号', max_length=50, blank=True)
    issuer_registration_number = models.CharField('登録番号', max_length=100, blank=True)
    status_changed_at = models.DateTimeField('状態変更日時', null=True, blank=True)
    issued_snapshot = models.JSONField('発行時の金額スナップショット', default=dict, blank=True)
    customer = models.ForeignKey(
        'customers.Customer', verbose_name='関連顧客', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    company = models.ForeignKey(
        'companies.Company', verbose_name='関連会社', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    case = models.ForeignKey(
        'cases.Case', verbose_name='関連案件', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='%(class)s_links',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='作成者',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='更新者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    NUMBER_PREFIX = ''
    NUMBER_FIELD = ''

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        normalized, summary = calculate_voucher_amounts(self.line_items)
        self.line_items = normalized
        self.amount = summary['subtotal']
        self.tax_amount = summary['tax_total']
        self.total_amount = summary['total']
        if not getattr(self, self.NUMBER_FIELD):
            from .voucher_infra import allocate_number

            setattr(self, self.NUMBER_FIELD,
                    allocate_number(self.NUMBER_PREFIX, self.issue_date, type(self), self.NUMBER_FIELD))
        super().save(*args, **kwargs)

    @property
    def number(self):
        return getattr(self, self.NUMBER_FIELD)


class Estimate(BusinessDocumentFields):
    """見積書。受注・失注は見積書自身の状態で、契約書・請求書の状態には連動しない。"""

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_ACCEPTED = 'accepted'
    STATUS_DECLINED = 'declined'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '下書き'),
        (STATUS_SUBMITTED, '提出済み'),
        (STATUS_ACCEPTED, '受注'),
        (STATUS_DECLINED, '失注'),
        (STATUS_CANCELLED, '取消'),
    )
    NUMBER_PREFIX = 'EST'
    NUMBER_FIELD = 'estimate_number'

    estimate_number = models.CharField('見積番号', max_length=50, unique=True, blank=True)
    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    valid_until = models.DateField('有効期限', null=True, blank=True)
    # P4：請求書と同じ（明細の委託底価スナップショット。社内用）
    internal_line_costs = models.JSONField('明細の委託底価（社内）', default=list, blank=True)

    class Meta:
        db_table = 'accounting_estimates'
        permissions = [('use_estimate', '見積書の利用')]
        verbose_name = '見積書'
        verbose_name_plural = '見積書'
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return f'見積書 {self.estimate_number}'


class Contract(BusinessDocumentFields):
    """契約書。送付・締結・終了は契約書自身の状態。報酬額は明細行で持つ。"""

    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_SIGNED = 'signed'
    STATUS_TERMINATED = 'terminated'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '下書き'),
        (STATUS_SENT, '送付済み'),
        (STATUS_SIGNED, '締結済み'),
        (STATUS_TERMINATED, '終了'),
        (STATUS_CANCELLED, '取消'),
    )
    NUMBER_PREFIX = 'CON'
    NUMBER_FIELD = 'contract_number'

    contract_number = models.CharField('契約番号', max_length=50, unique=True, blank=True)
    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    start_date = models.DateField('契約開始日', null=True, blank=True)
    end_date = models.DateField('契約終了日', null=True, blank=True)
    payment_terms = models.TextField('支払条件', blank=True)
    body = models.TextField('契約条項', blank=True)
    signed_date = models.DateField('締結日', null=True, blank=True)
    source_estimate = models.ForeignKey(
        Estimate, verbose_name='元の見積書', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contracts',
    )

    class Meta:
        db_table = 'accounting_contracts'
        permissions = [('use_contract', '契約書の利用')]
        verbose_name = '契約書'
        verbose_name_plural = '契約書'
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return f'契約書 {self.contract_number}'


class VoucherStatusHistory(models.Model):
    """請求書・領収書の状態変更の履歴（追記のみ。API からの変更・削除は無い）。

    変更前後の状態・操作者・時刻と、その時点の帳票内容のスナップショットを残す。下書きに戻して
    再発行した場合も、以前の発行内容はこの履歴から追跡できる（version は発行の通し番号）。
    帳票が削除されても履歴は残す（番号・種別を写して保持する）。
    """

    voucher = models.ForeignKey(
        'AccountingVoucher', null=True, blank=True, on_delete=models.SET_NULL, related_name='status_history',
        verbose_name='帳票',
    )
    document_kind = models.CharField('帳票種別', max_length=20)  # invoice / receipt
    voucher_number = models.CharField('帳票番号', max_length=50, blank=True)
    from_status = models.CharField('変更前の状態', max_length=20, blank=True)
    to_status = models.CharField('変更後の状態', max_length=20)
    version = models.PositiveIntegerField('発行の版', default=0)
    snapshot = models.JSONField('変更時の帳票内容', default=dict, blank=True)
    reason = models.CharField('理由・メモ', max_length=500, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='操作者',
    )
    changed_at = models.DateTimeField('変更日時', auto_now_add=True)

    class Meta:
        db_table = 'accounting_voucher_status_history'
        verbose_name = '請求書・領収書の状態履歴'
        verbose_name_plural = '請求書・領収書の状態履歴'
        ordering = ['-changed_at', '-id']

    def __str__(self):
        return f'{self.voucher_number} {self.from_status or "-"} → {self.to_status}'


class IssuedLineCostSnapshot(models.Model):
    """発行ごとの委託底価スナップショット（P4。追記のみ）。

    見積書・請求書が下書きを離れて発行されるたびに、その時点の internal_line_costs を版ごとに残す。
    下書きに戻して改価・再発行しても、以前の版の底価を追跡できる。帳票が削除されても残す。
    底価権限者向けの API（internal-costs）からだけ読む。状態履歴・発行スナップショットには入れない。
    """

    document_kind = models.CharField('帳票種別', max_length=20)  # estimate / invoice
    document_id = models.PositiveBigIntegerField('帳票 ID')
    document_number = models.CharField('帳票番号', max_length=50, blank=True)
    version = models.PositiveIntegerField('版')
    status_history = models.ForeignKey(
        VoucherStatusHistory, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='対応する状態履歴',
    )
    line_costs = models.JSONField('明細の委託底価', default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='発行者',
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        db_table = 'accounting_issued_line_cost_snapshots'
        verbose_name = '発行時の委託底価'
        verbose_name_plural = '発行時の委託底価'
        ordering = ['document_kind', 'document_id', 'version']
        constraints = [
            models.UniqueConstraint(fields=['document_kind', 'document_id', 'version'], name='uniq_issued_line_cost_version'),
        ]

    def __str__(self):
        return f'{self.document_number} v{self.version}'


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
    # 主流程で選んだ在日担保人テンプレート（P1・2026-10）。スナップショットは選択時のテンプレート内容。
    guarantor_template = models.ForeignKey(
        'VisaGuarantorTemplate', null=True, blank=True, on_delete=models.SET_NULL, related_name='applications',
        verbose_name='使用した担保人テンプレート',
    )
    form_data = models.JSONField('表单数据', default=dict, blank=True)
    note = models.TextField('備考', blank=True)
    # CSV/XLSX 一括取込で作られた場合の取込元（P2）
    import_batch = models.ForeignKey(
        'VisaImportBatch', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='applications', verbose_name='取込バッチ',
    )
    import_row_number = models.PositiveIntegerField('取込元の行番号', null=True, blank=True)
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
        permissions = [
            ('use_visa', '返签visa表の利用'),
        ]
        verbose_name = '返签visa表'
        verbose_name_plural = '返签visa表'
        ordering = ['-created_at']

    def __str__(self):
        return self.applicant_name or f'返签visa表 {self.pk}'


class VisaImportBatch(models.Model):
    """返签 visa 表の CSV/XLSX 一括取込の記録（重複取込の検出・再試行・監査の単位）。

    行データの本体は保存しない。結果（行番号・状態・作成した申請 ID・誤り）だけを残す。
    誤り行は利用者が修正できるよう、項目名・誤り内容・元の値を errors に保持する。
    """

    MODE_VALID_ONLY = 'valid_only'
    MODE_ALL_OR_NOTHING = 'all_or_nothing'
    MODE_CHOICES = [
        (MODE_VALID_ONLY, '有効な行だけ作成し、誤り行は報告'),
        (MODE_ALL_OR_NOTHING, 'すべて正しい場合だけ作成'),
    ]
    STATUS_PARSED = 'parsed'
    STATUS_PARTIAL = 'partial'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_PARSED, '読込済み'),
        (STATUS_PARTIAL, '一部作成'),
        (STATUS_COMPLETED, '作成完了'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='visa_import_batches', verbose_name='作成者',
    )
    file_name = models.CharField('ファイル名', max_length=255)
    file_sha256 = models.CharField('ファイルハッシュ', max_length=64, db_index=True)
    sheet_name = models.CharField('シート名', max_length=100, blank=True)
    encoding = models.CharField('文字コード', max_length=30, blank=True)
    column_mapping = models.JSONField('列の対応付け', default=dict, blank=True)
    mode = models.CharField('作成方式', max_length=20, choices=MODE_CHOICES, default=MODE_VALID_ONLY)
    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default=STATUS_PARSED)
    row_count = models.PositiveIntegerField('行数', default=0)
    success_count = models.PositiveIntegerField('作成件数', default=0)
    error_count = models.PositiveIntegerField('誤り件数', default=0)
    skipped_count = models.PositiveIntegerField('重複スキップ件数', default=0)
    results = models.JSONField('行ごとの結果', default=dict, blank=True)
    committed_request_ids = models.JSONField('処理済み request_id', default=list, blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        db_table = 'accounting_visa_import_batches'
        verbose_name = '返签visa表 一括取込'
        verbose_name_plural = '返签visa表 一括取込'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.file_name} ({self.created_at:%Y-%m-%d})'


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


def visa_pdf_upload_to(instance, filename):
    import uuid

    from django.utils import timezone

    return f'visa_return_pdfs/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}.pdf'


class VisaReturnPdfGeneration(models.Model):
    """返签 visa 表 PDF の生成記録（成功・失敗とも残す）。

    ダウンロードは成功し、ファイルが実在する記録からだけ行う。使ったテンプレートの版（ファイルの
    SHA-256）と生成方式（フォーム入力／座標描画）、担保人テンプレートを記録して失敗を追跡できるようにする。
    """

    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = ((STATUS_SUCCESS, '成功'), (STATUS_FAILED, '失敗'))
    METHOD_FORM = 'form'
    METHOD_COORDINATES = 'coordinates'
    METHOD_CHOICES = ((METHOD_FORM, 'フォーム項目へ入力'), (METHOD_COORDINATES, '座標へ描画'))

    application = models.ForeignKey(
        VisaReturnApplication, on_delete=models.CASCADE, related_name='pdf_generations', verbose_name='申請',
    )
    status = models.CharField('結果', max_length=10, choices=STATUS_CHOICES)
    method = models.CharField('生成方式', max_length=20, choices=METHOD_CHOICES, blank=True)
    template_name = models.CharField('PDF テンプレート', max_length=100, blank=True)
    template_version = models.CharField('PDF テンプレートの版', max_length=64, blank=True)
    guarantor_template = models.ForeignKey(
        'VisaGuarantorTemplate', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='担保人テンプレート',
    )
    guarantor_template_version = models.CharField('担保人テンプレートの版', max_length=40, blank=True)
    file = models.FileField('PDF', upload_to=visa_pdf_upload_to, max_length=255, blank=True)
    file_sha256 = models.CharField('SHA-256', max_length=64, blank=True)
    file_size = models.PositiveIntegerField('サイズ', null=True, blank=True)
    error_code = models.CharField('エラー種別', max_length=40, blank=True)
    error_message = models.TextField('エラー内容', blank=True)
    details = models.JSONField('詳細', default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='生成者',
    )
    created_at = models.DateTimeField('生成日時', auto_now_add=True)

    class Meta:
        db_table = 'accounting_visa_return_pdf_generations'
        verbose_name = '返签visa表 PDF 生成記録'
        verbose_name_plural = '返签visa表 PDF 生成記録'
        ordering = ['-created_at', '-id']


class SeifuNoticePdfRecord(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = (
        (STATUS_DRAFT, '下書き'),
        (STATUS_COMPLETED, '完了'),
    )

    title = models.CharField('记录名称', max_length=255)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    # P5: 従原来可任意改坐标的 text_items 迁移到固定栏位。新列保持可空，
    # 使未部署 P5 的旧代码仍可以向这张表 INSERT，也不要求回填旧记录。
    recipient_name = models.CharField('宛名', max_length=100, blank=True, null=True)
    permit_number = models.CharField('許可番号', max_length=30, blank=True, null=True)
    issue_date = models.DateField('通知日', blank=True, null=True)
    template_key = models.CharField('テンプレート', max_length=60, blank=True, null=True)
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
        permissions = [
            ('use_seifu', '清風合格通知書の利用'),
        ]
        verbose_name = '清風合格通知書记录'
        verbose_name_plural = '清風合格通知書记录'
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return self.title


def seifu_pdf_upload_to(instance, filename):
    import uuid

    from django.utils import timezone

    return f'seifu_notice_pdfs/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}.pdf'


class SeifuNoticePdfGeneration(models.Model):
    """清風合格通知書 PDF の生成記録（P5。成功だけを記録する）。

    PDF を検証し、保存先に書き込んで実在とサイズを確かめてから作る。失敗は監査ログにだけ残し、記録・ファイルを
    残さない。ダウンロードは成功し、ファイルが実在する記録からだけ行う。記録を消しても生成記録は残す（SET_NULL）。
    request_id は画面の 1 回の操作ごとの識別子で、二重送信のときは同じ生成結果を返す。
    """

    STATUS_SUCCESS = 'success'
    STATUS_CHOICES = ((STATUS_SUCCESS, '成功'),)

    record = models.ForeignKey(
        SeifuNoticePdfRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name='generations',
        verbose_name='記録',
    )
    status = models.CharField('結果', max_length=10, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    request_id = models.CharField('操作 ID', max_length=64, unique=True, null=True, blank=True)
    recipient_name = models.CharField('宛名', max_length=100)
    permit_number = models.CharField('許可番号', max_length=30)
    notice_number = models.CharField('通知書番号', max_length=40)
    issue_date = models.DateField('通知日')
    template_key = models.CharField('テンプレート', max_length=60)
    template_version = models.CharField('テンプレートの版', max_length=64)
    font_version = models.CharField('字体の版', max_length=64)
    method = models.CharField('生成方式', max_length=30)
    file = models.FileField('PDF', upload_to=seifu_pdf_upload_to, max_length=255)
    file_sha256 = models.CharField('SHA-256', max_length=64)
    file_size = models.PositiveIntegerField('サイズ')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        verbose_name='生成者',
    )
    created_at = models.DateTimeField('生成日時', auto_now_add=True)

    class Meta:
        db_table = 'accounting_seifu_notice_pdf_generations'
        verbose_name = '清風合格通知書 PDF 生成記録'
        verbose_name_plural = '清風合格通知書 PDF 生成記録'
        ordering = ['-created_at', '-id']


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
    case = models.ForeignKey(
        Case,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tax_renewal_voucher_records',
        verbose_name='案件',
        help_text='選択すると、その案件の顧客・会社・担当者を自動的に反映できる。',
    )
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
        permissions = [
            ('use_tax_renewal', '税務証明更新用の利用'),
        ]
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
