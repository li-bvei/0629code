"""LIST.xlsx（工作表1）から不動産取引を登録する共通処理（QA 取込・本番取込の両方が使う）。

- 読むのは対象シートだけ（read_table が他のシートを読まない。念のためここでも確認する）。
- 取込元の値は標準出力・ログに出さない（件数・行番号・番号だけ）。
- 検証エラー・ファイル内重複・登録済みの行は登録しない（推測で埋めない）。
"""
from django.core.management.base import CommandError
from django.db import transaction

from apps.audit.services import record

from .history import transaction_values
from .list_import import TARGET_SHEET, build_report, file_sha256
from .models import RealEstateImportRun, RealEstateTransaction

SOURCE_FILE_NAME = 'LIST.xlsx'
SKIP_LABELS = {
    'blank': '空行', 'validation_error': '検証エラー', 'duplicate_in_file': 'ファイル内重複',
    'already_registered': '登録済み',
}


def _no_candidates(*_args):
    return []


def existing_candidates(values):
    """既に登録済みの取引（取込元番号、無ければ当事者・物件・部屋・取引日の一致）。"""
    source_reference = values.get('source_number') or ''
    queryset = RealEstateTransaction.objects.all()
    if source_reference:
        queryset = queryset.filter(source_reference=source_reference)
    else:
        queryset = queryset.filter(
            party_name=values.get('party_name') or '',
            property_name=values.get('property_name') or '',
            room_number=values.get('room_number') or '',
            transaction_date=values.get('transaction_date') or None,
        )
    return [{'id': row.pk, 'number': row.transaction_number} for row in queryset[:10]]


def prepare(source_path):
    """ファイルを検証し、登録できる行と登録しない行の内訳を返す（書き込みはしない）。"""
    if source_path.name != SOURCE_FILE_NAME:
        raise CommandError(f'取込元は {SOURCE_FILE_NAME} に限定されています。')
    if not source_path.is_file():
        raise CommandError(f'{SOURCE_FILE_NAME} が見つかりません。')
    content = source_path.read_bytes()
    digest = file_sha256(content)
    report = build_report(source_path.name, content, candidates={
        'existing': existing_candidates, 'customer': _no_candidates, 'company': _no_candidates,
        'property': _no_candidates, 'responsible': _no_candidates,
    })
    if report['sheet'] != TARGET_SHEET or report['sheets_found'] != [TARGET_SHEET]:
        raise CommandError('対象シート以外を読み込もうとしたため中止しました。')
    skip_reasons = {'blank': report['summary']['blank_rows_skipped'], 'validation_error': 0,
                    'duplicate_in_file': 0, 'already_registered': 0}
    importable = []
    for row in report['results']:
        if row['errors']:
            skip_reasons['validation_error'] += 1
        elif row['duplicate_in_file_rows']:
            skip_reasons['duplicate_in_file'] += 1
        elif row['duplicate_existing']:
            skip_reasons['already_registered'] += 1
        else:
            importable.append(row)
    return {'digest': digest, 'report': report, 'importable': importable, 'skip_reasons': skip_reasons}


def summary_line(plan):
    reasons = plan['skip_reasons']
    return (f'対象行={plan["report"]["summary"]["rows"]} 取込予定={len(plan["importable"])} '
            + ' '.join(f'{SKIP_LABELS[key]}={reasons[key]}' for key in SKIP_LABELS)
            + f' 要補充のある行={sum(1 for row in plan["importable"] if row["to_complete"])}')


@transaction.atomic
def create_records(plan, *, source_name, actor, reason, run_key):
    """登録できる行を取引として作成し、履歴（監査）と取込記録を残す。作成した取引の一覧を返す。"""
    created = []
    for row in plan['importable']:
        values = row['values']
        obj = RealEstateTransaction.objects.create(
            transaction_type=values.get('transaction_type') or RealEstateTransaction.TYPE_RENTAL,
            party_name=values.get('party_name') or '',
            property_name=values.get('property_name') or '',
            room_number=values.get('room_number') or '',
            management_company_name=values.get('management_company_name') or '',
            responsible_name=values.get('responsible_name') or '',
            transaction_date=values.get('transaction_date') or None,
            brokerage_fee=values.get('brokerage_fee'),
            advertising_fee=values.get('advertising_fee'),
            handling_fee=values.get('handling_fee'),
            payment_status=values.get('payment_status') or '',
            payment_date=values.get('payment_date') or None,
            transfer_status=values.get('transfer_status') or '',
            source_file=source_name,
            source_file_sha256=plan['digest'],
            source_sheet=TARGET_SHEET,
            source_row=row['row_number'],
            source_reference=values.get('source_number') or '',
            source_values=row['raw'],
            created_by=actor,
            updated_by=actor,
        )
        record(
            module='real_estate', action='transaction_created', user=actor, obj=obj,
            object_repr=obj.transaction_number,
            changes={key: {'from': None, 'to': value} for key, value in transaction_values(obj).items()
                     if value not in (None, '')},
            reason=reason, via_permission='real_estate.import_real_estate',
        )
        created.append(obj)
    report = plan['report']
    summary = dict(report['summary'])
    summary.update({'imported_rows': len(created), 'skipped_rows': sum(plan['skip_reasons'].values()),
                    'skip_reasons': plan['skip_reasons']})
    report[run_key] = {'imported_rows': len(created), 'skip_reasons': plan['skip_reasons']}
    RealEstateImportRun.objects.create(
        file_name=source_name, file_sha256=plan['digest'], sheet=TARGET_SHEET,
        summary=summary, report=report, created_by=actor,
    )
    return created
