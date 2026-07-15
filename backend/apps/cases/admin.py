from django.contrib import admin

from .models import Case, CaseChecklistItem, CaseChecklistTemplate, CaseChecklistTemplateItem


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = (
        'case_number',
        'case_type',
        'status',
        'customer',
        'company',
        'responsible_employee',
        'accepted_at',
        'applied_at',
        'result_notified_at',
        'completed_at',
        'updated_at',
    )
    list_filter = ('status', 'case_type')
    search_fields = (
        'case_number',
        'case_type',
        'customer__name',
        'company__name',
        'responsible_employee__name',
    )
    autocomplete_fields = ('customer', 'company', 'responsible_employee')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CaseChecklistTemplate)
class CaseChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'sort_order', 'deleted_at', 'updated_at')
    list_filter = ('is_active', 'deleted_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CaseChecklistTemplateItem)
class CaseChecklistTemplateItemAdmin(admin.ModelAdmin):
    list_display = ('template', 'category', 'name', 'item_type', 'is_required', 'is_active', 'deleted_at', 'sort_order')
    list_filter = ('item_type', 'is_required', 'is_active', 'deleted_at', 'template')
    search_fields = ('name', 'category', 'description', 'template__name')
    autocomplete_fields = ('template',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CaseChecklistItem)
class CaseChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('case', 'category', 'name', 'item_type', 'is_required', 'is_completed', 'completed_by', 'sort_order')
    list_filter = ('item_type', 'is_required', 'is_completed')
    search_fields = ('name', 'category', 'note', 'case__case_number')
    autocomplete_fields = ('case', 'source_template_item', 'completed_by')
    readonly_fields = ('created_at', 'updated_at')
