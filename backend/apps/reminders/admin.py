from django.contrib import admin

from .models import Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'case', 'remind_at', 'is_done', 'updated_at')
    list_filter = ('is_done', 'remind_at')
    search_fields = ('title', 'note', 'case__case_number')
    autocomplete_fields = ('case',)
    readonly_fields = ('created_at', 'updated_at')
