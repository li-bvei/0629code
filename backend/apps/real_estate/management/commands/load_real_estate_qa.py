"""Load LIST.xlsx into a deliberately isolated local QA database.

The command never prints source values. It refuses production and any database
whose name is not explicitly marked as a real-estate QA database.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.audit.services import record
from apps.real_estate.history import transaction_values
from apps.real_estate.list_import import TARGET_SHEET, build_report, file_sha256
from apps.real_estate.models import RealEstateImportRun, RealEstateTransaction


def _no_candidates(*_args):
    return []


def _existing_candidates(values):
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


class Command(BaseCommand):
    help = '独立したローカル不動産 QA DB に LIST 工作表1 を検証して取り込む。'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path')
        parser.add_argument('--username', required=True, help='履歴に記録する実行者')
        parser.add_argument('--apply', action='store_true', help='省略時は件数確認だけで書き込まない')
        parser.add_argument('--expect-imported', type=int, help='想定件数と異なる場合は全体を中止する')

    def handle(self, *args, **options):
        database_name = str(connection.settings_dict.get('NAME') or '')
        if settings.IS_PRODUCTION:
            raise CommandError('本番環境では実行できません。')
        if 'real_estate_qa_' not in database_name.lower():
            raise CommandError('DB 名に real_estate_qa_ を含む独立 QA DB でのみ実行できます。')

        source_path = Path(options['xlsx_path']).expanduser().resolve()
        if source_path.name != 'LIST.xlsx':
            raise CommandError('取込元は LIST.xlsx に限定されています。')
        if not source_path.is_file():
            raise CommandError('LIST.xlsx が見つかりません。')

        try:
            actor = get_user_model().objects.get(username=options['username'], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError('指定した実行者が QA DB に存在しません。') from exc

        content = source_path.read_bytes()
        digest = file_sha256(content)
        report = build_report(source_path.name, content, candidates={
            'existing': _existing_candidates,
            'customer': _no_candidates,
            'company': _no_candidates,
            'property': _no_candidates,
            'responsible': _no_candidates,
        })
        if report['sheet'] != TARGET_SHEET or report['sheets_found'] != [TARGET_SHEET]:
            raise CommandError('対象シート以外を読み込もうとしたため中止しました。')

        skip_reasons = {
            'blank': report['summary']['blank_rows_skipped'],
            'validation_error': 0,
            'duplicate_in_file': 0,
            'already_registered': 0,
        }
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

        expected = options.get('expect_imported')
        if expected is not None and expected != len(importable):
            raise CommandError(f'想定取込件数 {expected} と検証結果 {len(importable)} が一致しません。')

        self.stdout.write(
            'QA検証: '
            f'対象行={report["summary"]["rows"]} '
            f'取込予定={len(importable)} '
            f'空行={skip_reasons["blank"]} '
            f'検証エラー={skip_reasons["validation_error"]} '
            f'ファイル内重複={skip_reasons["duplicate_in_file"]} '
            f'登録済み={skip_reasons["already_registered"]}'
        )
        if not options['apply']:
            self.stdout.write('dry-run のため書き込みませんでした。')
            return

        with transaction.atomic():
            created = 0
            for row in importable:
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
                    source_file=source_path.name,
                    source_file_sha256=digest,
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
                    reason='QA LIST 工作表1 取込', via_permission='real_estate.import_real_estate',
                )
                created += 1
            summary = dict(report['summary'])
            summary.update({'imported_rows': created, 'skipped_rows': sum(skip_reasons.values()),
                            'skip_reasons': skip_reasons})
            report['qa_import'] = {'imported_rows': created, 'skip_reasons': skip_reasons}
            RealEstateImportRun.objects.create(
                file_name=source_path.name, file_sha256=digest, sheet=TARGET_SHEET,
                summary=summary, report=report, created_by=actor,
            )

        self.stdout.write(self.style.SUCCESS(
            f'QA取込完了: 取込={created} スキップ={sum(skip_reasons.values())}（実データ値は出力していません）'
        ))
