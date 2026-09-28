"""帳票（見積書・契約書・請求書・領収書）の共通基盤（P2-C11）。

共有するのは「採番・金額スナップショット・状態遷移の実行と監査」の仕組みだけ。
状態の種類と遷移は帳票ごとに別の Workflow として定義し、互いに連動させない
（見積書が受注になっても請求書の状態は変わらない、など）。
"""
import re
from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

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

    def allowed_targets(self, current):
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

# 請求書・領収書は既存の表に同居しているが、状態の列も遷移も別。
# 空（''）は P2-C11 以前の旧データで、状態未設定のまま一覧・編集できる。
INVOICE_WORKFLOW = Workflow(
    kind='invoice', label='請求書', status_field='invoice_status',
    transitions={
        '': ('draft', 'issued', 'sent', 'paid', 'cancelled'),
        'draft': ('issued', 'cancelled'),
        'issued': ('sent', 'paid', 'cancelled'),
        'sent': ('paid', 'cancelled'),
    },
    editable_states=frozenset({'', 'draft'}),
    void_states=frozenset({'cancelled'}),
    date_on_enter={'paid': 'paid_date'},
    locked_fields=SNAPSHOT_FIELDS + ('details', 'payment_due_date', 'payment_method', 'bank_info', 'voucher_type'),
)

RECEIPT_WORKFLOW = Workflow(
    kind='receipt', label='領収書', status_field='receipt_status',
    transitions={
        '': ('draft', 'issued', 'voided'),
        'draft': ('issued', 'voided'),
        'issued': ('voided',),
    },
    editable_states=frozenset({'', 'draft'}),
    void_states=frozenset({'voided'}),
    locked_fields=SNAPSHOT_FIELDS + ('details', 'payment_method', 'voucher_type'),
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


def build_snapshot(obj, user):
    data = {name: _json_value(getattr(obj, name)) for name in SNAPSHOT_FIELDS if hasattr(obj, name)}
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
        raise ValidationError({
            'detail': f'{workflow.label}は発行後のため内容を変更できません（変更する場合は取消して作り直してください）。',
            'locked_fields': changed,
        })


def transition(obj, target, *, request, reason='', on_date=None):
    workflow = workflow_for(obj)
    current = getattr(obj, workflow.status_field) or ''
    if target not in workflow.allowed_targets(current):
        raise ValidationError({'status': f'{workflow.label}をこの状態に変更できません。'})
    leaving_draft = current in workflow.editable_states and target not in workflow.editable_states
    if leaving_draft and target not in workflow.void_states:
        if not (obj.line_items or obj.total_amount):
            raise ValidationError({'line_items': '明細または金額がないため発行できません。'})
        obj.issued_snapshot = build_snapshot(obj, request.user)
    setattr(obj, workflow.status_field, target)
    obj.status_changed_at = timezone.now()
    date_field = workflow.date_on_enter.get(target)
    if date_field:
        setattr(obj, date_field, on_date or getattr(obj, date_field) or timezone.localdate())
    obj.updated_by = request.user
    obj.save()
    record(
        module=AUDIT_MODULE, action=f'{workflow.kind}_status_changed', request=request, obj=obj,
        object_repr=f'{workflow.label} {obj.number}', changes={'status': [current, target]}, reason=reason,
    )
    return obj


def audit(request, obj, action, **kwargs):
    workflow = workflow_for(obj)
    record(module=AUDIT_MODULE, action=f'{workflow.kind}_{action}', request=request, obj=obj,
           object_repr=f'{workflow.label} {obj.number}', **kwargs)
