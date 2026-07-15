from zoneinfo import ZoneInfo

from django.utils import timezone


CASE_NUMBER_PREFIX_MAP = {
    '経営・管理新規申請': '経管',
    '経営・管理更新': '経管',
    '経営・管理': '経管',
    '技人国ビザ新規申請': '技人国',
    '技人国ビザ更新': '技人国',
    '技術・人文知識・国際業務': '技人国',
    '特別高度人材新規申請': '特高',
    '高度専門職': '高度',
    '高度専門職1号イ': '高度',
    '高度専門職1号ロ': '高度',
    '高度専門職1号ハ': '高度',
    '高度専門職2号': '高度',
    '永住許可申請': '永住',
    '永住申請': '永住',
    '永住者': '永住',
    '帰化申請': '帰化',
    '家族滞在': '家族',
    '日本人の配偶者等': '日配',
    '永住者の配偶者等': '永配',
    '定住者': '定住',
    '留学': '留学',
    '特定技能': '特定',
    '技能': '技能',
    '企業内転勤': '転勤',
    '在留申請': 'その他',
    '在留更新': 'その他',
    '会社設立': 'その他',
    '会社変更': 'その他',
    '入社手続': 'その他',
    '社会保険・年金': 'その他',
    '税務': 'その他',
    '許認可申請': 'その他',
    '届出・証明': 'その他',
    'その他': 'その他',
}

TOKYO_TZ = ZoneInfo('Asia/Tokyo')
APPLICATION_CATEGORY_APPLY = '申請'
APPLICATION_CATEGORY_RENEWAL = '更新'


def get_case_number_prefix(case_type):
    normalized = (case_type or '').strip()
    if not normalized:
        return 'その他'
    if normalized in CASE_NUMBER_PREFIX_MAP:
        return CASE_NUMBER_PREFIX_MAP[normalized]

    for keyword, prefix in [
        ('経営・管理', '経管'),
        ('技人国', '技人国'),
        ('技術・人文知識・国際業務', '技人国'),
        ('特別高度', '特高'),
        ('高度専門職', '高度'),
        ('永住', '永住'),
        ('帰化', '帰化'),
        ('家族滞在', '家族'),
        ('日本人の配偶者', '日配'),
        ('永住者の配偶者', '永配'),
        ('定住', '定住'),
        ('留学', '留学'),
        ('特定技能', '特定'),
        ('企業内転勤', '転勤'),
        ('技能', '技能'),
    ]:
        if keyword in normalized:
            return prefix
    return 'その他'


def get_case_number_month(created_at=None):
    target = created_at or timezone.now()
    if timezone.is_naive(target):
        target = timezone.make_aware(target, TOKYO_TZ)
    return timezone.localtime(target, TOKYO_TZ).strftime('%Y%m')


def get_case_application_category(case_type):
    normalized = (case_type or '').strip()
    if normalized in {'経営・管理更新', '技人国ビザ更新', '在留更新'}:
        return APPLICATION_CATEGORY_RENEWAL
    if '更新' in normalized:
        return APPLICATION_CATEGORY_RENEWAL
    return APPLICATION_CATEGORY_APPLY


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


def generate_case_number(case_type, customer=None, created_at=None):
    from .models import Case

    prefix = get_case_number_prefix(case_type)
    month = get_case_number_month(created_at)
    application_category = get_case_application_category(case_type)
    customer_name = sanitize_case_number_name(get_case_customer_name(customer))
    number_prefix = f'{prefix}-{month}-{application_category}-{customer_name}-'
    max_sequence = 0

    existing_numbers = Case.objects.filter(
        case_number__startswith=number_prefix,
    ).values_list('case_number', flat=True)

    for case_number in existing_numbers:
        suffix = case_number.replace(number_prefix, '', 1)
        if suffix.isdigit():
            max_sequence = max(max_sequence, int(suffix))

    return f'{number_prefix}{max_sequence + 1:04d}'
