from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import transaction
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
    month = get_case_number_month(created_at)
    customer_name = sanitize_case_number_name(get_case_customer_name(customer))
    if application_category is None and case_type_master is not None and not case_type_master.requires_application_category:
        # P4：申請区分の無い種別（税理士委託など）は「種別-年月-氏名-連番」
        return f'{case_type_abbreviation}-{month}-{customer_name}-'
    application_abbreviation = _get_number_abbreviation(application_category, '申請区分')
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


APPLY_MODE_MERGE = 'merge'
APPLY_MODE_REPLACE = 'replace'


def _checklist_item_key(category, name):
    return ((category or '').strip(), (name or '').strip())


def apply_checklist_template_to_case(case, template, mode=APPLY_MODE_MERGE):
    """案件にテンプレートを適用する。

    mode='merge'（既定）: 既存に無い項目だけを追加する（重複追加しない＝冪等）。
    mode='replace'      : 未完了かつテンプレート由来の項目を削除してから作り直す。
                          完了済みの項目は残す（無警告で消さない）。

    戻り値は今回新規作成された CaseChecklistItem のリスト。
    """
    from .models import CaseChecklistItem

    template_items = list(
        template.items.filter(is_active=True, deleted_at__isnull=True).order_by('sort_order', 'id')
    )

    created_items = []
    with transaction.atomic():
        existing_items = list(CaseChecklistItem.objects.filter(case=case))

        if mode == APPLY_MODE_REPLACE:
            template_item_ids = {item.id for item in template_items}
            removable = [
                item for item in existing_items
                if not item.is_completed and (
                    item.source_template_item_id is not None
                    and item.source_template_item.template_id == template.id
                )
            ]
            removable_ids = {item.id for item in removable}
            if removable_ids:
                CaseChecklistItem.objects.filter(id__in=removable_ids).delete()
            existing_items = [item for item in existing_items if item.id not in removable_ids]
            # replace でも、既に手動で追加済み・完了済みの同名項目は二重に作らない。
            del template_item_ids

        existing_keys = {
            _checklist_item_key(item.category, item.name) for item in existing_items
        }
        existing_source_ids = {
            item.source_template_item_id for item in existing_items if item.source_template_item_id
        }

        current_max_order = max(
            [item.sort_order for item in existing_items] + [0]
        )

        for index, template_item in enumerate(template_items, start=1):
            key = _checklist_item_key(template_item.category, template_item.name)
            if key in existing_keys or template_item.id in existing_source_ids:
                continue
            current_max_order += 1
            created_items.append(CaseChecklistItem.objects.create(
                case=case,
                source_template_item=template_item,
                category=template_item.category,
                name=template_item.name,
                item_type=template_item.item_type,
                quantity=template_item.quantity,
                unit=template_item.unit,
                is_required=template_item.is_required,
                note=template_item.description,
                responsible_party=template_item.responsible_party,
                acquisition_place=template_item.acquisition_place,
                required_details=template_item.required_details,
                internal_note=template_item.internal_note,
                customer_note=template_item.customer_note,
                is_visible_to_customer=template_item.is_visible_to_customer,
                importance_level=template_item.importance_level,
                sort_order=current_max_order,
            ))
            existing_keys.add(key)
    return created_items


def auto_apply_default_checklist_template(case):
    """案件種別・申請区分に一致するテンプレートがあれば、新規作成直後の案件に自動適用する。
    既存の必要資料を上書きしないよう、作成直後（必要資料が空の状態）でのみ呼び出すこと。
    """
    from .models import CaseChecklistTemplate

    if not case.case_type_master_id:
        return []
    templates = CaseChecklistTemplate.objects.filter(
        case_type_master_id=case.case_type_master_id, is_active=True, deleted_at__isnull=True,
    ).order_by('sort_order', 'id')
    if case.application_category_id:
        template = templates.filter(application_category_id=case.application_category_id).first()
    elif not case.case_type_master.requires_application_category:
        # P4：申請区分の無い種別は、種別だけに結び付いたテンプレート（申請区分が空）を使う
        template = templates.filter(application_category__isnull=True).first()
    else:
        return []
    if not template:
        return []

    return apply_checklist_template_to_case(case, template)
