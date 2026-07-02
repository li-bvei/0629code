from django.db import models

from apps.customers.models import Customer


class Company(models.Model):
    name = models.CharField(max_length=150)
    name_kana = models.CharField('会社名フリガナ', max_length=150, blank=True)
    representative_customer = models.ForeignKey(
        Customer,
        verbose_name='代表者顧客',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='representative_companies',
    )
    representative_name = models.CharField('代表者氏名', max_length=100, blank=True)
    representative_name_kana = models.CharField('代表者フリガナ', max_length=100, blank=True)
    corporate_number = models.CharField(max_length=30, blank=True)
    corporate_registration_number = models.CharField('会社法人等番号', max_length=20, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    postal_code = models.CharField('郵便番号', max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    fiscal_month = models.CharField('決算月', max_length=2, blank=True)
    bank_name = models.CharField('銀行名', max_length=100, blank=True)
    bank_branch = models.CharField('支店名', max_length=100, blank=True)
    bank_account_type = models.CharField('預金種別', max_length=20, blank=True)
    bank_account_number = models.CharField('口座番号', max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'companies'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.corporate_number and len(self.corporate_number) == 13 and self.corporate_number.isdigit():
            self.corporate_registration_number = self.corporate_number[1:]
        else:
            self.corporate_registration_number = ''
        super().save(*args, **kwargs)


class CompanyStaff(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='staff_members',
    )
    name = models.CharField(max_length=100)
    name_kana = models.CharField('フリガナ', max_length=100, blank=True)
    position = models.CharField('役職', max_length=100, blank=True)
    birth_date = models.DateField('生年月日', null=True, blank=True)
    gender = models.CharField('性別', max_length=20, blank=True)
    nationality = models.CharField('国籍', max_length=100, blank=True)
    residence_status = models.CharField('在留資格', max_length=100, blank=True)
    residence_card_no = models.CharField('在留カード番号', max_length=50, blank=True)
    residence_expiry = models.DateField('在留期限', null=True, blank=True)
    passport_no = models.CharField('パスポート番号', max_length=50, blank=True)
    passport_expiry = models.DateField('パスポート期限', null=True, blank=True)
    phone = models.CharField('電話番号', max_length=30, blank=True)
    email = models.EmailField('メール', blank=True)
    postal_code = models.CharField('郵便番号', max_length=20, blank=True)
    address = models.CharField('住所', max_length=255, blank=True)
    my_number = models.CharField('マイナンバー', max_length=30, blank=True)
    employment_start_date = models.DateField('入社日', null=True, blank=True)
    employment_end_date = models.DateField('退社日', null=True, blank=True)
    note = models.TextField('備考', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_staff'
        ordering = ['company', 'name']

    def __str__(self):
        return f'{self.company.name} - {self.name}'
