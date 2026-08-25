from django.db import migrations

TEMPLATE_NAME = '技人国ビザ変更申請'
CASE_NUMBER = '技人国-変更-202608-張 静-0001'

ITEM_COPY_FIELDS = [
    'category', 'name', 'item_type', 'quantity', 'unit', 'is_required',
    'responsible_party', 'acquisition_place', 'required_details',
    'internal_note', 'customer_note', 'is_visible_to_customer', 'importance_level',
]


def apply_template_to_case(apps, schema_editor):
    Case = apps.get_model('cases', 'Case')
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    CaseChecklistItem = apps.get_model('cases', 'CaseChecklistItem')

    case = Case.objects.filter(case_number=CASE_NUMBER).first()
    template = CaseChecklistTemplate.objects.filter(name=TEMPLATE_NAME).first()
    if not case or not template:
        return
    if CaseChecklistItem.objects.filter(case=case).exists():
        # 既に運用開始時などで手動適用済み（本開発時にローカルで適用したケースを含む）。
        return

    template_items = template.items.filter(is_active=True, deleted_at__isnull=True).order_by('sort_order', 'id')
    for index, template_item in enumerate(template_items, start=1):
        CaseChecklistItem.objects.create(
            case=case,
            source_template_item=template_item,
            note=template_item.description,
            sort_order=index,
            **{field: getattr(template_item, field) for field in ITEM_COPY_FIELDS},
        )


def remove_template_items(apps, schema_editor):
    Case = apps.get_model('cases', 'Case')
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    CaseChecklistItem = apps.get_model('cases', 'CaseChecklistItem')

    case = Case.objects.filter(case_number=CASE_NUMBER).first()
    template = CaseChecklistTemplate.objects.filter(name=TEMPLATE_NAME).first()
    if not case or not template:
        return
    CaseChecklistItem.objects.filter(case=case, source_template_item__template=template).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0015_case_residence_card_received_at'),
    ]

    operations = [
        migrations.RunPython(apply_template_to_case, remove_template_items),
    ]
