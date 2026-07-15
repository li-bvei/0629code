from django.db import transaction
from django.utils import timezone

from .models import CaseChecklistTemplate, CaseChecklistTemplateItem


OLD_DEMO_TEMPLATE_RENAMES = {
    '【DEMO】経営・管理在留資格更新': '経営・管理更新',
    '【DEMO】技術・人文知識・国際業務更新': '技人国ビザ更新',
    '【DEMO】永住許可申請': '永住許可申請',
}


def item(category, name, item_type='document', quantity=None, unit='', required=True, description=''):
    return {
        'category': category,
        'name': name,
        'item_type': item_type,
        'quantity': quantity,
        'unit': unit,
        'is_required': required,
        'description': description,
    }


STANDARD_TEMPLATES = [
    {
        'name': '経営・管理新規申請',
        'description': '経営・管理新規申請の標準案件事項テンプレートです。',
        'items': [
            item('本人資料', 'パスポートコピー'), item('本人資料', '在留カード両面コピー'),
            item('本人資料', '住民票', quantity=1, unit='通'), item('本人資料', '履歴書'),
            item('本人資料', '最終学歴証明書'), item('本人資料', '職歴証明書'),
            item('会社設立資料', '履歴事項全部証明書', quantity=1, unit='通'), item('会社設立資料', '定款コピー'),
            item('会社設立資料', '株主名簿'), item('会社設立資料', '役員名簿'), item('会社設立資料', '法人番号指定通知書'),
            item('事業計画資料', '事業計画書'), item('事業計画資料', '収支計画書'), item('事業計画資料', '事業内容説明資料'),
            item('事業計画資料', '取引予定資料'), item('事業計画資料', '仕入先・販売先資料'),
            item('事務所資料', '事務所賃貸借契約書コピー'), item('事務所資料', '事務所写真'),
            item('事務所資料', '事務所平面図'), item('事務所資料', '事務所案内図'),
            item('資本金・資金資料', '資本金払込証明資料'), item('資本金・資金資料', '通帳コピー'),
            item('資本金・資金資料', '資金形成経緯説明', 'confirmation'), item('資本金・資金資料', '海外送金資料'),
            item('税務・届出資料', '法人設立届出書'), item('税務・届出資料', '給与支払事務所等の開設届出書'),
            item('税務・届出資料', '青色申告承認申請書'), item('税務・届出資料', '税務署受付控え'),
            item('申請準備', '申請書作成', 'task'), item('申請準備', '事業内容確認', 'confirmation'),
            item('申請準備', '資金来源確認', 'confirmation'), item('申請準備', '事務所要件確認', 'confirmation'),
            item('申請準備', '提出書類最終確認', 'task'),
        ],
    },
    {
        'name': '技人国ビザ新規申請',
        'description': '技術・人文知識・国際業務新規申請の標準案件事項テンプレートです。',
        'items': [
            item('本人資料', 'パスポートコピー'), item('本人資料', '在留カード両面コピー'),
            item('本人資料', '住民票', quantity=1, unit='通'), item('本人資料', '証明写真'), item('本人資料', '履歴書'),
            item('勤務先資料', '履歴事項全部証明書', quantity=1, unit='通'), item('勤務先資料', '会社案内'),
            item('勤務先資料', '直近決算書一式'), item('勤務先資料', '法定調書合計表'), item('勤務先資料', '事業内容説明資料'),
            item('学歴・職歴資料', '卒業証明書'), item('学歴・職歴資料', '成績証明書'),
            item('学歴・職歴資料', '職歴証明書'), item('学歴・職歴資料', '資格証明書'),
            item('雇用条件資料', '雇用契約書'), item('雇用条件資料', '労働条件通知書'),
            item('雇用条件資料', '職務内容説明書'), item('雇用条件資料', '給与条件確認', 'confirmation'),
            item('申請準備', '職務内容と学歴の関連性確認', 'confirmation'), item('申請準備', '職務内容と職歴の関連性確認', 'confirmation'),
            item('申請準備', '申請書作成', 'task'), item('申請準備', '提出書類最終確認', 'task'),
        ],
    },
    {
        'name': '特別高度人材新規申請',
        'description': '特別高度人材新規申請の標準案件事項テンプレートです。',
        'items': [
            item('本人資料', 'パスポートコピー'), item('本人資料', '在留カード両面コピー'),
            item('本人資料', '住民票', quantity=1, unit='通'), item('本人資料', '証明写真'), item('本人資料', '履歴書'),
            item('学歴・職歴資料', '卒業証明書'), item('学歴・職歴資料', '学位証明書'), item('学歴・職歴資料', '成績証明書'),
            item('学歴・職歴資料', '職歴証明書'), item('学歴・職歴資料', '研究実績資料'), item('学歴・職歴資料', '資格証明書'),
            item('年収・契約資料', '雇用契約書'), item('年収・契約資料', '労働条件通知書'),
            item('年収・契約資料', '年収証明資料'), item('年収・契約資料', '予定年収確認資料'),
            item('ポイント計算資料', '高度専門職ポイント計算表'), item('ポイント計算資料', '年齢確認資料'),
            item('ポイント計算資料', '学歴ポイント資料'), item('ポイント計算資料', '職歴ポイント資料'),
            item('ポイント計算資料', '年収ポイント資料'), item('ポイント計算資料', '加算ポイント資料'),
            item('勤務先資料', '履歴事項全部証明書', quantity=1, unit='通'), item('勤務先資料', '会社案内'),
            item('勤務先資料', '直近決算書一式'), item('勤務先資料', '法定調書合計表'), item('勤務先資料', '職務内容説明書'),
            item('申請準備', '80点以上確認', 'confirmation'), item('申請準備', '特別高度人材要件確認', 'confirmation'),
            item('申請準備', '申請書作成', 'task'), item('申請準備', '提出書類最終確認', 'task'),
        ],
    },
    {
        'name': '経営・管理更新',
        'description': '経営・管理更新の標準案件事項テンプレートです。',
        'items': [
            item('本人資料', 'パスポートコピー'), item('本人資料', '在留カード両面コピー'), item('本人資料', '住民票', quantity=1, unit='通'),
            item('本人資料', '個人課税証明書', quantity=1, unit='通'), item('本人資料', '個人納税証明書', quantity=1, unit='通'),
            item('会社資料', '履歴事項全部証明書', quantity=1, unit='通'), item('会社資料', '定款コピー'),
            item('会社資料', '会社案内'), item('会社資料', '事務所賃貸借契約書コピー'),
            item('税務資料', '法人税納税証明書'), item('税務資料', '法人事業税納税証明書'), item('税務資料', '法人市民税納税証明書'),
            item('税務資料', '直近決算書一式'), item('税務資料', '法定調書合計表'),
            item('社会保険資料', '社会保険料納入証明書'), item('社会保険資料', '被保険者記録'), item('社会保険資料', '従業員名簿'),
            item('経営状況資料', '売上資料'), item('経営状況資料', '取引資料'), item('経営状況資料', '通帳コピー'), item('経営状況資料', '事業継続状況資料'),
            item('申請準備', '申請理由書作成', 'task'), item('申請準備', '事業内容確認', 'confirmation'),
            item('申請準備', '売上・取引状況確認', 'confirmation'), item('申請準備', '入管提出書類最終確認', 'task'),
        ],
    },
    {
        'name': '技人国ビザ更新',
        'description': '技人国ビザ更新の標準案件事項テンプレートです。',
        'items': [
            item('本人資料', 'パスポートコピー'), item('本人資料', '在留カード両面コピー'), item('本人資料', '住民票', quantity=1, unit='通'),
            item('本人資料', '個人課税証明書', quantity=1, unit='通'), item('本人資料', '個人納税証明書', quantity=1, unit='通'),
            item('勤務先資料', '在職証明書'), item('勤務先資料', '雇用契約書コピー'), item('勤務先資料', '労働条件通知書'),
            item('勤務先資料', '会社登記事項証明書'), item('勤務先資料', '会社案内'),
            item('給与・税務資料', '給与明細', quantity=3, unit='か月分'), item('給与・税務資料', '源泉徴収票'),
            item('給与・税務資料', '法定調書合計表'), item('給与・税務資料', '直近決算書一式'),
            item('申請準備', '職務内容確認', 'confirmation'), item('申請準備', '現在の勤務状況確認', 'confirmation'),
            item('申請準備', '転職履歴確認', 'confirmation'), item('申請準備', '申請書作成', 'task'), item('申請準備', '提出書類最終確認', 'task'),
        ],
    },
    {
        'name': '永住許可申請',
        'description': '永住許可申請の標準案件事項テンプレートです。',
        'items': [
            item('本人資料', 'パスポートコピー'), item('本人資料', '在留カード両面コピー'), item('本人資料', '住民票', quantity=1, unit='通'),
            item('本人資料', '家族全員の住民票'), item('本人資料', '証明写真'),
            item('税務資料', '課税証明書', quantity=5, unit='年分'), item('税務資料', '納税証明書', quantity=5, unit='年分'),
            item('税務資料', '国税納税証明書'), item('税務資料', '納税状況確認資料'),
            item('年金・保険資料', '年金記録'), item('年金・保険資料', '年金保険料領収書'), item('年金・保険資料', '健康保険料納付証明書'), item('年金・保険資料', '社会保険加入記録'),
            item('職業・収入資料', '在職証明書'), item('職業・収入資料', '雇用契約書'), item('職業・収入資料', '源泉徴収票'), item('職業・収入資料', '給与明細'), item('職業・収入資料', '会社経営資料'),
            item('身元保証人資料', '身元保証書'), item('身元保証人資料', '身元保証人本人確認書類'), item('身元保証人資料', '身元保証人在職証明書'), item('身元保証人資料', '身元保証人所得証明書'),
            item('在留履歴資料', '在留履歴確認', 'confirmation'), item('在留履歴資料', '出入国履歴確認', 'confirmation'), item('在留履歴資料', '交通違反・法令違反確認', 'confirmation'), item('在留履歴資料', '家族関係確認', 'confirmation'),
            item('申請準備', '理由書作成', 'task'), item('申請準備', '在留年数確認', 'confirmation'), item('申請準備', '素行要件確認', 'confirmation'), item('申請準備', '独立生計要件確認', 'confirmation'), item('申請準備', '国益適合要件確認', 'confirmation'), item('申請準備', '提出書類最終確認', 'task'),
        ],
    },
]


def standard_template_names():
    return [template['name'] for template in STANDARD_TEMPLATES]


def _normalize_orders(queryset):
    for index, obj in enumerate(queryset.order_by('sort_order', 'id'), start=1):
        if obj.sort_order != index:
            obj.sort_order = index
            obj.save(update_fields=['sort_order', 'updated_at'])


def normalize_template_orders():
    _normalize_orders(CaseChecklistTemplate.objects.filter(deleted_at__isnull=True))


def normalize_template_item_orders(template):
    _normalize_orders(template.items.filter(deleted_at__isnull=True))


def _rename_old_demo_templates():
    for old_name, new_name in OLD_DEMO_TEMPLATE_RENAMES.items():
        old_template = CaseChecklistTemplate.objects.filter(name=old_name).first()
        if old_template is None:
            continue
        existing = CaseChecklistTemplate.objects.filter(name=new_name).exclude(pk=old_template.pk).first()
        if existing:
            now = timezone.now()
            for item_obj in old_template.items.filter(deleted_at__isnull=True):
                target_exists = existing.items.filter(
                    category=item_obj.category,
                    name=item_obj.name,
                    deleted_at__isnull=True,
                ).exists()
                if not target_exists:
                    item_obj.pk = None
                    item_obj.template = existing
                    item_obj.sort_order = existing.items.filter(deleted_at__isnull=True).count() + 1
                    item_obj.save()
            old_template.is_active = False
            old_template.deleted_at = old_template.deleted_at or now
            old_template.save(update_fields=['is_active', 'deleted_at', 'updated_at'])
            old_template.items.filter(deleted_at__isnull=True).update(
                deleted_at=now,
                deleted_with_template=True,
                updated_at=now,
            )
        else:
            old_template.name = new_name
            old_template.save(update_fields=['name', 'updated_at'])


def _upsert_template(template_data, sort_order):
    deleted = CaseChecklistTemplate.objects.filter(
        name=template_data['name'],
        deleted_at__isnull=False,
    ).first()
    if deleted:
        return deleted, False, True
    template = CaseChecklistTemplate.objects.filter(
        name=template_data['name'],
        deleted_at__isnull=True,
    ).first()
    if template:
        template.description = template_data['description']
        template.sort_order = sort_order
        template.save(update_fields=['description', 'sort_order', 'updated_at'])
        return template, False, False
    template = CaseChecklistTemplate.objects.create(
        name=template_data['name'],
        description=template_data['description'],
        sort_order=sort_order,
        is_active=True,
    )
    return template, True, False


def _upsert_template_item(template, item_data, sort_order):
    existing_deleted = template.items.filter(
        category=item_data['category'],
        name=item_data['name'],
        deleted_at__isnull=False,
    ).first()
    if existing_deleted:
        return existing_deleted, False, True
    item_obj = template.items.filter(
        category=item_data['category'],
        name=item_data['name'],
        deleted_at__isnull=True,
    ).first()
    if item_obj:
        item_obj.item_type = item_data['item_type']
        item_obj.quantity = item_data['quantity']
        item_obj.unit = item_data['unit']
        item_obj.is_required = item_data['is_required']
        item_obj.description = item_data['description']
        item_obj.sort_order = sort_order
        item_obj.save(update_fields=['item_type', 'quantity', 'unit', 'is_required', 'description', 'sort_order', 'updated_at'])
        return item_obj, False, False
    item_obj = CaseChecklistTemplateItem.objects.create(
        template=template,
        category=item_data['category'],
        name=item_data['name'],
        item_type=item_data['item_type'],
        quantity=item_data['quantity'],
        unit=item_data['unit'],
        is_required=item_data['is_required'],
        description=item_data['description'],
        sort_order=sort_order,
        is_active=True,
    )
    return item_obj, True, False


@transaction.atomic
def seed_standard_case_checklist_templates():
    result = {
        'success': True,
        'message': '標準テンプレートを取り込みました。',
        'templates_created': 0,
        'templates_updated': 0,
        'templates_skipped_deleted': 0,
        'template_items_created': 0,
        'template_items_updated': 0,
        'template_items_skipped_deleted': 0,
        'template_ids': [],
    }

    _rename_old_demo_templates()

    for template_index, template_data in enumerate(STANDARD_TEMPLATES, start=1):
        template, created, skipped_deleted = _upsert_template(template_data, template_index)
        result['template_ids'].append(template.id)
        if skipped_deleted:
            result['templates_skipped_deleted'] += 1
            continue
        if created:
            result['templates_created'] += 1
        else:
            result['templates_updated'] += 1

        for item_index, item_data in enumerate(template_data['items'], start=1):
            _, item_created, item_skipped_deleted = _upsert_template_item(template, item_data, item_index)
            if item_skipped_deleted:
                result['template_items_skipped_deleted'] += 1
            elif item_created:
                result['template_items_created'] += 1
            else:
                result['template_items_updated'] += 1
        normalize_template_item_orders(template)

    normalize_template_orders()
    return result


def seed_case_checklist_demo_data():
    return seed_standard_case_checklist_templates()
