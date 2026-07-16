from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone

TOKYO_TZ = ZoneInfo('Asia/Tokyo')
def get_case_number_month(created_at=None):
    target = created_at or timezone.now()
    if timezone.is_naive(target):
        target = timezone.make_aware(target, TOKYO_TZ)
    return timezone.localtime(target, TOKYO_TZ).strftime('%Y%m')


def sanitize_case_number_name(name):
    normalized = ' '.join((name or '').strip().split())
    for unsafe_char in ['-', '‐', '‑', '‒', '–', '—', '―', '/', '\\']:
        normalized = normalized.replace(unsafe_char, '')
    normalized = ' '.join(normalized.split())
    return normalized or '氏名未登録'


def get_case_customer_name(customer):
    if customer is None:
        return ''
    return getattr(customer, 'name', '') or ''


def _get_number_abbreviation(obj, label):
    if obj is None:
        raise ValidationError(f'{label}を選択してください。')
    abbreviation = (getattr(obj, 'number_abbreviation', '') or '').strip()
    if not abbreviation:
        raise ValidationError(f'{label}の案件番号略称が未設定です。')
    return abbreviation


def build_case_number_prefix(case_type_master, application_category, customer, created_at=None):
    case_type_abbreviation = _get_number_abbreviation(case_type_master, '案件種別')
    application_abbreviation = _get_number_abbreviation(application_category, '申請区分')
    month = get_case_number_month(created_at)
    customer_name = sanitize_case_number_name(get_case_customer_name(customer))
    return f'{case_type_abbreviation}-{application_abbreviation}-{month}-{customer_name}-'


def generate_case_number(case_type_master, application_category, customer=None, created_at=None):
    from .models import Case

    number_prefix = build_case_number_prefix(case_type_master, application_category, customer, created_at)
    max_sequence = 0

    existing_numbers = Case.objects.filter(
        case_number__startswith=number_prefix,
    ).values_list('case_number', flat=True)

    for case_number in existing_numbers:
        suffix = case_number.replace(number_prefix, '', 1)
        if suffix.isdigit():
            max_sequence = max(max_sequence, int(suffix))

    return f'{number_prefix}{max_sequence + 1:04d}'
