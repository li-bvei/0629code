from django.contrib import admin

from .models import (
    AccountingProject,
    AccountingProjectExpense,
    AccountingProjectIncome,
    AccountingVoucher,
    Expense,
    ExpenseCategory,
    IncomeSource,
    SeifuNoticePdfRecord,
    TaxRenewalAgentTemplate,
    TaxRenewalVoucherRecord,
    VehicleUsage,
    VisaGuarantorTemplate,
    VisaReturnApplication,
    VoucherItemTemplate,
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'sort_order', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'expense_date',
        'category',
        'amount',
        'payment_method',
        'expense_target',
        'is_reimbursed',
        'is_exported',
        'created_at',
    )
    list_filter = ('category', 'payment_method', 'is_reimbursed', 'is_exported', 'expense_date')
    search_fields = ('place', 'category', 'payment_method', 'expense_target', 'note')
    date_hierarchy = 'expense_date'


@admin.register(IncomeSource)
class IncomeSourceAdmin(admin.ModelAdmin):
    list_display = ('source_date', 'source_target', 'amount', 'is_exported', 'created_at')
    list_filter = ('is_exported', 'source_date')
    search_fields = ('source_target', 'note')
    date_hierarchy = 'source_date'


@admin.register(VehicleUsage)
class VehicleUsageAdmin(admin.ModelAdmin):
    list_display = (
        'usage_date',
        'place',
        'distance_km',
        'usage_target',
        'purpose',
        'is_exported',
        'created_at',
    )
    list_filter = ('purpose', 'is_exported', 'usage_date')
    search_fields = ('place', 'usage_target', 'purpose', 'note')
    date_hierarchy = 'usage_date'


@admin.register(AccountingProject)
class AccountingProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active', 'created_at')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'note')


@admin.register(AccountingProjectIncome)
class AccountingProjectIncomeAdmin(admin.ModelAdmin):
    list_display = ('project', 'income_date', 'income_target', 'amount', 'created_at')
    list_filter = ('project', 'income_date')
    search_fields = ('income_target', 'note', 'project__name')
    date_hierarchy = 'income_date'


@admin.register(AccountingProjectExpense)
class AccountingProjectExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'project',
        'expense_date',
        'place',
        'category_name',
        'amount',
        'expense_target',
        'source_expense',
        'created_at',
    )
    list_filter = ('project', 'category_name', 'payment_method', 'expense_date')
    search_fields = ('place', 'category_name', 'payment_method', 'expense_target', 'note', 'project__name')
    date_hierarchy = 'expense_date'


@admin.register(AccountingVoucher)
class AccountingVoucherAdmin(admin.ModelAdmin):
    list_display = (
        'issue_date',
        'voucher_type',
        'voucher_number',
        'recipient_name',
        'title',
        'total_amount',
        'created_by',
        'created_at',
    )
    list_filter = ('voucher_type', 'issue_date')
    search_fields = ('voucher_number', 'recipient_name', 'title', 'details', 'note')
    readonly_fields = ('total_amount', 'created_by', 'created_at', 'updated_at')
    date_hierarchy = 'issue_date'


@admin.register(VoucherItemTemplate)
class VoucherItemTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_unit_price', 'is_active', 'sort_order', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(VisaReturnApplication)
class VisaReturnApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant_name', 'nationality', 'passport_number', 'residence_status', 'created_at')
    list_filter = ('nationality', 'residence_status', 'gender', 'marital_status')
    search_fields = ('applicant_name', 'passport_number', 'phone', 'email', 'guarantor_name')
    readonly_fields = ('created_by', 'created_at', 'updated_at')


@admin.register(VisaGuarantorTemplate)
class VisaGuarantorTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'guarantor_name', 'guarantor_phone', 'is_active', 'sort_order', 'created_at')
    list_filter = ('is_active',)
    search_fields = (
        'name',
        'guarantor_name',
        'guarantor_name_en',
        'guarantor_phone',
        'guarantor_address',
        'guarantor_occupation',
        'guarantor_relationship',
    )


@admin.register(SeifuNoticePdfRecord)
class SeifuNoticePdfRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'text_count', 'created_by', 'updated_at')
    list_filter = ('status', 'updated_at')
    search_fields = ('title', 'note')
    readonly_fields = ('created_by', 'created_at', 'updated_at')

    def text_count(self, obj):
        if not isinstance(obj.text_items, list):
            return 0
        return len([item for item in obj.text_items if str(item.get('text') or '').strip()])

    text_count.short_description = '文字数量'


@admin.register(TaxRenewalVoucherRecord)
class TaxRenewalVoucherRecordAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'company',
        'customer',
        'status',
        'selected_template_count',
        'updated_at',
    )
    list_filter = ('category', 'status', 'has_employees', 'has_dependents', 'updated_at')
    search_fields = ('title', 'note', 'company__name', 'customer__name')
    readonly_fields = ('created_by', 'created_at', 'updated_at')

    def selected_template_count(self, obj):
        if not isinstance(obj.selected_templates, list):
            return 0
        return len(obj.selected_templates)

    selected_template_count.short_description = '模板数量'


@admin.register(TaxRenewalAgentTemplate)
class TaxRenewalAgentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'agent_name', 'agent_company_name', 'agent_phone', 'is_active', 'sort_order', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'agent_name', 'agent_kana', 'agent_company_name', 'agent_phone', 'note')
