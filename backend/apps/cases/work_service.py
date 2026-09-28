"""案件の作業状態（Next Action・待機）と案件経過の記録サービス。

13 の進捗 status は変更しない。すべての変更は事務（select_for_update）の中で行い、
業務の経過は Timeline、システム操作は AuditLog に記録する。権限（案件を変更できるか）は
呼び出し側の ViewSet で BusinessAccessPolicy が判定済みであることを前提とする。
"""
from datetime import date

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.audit.services import record
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .models import Case

TERMINAL_STATUSES = {Case.STATUS_COMPLETED, Case.STATUS_WITHDRAWN, Case.STATUS_REJECTED}
WAITING_REASON_LABELS = dict(Case.WAITING_REASON_CHOICES)


class CaseWorkError(Exception):
    def __init__(self, detail, field=None):
        super().__init__(detail)
        self.detail = detail
        self.field = field


def _parse_date(value, field):
    if value in (None, ''):
        return None
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        raise CaseWorkError('日付の形式が正しくありません。', field)
    return parsed


def _lock(case):
    return Case.objects.select_for_update().get(pk=case.pk)


def _audit(request, action, case, extra=None):
    record(module='cases', action=action, request=request, obj=case, extra=extra or {})


def validate_next_action_assignee(case, assignee):
    """担当者に指定できるのは、その案件を閲覧できる利用者（アカウント未関連の担当者は記録のみ可）。"""
    if assignee is None:
        return
    if not assignee.is_active:
        raise CaseWorkError('無効な担当者は指定できません。', 'assignee')
    user = assignee.user
    if user is None:
        return
    from apps.authentication.access_policy import ALLOW, BusinessAccessPolicy

    if BusinessAccessPolicy(user).decide('case', case, 'view') != ALLOW:
        raise CaseWorkError('この担当者はこの案件を閲覧できないため、次の対応の担当者に指定できません。', 'assignee')


def set_next_action(case, *, text, assignee=None, due_at=None, blocked_reason='', actor=None, request=None):
    text = (text or '').strip()
    if not text:
        raise CaseWorkError('次の対応を入力してください。', 'next_action')
    due = _parse_date(due_at, 'next_action_due_at')
    validate_next_action_assignee(case, assignee)
    with transaction.atomic():
        locked = _lock(case)
        previous = {
            'next_action': locked.next_action,
            'next_action_due_at': locked.next_action_due_at.isoformat() if locked.next_action_due_at else None,
            'assignee_id': locked.next_action_assignee_id,
        }
        locked.next_action = text
        locked.next_action_due_at = due
        locked.next_action_assignee = assignee
        locked.next_action_blocked_reason = (blocked_reason or '').strip()
        locked.next_action_completed_at = None
        locked.next_action_completed_by = None
        locked.save(update_fields=[
            'next_action', 'next_action_due_at', 'next_action_assignee', 'next_action_blocked_reason',
            'next_action_completed_at', 'next_action_completed_by', 'updated_at',
        ])
        lines = [f'次の対応：{text}']
        if due:
            lines.append(f'期限：{due.isoformat()}')
        if assignee:
            lines.append(f'担当：{assignee.name}')
        if locked.next_action_blocked_reason:
            lines.append(f'阻害要因：{locked.next_action_blocked_reason}')
        record_case_event(
            locked, Timeline.EVENT_ACTION_CREATED, '次の対応を設定', description='\n'.join(lines), actor=actor,
            metadata={'due_at': due.isoformat() if due else None, 'assignee_id': assignee.pk if assignee else None,
                      'blocked': bool(locked.next_action_blocked_reason)},
        )
        _audit(request, 'case_next_action_set', locked, {'previous': previous})
    return locked


def complete_next_action(case, *, note='', actor=None, request=None):
    with transaction.atomic():
        locked = _lock(case)
        if not locked.next_action:
            raise CaseWorkError('完了にする次の対応がありません。', 'next_action')
        if locked.next_action_completed_at:
            raise CaseWorkError('この次の対応は既に完了しています。', 'next_action')
        locked.next_action_completed_at = timezone.now()
        locked.next_action_completed_by = actor if getattr(actor, 'is_authenticated', False) else None
        locked.save(update_fields=['next_action_completed_at', 'next_action_completed_by', 'updated_at'])
        lines = [f'完了：{locked.next_action}']
        if note:
            lines.append(f'備考：{note.strip()}')
        record_case_event(
            locked, Timeline.EVENT_ACTION_COMPLETED, '次の対応を完了', description='\n'.join(lines), actor=actor,
            metadata={'due_at': locked.next_action_due_at.isoformat() if locked.next_action_due_at else None},
        )
        _audit(request, 'case_next_action_completed', locked)
    return locked


def start_waiting(case, *, reason, note='', until=None, actor=None, request=None):
    if reason not in WAITING_REASON_LABELS:
        raise CaseWorkError('待機理由を選択してください。', 'waiting_reason')
    until_date = _parse_date(until, 'waiting_until')
    today = timezone.localdate()
    if until_date and until_date < today:
        raise CaseWorkError('予定終了日は今日以降にしてください。', 'waiting_until')
    with transaction.atomic():
        locked = _lock(case)
        if locked.status in TERMINAL_STATUSES:
            raise CaseWorkError('終了した案件は待機にできません。', 'work_status')
        if locked.work_status == Case.WORK_STATUS_WAITING:
            raise CaseWorkError('既に待機中です。', 'work_status')
        locked.work_status = Case.WORK_STATUS_WAITING
        locked.waiting_reason = reason
        locked.waiting_note = (note or '').strip()
        locked.waiting_since = today
        locked.waiting_until = until_date
        locked.save(update_fields=['work_status', 'waiting_reason', 'waiting_note', 'waiting_since', 'waiting_until', 'updated_at'])
        lines = [f'理由：{WAITING_REASON_LABELS[reason]}']
        if until_date:
            lines.append(f'予定終了日：{until_date.isoformat()}')
        if locked.waiting_note:
            lines.append(f'メモ：{locked.waiting_note}')
        record_case_event(
            locked, Timeline.EVENT_WAITING_STARTED, f'待機開始（{WAITING_REASON_LABELS[reason]}）',
            description='\n'.join(lines), actor=actor,
            metadata={'reason': reason, 'until': until_date.isoformat() if until_date else None},
        )
        _audit(request, 'case_waiting_started', locked, {'reason': reason})
    return locked


def end_waiting(case, *, note='', actor=None, request=None):
    with transaction.atomic():
        locked = _lock(case)
        if locked.work_status != Case.WORK_STATUS_WAITING:
            raise CaseWorkError('待機中ではありません。', 'work_status')
        reason = locked.waiting_reason
        since = locked.waiting_since
        days = (timezone.localdate() - since).days if since else None
        locked.work_status = Case.WORK_STATUS_ACTIVE
        locked.waiting_reason = ''
        locked.waiting_note = ''
        locked.waiting_since = None
        locked.waiting_until = None
        locked.save(update_fields=['work_status', 'waiting_reason', 'waiting_note', 'waiting_since', 'waiting_until', 'updated_at'])
        lines = [f'理由：{WAITING_REASON_LABELS.get(reason, reason)}']
        if days is not None:
            lines.append(f'待機日数：{days}日')
        if note:
            lines.append(f'備考：{note.strip()}')
        record_case_event(
            locked, Timeline.EVENT_WAITING_ENDED, '待機終了', description='\n'.join(lines), actor=actor,
            metadata={'reason': reason, 'since': since.isoformat() if since else None, 'days': days},
        )
        _audit(request, 'case_waiting_ended', locked, {'reason': reason, 'days': days})
    return locked


def record_payment_link(case, *, amount=None, received_on=None, note='', reference='', actor=None, request=None):
    """入金の「案件経過への記録」だけを行う。会計データは作らない（会計は Accounting モジュールの責務）。"""
    received = _parse_date(received_on, 'received_on') or timezone.localdate()
    amount_text = ''
    if amount not in (None, ''):
        try:
            amount_value = int(str(amount).replace(',', ''))
        except ValueError as exc:
            raise CaseWorkError('金額は整数で入力してください。', 'amount') from exc
        if amount_value < 0:
            raise CaseWorkError('金額は 0 以上で入力してください。', 'amount')
        amount_text = f'{amount_value:,}円'
    lines = [f'入金日：{received.isoformat()}']
    if amount_text:
        lines.append(f'金額：{amount_text}')
    if reference:
        lines.append(f'会計側の参照：{reference.strip()}')
    if note:
        lines.append(f'備考：{note.strip()}')
    with transaction.atomic():
        timeline = record_case_event(
            case, Timeline.EVENT_PAYMENT_RECEIVED, '入金を確認', description='\n'.join(lines), actor=actor,
            occurred_at=received,
            metadata={'amount_recorded': bool(amount_text), 'reference': (reference or '').strip()[:100],
                      'accounting_record_created': False},
        )
        _audit(request, 'case_payment_noted', case, {'timeline_id': timeline.id})
    return timeline


def receive_checklist_item(item, *, document=None, received_on=None, note='', complete=False, actor=None, request=None):
    """資料受領：受領日と（任意で）同じ案件の既存 Document を関連付け、Timeline に記録する。

    complete=True のときは Checklist 項目も完了にする。Google Drive などの外部保存先は扱わない。
    """
    from .models import CaseChecklistItem

    received = _parse_date(received_on, 'received_on') or timezone.localdate()
    if document is not None and document.case_id != item.case_id:
        raise CaseWorkError('同じ案件のファイルだけを関連付けできます。', 'document')
    employee = getattr(actor, 'employee', None) if actor is not None and hasattr(actor, 'employee') else None
    with transaction.atomic():
        locked = CaseChecklistItem.objects.select_for_update().select_related('case').get(pk=item.pk)
        locked.received_at = received
        if document is not None:
            locked.document = document
        fields = ['received_at', 'document', 'updated_at']
        completed_now = complete and not locked.is_completed
        if completed_now:
            locked.is_completed = True
            locked.completed_at = timezone.now()
            locked.completed_by = employee
            fields += ['is_completed', 'completed_at', 'completed_by']
        locked.save(update_fields=fields)
        lines = [f'受領日：{received.isoformat()}']
        if document is not None:
            lines.append(f'ファイル：{document.title}')
        if note:
            lines.append(f'備考：{note.strip()}')
        record_case_event(
            locked.case, Timeline.EVENT_DOCUMENT_RECEIVED, f'資料受領：{locked.name}', description='\n'.join(lines),
            actor=actor, occurred_at=received,
            metadata={'checklist_item_id': locked.id, 'document_id': document.pk if document else None},
        )
        if completed_now:
            record_case_event(
                locked.case, Timeline.EVENT_CHECKLIST_COMPLETED, f'資料・タスク完了：{locked.name}', actor=actor,
                metadata={'checklist_item_id': locked.id, 'category': locked.category},
            )
        record(module='cases', action='checklist_item_received', request=request, obj=locked,
               extra={'case_id': locked.case_id, 'document_id': document.pk if document else None,
                      'completed': completed_now})
    return locked
