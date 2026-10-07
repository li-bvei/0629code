"""業務フローを持つ案件（P4）の段階変更。

- 同じフローの有効な段階へ、前後どちらにも人工で変更できる（「取下げ」へも、取下げから他の段階へも）。
- 変更はロックした行で行い、画面で見ていた段階（expected_stage）と違えば 409 相当のエラー。
- Case.status は段階の base_status に合わせる（一覧の完了判定・期限・並び順など既存処理用）。
- 完了日・取下げ日は、その段階に入った時に記録し、離れた時は空に戻す（経過は Timeline と監査に残る）。
- 従来の 13 段階の案件（workflow_template が空）はここでは扱わない（status_service を使う）。
"""
from django.db import transaction
from django.utils import timezone

from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .models import Case, WorkflowStage

STAGE_DATE_FIELDS = {
    Case.STATUS_COMPLETED: 'completed_at',
    Case.STATUS_WITHDRAWN: 'withdrawn_at',
}


class StageChangeError(Exception):
    def __init__(self, detail, code='invalid', status=400):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status = status


def _parse_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def change_stage(case, stage_id, *, actor, expected_stage=None, note=''):
    """段階を変更して (案件, 変更前の段階, 変更後の段階) を返す。"""
    target_id = _parse_id(stage_id)
    if target_id is None:
        raise StageChangeError('変更先の段階を選択してください。')
    note = (note or '').strip()
    with transaction.atomic():
        locked = Case.objects.select_for_update().select_related('workflow_stage').get(pk=case.pk)  # access-reviewed: 変更権限を確認済みの同じ案件をロックする
        if not locked.workflow_template_id:
            raise StageChangeError('この案件は従来の進捗（13 段階）で管理しています。進捗変更を使ってください。',
                                   code='legacy_workflow')
        if expected_stage not in (None, '') and _parse_id(expected_stage) != locked.workflow_stage_id:
            raise StageChangeError('他の操作で段階が変わりました。画面を更新してからもう一度操作してください。',
                                   code='stage_conflict', status=409)
        stage = WorkflowStage.objects.filter(template_id=locked.workflow_template_id, pk=target_id).first()
        if stage is None:
            raise StageChangeError('この案件の業務フローにない段階です。')
        if not stage.is_active:
            raise StageChangeError('無効になった段階には変更できません。')
        if stage.pk == locked.workflow_stage_id:
            raise StageChangeError('既にこの段階です。')
        previous = locked.workflow_stage
        today = timezone.localdate()
        changed = {'workflow_stage', 'status', 'status_changed_at', 'updated_at'}
        old_field = STAGE_DATE_FIELDS.get(locked.status)
        new_field = STAGE_DATE_FIELDS.get(stage.base_status)
        if old_field and old_field != new_field:
            setattr(locked, old_field, None)
            changed.add(old_field)
        if new_field:
            setattr(locked, new_field, today)
            changed.add(new_field)
        locked.workflow_stage = stage
        locked.status = stage.base_status
        locked.status_changed_at = today
        locked.save(update_fields=sorted(changed))
        previous_name = previous.name if previous else '-'
        description = f'{previous_name} → {stage.name}'
        if note:
            description += f'\n備考：{note}'
        record_case_event(
            locked, Timeline.EVENT_STATUS_CHANGED, f'段階を「{stage.name}」に変更', description=description,
            actor=actor, metadata={
                'workflow_template_id': locked.workflow_template_id,
                'from_stage_id': previous.pk if previous else None, 'to_stage_id': stage.pk,
            },
        )
    return locked, previous, stage
