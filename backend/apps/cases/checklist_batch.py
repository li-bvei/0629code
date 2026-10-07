"""案件内の必要資料の一括更新（P2）。範囲は 1 つの案件の中だけ（案件をまたぐ一括更新は行わない）。

- 依頼された項目がすべて URL の案件のものか先に確認し、1 件でも違えば何も変えずに拒否する。
- 項目ごとに別のトランザクションで更新する。1 件の失敗で他の成功を取り消さない（項目同士は独立）。
- 画面で見ていた版（updated_at）が渡されれば比較し、他の操作で変わっていた項目は失敗として返す。
- 成功した項目ごとに監査（変更前後）を、最後に一括操作の要約を監査に残す。完了にした項目は案件経過にも残す。
"""
import logging
import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.audit.services import record, safe_changes
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .work_service import CaseWorkError, _parse_date

logger = logging.getLogger(__name__)

MAX_BATCH_ITEMS = 200
FIELD_LABELS = {
    'is_completed': '状態', 'received_at': '受領日', 'responsible_party': '準備者',
    'acquisition_place': '取得先・手続先', 'note': '備考',
}
FAILURE_LABELS = {
    'conflict': '他の操作で内容が変わっています。画面を更新してからもう一度操作してください。',
    'not_applicable': '受領日は必要資料（書類）の項目にだけ設定できます。',
    'not_found': 'この項目は削除されています。',
    'error': '更新できませんでした。',
}


def _responsible_party_choices():
    from .models import CaseChecklistItem

    return {value for value, _ in CaseChecklistItem.RESPONSIBLE_PARTY_CHOICES}


def normalize_changes(raw):
    """変更内容を検査して正規化する。不正なら CaseWorkError（何も変えない）。"""
    if not isinstance(raw, dict):
        raise CaseWorkError('変更内容を指定してください。', 'changes')
    changes = {}
    if 'is_completed' in raw:
        value = raw['is_completed']
        if not isinstance(value, bool):
            raise CaseWorkError('状態は完了／未完了で指定してください。', 'is_completed')
        changes['is_completed'] = value
    if 'received_at' in raw:
        changes['received_at'] = _parse_date(raw['received_at'], 'received_at')  # null は受領日を消す
    if 'responsible_party' in raw:
        value = str(raw['responsible_party'] or '')
        if value and value not in _responsible_party_choices():
            raise CaseWorkError('準備者の指定が正しくありません。', 'responsible_party')
        changes['responsible_party'] = value
    if 'acquisition_place' in raw:
        value = str(raw['acquisition_place'] or '').strip()
        if len(value) > 255:
            raise CaseWorkError('取得先・手続先は 255 文字までです。', 'acquisition_place')
        changes['acquisition_place'] = value
    if 'note' in raw:
        changes['note'] = str(raw['note'] or '').strip()
        mode = raw.get('note_mode') or 'replace'
        if mode not in ('replace', 'append'):
            raise CaseWorkError('備考の更新方法が正しくありません。', 'note_mode')
        changes['note_mode'] = mode
    if not [key for key in changes if key != 'note_mode']:
        raise CaseWorkError('変更する項目を 1 つ以上指定してください。', 'changes')
    return changes


def normalize_ids(raw):
    if not isinstance(raw, list) or not raw:
        raise CaseWorkError('対象の必要資料を選択してください。', 'item_ids')
    try:
        ids = list(dict.fromkeys(int(value) for value in raw))
    except (TypeError, ValueError):
        raise CaseWorkError('対象の指定が正しくありません。', 'item_ids')
    if len(ids) > MAX_BATCH_ITEMS:
        raise CaseWorkError(f'一度に更新できるのは {MAX_BATCH_ITEMS} 件までです。', 'item_ids')
    return ids


def _apply(item, changes, employee):
    """1 件に変更を当てはめる。(更新する列, 変更前後, 完了にしたか) を返す。"""
    diff = {}
    fields = set()
    completed_now = False
    if 'is_completed' in changes and changes['is_completed'] != item.is_completed:
        diff['is_completed'] = [item.is_completed, changes['is_completed']]
        item.is_completed = changes['is_completed']
        if item.is_completed:
            item.completed_at, item.completed_by = timezone.now(), employee
            completed_now = True
        else:
            item.completed_at, item.completed_by = None, None
        fields.update({'is_completed', 'completed_at', 'completed_by'})
    if 'received_at' in changes and changes['received_at'] != item.received_at:
        diff['received_at'] = [str(item.received_at or ''), str(changes['received_at'] or '')]
        item.received_at = changes['received_at']
        fields.add('received_at')
    for name in ('responsible_party', 'acquisition_place'):
        if name in changes and changes[name] != getattr(item, name):
            diff[name] = [getattr(item, name), changes[name]]
            setattr(item, name, changes[name])
            fields.add(name)
    if 'note' in changes:
        if changes['note_mode'] == 'append' and changes['note']:
            new_note = f'{item.note}\n{changes["note"]}' if item.note else changes['note']
        else:
            new_note = changes['note']
        if new_note != item.note:
            diff['note'] = [item.note, new_note]
            item.note = new_note
            fields.add('note')
    return fields, diff, completed_now


def batch_update_checklist(case, *, item_ids, changes, versions=None, actor=None, request=None):
    """案件 case の必要資料 item_ids に changes を当てる。項目ごとの結果を返す。"""
    from .models import CaseChecklistItem

    ids = normalize_ids(item_ids)
    changes = normalize_changes(changes)
    versions = versions if isinstance(versions, dict) else {}
    in_case = set(CaseChecklistItem.objects.filter(case_id=case.pk, pk__in=ids).values_list('pk', flat=True))
    foreign = [pk for pk in ids if pk not in in_case]
    if foreign:
        # 他の案件の項目（または存在しない項目）を含む依頼は、一部だけ実行せずに全体を拒否する
        record(module='cases', action='checklist_batch_rejected', request=request, obj=case, result='denied',
               reason='foreign_items', extra={'case_id': case.pk, 'requested': len(ids), 'foreign_ids': foreign[:50]})
        raise CaseWorkError('この案件の必要資料ではない項目が含まれています。画面を更新して選び直してください。', 'item_ids')

    employee = getattr(actor, 'employee', None) if actor is not None and hasattr(actor, 'employee') else None
    batch_id = uuid.uuid4().hex
    results = []
    for pk in ids:
        try:
            with transaction.atomic():
                item = CaseChecklistItem.objects.select_for_update().filter(pk=pk, case_id=case.pk).first()
                if item is None:
                    results.append({'id': pk, 'status': 'failed', 'code': 'not_found'})
                    continue
                expected = versions.get(str(pk), versions.get(pk))
                if expected:
                    seen = parse_datetime(str(expected))
                    if seen is None or abs((item.updated_at - seen).total_seconds()) >= 0.001:
                        results.append({'id': pk, 'name': item.name, 'status': 'failed', 'code': 'conflict'})
                        continue
                if 'received_at' in changes and changes['received_at'] and item.item_type != item.ITEM_TYPE_DOCUMENT:
                    results.append({'id': pk, 'name': item.name, 'status': 'failed', 'code': 'not_applicable'})
                    continue
                fields, diff, completed_now = _apply(item, changes, employee)
                if fields:
                    item.save(update_fields=[*sorted(fields), 'updated_at'])
                    record(module='cases', action='checklist_item_batch_updated', request=request, obj=item,
                           changes=safe_changes({k: v[0] for k, v in diff.items()}, {k: v[1] for k, v in diff.items()}),
                           extra={'case_id': case.pk, 'batch_id': batch_id})
                    if completed_now:
                        record_case_event(case, Timeline.EVENT_CHECKLIST_COMPLETED, f'資料・タスク完了：{item.name}',
                                          actor=actor, metadata={'checklist_item_id': item.id, 'category': item.category,
                                                                 'batch_id': batch_id})
                results.append({'id': pk, 'name': item.name, 'status': 'success', 'changed': sorted(diff)})
        except Exception:  # noqa: BLE001 1 件の想定外の失敗で他の項目を止めない（詳細はログ）
            logger.exception('checklist batch item failed (case=%s item=%s)', case.pk, pk)
            results.append({'id': pk, 'status': 'failed', 'code': 'error'})
    for row in results:
        if row['status'] == 'failed':
            row['detail'] = FAILURE_LABELS.get(row['code'], FAILURE_LABELS['error'])
    succeeded = [row['id'] for row in results if row['status'] == 'success']
    failed = [row for row in results if row['status'] == 'failed']
    record(module='cases', action='checklist_batch_update', request=request, obj=case,
           result='success' if not failed else 'error',  # 一部成功は件数（succeeded／failed）で示す
           extra={'case_id': case.pk, 'batch_id': batch_id, 'requested': len(ids), 'succeeded': len(succeeded),
                  'failed': len(failed), 'fields': sorted(key for key in changes if key != 'note_mode'),
                  'failures': [{'id': row['id'], 'code': row['code']} for row in failed][:50]})
    return {'batch_id': batch_id, 'requested': len(ids), 'succeeded': len(succeeded), 'failed': len(failed),
            'results': results, 'fields': [FIELD_LABELS[key] for key in FIELD_LABELS if key in changes]}
