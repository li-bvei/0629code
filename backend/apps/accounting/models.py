from django.db import models


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
