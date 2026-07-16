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
        suggestion_message = '必須事項がすべて完了しました。現在の進捗を「書類作成中」に変更できます。'
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
        warnings.append(_warning('direct_status_jump', '現在の進捗から申請済みへ直接変更します。'))
    if new_status == Case.STATUS_COMPLETED:
        unfinished_count = CaseChecklistItem.objects.filter(case=case, is_completed=False).count()
        if unfinished_count:
            warnings.append(_warning('checklist_items_incomplete', f'未完了の案件事項が{unfinished_count}件あります。'))
        if case.status not in [Case.STATUS_APPROVED, Case.STATUS_REJECTED, Case.STATUS_WITHDRAWN]:
            warnings.append(_warning('result_status_not_terminal', '進捗が許可・不許可・取下げではありません。'))
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
        return [_warning('business_status_not_finished', '現在の進捗が完了・許可・不許可・取下げではありません。')]
    return []


def _normalize_change_date(change_date):
    if not change_date:
        return timezone.localdate()
    if isinstance(change_date, date):
        return change_date
    return date.fromisoformat(str(change_date))


def validate_case_progress_dates(case):
    if case.applied_at and case.result_received_at and case.result_received_at < case.applied_at:
        raise CaseStatusChangeError('結果日は申請日より前にできません。')
    if (
        case.applied_at
        and case.additional_documents_requested_at
        and case.additional_documents_requested_at < case.applied_at
    ):
        raise CaseStatusChangeError('追加資料依頼日は申請日より前にできません。')
    if (
        case.additional_documents_requested_at
        and case.additional_documents_submitted_at
        and case.additional_documents_submitted_at < case.additional_documents_requested_at
    ):
        raise CaseStatusChangeError('追加資料提出日は追加資料依頼日より前にできません。')
    if case.applied_at and case.completed_at and case.completed_at < case.applied_at:
        raise CaseStatusChangeError('完了日は申請日より前にできません。')


def _create_timeline(
    case,
    title,
    previous_label,
    new_label,
    changed_by,
    change_date,
    note,
    forced,
    source,
    detail_lines=None,
):
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
    if detail_lines:
        lines.extend(detail_lines)
    return Timeline.objects.create(
        case=case,
        occurred_at=change_date,
        title=title,
        content='\n'.join(lines),
        is_visible_to_client=False,
    )


def _format_date(value):
    return value.isoformat() if value else ''


def _apply_if_empty(locked_case, field_name, value, changed_fields, detail_lines, label):
    if value and not getattr(locked_case, field_name):
        setattr(locked_case, field_name, value)
        changed_fields.add(field_name)
        detail_lines.append(f'{label}：{_format_date(value)}')


def _apply_payload_field(locked_case, field_name, value, changed_fields, detail_lines, label):
    if value in [None, '']:
        return
    if getattr(locked_case, field_name) != value:
        setattr(locked_case, field_name, value)
        changed_fields.add(field_name)
        detail_lines.append(f'{label}：{value}')


def _apply_status_business_fields(locked_case, previous_status, new_status, change_date_value, status_payload):
    status_payload = status_payload or {}
    changed_fields = {'status', 'status_changed_at'}
    detail_lines = []

    locked_case.status_changed_at = change_date_value
    if new_status == Case.STATUS_CONSULTATION:
        _apply_if_empty(locked_case, 'consulted_at', change_date_value, changed_fields, detail_lines, '相談日')
    if new_status == Case.STATUS_ACCEPTED:
        _apply_if_empty(locked_case, 'accepted_at', change_date_value, changed_fields, detail_lines, '受任日')
    if new_status == Case.STATUS_COLLECTING_DOCUMENTS:
        _apply_if_empty(locked_case, 'document_collection_started_at', change_date_value, changed_fields, detail_lines, '資料待ち開始日')
    if new_status == Case.STATUS_PREPARING_DOCUMENTS:
        if get_required_checklist_progress(locked_case)['all_required_items_completed']:
            _apply_if_empty(locked_case, 'documents_completed_at', change_date_value, changed_fields, detail_lines, '必要資料完了日')
    if new_status == Case.STATUS_READY_TO_APPLY:
        _apply_if_empty(locked_case, 'application_ready_at', change_date_value, changed_fields, detail_lines, '申請準備完了日')
    if new_status == Case.STATUS_APPLIED:
        applied_at = _normalize_change_date(status_payload.get('applied_at') or change_date_value)
        _apply_payload_field(locked_case, 'applied_at', applied_at, changed_fields, detail_lines, '申請日')
        _apply_payload_field(locked_case, 'application_receipt_number', status_payload.get('application_receipt_number'), changed_fields, detail_lines, '受付番号')
    if new_status == Case.STATUS_UNDER_REVIEW:
        _apply_if_empty(locked_case, 'review_started_at', change_date_value, changed_fields, detail_lines, '審査開始日')
        if previous_status == Case.STATUS_ADDITIONAL_DOCUMENTS:
            _apply_if_empty(locked_case, 'additional_documents_submitted_at', change_date_value, changed_fields, detail_lines, '追加資料提出日')
        expected_result_at = status_payload.get('expected_result_at')
        if expected_result_at:
            _apply_payload_field(locked_case, 'expected_result_at', _normalize_change_date(expected_result_at), changed_fields, detail_lines, '結果予定日')
    if new_status == Case.STATUS_ADDITIONAL_DOCUMENTS:
        requested_at = _normalize_change_date(status_payload.get('additional_documents_requested_at') or change_date_value)
        _apply_payload_field(locked_case, 'additional_documents_requested_at', requested_at, changed_fields, detail_lines, '追加資料依頼日')
        _apply_payload_field(locked_case, 'additional_documents_detail', status_payload.get('additional_documents_detail'), changed_fields, detail_lines, '追加資料内容')
    if new_status == Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED:
        submitted_at = _normalize_change_date(status_payload.get('additional_documents_submitted_at') or change_date_value)
        _apply_payload_field(locked_case, 'additional_documents_submitted_at', submitted_at, changed_fields, detail_lines, '追加資料提出日')
    if new_status in [Case.STATUS_APPROVED, Case.STATUS_REJECTED]:
        result_received_at = _normalize_change_date(status_payload.get('result_received_at') or change_date_value)
        _apply_payload_field(locked_case, 'result_received_at', result_received_at, changed_fields, detail_lines, '結果日')
        if new_status == Case.STATUS_APPROVED:
            _apply_payload_field(locked_case, 'permission_number', status_payload.get('permission_number'), changed_fields, detail_lines, '許可番号')
        _apply_payload_field(locked_case, 'result_note', status_payload.get('result_note'), changed_fields, detail_lines, '結果備考')
    if new_status == Case.STATUS_WITHDRAWN:
        withdrawn_at = _normalize_change_date(status_payload.get('withdrawn_at') or change_date_value)
        _apply_payload_field(locked_case, 'withdrawn_at', withdrawn_at, changed_fields, detail_lines, '取下げ日')
    if new_status == Case.STATUS_COMPLETED:
        completed_at = _normalize_change_date(status_payload.get('completed_at') or change_date_value)
        _apply_payload_field(locked_case, 'completed_at', completed_at, changed_fields, detail_lines, '完了日')

    return changed_fields, detail_lines


def change_case_status(
    case,
    new_status,
    changed_by,
    change_date=None,
    note='',
    force=False,
    source='manual',
    next_action=None,
    next_action_due_at=None,
    status_payload=None,
):
    valid_statuses = {choice[0] for choice in Case.STATUS_CHOICES}
    if new_status not in valid_statuses:
        raise CaseStatusChangeError('指定された進捗は使用できません。')
    note = (note or '').strip()
    if force and not note:
        raise CaseStatusChangeError('強制変更する場合は備考を入力してください。')

    with transaction.atomic():
        locked_case = Case.objects.select_for_update().get(pk=case.pk)
        warnings = build_case_status_warnings(locked_case, new_status)
        if warnings and not force:
            raise CaseStatusChangeError('進捗変更には確認が必要です。', warnings=warnings, requires_force=True)
        previous_status = locked_case.status
        change_date_value = _normalize_change_date(change_date)
        locked_case.status = new_status
        changed_fields, detail_lines = _apply_status_business_fields(
            locked_case,
            previous_status,
            new_status,
            change_date_value,
            status_payload,
        )
        if next_action is not None:
            locked_case.next_action = (next_action or '').strip()
            changed_fields.add('next_action')
            if locked_case.next_action:
                detail_lines.append(f'次の対応：{locked_case.next_action}')
        if next_action_due_at is not None:
            locked_case.next_action_due_at = _normalize_change_date(next_action_due_at) if next_action_due_at else None
            changed_fields.add('next_action_due_at')
            if locked_case.next_action_due_at:
                detail_lines.append(f'対応期限：{_format_date(locked_case.next_action_due_at)}')
        validate_case_progress_dates(locked_case)
        locked_case.save(update_fields=[*changed_fields, 'updated_at'])
        timeline = _create_timeline(
            locked_case,
            '案件進捗変更',
            CASE_STATUS_LABELS.get(previous_status, previous_status),
            CASE_STATUS_LABELS.get(new_status, new_status),
            changed_by,
            change_date_value,
            note,
            force,
            source,
            detail_lines,
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


PROGRESS_INFO_FIELDS = {
    'applied_at': '申請日',
    'application_receipt_number': '申請受付番号',
    'additional_documents_requested_at': '追加資料依頼日',
    'additional_documents_detail': '追加資料内容',
    'additional_documents_submitted_at': '追加資料提出日',
    'result_received_at': '結果日',
    'permission_number': '許可番号',
    'result_note': '備考',
    'withdrawn_at': '取下げ日',
    'completed_at': '完了日',
}

DATE_PROGRESS_INFO_FIELDS = {
    'applied_at',
    'additional_documents_requested_at',
    'additional_documents_submitted_at',
    'result_received_at',
    'withdrawn_at',
    'completed_at',
}


def update_case_progress_info(case, payload, changed_by, note=''):
    with transaction.atomic():
        locked_case = Case.objects.select_for_update().get(pk=case.pk)
        changed_fields = set()
        detail_lines = []
        for field_name, label in PROGRESS_INFO_FIELDS.items():
            if field_name not in payload:
                continue
            old_value = getattr(locked_case, field_name)
            new_value = payload.get(field_name)
            if field_name in DATE_PROGRESS_INFO_FIELDS:
                new_value = _normalize_change_date(new_value) if new_value else None
            else:
                new_value = (new_value or '').strip()
            if old_value == new_value:
                continue
            setattr(locked_case, field_name, new_value)
            changed_fields.add(field_name)
            detail_lines.append(f'{label}：{old_value or "-"} → {new_value or "-"}')

        if not changed_fields:
            return {'changed': False, 'changed_fields': []}

        validate_case_progress_dates(locked_case)
        locked_case.save(update_fields=[*changed_fields, 'updated_at'])
        actor = getattr(changed_by, 'get_username', lambda: '')() if changed_by else ''
        lines = [
            *detail_lines,
            f'担当：{actor or "不明"}',
        ]
        if note:
            lines.append(f'備考：{note}')
        Timeline.objects.create(
            case=locked_case,
            occurred_at=timezone.localdate(),
            title='案件進捗情報変更',
            content='\n'.join(lines),
            is_visible_to_client=False,
        )
        return {'changed': True, 'changed_fields': sorted(changed_fields)}


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
        update_fields = ['registration_status', 'updated_at']
        detail_lines = []
        if new_status == Case.REGISTRATION_STATUS_ARCHIVED and not locked_case.archived_at:
            locked_case.archived_at = change_date_value
            update_fields.append('archived_at')
            detail_lines.append(f'アーカイブ日：{_format_date(change_date_value)}')
        locked_case.save(update_fields=update_fields)
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
            detail_lines,
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
