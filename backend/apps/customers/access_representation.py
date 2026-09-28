"""顧客・会社・家族・会社職員の表現レベル別の整形（BusinessAccessPolicy の判定結果に従う）。

レベルの判定は access_rules（CUSTOMER_RULE / COMPANY_RULE）が行い、ここでは結果に応じて
項目を削る・伏せるだけ。My Number はどのレベルでも明文を返さない。
"""
from apps.authentication.access_rules import (
    LEVEL_BASIC,
    LEVEL_FULL,
    LEVEL_MASKED,
    LEVEL_MINIMAL,
)

IDENTITY_FIELDS = ('residence_card_no', 'passport_no')
BANK_MASK_FIELDS = ('bank_account_number',)

# 案件の無い顧客（受付のみ）：普通の業務利用者に見せるのはこれだけ。電話・メールは伏せ字。
# 住所・在留カード・旅券・My Number・家族詳細・ファイル・会計は含めない（2026-09-28 確定）。
CUSTOMER_BASIC_FIELDS = ('id', 'name', 'name_kana', 'birth_date', 'nationality', 'created_at')
COMPANY_MINIMAL_FIELDS = ('id', 'name', 'name_kana', 'corporate_number')
COMPANY_BASIC_FIELDS = COMPANY_MINIMAL_FIELDS + (
    'representative_name', 'postal_code', 'address', 'fiscal_month', 'cases_count', 'created_at', 'updated_at',
)


def mask_value(value):
    if not value:
        return value
    text = str(value)
    return '****' + text[-4:] if len(text) > 4 else '****'


def mask_email(value):
    if not value or '@' not in str(value):
        return mask_value(value)
    local, _, domain = str(value).partition('@')
    return f'{local[:1]}***@{domain}'


def mask_fields(data, fields):
    for field in fields:
        if field in data:
            data[field] = mask_value(data[field])
    return data


def _active_case_summary(customer=None, company=None):
    from apps.cases.models import Case

    qs = Case.objects.filter(registration_status=Case.REGISTRATION_STATUS_ACTIVE).exclude(
        status__in=[Case.STATUS_COMPLETED, Case.STATUS_WITHDRAWN, Case.STATUS_REJECTED],
    )
    qs = qs.filter(customer=customer) if customer is not None else qs.filter(company=company)
    names = sorted({
        name for name in qs.exclude(responsible_employee__isnull=True)
        .values_list('responsible_employee__name', flat=True) if name
    })
    return qs.exists(), names


def minimal_customer(instance):
    """重複防止用の最小識別情報。証件・住所・連絡先・My Number・ファイル・会計は含めない。"""
    has_active_case, responsible_names = _active_case_summary(customer=instance)
    return {
        'id': instance.id,
        'name': instance.name,
        'name_kana': instance.name_kana,
        'birth_date': instance.birth_date.isoformat() if instance.birth_date else None,
        'nationality': instance.nationality,
        'has_active_case': has_active_case,
        'responsible_employee_names': responsible_names,
        'access_level': LEVEL_MINIMAL,
    }


def shape_customer(data, level):
    data.pop('my_number', None)
    if level == LEVEL_BASIC:
        basic = {key: data[key] for key in CUSTOMER_BASIC_FIELDS if key in data}
        basic['phone'] = mask_value(data.get('phone') or '')
        basic['email'] = mask_email(data.get('email') or '')
        data = basic
    elif level == LEVEL_MASKED:
        mask_fields(data, IDENTITY_FIELDS)
    data['access_level'] = level
    return data


def minimal_company(instance):
    return {
        'id': instance.id,
        'name': instance.name,
        'name_kana': instance.name_kana,
        'corporate_number': instance.corporate_number,
        'access_level': LEVEL_MINIMAL,
    }


def shape_company(data, level):
    if level == LEVEL_BASIC:
        data = {key: data[key] for key in COMPANY_BASIC_FIELDS if key in data}
    elif level == LEVEL_MASKED:
        mask_fields(data, BANK_MASK_FIELDS)
    data['access_level'] = level
    return data


def shape_person_child(data, parent_level):
    """家族・会社職員の人物項目。親が伏せ字レベルなら証件番号を伏せる。My Number は常に除外。"""
    data.pop('my_number', None)
    if parent_level != LEVEL_FULL:
        mask_fields(data, IDENTITY_FIELDS)
    return data
