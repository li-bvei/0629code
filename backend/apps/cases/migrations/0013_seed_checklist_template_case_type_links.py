from django.db import migrations


# テンプレート名 -> (案件種別名, 申請区分名) の対応。
# 「特別高度人材新規申請」は case_type_masters に対応する種別（特定高度人材/J-Skip）が
# 存在しないため対象外。誤って「高度専門職」に紐付けない。
TEMPLATE_LINKS = {
    '経営・管理新規申請': ('経営・管理', '新規'),
    '技人国ビザ新規申請': ('技術・人文知識・国際業務', '新規'),
    '経営・管理更新': ('経営・管理', '更新'),
    '技人国ビザ更新': ('技術・人文知識・国際業務', '更新'),
    '永住許可申請': ('永住許可', '新規'),
}


def link_templates(apps, schema_editor):
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    CaseTypeMaster = apps.get_model('cases', 'CaseTypeMaster')
    CaseApplicationCategory = apps.get_model('cases', 'CaseApplicationCategory')

    for template_name, (case_type_name, category_name) in TEMPLATE_LINKS.items():
        template = CaseChecklistTemplate.objects.filter(name=template_name).first()
        if not template:
            continue
        case_type = CaseTypeMaster.objects.filter(name=case_type_name).first()
        category = CaseApplicationCategory.objects.filter(name=category_name).first()
        if not case_type or not category:
            continue
        template.case_type_master = case_type
        template.application_category = category
        template.save(update_fields=['case_type_master', 'application_category'])


def unlink_templates(apps, schema_editor):
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    CaseChecklistTemplate.objects.filter(name__in=TEMPLATE_LINKS.keys()).update(
        case_type_master=None,
        application_category=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0012_casechecklisttemplate_application_category_and_more'),
    ]

    operations = [
        migrations.RunPython(link_templates, unlink_templates),
    ]
