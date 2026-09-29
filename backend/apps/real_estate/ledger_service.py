"""法定台帳の操作（ロック・更正・年度締め・保存期限）。権限判定は access_rules、ここは業務規則と監査だけ。"""
from datetime import date

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record

from .models import LegalLedger, LegalLedgerCorrection

AUDIT_MODULE = 'real_estate'
# 事業年度の末月（既定 3 月）。会社の事業年度に合わせて設定で変える（本番前に確認する）。
FISCAL_YEAR_END_MONTH = getattr(settings, 'REAL_ESTATE_FISCAL_YEAR_END_MONTH', 3)

LEDGER_FIELDS = (
    'transaction_form', 'transaction_type', 'property_location', 'property_name', 'room_number', 'area_sqm',
    'building_outline', 'rent_or_price', 'remuneration', 'advertising_fee', 'handling_fee', 'special_terms',
    'contract_date',
)


def fiscal_year_of(day):
    """事業年度（末日の属する暦年で表す）。例：3 月決算なら 2026-04-01〜2027-03-31 は 2027 年度。"""
    if day is None:
        return None
    return day.year if day.month <= FISCAL_YEAR_END_MONTH else day.year + 1


def fiscal_year_end(year):
    import calendar

    return date(year, FISCAL_YEAR_END_MONTH, calendar.monthrange(year, FISCAL_YEAR_END_MONTH)[1])


def retention_until(ledger):
    """保存期限＝事業年度末日から保存年数（期限到来でも自動削除しない。到期復核の目安）。"""
    if not ledger.fiscal_year:
        return None
    end = fiscal_year_end(ledger.fiscal_year)
    try:
        return end.replace(year=end.year + ledger.retention_years)
    except ValueError:
        return end.replace(year=end.year + ledger.retention_years, day=28)


def refresh_derived(ledger):
    ledger.fiscal_year = fiscal_year_of(ledger.contract_date)
    ledger.retention_until = retention_until(ledger)


def _value(v):
    if v is None:
        return None
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    if hasattr(v, 'as_tuple'):
        return str(v)
    return v


def ledger_snapshot(ledger):
    tx = ledger.transaction
    return {
        **{f: _value(getattr(ledger, f)) for f in LEDGER_FIELDS},
        'fiscal_year': ledger.fiscal_year,
        'retention_until': _value(ledger.retention_until),
        'parties': [
            {'role': p.get_role_display(), 'name': p.name, 'address': p.address, 'license_number': p.license_number}
            for p in tx.parties.all()
        ],
        'transaction_number': tx.transaction_number,
        'version': ledger.version,
    }


def reject_if_locked(ledger, attrs):
    changed = [f for f in LEDGER_FIELDS if f in attrs and _value(attrs[f]) != _value(getattr(ledger, f))]
    if ledger.is_locked and changed:
        raise ValidationError({'detail': 'ロック済みの台帳は直接変更できません。更正として理由を付けて変更してください。',
                               'locked_fields': changed})


def lock(ledger, request):
    if ledger.is_locked:
        raise ValidationError({'detail': '既にロックされています。'})
    if not ledger.contract_date:
        raise ValidationError({'contract_date': '取引日を入力してからロックしてください。'})
    refresh_derived(ledger)
    ledger.is_locked = True
    ledger.locked_at = timezone.now()
    ledger.locked_by = request.user
    ledger.locked_snapshot = ledger_snapshot(ledger)
    ledger.save()
    record(module=AUDIT_MODULE, action='ledger_locked', request=request, obj=ledger,
           object_repr=ledger.transaction.transaction_number, extra={'version': ledger.version})
    return ledger


@db_transaction.atomic
def correct(ledger, changes, reason, request):
    if not ledger.is_locked:
        raise ValidationError({'detail': 'ロック前の台帳は通常の編集で変更してください。'})
    if not (reason or '').strip():
        raise ValidationError({'reason': '更正理由を入力してください。'})
    diff = {}
    for field, new in changes.items():
        if field not in LEDGER_FIELDS:
            raise ValidationError({field: '更正できない項目です。'})
        old = getattr(ledger, field)
        if _value(old) != _value(new):
            diff[field] = [_value(old), _value(new)]
            setattr(ledger, field, new)
    if not diff:
        raise ValidationError({'detail': '変更がありません。'})
    ledger.version += 1
    refresh_derived(ledger)
    ledger.locked_snapshot = ledger_snapshot(ledger)
    ledger.save()
    LegalLedgerCorrection.objects.create(ledger=ledger, version=ledger.version, changes=diff,
                                         reason=reason.strip(), corrected_by=request.user)
    record(module=AUDIT_MODULE, action='ledger_corrected', request=request, obj=ledger,
           object_repr=ledger.transaction.transaction_number, changes=diff, reason=reason.strip(),
           extra={'version': ledger.version})
    return ledger


@db_transaction.atomic
def close_fiscal_year(year, queryset, request):
    """指定年度の台帳をすべてロックし、締め日時を記録する（削除はしない）。"""
    rows = list(queryset.select_for_update().filter(fiscal_year=year))
    now = timezone.now()
    locked = 0
    for ledger in rows:
        if not ledger.is_locked:
            refresh_derived(ledger)
            ledger.is_locked, ledger.locked_at, ledger.locked_by = True, now, request.user
            ledger.locked_snapshot = ledger_snapshot(ledger)
            locked += 1
        ledger.fiscal_year_closed_at = ledger.fiscal_year_closed_at or now
        ledger.save()
    record(module=AUDIT_MODULE, action='ledger_fiscal_year_closed', request=request,
           object_type='real_estate.legalledger', object_id=str(year), object_repr=f'{year} 年度',
           extra={'fiscal_year': year, 'ledgers': len(rows), 'newly_locked': locked})
    return {'fiscal_year': year, 'ledgers': len(rows), 'newly_locked': locked}


def set_legal_hold(ledger, hold, reason, request):
    if hold and not (reason or '').strip():
        raise ValidationError({'reason': 'legal hold の理由を入力してください。'})
    ledger.legal_hold = bool(hold)
    ledger.legal_hold_reason = (reason or '').strip() if hold else ''
    ledger.save(update_fields=['legal_hold', 'legal_hold_reason', 'updated_at'])
    record(module=AUDIT_MODULE, action='ledger_legal_hold_set' if hold else 'ledger_legal_hold_released',
           request=request, obj=ledger, object_repr=ledger.transaction.transaction_number, reason=reason or '')
    return ledger


def ensure_ledger(tx):
    """取引の台帳を用意する（無ければ取引の値から下書きを作る。既存は変更しない）。"""
    try:
        return tx.legal_ledger
    except LegalLedger.DoesNotExist:
        pass
    ledger = LegalLedger(
        transaction=tx, transaction_type=tx.transaction_type, property_location=tx.property_address,
        property_name=tx.property_name, room_number=tx.room_number, area_sqm=tx.area_sqm,
        rent_or_price=tx.rent_or_price, remuneration=tx.brokerage_fee, advertising_fee=tx.advertising_fee,
        handling_fee=tx.handling_fee, contract_date=tx.transaction_date,
        retention_years=LegalLedger.DEFAULT_RETENTION_YEARS.get(tx.transaction_type, 5),
    )
    refresh_derived(ledger)
    ledger.save()
    return ledger
