"""既存 Expense の owner 回填（本番データ操作 D8）。既定 dry-run。

手順：只読統計 → 備份（mysqldump、本コマンド外）→ dry-run → 目標 username/Employee 確認
→ --apply --expect-count N（実数一致必須）→ ID 清单 CSV 出力 → 用户确认后执行
→ 必要时 --rollback <csv>。
"""
import csv
from pathlib import Path

from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Max, Min, Sum
from django.utils import timezone

from apps.accounting.models import Expense
from apps.authentication.management.base import SafeCommand
from apps.authentication.models import ProtectedAccount


class Command(SafeCommand):
    help = 'owner が未設定の Expense を指定ユーザーに回填する（username 指定・expect-count 必須・CSV で回滚可能）。'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--username', help='回填先 username')
        parser.add_argument('--expect-count', type=int, help='--apply 時必須。owner 未設定件数の実数と一致しなければ中止')
        parser.add_argument('--output-dir', default='.', help='ID 清单 CSV の出力先')
        parser.add_argument('--rollback', help='過去の回填 CSV を指定して元に戻す')
        parser.add_argument('--allow-unprotected', action='store_true', help='保護アカウント以外への回填を許可（テスト用）')

    def handle(self, *args, **options):
        if options['rollback']:
            return self.handle_rollback(options)
        if not options['username']:
            raise CommandError('--username を指定してください。')
        user = self.get_user(options['username'])
        employee = getattr(user, 'employee', None) if hasattr(user, 'employee') else None
        if employee is None:
            raise CommandError('回填先ユーザーが担当者（Employee）に関連付いていません（先に link_user_employee）。')
        if not options['allow_unprotected'] and not ProtectedAccount.objects.filter(user=user).exists():
            raise CommandError('回填先が保護アカウントではありません（先に protect_account）。')

        pending = Expense.objects.filter(owner__isnull=True)
        stats = pending.aggregate(
            min_id=Min('id'), max_id=Max('id'),
            min_date=Min('expense_date'), max_date=Max('expense_date'), total=Sum('amount'),
        )
        count = pending.count()
        self.stdout.write(f'回填先: username={user.username} id={user.pk} 氏名={user.last_name}{user.first_name} 担当者={employee.name}（id={employee.pk}）')
        self.stdout.write(f'owner 未設定: {count} 件 / ID {stats["min_id"]}〜{stats["max_id"]} / 日付 {stats["min_date"]}〜{stats["max_date"]} / 金額合計 {stats["total"] or 0}')
        self.stdout.write(f'owner 設定済み: {Expense.objects.filter(owner__isnull=False).count()} 件')
        if count == 0:
            self.stdout.write('回填対象はありません。')
            return
        if options['apply']:
            if options['expect_count'] is None:
                raise CommandError('--apply には --expect-count が必要です。')
            if options['expect_count'] != count:
                raise CommandError(f'--expect-count={options["expect_count"]} が実数 {count} と一致しません。中止しました。')
        if not self.confirm(options, f'{count} 件の Expense の owner を {user.username} に設定します。'):
            return

        ids = list(pending.order_by('id').values_list('id', flat=True))
        out_dir = Path(options['output_dir'])
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / f'expense_owner_backfill_{timezone.localtime():%Y%m%d_%H%M%S}.csv'
        with csv_path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['expense_id', 'old_owner_id', 'new_owner_id', 'new_owner_username'])
            for expense_id in ids:
                writer.writerow([expense_id, '', user.pk, user.username])
        with transaction.atomic():
            updated = Expense.objects.filter(id__in=ids, owner__isnull=True).update(owner=user, created_by=user)
            if updated != count:
                raise CommandError(f'更新件数 {updated} が想定 {count} と異なるためロールバックしました。')
            self.audit('expense_owner_backfill', obj=user, extra={
                'count': updated, 'min_id': ids[0], 'max_id': ids[-1], 'csv': str(csv_path),
            })
        self.stdout.write(self.style.SUCCESS(f'{updated} 件を回填しました。ID 清单: {csv_path}'))

    def handle_rollback(self, options):
        path = Path(options['rollback'])
        if not path.exists():
            raise CommandError(f'ファイルがありません: {path}')
        with path.open(encoding='utf-8') as fh:
            rows = list(csv.DictReader(fh))
        ids = [int(r['expense_id']) for r in rows]
        new_owner_ids = {int(r['new_owner_id']) for r in rows}
        if len(new_owner_ids) != 1:
            raise CommandError('CSV の new_owner_id が一意ではありません。')
        owner_id = new_owner_ids.pop()
        target = Expense.objects.filter(id__in=ids, owner_id=owner_id)
        count = target.count()
        self.stdout.write(f'回滚対象: CSV {len(ids)} 件のうち、現在も owner_id={owner_id} の {count} 件を owner=NULL に戻します。')
        if not self.confirm(options, f'{count} 件の owner を元に戻します。'):
            return
        with transaction.atomic():
            updated = target.update(owner=None, created_by=None)
            self.audit('expense_owner_backfill_rollback', extra={'count': updated, 'csv': str(path)})
        self.stdout.write(self.style.SUCCESS(f'{updated} 件を元に戻しました。'))
