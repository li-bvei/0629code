# P4（2026-10-06 用户确认）：業務フロー 3 種、新しい案件種別 4 種、既存「その他」の汎用フロー結び付け、
# 各種別の空の必要資料テンプレート。必要資料の項目は業務確認前のため作らない（空テンプレート＝結び付けのみ）。
# 既存案件は変更しない（workflow_template は空のまま＝従来の 13 段階）。
from django.db import migrations

# (code, 名称, 系統, 並び順, [(段階コード, 段階名, 対応する進捗)])
# 対応する進捗（base_status）は既存の一覧・ダッシュボード・期限処理用。画面には段階名を表示する。
WORKFLOWS = [
    ('general', '汎用', 'general', 10, [
        ('reception', '受付', 'accepted'),
        ('in_progress', '対応中', 'preparing_documents'),
        ('completed', '完了', 'completed'),
        ('withdrawn', '取下げ', 'withdrawn'),
    ]),
    ('professional', '専門家委託', 'professional', 20, [
        ('reception', '受付', 'accepted'),
        ('collecting', '資料収集', 'collecting_documents'),
        ('requested', '専門家へ依頼', 'applied'),
        ('in_progress', '専門家対応中', 'under_review'),
        ('result_received', '結果受領', 'approved'),
        ('completed', '完了', 'completed'),
        ('withdrawn', '取下げ', 'withdrawn'),
    ]),
    ('employee_procedure', '従業員・社会保険手続', 'employee_procedure', 30, [
        ('reception', '受付', 'accepted'),
        ('collecting', '資料収集', 'collecting_documents'),
        ('preparing', '書類作成', 'preparing_documents'),
        ('submitted', '窓口提出', 'applied'),
        ('acceptance_check', '受理確認', 'under_review'),
        ('completed', '完了', 'completed'),
        ('withdrawn', '取下げ', 'withdrawn'),
    ]),
]

# (名称, code, 案件番号略称, 業務フロー code, 並び順)
NEW_CASE_TYPES = [
    ('税理士委託', 'tax_accountant_commission', '税理士', 'professional', 110),
    ('会社解散', 'company_dissolution', '解散', 'professional', 120),
    ('就労ビザ社員入社手続', 'employee_onboarding', '入社', 'employee_procedure', 130),
    ('年金脱退・加入手続', 'pension_procedure', '年金', 'employee_procedure', 140),
]
OTHER_CODE = 'other'
TEMPLATE_DESCRIPTION = '必要資料は業務確認後に追加してください（P4 で種別との結び付けだけを作成）。'


def forward(apps, schema_editor):
    WorkflowTemplate = apps.get_model('cases', 'WorkflowTemplate')
    WorkflowStage = apps.get_model('cases', 'WorkflowStage')
    CaseTypeMaster = apps.get_model('cases', 'CaseTypeMaster')
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')

    workflows = {}
    for code, name, family, sort_order, stages in WORKFLOWS:
        template, _ = WorkflowTemplate.objects.get_or_create(
            code=code, defaults={'name': name, 'family': family, 'sort_order': sort_order},
        )
        workflows[code] = template
        for index, (stage_code, stage_name, base_status) in enumerate(stages, start=1):
            WorkflowStage.objects.get_or_create(
                template=template, code=stage_code,
                defaults={'name': stage_name, 'base_status': base_status, 'sort_order': index * 10},
            )

    case_types = []
    for name, code, abbreviation, workflow_code, sort_order in NEW_CASE_TYPES:
        case_type = CaseTypeMaster.objects.filter(code=code).first() or CaseTypeMaster.objects.filter(name=name).first()
        if case_type is None:
            case_type = CaseTypeMaster.objects.create(
                name=name, code=code, number_abbreviation=abbreviation, sort_order=sort_order,
            )
        case_type.workflow_template = workflows[workflow_code]
        case_type.requires_application_category = False
        if not case_type.number_abbreviation:
            case_type.number_abbreviation = abbreviation
        case_type.save(update_fields=['workflow_template', 'requires_application_category', 'number_abbreviation'])
        case_types.append(case_type)

    other = CaseTypeMaster.objects.filter(code=OTHER_CODE).first()
    if other is not None:
        other.workflow_template = workflows['general']
        other.requires_application_category = False
        other.save(update_fields=['workflow_template', 'requires_application_category'])
        case_types.append(other)

    for case_type in case_types:
        exists = CaseChecklistTemplate.objects.filter(
            case_type_master=case_type, application_category__isnull=True, deleted_at__isnull=True,
        ).exists()
        if not exists:
            CaseChecklistTemplate.objects.create(
                name=f'{case_type.name}（標準）', description=TEMPLATE_DESCRIPTION, case_type_master=case_type,
                application_category=None, sort_order=900,
            )


def backward(apps, schema_editor):
    """巻き戻し：P4 の結び付けを外し、この migration が作った空のテンプレート・未使用の種別・フローを消す。

    フローを持つ案件の workflow_template / workflow_stage は空に戻す（列自体も 0022 の巻き戻しで消える）。
    使われている案件種別は残す（案件が PROTECT で参照しているため）。
    """
    WorkflowTemplate = apps.get_model('cases', 'WorkflowTemplate')
    CaseTypeMaster = apps.get_model('cases', 'CaseTypeMaster')
    CaseChecklistTemplate = apps.get_model('cases', 'CaseChecklistTemplate')
    Case = apps.get_model('cases', 'Case')

    Case.objects.filter(workflow_template__isnull=False).update(workflow_template=None, workflow_stage=None)
    codes = [code for _, code, _, _, _ in NEW_CASE_TYPES]
    CaseTypeMaster.objects.filter(workflow_template__isnull=False).update(
        workflow_template=None, requires_application_category=True,
    )
    # 履歴モデルの削除（Collector）は巻き戻し時に別の状態のモデルと比較して失敗することがあるため、参照が
    # 無いことを ID で確かめてから SQL で消す（案件・テンプレートの参照は上で外すか、残す判断をしている）。
    quote = schema_editor.quote_name
    cursor = schema_editor.connection.cursor()
    empty_templates = list(CaseChecklistTemplate.objects.filter(
        case_type_master__code__in=codes + [OTHER_CODE], application_category__isnull=True,
        description=TEMPLATE_DESCRIPTION, items__isnull=True,
    ).values_list('pk', flat=True))
    for pk in empty_templates:
        cursor.execute(f'DELETE FROM {quote("case_checklist_templates")} WHERE id = %s', [pk])
    removable_types = [
        pk for pk in CaseTypeMaster.objects.filter(code__in=codes).values_list('pk', flat=True)
        if not Case.objects.filter(case_type_master_id=pk).exists()
        and not CaseChecklistTemplate.objects.filter(case_type_master_id=pk).exists()
    ]
    for pk in removable_types:
        cursor.execute(f'DELETE FROM {quote("case_type_masters")} WHERE id = %s', [pk])
    workflow_ids = list(WorkflowTemplate.objects.filter(code__in=[code for code, *_ in WORKFLOWS]).values_list('pk', flat=True))
    for pk in workflow_ids:
        cursor.execute(f'DELETE FROM {quote("case_workflow_stages")} WHERE template_id = %s', [pk])
        cursor.execute(f'DELETE FROM {quote("case_workflow_templates")} WHERE id = %s', [pk])


class Migration(migrations.Migration):
    dependencies = [('cases', '0023_db_defaults_for_rollback_compat_p4')]

    operations = [migrations.RunPython(forward, backward)]
