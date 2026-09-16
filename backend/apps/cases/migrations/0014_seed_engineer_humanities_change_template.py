from django.db import migrations

SOURCE_TEMPLATE_NAME = '技人国ビザ新規申請'
NEW_TEMPLATE_NAME = '技人国ビザ変更申請'
CASE_TYPE_NAME = '技術・人文知識・国際業務'
APPLICATION_CATEGORY_NAME = '変更'

ITEM_COPY_FIELDS = [
    'category', 'name', 'item_type', 'quantity', 'unit', 'is_required',
    'description', 'responsible_party', 'acquisition_place', 'required_details',
    'internal_note', 'customer_note', 'is_visible_to_customer', 'importance_level',
    'sort_order',
]


def create_change_template(apps, schema_editor):
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    CaseChecklistTemplateItem = apps.get_model('cases', 'CaseChecklistTemplateItem')
    CaseTypeMaster = apps.get_model('cases', 'CaseTypeMaster')
    CaseApplicationCategory = apps.get_model('cases', 'CaseApplicationCategory')

    if CaseChecklistTemplate.objects.filter(name=NEW_TEMPLATE_NAME).exists():
        return

    source = CaseChecklistTemplate.objects.filter(name=SOURCE_TEMPLATE_NAME).first()
    case_type = CaseTypeMaster.objects.filter(name=CASE_TYPE_NAME).first()
    category = CaseApplicationCategory.objects.filter(name=APPLICATION_CATEGORY_NAME).first()
    if not source or not case_type or not category:
        return

    max_sort_order = CaseChecklistTemplate.objects.order_by('-sort_order').values_list(
        'sort_order', flat=True,
    ).first() or 0

    new_template = CaseChecklistTemplate.objects.create(
        name=NEW_TEMPLATE_NAME,
        description=f'{SOURCE_TEMPLATE_NAME}の必要資料を複製（資格変更用、新規と同一内容）。',
        case_type_master=case_type,
        application_category=category,
        is_active=True,
        sort_order=max_sort_order + 1,
    )

    source_items = source.items.filter(is_active=True, deleted_at__isnull=True).order_by('sort_order', 'id')
    for item in source_items:
        CaseChecklistTemplateItem.objects.create(
            template=new_template,
            **{field: getattr(item, field) for field in ITEM_COPY_FIELDS},
        )


def remove_change_template(apps, schema_editor):
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    CaseChecklistTemplate.objects.filter(name=NEW_TEMPLATE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0013_seed_checklist_template_case_type_links'),
    ]

    operations = [
        migrations.RunPython(create_change_template, remove_change_template),
    ]
