from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'case', 'status', 'due_date', 'updated_at')
    list_filter = ('status', 'due_date')
    search_fields = ('title', 'description', 'case__case_number')
    autocomplete_fields = ('case',)
    readonly_fields = ('created_at', 'updated_at')
