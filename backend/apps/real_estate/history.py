"""不動産の操作履歴を、業務画面向けの日本語に整える。

AuditLog の技術情報は保持するが、通常表示では DB 項目名・ID・権限名を返さない。
"""
from apps.audit.services import safe_changes


TRANSACTION_FIELDS = {
    'party_name': ('当事者', lambda obj: obj.party_name),
    'customer': ('顧客主档', lambda obj: obj.customer.name if obj.customer_id else None),
    'property_name': ('物件名', lambda obj: obj.property_name),
    'room_number': ('部屋番号', lambda obj: obj.room_number),
    'property_address': ('所在地', lambda obj: obj.property_address),
    'property_kind': ('物件種類', lambda obj: obj.property_kind),
    'area_sqm': ('面積', lambda obj: obj.area_sqm),
    'management_company_name': ('管理会社', lambda obj: obj.management_company_name),
    'management_company': ('管理会社主档', lambda obj: obj.management_company.name if obj.management_company_id else None),
    'responsible_name': ('担当者', lambda obj: obj.responsible_name),
    'transaction_type': ('取引種別', lambda obj: obj.get_transaction_type_display()),
    'stage': ('段階', lambda obj: obj.get_stage_display()),
    'transaction_date': ('取引日', lambda obj: obj.transaction_date),
    'rent_or_price': ('賃料・価格', lambda obj: obj.rent_or_price),
    'brokerage_fee': ('仲介手数料', lambda obj: obj.brokerage_fee),
    'advertising_fee': ('広告料', lambda obj: obj.advertising_fee),
    'handling_fee': ('手数料', lambda obj: obj.handling_fee),
    'payment_status': ('支払状態', lambda obj: obj.get_payment_status_display()),
    'payment_date': ('支払日', lambda obj: obj.payment_date),
    'transfer_status': ('振込状態', lambda obj: obj.get_transfer_status_display()),
    'note': ('備考', lambda obj: obj.note),
}

FIELD_LABELS = {name: label for name, (label, _) in TRANSACTION_FIELDS.items()}
FIELD_LABELS.update({
    'transaction_form': '取引態様', 'property_location': '所在地', 'building_outline': '建物の概要',
    'remuneration': '報酬', 'special_terms': '特約', 'contract_date': '取引日',
    'role': '立場', 'name': '氏名・名称', 'address': '住所', 'license_number': '免許番号',
    'archive_state': '保管状態',
})


def transaction_values(obj, fields=None):
    names = fields or TRANSACTION_FIELDS.keys()
    return {name: getter(obj) for name, (_, getter) in TRANSACTION_FIELDS.items() if name in names}


def transaction_changes(before, after):
    return safe_changes(before, after)


def user_display_name(user):
    if user is None:
        return 'システム'
    employee = getattr(user, 'employee', None)
    if employee is not None and employee.name:
        return employee.name
    full_name = user.get_full_name().strip()
    return full_name or user.get_username()


def _actor(row):
    if row.employee_id and row.employee and row.employee.name:
        return row.employee.name
    if row.user_id and row.user:
        return user_display_name(row.user)
    return row.username_snapshot or 'システム'


def _display(value):
    if value is None or value == '':
        return '未登録'
    if value is True:
        return '有効'
    if value is False:
        return '無効'
    return str(value)


def _normalized_changes(raw):
    items = []
    for field, value in (raw or {}).items():
        if field not in FIELD_LABELS:
            continue
        if isinstance(value, dict) and ('from' in value or 'to' in value):
            before, after = value.get('from'), value.get('to')
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            before, after = value
        else:
            continue
        if before == after:
            continue
        items.append({'field': FIELD_LABELS[field], 'before': _display(before), 'after': _display(after)})
    return items


def _message(row, actor, changes):
    if row.action == 'transaction_created':
        return f'{actor}が不動産記録「{row.object_repr}」を新規登録しました'
    if row.action == 'transaction_updated':
        suffix = '（一括変更）' if (row.extra or {}).get('bulk') else ''
        if len(changes) == 1:
            change = changes[0]
            return f'{actor}が{change["field"]}を「{change["before"]}」から「{change["after"]}」に変更しました{suffix}'
        return f'{actor}が不動産記録の{len(changes)}項目を変更しました{suffix}'
    if row.action == 'transaction_archived':
        return f'{actor}が不動産記録「{row.object_repr}」をアーカイブしました'
    if row.action == 'transaction_restored':
        return f'{actor}が不動産記録「{row.object_repr}」を復元しました'
    templates = {
        'party_created': '当事者を追加しました', 'party_updated': '当事者を変更しました',
        'party_deleted': '当事者を削除しました', 'ledger_created': '法定台帳を作成しました',
        'ledger_updated': '法定台帳を変更しました', 'ledger_locked': '法定台帳をロックしました',
        'ledger_corrected': '法定台帳を更正しました', 'ledger_fiscal_year_closed': '法定台帳の年度を締めました',
        'ledger_legal_hold_set': '法定台帳を保存延長にしました',
        'ledger_legal_hold_released': '法定台帳の保存延長を解除しました',
        'ledger_exported': '法定台帳を出力しました', 'transaction_exported': '不動産記録を出力しました',
        'file_uploaded': 'ファイルを登録しました', 'file_download_started': 'ファイルをダウンロードしました',
        'accounting_linked': '会計参照を追加しました', 'accounting_unlinked': '会計参照を解除しました',
        'profit_distribution_created': '内部利益配分を追加しました',
        'profit_distribution_updated': '内部利益配分を変更しました',
        'profit_distribution_settled': '内部利益配分を結算済みにしました',
        'profit_distribution_reopened': '内部利益配分を草稿に戻しました',
        'profit_distribution_deleted': '内部利益配分を削除しました',
    }
    return f'{actor}が{templates.get(row.action, "操作を記録しました")}'


def serialize_history(row, *, include_technical=False):
    actor = _actor(row)
    changes = _normalized_changes(row.changes)
    result = {
        'occurred_at': row.occurred_at,
        'actor': actor,
        'message': _message(row, actor, changes),
        'changes': changes,
        'reason': row.reason or '',
    }
    if include_technical:
        result['technical_details'] = {
            'action': row.action,
            'object_type': row.object_type,
            'object_id': row.object_id,
            'result': row.result,
            'request_id': row.request_id,
            'via_permission': row.via_permission,
            'raw_changes': row.changes,
            'extra': row.extra,
        }
    return result
