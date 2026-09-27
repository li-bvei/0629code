import json
from pathlib import Path

from django.core.management.base import CommandError

from apps.authentication.management.base import SafeCommand
from apps.authentication.snapshot import diff_snapshot, restore_snapshot


class Command(SafeCommand):
    help = 'export_access_snapshot の JSON からアカウント権限を復元する。差分を表示し、既定 dry-run。'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('snapshot')
        parser.add_argument('--user', action='append', default=[], help='対象 username（複数可。省略時は全員）')
        parser.add_argument('--dry-run', action='store_true', help='明示的な dry-run（既定動作と同じ）')

    def handle(self, *args, **options):
        path = Path(options['snapshot'])
        if not path.exists():
            raise CommandError(f'ファイルがありません: {path}')
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        usernames = set(options['user']) or None
        diffs = diff_snapshot(snapshot, usernames)
        if not diffs:
            self.stdout.write('差分はありません。')
            return
        for diff in diffs:
            self.stdout.write(json.dumps(diff, ensure_ascii=False))
        if options['dry_run'] or not self.confirm(options, f'{len(diffs)} アカウントを復元します。'):
            return
        restored = restore_snapshot(snapshot, usernames)
        self.audit('access_snapshot_restore', extra={'path': str(path), 'users': [d['username'] for d in restored]})
        self.stdout.write(self.style.SUCCESS(f'{len(restored)} アカウントを復元しました。'))
