"""事務所設定の読み書き。日常の値はデータベースを優先し、行が無いときだけ環境変数・既定値で補う。"""
import os

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.audit.services import record

from .models import OfficeSettings

DEFAULT_FISCAL_YEAR_END_MONTH = 3


def _fallback_month():
    raw = os.getenv('OFFICE_FISCAL_YEAR_END_MONTH') or getattr(settings, 'REAL_ESTATE_FISCAL_YEAR_END_MONTH', None)
    try:
        month = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_FISCAL_YEAR_END_MONTH
    return month if 1 <= month <= 12 else DEFAULT_FISCAL_YEAR_END_MONTH


def get_office_settings():
    return OfficeSettings.objects.filter(pk=OfficeSettings.SINGLETON_ID).first()


def fiscal_year_end_month():
    row = get_office_settings()
    return row.fiscal_year_end_month if row else _fallback_month()


def current_settings():
    row = get_office_settings()
    return {
        'fiscal_year_end_month': row.fiscal_year_end_month if row else _fallback_month(),
        'source': 'database' if row else 'fallback',
        'updated_at': row.updated_at if row else None,
        'updated_by': row.updated_by.get_username() if row and row.updated_by else '',
    }


def set_fiscal_year_end_month(month, request):
    try:
        month = int(month)
    except (TypeError, ValueError):
        raise ValidationError({'fiscal_year_end_month': '1〜12 の月を指定してください。'})
    if not 1 <= month <= 12:
        raise ValidationError({'fiscal_year_end_month': '1〜12 の月を指定してください。'})
    before = current_settings()
    row = get_office_settings() or OfficeSettings(fiscal_year_end_month=month)
    row.fiscal_year_end_month = month
    row.updated_by = request.user
    row.save()
    record(module='office', action='fiscal_year_end_month_changed', request=request, obj=row,
           object_repr='事業年度末月', changes={'fiscal_year_end_month': [before['fiscal_year_end_month'], month]},
           extra={'previous_source': before['source']})
    return current_settings()
