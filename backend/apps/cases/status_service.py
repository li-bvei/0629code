from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.timelines.models import Timeline

from .models import Case, CaseChecklistItem


CASE_STATUS_LABELS = dict(Case.STATUS_CHOICES)
REGISTRATION_STATUS_LABELS = dict(Case.REGISTRATION_STATUS_CHOICES)


class CaseStatusChangeError(Exception):
    def __init__(self, detail, warnings=None, requires_force=False):
        super().__init__(detail)
        self.detail = detail
        self.warnings = warnings or []
        self.requires_force = requires_force


@dataclass
class CaseStatusChangeResult:
    case_id: int
    previous_status: str
    new_status: str
    warnings: list
    timeline_created: bool
    forced: bool
    event: dict


def get_required_checklist_progress(case):
    queryset = CaseChecklistItem.objects.filter(case=case, is_required=True)
    total = queryset.count()
    completed = queryset.filter(is_completed=True).count()
    remaining = max(total - completed, 0)
    percent = round((completed / total) * 100) if total else 0
    all_completed = total > 0 and remaining == 0
    suggested_status = ''
    suggestion_message = ''
    if all_completed and case.status == Case.STATUS_COLLECTING_DOCUMENTS:
        suggested_status = Case.STATUS_PREPARING_DOCUMENTS
        suggestion_message = '必須事項がすべて完了しました。案件状態を「書類作成中」に変更できます。'
    return {
        'required_items_total': total,
        'required_items_completed': completed,
        'required_items_remaining': remaining,
        'required_items_progress_percent': percent,
        'all_required_items_completed': all_completed,
        'suggested_case_status': suggested_status,
        'suggestion_message': suggestion_message,
    }


def _warning(code, message):
    return {'code': code, 'message': message}


def _required_items_incomplete_warning(case):
    remaining = get_required_checklist_progress(case)['required_items_remaining']
    if remaining:
        return _warning('required_items_incomplete', f'未完了の必須事項が{remaining}件あります。')
    return None


def build_case_status_warnings(case, new_status):
    warnings = []
    if new_status in [Case.STATUS_READY_TO_APPLY, Case.STATUS_APPLIED]:
        warning = _required_items_incomplete_warning(case)
        if warning:
            warnings.append(warning)
    if new_status == Case.STATUS_APPLIED and case.status in [Case.STATUS_CONSULTATION, Case.STATUS_ACCEPTED]:
        warnings.append(_warning('direct_status_jump', '現在の状態から申請済みへ直接変更します。'))
    if new_status == Case.STATUS_COMPLETED:
        unfinished_count = CaseChecklistItem.objects.filter(case=case, is_completed=False).count()
        if unfinished_count:
            warnings.append(_warning('checklist_items_incomplete', f'未完了の案件事項が{unfinished_count}件あります。'))
        if case.status not in [Case.STATUS_APPROVED, Case.STATUS_REJECTED, Case.STATUS_WITHDRAWN]:
            warnings.append(_warning('result_status_not_terminal', '結果状態が許可・不許可・取下げではありません。'))
    return warnings


def build_registration_status_warnings(case, new_status):
    if new_status != Case.REGISTRATION_STATUS_ARCHIVED:
        return []
    if case.status not in [
        Case.STATUS_COMPLETED,
        Case.STATUS_APPROVED,
        Case.STATUS_REJECTED,
        Case.STATUS_WITHDRAWN,
    ]:
        return [_warning('business_status_not_finished', '現在の状態が完了・許可・不許可・取下げではありません。')]
    return []


def _normalize_change_date(change_date):
    if not change_date:
        return timezone.localdate()
    if isinstance(change_date, date):
        return change_date
    return date.fromisoformat(str(change_date))


def _create_timeline(case, title, previous_label, new_label, changed_by, change_date, note, forced, source):
    actor = getattr(changed_by, 'get_username', lambda: '')() if changed_by else ''
    lines = [
        f'{previous_label} → {new_label}',
        f'担当：{actor or "不明"}',
        f'変更日：{change_date}',
        f'強制変更：{"true" if forced else "false"}',
        f'変更元：{source}',
    ]
    if note:
        lines.append(f'備考：{note}')
    return Timeline.objects.create(
        case=case,
        occurred_at=change_date,
        title=title,
        content='\n'.join(lines),
        is_visible_to_client=False,
    )


def change_case_status(case, new_status, changed_by, change_date=None, note='', force=False, source='manual'):
    valid_statuses = {choice[0] for choice in Case.STATUS_CHOICES}
    if new_status not in valid_statuses:
        raise CaseStatusChangeError('指定された状態は使用できません。')
    note = (note or '').strip()
    if force and not note:
        raise CaseStatusChangeError('強制変更する場合は備考を入力してください。')

    with transaction.atomic():
        locked_case = Case.objects.select_for_update().get(pk=case.pk)
        warnings = build_case_status_warnings(locked_case, new_status)
        if warnings and not force:
            raise CaseStatusChangeError('状態変更には確認が必要です。', warnings=warnings, requires_force=True)
        previous_status = locked_case.status
        change_date_value = _normalize_change_date(change_date)
        locked_case.status = new_status
        if new_status == Case.STATUS_COMPLETED and not locked_case.completed_at:
            locked_case.completed_at = change_date_value
            locked_case.save(update_fields=['status', 'completed_at', 'updated_at'])
        else:
            locked_case.save(update_fields=['status', 'updated_at'])
        timeline = _create_timeline(
            locked_case,
            '案件状態変更',
            CASE_STATUS_LABELS.get(previous_status, previous_status),
            CASE_STATUS_LABELS.get(new_status, new_status),
            changed_by,
            change_date_value,
            note,
            force,
            source,
        )
        event = {
            'event_type': 'case_status_changed',
            'case_id': locked_case.id,
            'previous_status': previous_status,
            'new_status': new_status,
            'changed_by': getattr(changed_by, 'id', None),
            'changed_at': timezone.now().isoformat(),
            'metadata': {'timeline_id': timeline.id, 'source': source, 'forced': force},
        }
    return CaseStatusChangeResult(locked_case.id, previous_status, new_status, warnings, True, force, event)


def change_case_registration_status(case, new_status, changed_by, change_date=None, note='', force=False, source='manual'):
    valid_statuses = {choice[0] for choice in Case.REGISTRATION_STATUS_CHOICES}
    if new_status not in valid_statuses:
        raise CaseStatusChangeError('指定された登録状態は使用できません。')
    note = (note or '').strip()
    if force and not note:
        raise CaseStatusChangeError('強制変更する場合は備考を入力してください。')

    with transaction.atomic():
        locked_case = Case.objects.select_for_update().get(pk=case.pk)
        warnings = build_registration_status_warnings(locked_case, new_status)
        if warnings and not force:
            raise CaseStatusChangeError('登録状態変更には確認が必要です。', warnings=warnings, requires_force=True)
        previous_status = locked_case.registration_status
        change_date_value = _normalize_change_date(change_date)
        locked_case.registration_status = new_status
        locked_case.save(update_fields=['registration_status', 'updated_at'])
        timeline = _create_timeline(
            locked_case,
            '登録状態変更',
            REGISTRATION_STATUS_LABELS.get(previous_status, previous_status),
            REGISTRATION_STATUS_LABELS.get(new_status, new_status),
            changed_by,
            change_date_value,
            note,
            force,
            source,
        )
        event = {
            'event_type': 'case_registration_status_changed',
            'case_id': locked_case.id,
            'previous_status': previous_status,
            'new_status': new_status,
            'changed_by': getattr(changed_by, 'id', None),
            'changed_at': timezone.now().isoformat(),
            'metadata': {'timeline_id': timeline.id, 'source': source, 'forced': force},
        }
    return CaseStatusChangeResult(locked_case.id, previous_status, new_status, warnings, True, force, event)
