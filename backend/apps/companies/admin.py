from django.contrib import admin

from .models import Company, CompanyStaff


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'name_kana',
        'representative_customer',
        'representative_name',
        'representative_name_kana',
        'corporate_number',
        'corporate_registration_number',
        'phone',
        'postal_code',
        'updated_at',
    )
    search_fields = (
        'name',
        'name_kana',
        'representative_customer__name',
        'representative_name',
        'representative_name_kana',
        'corporate_number',
        'corporate_registration_number',
        'email',
        'phone',
        'postal_code',
    )
    autocomplete_fields = ('representative_customer',)
    readonly_fields = ('corporate_registration_number', 'created_at', 'updated_at')


@admin.register(CompanyStaff)
class CompanyStaffAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'name_kana',
        'company',
        'position',
        'nationality',
        'residence_status',
        'residence_expiry',
        'employment_start_date',
        'updated_at',
    )
    search_fields = (
        'name',
        'name_kana',
        'company__name',
        'position',
        'phone',
        'email',
        'residence_card_no',
        'passport_no',
    )
    list_filter = ('gender', 'nationality', 'residence_status')
    autocomplete_fields = ('company',)
    readonly_fields = ('created_at', 'updated_at')
