import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.authentication.snapshot import build_snapshot


class Command(BaseCommand):
    help = 'アカウントの is_active/is_staff/is_superuser・Group・個別権限・担当者関連を JSON に出力する（読み取りのみ）。'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='出力先。省略時は access_snapshot_<時刻>.json')

    def handle(self, *args, **options):
        snapshot = build_snapshot()
        path = Path(options['output'] or f"access_snapshot_{timezone.localtime():%Y%m%d_%H%M%S}.json")
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        from apps.audit.services import record

        record(module='command', action='access_snapshot_export', extra={'path': str(path), 'users': len(snapshot['users'])})
        self.stdout.write(self.style.SUCCESS(f'{len(snapshot["users"])} アカウントを {path} に出力しました。'))
