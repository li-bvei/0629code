"""不動産記録の一括変更（絞り込み・選択の固定・検証・原子的な書き込み・履歴）。

- 権限判定は access_rules（bulk_change）。ここは業務規則と監査だけで、対象の queryset は
  ビューが BusinessAccessPolicy で絞ったものを受け取る。
- 変更できるのは段階・担当者・取引日だけ。アーカイブ状態・金額・法定台帳には触れない。
- 対象は必ず bulk-preview の署名付きトークンで固定する（ID・操作者・各記録の版）。プレビュー後に 1 件でも
  変更・アーカイブ・削除されていれば 409 で全体を中止する（部分的な書き込みをしない）。
"""
import uuid
from datetime import timezone as dt_timezone

from django.core import signing
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record
from apps.authentication.access_policy import ALLOW

from .history import transaction_changes, transaction_values
from .models import RealEstateTransaction

AUDIT_MODULE = 'real_estate'
BULK_FIELDS = ('stage', 'responsible_name', 'transaction_date')
CLEARABLE_FIELDS = {'responsible_name': '', 'transaction_date': None}
MAX_BULK_RECORDS = 2000
TOKEN_SALT = 'real_estate.bulk_selection'
TOKEN_MAX_AGE_SECONDS = 15 * 60

CHOICE_FILTERS = {
    'stage': ('段階', RealEstateTransaction.STAGE_CHOICES),
    'payment_status': ('支払状態', RealEstateTransaction.PAYMENT_CHOICES),
    'transfer_status': ('振込状態', RealEstateTransaction.TRANSFER_CHOICES),
    'transaction_type': ('取引種別', RealEstateTransaction.TYPE_CHOICES),
}


class BulkConflict(APIException):
    """選択後に対象の状態が変わった等で、一括変更を全体として中止する。"""

    status_code = status.HTTP_409_CONFLICT
    default_detail = '対象の状態が変わったため、一括変更を中止しました。一覧を更新してやり直してください。'
    default_code = 'bulk_conflict'


def _text(params, name):
    value = params.get(name)
    return value.strip() if isinstance(value, str) else ''


def _date(params, name, label):
    raw = _text(params, name)
    if not raw:
        return None
    try:
        value = parse_date(raw)
    except ValueError:
        value = None
    if value is None:
        raise ValidationError({name: f'{label}は YYYY-MM-DD 形式で指定してください。'})
    return value


def _truthy(value):
    return value is True or str(value).lower() in ('1', 'true')


def apply_filters(queryset, params):
    """一覧・出力・一括変更で共通の絞り込み（アーカイブ状態は呼び出し側が決める）。"""
    if _text(params, 'responsible_name'):
        queryset = queryset.filter(responsible_name__icontains=_text(params, 'responsible_name'))
    for name in CHOICE_FILTERS:
        value = _text(params, name)
        if value:
            queryset = queryset.filter(**{name: '' if value == 'unset' else value})
    company = _text(params, 'management_company')
    if company:
        queryset = queryset.filter(Q(management_company_name__icontains=company)
                                   | Q(management_company__name__icontains=company))
    date_from = _date(params, 'transaction_date_from', '取引日（開始）')
    date_to = _date(params, 'transaction_date_to', '取引日（終了）')
    if date_from:
        queryset = queryset.filter(transaction_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(transaction_date__lte=date_to)
    if _truthy(params.get('missing')):
        queryset = queryset.filter(Q(transaction_date__isnull=True) | Q(responsible_name='')
                                   | Q(management_company_name='') | Q(payment_status=''))
    keyword = _text(params, 'keyword') or _text(params, 'search')
    if keyword:
        queryset = queryset.filter(Q(transaction_number__icontains=keyword) | Q(party_name__icontains=keyword)
                                   | Q(property_name__icontains=keyword) | Q(room_number__icontains=keyword)
                                   | Q(note__icontains=keyword))
    return queryset


def filter_summary(params):
    """絞り込み条件の業務向け要約（確認画面と監査に使う。項目名・ID は出さない）。"""
    lines = ['保存状態：利用中']
    if _text(params, 'responsible_name'):
        lines.append(f'担当：「{_text(params, "responsible_name")}」を含む')
    for name, (label, choices) in CHOICE_FILTERS.items():
        value = _text(params, name)
        if value:
            display = dict(choices).get('' if value == 'unset' else value, value)
            lines.append(f'{label}：{display}')
    if _text(params, 'management_company'):
        lines.append(f'管理会社：「{_text(params, "management_company")}」を含む')
    date_from, date_to = _text(params, 'transaction_date_from'), _text(params, 'transaction_date_to')
    if date_from or date_to:
        lines.append(f'取引日：{date_from or "指定なし"} 〜 {date_to or "指定なし"}')
    if _truthy(params.get('missing')):
        lines.append('要補充のみ')
    keyword = _text(params, 'keyword') or _text(params, 'search')
    if keyword:
        lines.append(f'キーワード：「{keyword}」')
    return lines


# --- 選択の固定（絞り込み結果の全件／一覧で選択した記録） ---------------------------
#
# 一括変更は必ず「プレビュー → 署名付きトークン → 実行」の順で行う。トークンは操作者・対象 ID・
# 各記録の版（updated_at）・条件の要約を固定する。実行時に 1 件でも版が変わっていれば全体を中止する。
# 一覧で手動選択した記録も同じ経路を通る（利用者が一覧で見た時点の版を提示させ、発行時に照合する）。

MODE_FILTER = 'filter'
MODE_IDS = 'ids'
STALE_MESSAGE = '選択後に他の操作で変更された記録があります。一覧を更新して選び直してください。'


def version_of(tx):
    """記録の版。単票編集・一括変更・アーカイブ・復元のいずれでも updated_at が進む。"""
    return tx.updated_at.astimezone(dt_timezone.utc).strftime('%Y%m%d%H%M%S%f')


def _seen_version(raw):
    """利用者が一覧で見た updated_at（API が返した文字列）を版に直す。"""
    try:
        value = parse_datetime(raw) if isinstance(raw, str) else None
    except ValueError:
        value = None
    if value is None or value.tzinfo is None:
        raise ValidationError({'selection': '選択した記録の更新日時を正しく指定してください。'})
    return value.astimezone(dt_timezone.utc).strftime('%Y%m%d%H%M%S%f')


def _selected_rows(queryset, items):
    """一覧で選択した記録：ID と「見た時点の版」を受け取り、現在も同じ版で利用中であることを確かめる。"""
    if not isinstance(items, list) or not items:
        raise ValidationError({'selection': '対象の記録を選択してください。'})
    if len(items) > MAX_BULK_RECORDS:
        raise ValidationError({'selection': f'一度に一括変更できるのは {MAX_BULK_RECORDS} 件までです。'})
    seen = {}
    for item in items:
        pk = item.get('id') if isinstance(item, dict) else None
        if isinstance(pk, bool) or not isinstance(pk, int):
            raise ValidationError({'selection': '対象の記録を正しく指定してください。'})
        if pk in seen:
            raise ValidationError({'selection': '同じ記録が重複して指定されています。'})
        seen[pk] = _seen_version(item.get('updated_at'))
    current = {tx.pk: tx for tx in queryset.filter(pk__in=seen)}
    if len(current) != len(seen):
        raise BulkConflict('対象に、存在しない記録または操作できない記録が含まれています。一覧を更新してやり直してください。')
    if any(tx.is_archived for tx in current.values()):
        raise BulkConflict('アーカイブ済みの記録が含まれています。一括変更は利用中の記録だけが対象です。')
    if any(version_of(current[pk]) != version for pk, version in seen.items()):
        raise BulkConflict(STALE_MESSAGE)
    return sorted(seen.items())


def issue_selection_token(queryset, data, user):
    """対象（絞り込み結果の全件、または一覧で選択した記録）を固定した短期トークンを発行する。書き込みはしない。"""
    selection = data.get('selection') if isinstance(data, dict) else None
    if selection is not None:
        if not isinstance(selection, dict) or selection.get('mode') != MODE_IDS:
            raise ValidationError({'selection': '対象の選択方法が正しくありません。'})
        mode, summary = MODE_IDS, ['一覧で選択した記録']
        rows = _selected_rows(queryset, selection.get('items'))
    else:
        params = (data.get('filters') if isinstance(data, dict) else None) or {}
        if not isinstance(params, dict):
            raise ValidationError({'filters': '絞り込み条件の形式が正しくありません。'})
        mode, summary = MODE_FILTER, filter_summary(params)
        matched = apply_filters(queryset.filter(is_archived=False), params).order_by('id')
        rows = [(tx.pk, version_of(tx)) for tx in matched.only('id', 'updated_at')]
        if len(rows) > MAX_BULK_RECORDS:
            raise ValidationError({'detail': f'一度に一括変更できるのは {MAX_BULK_RECORDS} 件までです。条件を絞ってください。'})
    token = signing.dumps({'u': user.pk, 'm': mode, 'rows': rows, 'summary': summary}, salt=TOKEN_SALT, compress=True)
    return {
        'selection_token': token, 'count': len(rows), 'filter_summary': summary, 'mode': mode,
        'expires_in_seconds': TOKEN_MAX_AGE_SECONDS,
    }


def resolve_selection(token, user):
    """トークンから (mode, {id: 版}, 条件の要約) を得る。ブラウザが名乗る ID・件数・版は信用しない。"""
    if not isinstance(token, str) or not token:
        raise ValidationError({'selection_token': '対象を選択し直してください（選択トークンがありません）。'})
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
    except signing.SignatureExpired:
        raise ValidationError({'selection_token': '選択の有効期限が切れました。対象を選択し直してください。'})
    except signing.BadSignature:
        raise ValidationError({'selection_token': '選択トークンが正しくありません。'})
    if data.get('u') != user.pk:
        raise ValidationError({'selection_token': '選択トークンが正しくありません。'})
    versions = {int(pk): version for pk, version in data.get('rows') or []}
    if not versions:
        raise ValidationError({'selection_token': '対象の記録がありません。'})
    return data.get('m') or MODE_FILTER, versions, list(data.get('summary') or [])


# --- 変更内容の検証 -------------------------------------------------------------

def clean_changes(changes, clear_fields):
    """変更する項目だけを取り出す。空欄での消去は clear_fields で明示させる（空文字の誤送信で消さない）。"""
    changes = {} if changes is None else changes
    clear_fields = [] if clear_fields is None else clear_fields
    if not isinstance(changes, dict) or not isinstance(clear_fields, list):
        raise ValidationError({'changes': '変更内容の形式が正しくありません。'})
    unknown = sorted(set(changes) - set(BULK_FIELDS))
    if unknown:
        raise ValidationError({'changes': '一括変更できるのは段階・担当者・取引日だけです。'})
    bad_clear = [name for name in clear_fields if name not in CLEARABLE_FIELDS]
    if bad_clear or len(set(clear_fields)) != len(clear_fields):
        raise ValidationError({'clear_fields': '空欄にできるのは担当者・取引日だけです。'})
    values = {}
    for name, value in changes.items():
        if name in clear_fields:
            raise ValidationError({name: '値の指定と空欄化を同時に指定することはできません。'})
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationError({name: '変更後の値を入力してください（空欄にする場合は「空欄にする」を選択）。'})
        values[name] = value
    for name in clear_fields:
        values[name] = CLEARABLE_FIELDS[name]
    if not values:
        raise ValidationError({'changes': '変更する項目を 1 つ以上選択してください。'})
    return values


def _expected_count(raw):
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        raise ValidationError({'expected_count': '確認した対象件数を指定してください。'})
    return raw


# --- 実行 -----------------------------------------------------------------------

@db_transaction.atomic
def execute(*, request, policy, rule, queryset, serializer_class, serializer_context, data):
    """一括変更を 1 つのトランザクションで実行する。途中で失敗したら何も書き込まない。"""
    if data.get('selection') is not None:
        # ID を直接渡す経路は無い（版の確認を迂回させない）。必ず bulk-preview のトークンを使う。
        raise ValidationError({'selection_token': '対象は bulk-preview で固定した選択トークンで指定してください。'})
    mode, versions, summary = resolve_selection(data.get('selection_token'), request.user)
    values = clean_changes(data.get('changes'), data.get('clear_fields'))
    expected = _expected_count(data.get('expected_count'))
    if expected != len(versions):
        raise BulkConflict('確認した件数と対象の件数が一致しません。一覧を更新してやり直してください。')

    # 対象行をロックしてから版を照合する（照合後に他の操作が割り込めない）
    targets = list(queryset.select_for_update().filter(pk__in=versions).order_by('id'))
    if len(targets) != len(versions):
        raise BulkConflict('選択後に削除された、または操作できなくなった記録があります。一覧を更新して選び直してください。')
    archived = [tx.transaction_number for tx in targets if tx.is_archived]
    if archived:
        raise BulkConflict(f'選択後にアーカイブされた記録があります（{"、".join(archived[:5])}）。一括変更は利用中の記録だけが対象です。')
    stale = [tx.transaction_number for tx in targets if version_of(tx) != versions[tx.pk]]
    if stale:
        raise BulkConflict(f'{STALE_MESSAGE}（{"、".join(stale[:5])}{" ほか" if len(stale) > 5 else ""}）')

    batch_id = uuid.uuid4().hex
    fields = set(values)
    updated = 0
    locked_ledgers = 0
    for tx in targets:
        if rule.object_decision(policy, tx, 'bulk_change') != ALLOW:
            raise BulkConflict('対象に、操作できない記録が含まれています。')
        before = transaction_values(tx, fields)
        # 単票編集と同じシリアライザで検証する（アーカイブ制限・選択肢・日付形式を迂回しない）
        serializer = serializer_class(tx, data=values, partial=True, context=serializer_context)
        if not serializer.is_valid():
            raise ValidationError({'changes': serializer.errors, 'transaction_number': tx.transaction_number})
        extra = rule.prepare_update(policy, tx, serializer.validated_data)
        if all(getattr(tx, name) == value for name, value in serializer.validated_data.items()):
            continue  # 既に同じ値：更新者・更新日時も変えない
        tx = serializer.save(**extra)
        changes = transaction_changes(before, transaction_values(tx, fields))
        updated += 1
        if 'transaction_date' in changes and getattr(getattr(tx, 'legal_ledger', None), 'is_locked', False):
            locked_ledgers += 1
        record(module=AUDIT_MODULE, action='transaction_updated', request=request, obj=tx,
               object_repr=tx.transaction_number, changes=changes, via_permission=rule.BULK_CHANGE,
               extra={'bulk': True, 'batch_id': batch_id})

    record(module=AUDIT_MODULE, action='transaction_bulk_updated', request=request,
           object_type='real_estate.realestatetransaction', via_permission=rule.BULK_CHANGE,
           extra={'batch_id': batch_id, 'mode': mode, 'matched': len(targets), 'updated': updated,
                  'fields': sorted(fields), 'filter_summary': summary})
    return {
        'batch_id': batch_id, 'matched': len(targets), 'updated': updated, 'unchanged': len(targets) - updated,
        # 取引日を変えても法定台帳（ロック済み）は変わらない。必要なら台帳の更正を別途行う。
        'locked_ledger_count': locked_ledgers,
    }
