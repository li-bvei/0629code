from django.contrib import admin

from .models import DismissedDeadline, Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'case', 'remind_at', 'is_done', 'updated_at')
    list_filter = ('is_done', 'remind_at')
    search_fields = ('title', 'note', 'case__case_number')
    autocomplete_fields = ('case',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DismissedDeadline)
class DismissedDeadlineAdmin(admin.ModelAdmin):
    # ダッシュボードの「非表示」ボタンで作られたレコード。削除すれば
    # 該当項目は次回ダッシュボード表示時にまた出てくる（＝取り消し操作になる）。
    list_display = ('source_type', 'source_id', 'deadline_type', 'deadline_date', 'dismissed_by', 'created_at')
    list_filter = ('source_type', 'deadline_type')
    search_fields = ('note',)
    readonly_fields = ('created_at',)
