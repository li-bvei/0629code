from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'sort_order',
        'title',
        'case',
        'responsible_employee',
        'status',
        'due_date',
        'completed_at',
        'updated_at',
    )
    list_filter = ('status', 'responsible_employee', 'due_date', 'completed_at')
    search_fields = ('title', 'description', 'case__case_number')
    autocomplete_fields = ('case', 'responsible_employee')
    readonly_fields = ('created_at', 'updated_at')
