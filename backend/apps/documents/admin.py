from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'case',
        'file_name',
        'source',
        'is_visible_to_client',
        'updated_at',
    )
    list_filter = ('source', 'is_visible_to_client')
    search_fields = ('title', 'file_name', 'file_path', 'case__case_number')
    autocomplete_fields = ('case',)
    readonly_fields = ('created_at', 'updated_at')
