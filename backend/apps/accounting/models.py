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
