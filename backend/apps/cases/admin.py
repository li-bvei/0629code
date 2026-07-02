from django.contrib import admin

from .models import Case


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
