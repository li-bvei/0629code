from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
