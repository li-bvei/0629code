"""Load LIST.xlsx into a deliberately isolated local QA database.

The command never prints source values. It refuses production and any database
whose name is not explicitly marked as a real-estate QA database.
本番への取込は import_real_estate_list（既定 dry-run・件数一致必須・回滚可能）を使う。
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.real_estate import list_load


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
        plan = list_load.prepare(source_path)
        try:
            actor = get_user_model().objects.get(username=options['username'], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError('指定した実行者が QA DB に存在しません。') from exc

        expected = options.get('expect_imported')
        if expected is not None and expected != len(plan['importable']):
            raise CommandError(f'想定取込件数 {expected} と検証結果 {len(plan["importable"])} が一致しません。')

        self.stdout.write('QA検証: ' + list_load.summary_line(plan))
        if not options['apply']:
            self.stdout.write('dry-run のため書き込みませんでした。')
            return

        created = list_load.create_records(plan, source_name=source_path.name, actor=actor,
                                           reason='QA LIST 工作表1 取込', run_key='qa_import')
        self.stdout.write(self.style.SUCCESS(
            f'QA取込完了: 取込={len(created)} スキップ={sum(plan["skip_reasons"].values())}（実データ値は出力していません）'
        ))
