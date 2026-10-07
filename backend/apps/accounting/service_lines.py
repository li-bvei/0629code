"""サービス項目（P4）の明細行スナップショットと委託底価の扱い。

明細行（line_items の 1 行）に追加する後端管理のキー：
- line_key：帳票内で一意の行識別子。後端が生成し、保存済みの行と一致する場合だけ引き継ぐ。
- service_item_id：選んだサービス項目（手入力の行には無い）。
- service：選んだ時点のサービス項目の内容（底価は含めない）。後端がマスタから作り、客户端の値は使わない。

委託底価は行に入れず、帳票の internal_line_costs に line_key で対応させて持つ（底価権限者にだけ返す）。
発行スナップショット・状態履歴・PDF・明細の検索は line_items だけを見るため、底価は混ざらない。

行の扱い：
- 保存済みの行（line_key 一致）で service_item_id が同じなら、保存済みのスナップショットと底価を引き継ぐ
  （マスタが後で変わっても、無効化されても、その行の内容は変わらない）。
- それ以外で service_item_id がある行は「新しい選択」。有効なマスタからスナップショットと底価を作る。
  客户端が line_key を入れ替えても、項目が一致しない限り別の行の底価は引き継がれない。
"""
import uuid

from django.utils import timezone

from .voucher_calculations import decimal_to_number

SERVICE_LINE_KEYS = ('line_key', 'service_item_id', 'service')
# 客户端から受け取らない（送られても捨てる）内部キー
INTERNAL_LINE_KEYS = ('floor_price', 'internal_cost', 'internal_line_costs', 'cost', 'floor')


class ServiceLineError(ValueError):
    def __init__(self, message, row=None):
        super().__init__(message)
        self.row = row


def _number(value):
    return None if value is None else decimal_to_number(value)


def _parse_id(value):
    if value in (None, '', 0, '0'):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 'invalid'
    return parsed if parsed > 0 else 'invalid'


def service_snapshot(item, now=None):
    """明細行・案件に残すサービス項目の内容（底価・社内メモは含めない）。"""
    return {
        'id': item.id,
        'category': item.category,
        'name': item.name,
        'default_price': _number(item.default_price),
        'price_type': item.price_type,
        'tax_category': item.tax_category,
        'unit': item.unit,
        'professional_type': item.professional_type,
        'professional_type_display': item.get_professional_type_display() if item.professional_type else '',
        # P6：選んだ時点の価格の状態（暫定／確定）。後で確定しても過去の帳票・案件の表示は変わらない
        'price_status': item.price_status,
        'code': item.code or '',
        'selected_at': (now or timezone.now()).isoformat(),
    }


def cost_snapshot(item, line_key, now=None):
    return {
        'line_key': line_key,
        'service_item_id': item.id,
        'floor_price': _number(item.floor_price),
        'professional_type': item.professional_type,
        'captured_at': (now or timezone.now()).isoformat(),
    }


def strip_service_keys(lines):
    """サービス項目を使わない帳票（契約書・領収書）用：後端管理のキーと内部キーを外す。"""
    result = []
    for line in lines or []:
        if isinstance(line, dict):
            line = {k: v for k, v in line.items() if k not in SERVICE_LINE_KEYS and k not in INTERNAL_LINE_KEYS}
        result.append(line)
    return result


def _new_key(taken):
    while True:
        key = uuid.uuid4().hex[:12]
        if key not in taken:
            return key


def apply_service_lines(lines, old_lines=None, old_costs=None):
    """正規化済みの明細行にスナップショットを付ける。戻り値は (行, 底価リスト, 新しく使った項目 ID の集合)。"""
    from .models import ServiceItem

    now = timezone.now()
    old_by_key = {
        line['line_key']: line for line in (old_lines or [])
        if isinstance(line, dict) and isinstance(line.get('line_key'), str) and line['line_key']
    }
    costs_by_key = {
        cost['line_key']: cost for cost in (old_costs or [])
        if isinstance(cost, dict) and isinstance(cost.get('line_key'), str)
    }

    prepared = []
    taken = set(old_by_key)
    used = set()
    needed_ids = set()
    for index, raw in enumerate(lines or [], start=1):
        if not isinstance(raw, dict):
            continue
        line = {k: v for k, v in raw.items() if k not in INTERNAL_LINE_KEYS}
        key = line.get('line_key')
        old = old_by_key.get(key) if isinstance(key, str) and key not in used else None
        if old is None:
            key = _new_key(taken | used)
        used.add(key)
        line['line_key'] = key
        service_id = _parse_id(line.get('service_item_id'))
        if service_id == 'invalid':
            raise ServiceLineError(f'{index} 行目：サービス項目の指定が正しくありません。', row=index)
        inherited = (
            old is not None and service_id is not None and old.get('service_item_id') == service_id
            and isinstance(old.get('service'), dict)
        )
        if service_id is not None and not inherited:
            needed_ids.add(service_id)
        prepared.append((index, line, old, service_id, inherited))

    items = ServiceItem.objects.in_bulk(needed_ids) if needed_ids else {}
    result, costs, newly_used = [], [], set()
    for index, line, old, service_id, inherited in prepared:
        if service_id is None:
            line.pop('service_item_id', None)
            line.pop('service', None)
        elif inherited:
            line['service_item_id'] = service_id
            line['service'] = old['service']
            cost = costs_by_key.get(line['line_key'])
            if cost and cost.get('service_item_id') == service_id:
                costs.append(cost)
        else:
            item = items.get(service_id)
            if item is None:
                raise ServiceLineError(f'{index} 行目：サービス項目が見つかりません。', row=index)
            if not item.is_active:
                raise ServiceLineError(f'{index} 行目：「{item.name}」は無効のため新しく選べません。', row=index)
            line['service_item_id'] = service_id
            line['service'] = service_snapshot(item, now)
            costs.append(cost_snapshot(item, line['line_key'], now))
            newly_used.add(service_id)
        result.append(line)
    return result, costs, newly_used


def mark_used(item_ids):
    """初めて帳票・案件で使われた項目に first_used_at を付ける（以後は物理削除できない）。"""
    from .models import ServiceItem

    if item_ids:
        ServiceItem.objects.filter(pk__in=item_ids, first_used_at__isnull=True).update(first_used_at=timezone.now())


def case_service_items(entries):
    """新規受付で選んだサービス項目（参考）を案件用のスナップショットにする。戻り値は (一覧, 使った ID)。

    entries: [{'service_item': id, 'quantity': n}]。無効・存在しない項目は選べない。底価は含めない。
    """
    from .models import ServiceItem

    now = timezone.now()
    ids = []
    for index, entry in enumerate(entries or [], start=1):
        service_id = _parse_id((entry or {}).get('service_item'))
        if service_id in (None, 'invalid'):
            raise ServiceLineError(f'{index} 件目：サービス項目を選択してください。', row=index)
        ids.append(service_id)
    items = ServiceItem.objects.in_bulk(set(ids))
    result = []
    for index, (entry, service_id) in enumerate(zip(entries or [], ids), start=1):
        item = items.get(service_id)
        if item is None:
            raise ServiceLineError(f'{index} 件目：サービス項目が見つかりません。', row=index)
        if not item.is_active:
            raise ServiceLineError(f'{index} 件目：「{item.name}」は無効のため選べません。', row=index)
        snapshot = service_snapshot(item, now)
        snapshot['quantity'] = _number(entry.get('quantity')) if entry.get('quantity') not in (None, '') else 1
        result.append(snapshot)
    return result, set(ids)


def provisional_lines(lines):
    """暫定価格から作った明細行の番号（1 始まり）。発行前の確認に使う。"""
    return [index for index, line in enumerate(lines or [], start=1)
            if isinstance(line, dict) and isinstance(line.get('service'), dict)
            and line['service'].get('price_status') == 'provisional']
