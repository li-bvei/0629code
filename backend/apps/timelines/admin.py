from django.contrib import admin

from .models import Timeline


@admin.register(Timeline)
class TimelineAdmin(admin.ModelAdmin):
    list_display = ('title', 'case', 'occurred_at', 'is_visible_to_client', 'created_at')
    list_filter = ('is_visible_to_client', 'occurred_at', 'created_at')
    search_fields = ('title', 'content', 'case__case_number')
    autocomplete_fields = ('case',)
    readonly_fields = ('created_at', 'updated_at')
