"""帳票（見積書・契約書・請求書・領収書）の共通基盤（P2-C11）。

共有するのは「採番・金額スナップショット・状態遷移の実行と監査」の仕組みだけ。
状態の種類と遷移は帳票ごとに別の Workflow として定義し、互いに連動させない
（見積書が受注になっても請求書の状態は変わらない、など）。
"""
import re
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record

from .models import DocumentNumberSequence
from .voucher_calculations import VoucherCalculationError, calculate_voucher_amounts, decimal_to_number

AUDIT_MODULE = 'voucher'

# --- 採番 ---------------------------------------------------------------------


def _max_existing_suffix(model, number_field, base):
    pattern = re.compile(rf'^{re.escape(base)}-(\d+)$')
    numbers = model.objects.filter(**{f'{number_field}__startswith': f'{base}-'}).values_list(number_field, flat=True)
    return max((int(m.group(1)) for m in map(pattern.match, numbers) if m), default=0)


def allocate_number(prefix, issue_date, model, number_field):
    """「接頭辞-YYYYMMDD-NNNN」を排他的に払い出す。既存の番号（旧来の採番分）より必ず大きくする。"""
    base = f'{prefix}-{issue_date:%Y%m%d}'
    for _ in range(3):
        try:
            with transaction.atomic():
                sequence, _ = DocumentNumberSequence.objects.select_for_update().get_or_create(key=base)
                number = max(sequence.last_number, _max_existing_suffix(model, number_field, base)) + 1
                sequence.last_number = number
                sequence.save(update_fields=['last_number', 'updated_at'])
            return f'{base}-{number:04d}'
        except IntegrityError:
            continue  # 同時に同じキーの連番行が作られた場合は取り直す
    raise ValidationError({'detail': '帳票番号を採番できませんでした。もう一度お試しください。'})


# --- 状態遷移（帳票ごとに別定義） ---------------------------------------------------

SNAPSHOT_FIELDS = (
    'issue_date', 'recipient_name', 'recipient_honorific', 'recipient_postal_code', 'recipient_address',
    'title', 'line_items', 'amount', 'tax_amount', 'total_amount',
    'issuer_name', 'issuer_postal_code', 'issuer_address', 'issuer_tel', 'issuer_registration_number',
)


def same_version(obj, version):
    """画面で見ていた版（updated_at の ISO 文字列）と一致するか。版を送らない場合は確認しない（旧画面互換）。"""
    if not version:
        return True
    from django.utils.dateparse import parse_datetime

    seen = parse_datetime(str(version))
    return seen is not None and obj.updated_at is not None and abs((obj.updated_at - seen).total_seconds()) < 0.001


class DocumentConflict(APIException):
    """画面で見ていた状態と現在の状態が違う（他の操作が先に行われた）。全体を中止する。"""

    status_code = http_status.HTTP_409_CONFLICT
    default_detail = '他の操作で状態が変わりました。画面を更新してからもう一度操作してください。'
    default_code = 'document_conflict'


@dataclass(frozen=True)
class Workflow:
    kind: str                      # 監査・表示用の帳票名（estimate / contract / invoice / receipt）
    label: str
    status_field: str
    transitions: dict              # 現在の状態 → 遷移できる状態
    editable_states: frozenset     # 内容（宛先・金額など）を編集・削除できる状態
    void_states: frozenset         # 取消・無効（スナップショットを取らない遷移先）
    date_on_enter: dict = field(default_factory=dict)  # 遷移先 → 日付を記録する列
    locked_fields: tuple = SNAPSHOT_FIELDS
    # 状態を自由に切り替えられる帳票（請求書・領収書）：有効な状態どうしを相互に変更でき、終端の状態を持たない。
    # 内容の編集は editable_states（下書き）のときだけ。発行後に直す場合は下書きに戻してから再発行する。
    free_transitions: bool = False
    history_kind: str = ''  # 状態履歴（VoucherStatusHistory）を残す帳票の種別

    def allowed_targets(self, current):
        if self.free_transitions:
            return [state for state in self.transitions[''] if state != (current or '')]
        return list(self.transitions.get(current or '', ()))

    def is_editable(self, obj):
        return (getattr(obj, self.status_field) or '') in self.editable_states


ESTIMATE_WORKFLOW = Workflow(
    kind='estimate', label='見積書', status_field='status',
    transitions={
        'draft': ('submitted', 'cancelled'),
        'submitted': ('accepted', 'declined', 'cancelled'),
    },
    editable_states=frozenset({'draft'}),
    void_states=frozenset({'cancelled'}),
    locked_fields=SNAPSHOT_FIELDS + ('valid_until',),
)

CONTRACT_WORKFLOW = Workflow(
    kind='contract', label='契約書', status_field='status',
    transitions={
        'draft': ('sent', 'cancelled'),
        'sent': ('signed', 'cancelled'),
        'signed': ('terminated',),
    },
    editable_states=frozenset({'draft'}),
    void_states=frozenset({'cancelled'}),
    date_on_enter={'signed': 'signed_date'},
    locked_fields=SNAPSHOT_FIELDS + ('start_date', 'end_date', 'payment_terms', 'body'),
)

# 請求書・領収書は既存の表に同居しているが、状態の列も遷移も別（互いに連動しない）。
# 空（''）は P2-C11 以前の旧データで、状態未設定のまま一覧・編集できる（空へ戻すことはできない）。
# 2026-10（P1）：有効な状態の間はどこからでも人工で切り替えられる。発行済み・無効からも下書きに戻せる。
INVOICE_WORKFLOW = Workflow(
    kind='invoice', label='請求書', status_field='invoice_status',
    transitions={'': ('draft', 'issued', 'sent', 'paid', 'cancelled')},
    editable_states=frozenset({'', 'draft'}),
    void_states=frozenset({'cancelled'}),
    date_on_enter={'paid': 'paid_date'},
    locked_fields=SNAPSHOT_FIELDS + ('details', 'payment_due_date', 'payment_method', 'bank_info', 'voucher_type'),
    free_transitions=True, history_kind='invoice',
)

RECEIPT_WORKFLOW = Workflow(
    kind='receipt', label='領収書', status_field='receipt_status',
    transitions={'': ('draft', 'issued', 'voided')},
    editable_states=frozenset({'', 'draft'}),
    void_states=frozenset({'voided'}),
    locked_fields=SNAPSHOT_FIELDS + ('details', 'payment_method', 'voucher_type'),
    free_transitions=True, history_kind='receipt',
)

# 状態履歴のスナップショットに含める項目（発行時スナップショットより広く、帳票の内容をすべて残す）
HISTORY_SNAPSHOT_FIELDS = SNAPSHOT_FIELDS + (
    'voucher_type', 'details', 'note', 'payment_due_date', 'payment_method', 'bank_info', 'paid_date',
    'invoice_status', 'receipt_status',
)


def workflow_for(obj):
    from .models import AccountingVoucher, Contract, Estimate

    if isinstance(obj, Estimate):
        return ESTIMATE_WORKFLOW
    if isinstance(obj, Contract):
        return CONTRACT_WORKFLOW
    if isinstance(obj, AccountingVoucher):
        return INVOICE_WORKFLOW if obj.voucher_type == AccountingVoucher.VOUCHER_TYPE_INVOICE else RECEIPT_WORKFLOW
    raise TypeError(type(obj))


def _json_value(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'as_tuple'):
        return decimal_to_number(value)
    return value


def build_snapshot(obj, user, fields=SNAPSHOT_FIELDS):
    data = {name: _json_value(getattr(obj, name)) for name in fields if hasattr(obj, name)}
    data['number'] = obj.number
    data['snapshot_at'] = timezone.now().isoformat()
    data['snapshot_by'] = user.get_username() if user is not None else ''
    return data


LINE_KEYS = ('item_name', 'quantity', 'unit_price', 'tax_category', 'price_type', 'line_total')


def _comparable(name, value):
    if name == 'line_items':
        try:
            items = calculate_voucher_amounts(value or [])[0]
        except VoucherCalculationError:
            return value
        return [{key: item.get(key) for key in LINE_KEYS} for item in items]
    if value is None:
        return '' if name not in ('issue_date', 'payment_due_date', 'valid_until', 'start_date', 'end_date') else None
    return _json_value(value)


def reject_locked_changes(workflow, instance, attrs):
    """発行後（編集可能な状態を離れた後）は宛先・金額などを変更させない。"""
    if instance is None or workflow.is_editable(instance):
        return
    changed = [
        name for name in workflow.locked_fields
        if name in attrs and _comparable(name, attrs[name]) != _comparable(name, getattr(instance, name))
    ]
    if changed:
        hint = '「下書き」に戻してから変更し、再発行してください' if workflow.free_transitions else '変更する場合は取消して作り直してください'
        raise ValidationError({
            'detail': f'{workflow.label}は下書き以外の状態のため内容を変更できません（{hint}）。',
            'locked_fields': changed,
        })


# P4：発行ごとに委託底価を版として残す帳票（サービス項目を使う帳票）
COST_SNAPSHOT_KINDS = ('estimate', 'invoice')


def record_issued_line_costs(obj, workflow, user, history=None):
    """発行時点の internal_line_costs を版ごとに残す（状態履歴・発行スナップショットとは別の表）。"""
    from .models import IssuedLineCostSnapshot

    previous = IssuedLineCostSnapshot.objects.filter(document_kind=workflow.kind, document_id=obj.pk).count()
    return IssuedLineCostSnapshot.objects.create(
        document_kind=workflow.kind, document_id=obj.pk, document_number=obj.number, version=previous + 1,
        status_history=history, line_costs=list(getattr(obj, 'internal_line_costs', None) or []), created_by=user,
    )


def _next_issue_version(obj, workflow):
    from .models import VoucherStatusHistory

    issued = VoucherStatusHistory.objects.filter(voucher=obj, document_kind=workflow.history_kind, to_status='issued')
    return issued.count() + 1


@transaction.atomic
def transition(obj, target, *, request, reason='', on_date=None, expected_status=None, confirm_provisional=False):
    """状態を変更する。行をロックしてから現在の状態を確認し、履歴と監査を同じトランザクションで残す。

    expected_status（画面で見ていた状態）が渡され、現在と違えば 409 で中止する（二重操作・古い画面の防止）。
    """
    from .models import VoucherStatusHistory

    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    workflow = workflow_for(obj)
    current = getattr(obj, workflow.status_field) or ''
    if expected_status is not None and (expected_status or '') != current:
        raise DocumentConflict()
    if target == current:
        raise ValidationError({'status': f'{workflow.label}は既にこの状態です。'})
    if target not in workflow.allowed_targets(current):
        raise ValidationError({'status': f'{workflow.label}をこの状態に変更できません。'})
    leaving_draft = current in workflow.editable_states and target not in workflow.editable_states
    issuing = leaving_draft and target not in workflow.void_states
    provisional = []
    if issuing:
        if not (obj.line_items or obj.total_amount):
            raise ValidationError({'line_items': '明細または金額がないため発行できません。'})
        # P6：暫定価格のサービス項目から作った行がある場合は、発行の前に明示的な確認を求める（止めはしない）
        from .service_lines import provisional_lines

        provisional = provisional_lines(obj.line_items) if workflow.kind in COST_SNAPSHOT_KINDS else []
        if provisional and not confirm_provisional:
            raise ValidationError({
                'code': 'provisional_price_confirmation_required',
                'detail': f'{workflow.label}に暫定価格のサービス項目（{"・".join(f"{n} 行目" for n in provisional)}）が含まれています。'
                          '価格を確認したうえで発行してください。',
                'provisional_rows': provisional,
            })
        obj.issued_snapshot = build_snapshot(obj, request.user)
    setattr(obj, workflow.status_field, target)
    obj.status_changed_at = timezone.now()
    date_field = workflow.date_on_enter.get(target)
    if date_field:
        setattr(obj, date_field, on_date or getattr(obj, date_field) or timezone.localdate())
    obj.updated_by = request.user
    obj.save()
    version = 0
    history = None
    if workflow.history_kind:
        version = _next_issue_version(obj, workflow) if target == 'issued' else 0
        history = VoucherStatusHistory.objects.create(
            voucher=obj, document_kind=workflow.history_kind, voucher_number=obj.number,
            from_status=current, to_status=target, version=version, reason=(reason or '')[:500],
            snapshot=build_snapshot(obj, request.user, HISTORY_SNAPSHOT_FIELDS), changed_by=request.user,
        )
    if issuing and workflow.kind in COST_SNAPSHOT_KINDS:
        record_issued_line_costs(obj, workflow, request.user, history)
    extra = {'version': version} if version else {}
    if provisional:
        extra['provisional_price_confirmed_rows'] = provisional
    record(
        module=AUDIT_MODULE, action=f'{workflow.kind}_status_changed', request=request, obj=obj,
        object_repr=f'{workflow.label} {obj.number}', changes={'status': [current, target]}, reason=reason,
        extra=extra or None,
    )
    return obj


def audit(request, obj, action, **kwargs):
    workflow = workflow_for(obj)
    record(module=AUDIT_MODULE, action=f'{workflow.kind}_{action}', request=request, obj=obj,
           object_repr=f'{workflow.label} {obj.number}', **kwargs)
