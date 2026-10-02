"""LIST.xlsx（工作表1）の正式取込。本番で使う唯一の取込経路。

- 既定は dry-run（件数だけ表示）。書き込みは --apply と --expect-imported（検証結果と一致必須）が必要。
- 実行者は username で指定し、real_estate.import_real_estate を明示的に持つ利用者に限る（is_superuser は見ない）。
- 対象シート以外は読まない。取込元の値は標準出力に出さない（件数・行番号・番号だけ）。
- 検証エラー・ファイル内重複・登録済みの行は登録しない。同じファイルを再実行しても二重登録しない。
- 取り込んだ取引の ID 清单 CSV を出力し、--rollback でその清单だけを取り消せる
  （取込後に編集された記録・子データのある記録は消さずに報告する）。
"""
import csv
from datetime import timezone as dt_timezone
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from apps.authentication.access_policy import BusinessAccessPolicy
from apps.real_estate import list_load
from apps.real_estate.models import LegalLedger, RealEstateTransaction

IMPORT_PERMISSION = 'real_estate.import_real_estate'
CSV_FIELDS = ['id', 'transaction_number', 'source_row', 'source_file_sha256', 'updated_at']


def _stamp(value):
    return value.astimezone(dt_timezone.utc).strftime('%Y%m%d%H%M%S%f')


class Command(BaseCommand):
    help = 'LIST.xlsx の 工作表1 を検証して不動産取引に取り込む（既定 dry-run・件数一致必須・回滚可能）。'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', nargs='?', help='LIST.xlsx のパス（--rollback のときは不要）')
        parser.add_argument('--username', required=True, help='実行者（履歴・監査に記録。取込権限が必要）')
        parser.add_argument('--apply', action='store_true', help='省略時は件数確認だけで書き込まない')
        parser.add_argument('--yes', action='store_true', help='--apply の確認を省略する')
        parser.add_argument('--expect-imported', type=int, help='--apply 時必須。検証結果の取込予定件数と一致しなければ中止')
        parser.add_argument('--output-dir', default='.', help='ID 清单 CSV の出力先')
        parser.add_argument('--rollback', help='過去の取込の ID 清单 CSV を指定して取り消す')

    def _actor(self, username):
        try:
            actor = get_user_model().objects.get(username=username, is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError('指定した実行者が見つかりません。') from exc
        if not BusinessAccessPolicy(actor).has(IMPORT_PERMISSION):
            raise CommandError(f'実行者に {IMPORT_PERMISSION} が明示付与されていません。')
        return actor

    def _confirm(self, options, message):
        if not options['yes'] and input(f'{message} [y/N] ').lower() != 'y':
            raise CommandError('中止しました。')

    def handle(self, *args, **options):
        actor = self._actor(options['username'])
        if options['rollback']:
            return self._rollback(Path(options['rollback']), actor, options)
        if not options['xlsx_path']:
            raise CommandError('LIST.xlsx のパスを指定してください。')
        source_path = Path(options['xlsx_path']).expanduser().resolve()
        plan = list_load.prepare(source_path)
        count = len(plan['importable'])
        self.stdout.write('検証: ' + list_load.summary_line(plan))
        self.stdout.write(f'取込元 SHA-256: {plan["digest"][:12]}… / 既存の不動産取引: {RealEstateTransaction.objects.count()} 件')
        skipped = [(row['row_number'], '検証エラー' if row['errors'] else 'ファイル内重複' if row['duplicate_in_file_rows']
                    else '登録済み') for row in plan['report']['results'] if row not in plan['importable']]
        if skipped:
            self.stdout.write('登録しない行（行番号：理由）：' + '、'.join(f'{n}：{why}' for n, why in skipped))
        if not options['apply']:
            self.stdout.write(f'dry-run：書き込みは行いません（--apply --expect-imported {count} で実行）。')
            return
        if options['expect_imported'] is None:
            raise CommandError('--apply には --expect-imported が必要です。')
        if options['expect_imported'] != count:
            raise CommandError(f'--expect-imported={options["expect_imported"]} が検証結果 {count} と一致しません。中止しました。')
        if count == 0:
            self.stdout.write('取り込む行がありません。')
            return
        self._confirm(options, f'{count} 件を不動産取引として登録します。よろしいですか？')

        with transaction.atomic():
            created = list_load.create_records(plan, source_name=source_path.name, actor=actor,
                                               reason='LIST 工作表1 正式取込', run_key='formal_import')
            output = Path(options['output_dir']) / f'real_estate_import_{timezone.localtime():%Y%m%d_%H%M%S}.csv'
            with output.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for obj in created:
                    writer.writerow({'id': obj.pk, 'transaction_number': obj.transaction_number,
                                     'source_row': obj.source_row, 'source_file_sha256': obj.source_file_sha256,
                                     'updated_at': _stamp(obj.updated_at)})
            record(module='real_estate', action='list_imported', user=actor,
                   object_type='real_estate.realestatetransaction', via_permission=IMPORT_PERMISSION,
                   extra={'imported': len(created), 'skip_reasons': plan['skip_reasons'],
                          'file_sha256': plan['digest'], 'id_list': output.name})
        self.stdout.write(self.style.SUCCESS(
            f'取込完了: {len(created)} 件（番号 {created[0].transaction_number}〜{created[-1].transaction_number}）。'
            f'ID 清单: {output}（実データ値は出力していません）'
        ))

    def _rollback(self, path, actor, options):
        if not path.is_file():
            raise CommandError('ID 清单 CSV が見つかりません。')
        with path.open(encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        if not rows or set(CSV_FIELDS) - set(rows[0]):
            raise CommandError('ID 清单 CSV の形式が正しくありません。')
        removable, kept = [], []
        current = {obj.pk: obj for obj in RealEstateTransaction.objects.filter(pk__in=[int(r['id']) for r in rows])}
        with_ledger = set(LegalLedger.objects.filter(transaction_id__in=current).values_list('transaction_id', flat=True))
        for row in rows:
            obj = current.get(int(row['id']))
            if obj is None:
                kept.append((row['transaction_number'], '既に存在しない'))
            elif obj.transaction_number != row['transaction_number'] or obj.source_file_sha256 != row['source_file_sha256']:
                kept.append((row['transaction_number'], '清单と一致しない'))
            elif _stamp(obj.updated_at) != row['updated_at'] or obj.is_archived:
                kept.append((row['transaction_number'], '取込後に変更・アーカイブされた'))
            elif obj.pk in with_ledger or obj.parties.exists() or obj.files.exists() \
                    or obj.accounting_links.exists() or obj.profit_distributions.exists():
                kept.append((row['transaction_number'], '台帳・当事者・ファイル等が登録されている'))
            else:
                removable.append(obj)
        self.stdout.write(f'清单 {len(rows)} 件：取り消せる {len(removable)} 件 / 取り消さない {len(kept)} 件')
        for number, reason in kept:
            self.stdout.write(f'  残す：{number}（{reason}）')
        if not options['apply']:
            self.stdout.write('dry-run：書き込みは行いません（--apply で実行）。')
            return
        if not removable:
            self.stdout.write('取り消す記録がありません。')
            return
        self._confirm(options, f'{len(removable)} 件の不動産取引を削除します。よろしいですか？')
        with transaction.atomic():
            numbers = [obj.transaction_number for obj in removable]
            for obj in removable:
                record(module='real_estate', action='list_import_rolled_back', user=actor, obj=obj,
                       object_repr=obj.transaction_number, via_permission=IMPORT_PERMISSION,
                       reason=f'取込の取り消し（{path.name}）')
                obj.delete()
            record(module='real_estate', action='list_import_rollback', user=actor,
                   object_type='real_estate.realestatetransaction', via_permission=IMPORT_PERMISSION,
                   extra={'removed': len(numbers), 'kept': len(kept), 'id_list': path.name})
        self.stdout.write(self.style.SUCCESS(f'取り消しました: {len(removable)} 件。'))
