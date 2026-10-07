"""LIST.xlsx の正式取込コマンド（import_real_estate_list）：dry-run・件数一致・権限・再実行・回滚。"""
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.audit.models import AuditLog
from apps.real_estate.models import RealEstateImportRun, RealEstateTransaction
from apps.real_estate.tests import RealEstateFixture
from apps.real_estate.tests_import import ROWS, SENTINEL, workbook_bytes
from apps.common.test_isolation import safe_rmtree


class ListImportCommandTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(safe_rmtree, self.dir)
        self.path = self.dir / 'LIST.xlsx'
        self.path.write_bytes(workbook_bytes(ROWS))

    def run_cmd(self, *args, username='re_li'):
        out = StringIO()
        call_command('import_real_estate_list', *args, '--username', username, stdout=out)
        return out.getvalue()

    def csv_path(self):
        return next(self.dir.glob('real_estate_import_*.csv'))

    def test_dry_run_reports_counts_without_writing_or_printing_values(self):
        output = self.run_cmd(str(self.path))
        self.assertIn('対象行=5 取込予定=2', output)  # 検証エラー 2 行・ファイル内重複 1 行は登録しない
        self.assertIn('検証エラー=2', output)
        self.assertIn('ファイル内重複=1', output)
        self.assertIn('--apply --expect-imported 2', output)
        for value in ('取引先1', '物件1', '管理会社1', '85000', SENTINEL):
            self.assertNotIn(value, output)
        self.assertEqual(RealEstateTransaction.objects.count(), 0)
        self.assertEqual(RealEstateImportRun.objects.count(), 0)

    def test_apply_requires_matching_expected_count(self):
        with self.assertRaises(CommandError):
            self.run_cmd(str(self.path), '--apply', '--yes')
        with self.assertRaises(CommandError):
            self.run_cmd(str(self.path), '--apply', '--yes', '--expect-imported', '3')
        self.assertEqual(RealEstateTransaction.objects.count(), 0)

    def test_actor_needs_explicit_import_permission_not_superuser(self):
        from apps.authentication.testing import make_user

        make_user('list_su', superuser=True)
        for username in ('re_a', 're_manager', 'list_su', 'nobody'):
            with self.assertRaises(CommandError):
                self.run_cmd(str(self.path), username=username)

    def test_only_list_xlsx_is_accepted(self):
        other = self.dir / 'other.xlsx'
        other.write_bytes(workbook_bytes(ROWS))
        with self.assertRaises(CommandError):
            self.run_cmd(str(other))

    @override_settings(APP_ENV='production', IS_PRODUCTION=True)
    def test_apply_in_production_imports_once_with_history_and_id_list(self):
        output = self.run_cmd(str(self.path), '--apply', '--yes', '--expect-imported', '2', '--output-dir', str(self.dir))
        self.assertIn('取込完了: 2 件', output)
        self.assertNotIn('取引先1', output)
        rows = list(RealEstateTransaction.objects.order_by('source_row'))
        self.assertEqual([(tx.source_sheet, tx.source_file, tx.created_by) for tx in rows],
                         [('工作表1', 'LIST.xlsx', self.li)] * 2)
        self.assertEqual(rows[0].responsible_name, '担当候補')  # 自由文字のまま（Employee に結び付けない）
        self.assertEqual(rows[1].responsible_name, '')          # 空欄は推測で埋めない
        self.assertTrue(all(not tx.is_archived for tx in rows))
        self.assertEqual(AuditLog.objects.filter(action='transaction_created', user=self.li).count(), 2)
        summary = AuditLog.objects.get(action='list_imported')
        self.assertEqual((summary.extra['imported'], summary.via_permission), (2, 'real_estate.import_real_estate'))
        self.assertEqual(len(self.csv_path().read_text().strip().splitlines()), 3)
        # 画面の履歴に実行者が出る
        history = self.api(self.staff_a, 'get', f'/api/real-estate/transactions/{rows[0].pk}/audit-log/').json()
        self.assertTrue(any(row['actor'] == '李' and '新規登録' in row['message'] for row in history))
        # 同じファイルの再実行は二重登録しない
        again = self.run_cmd(str(self.path))
        self.assertIn('取込予定=0', again)
        self.assertIn('登録済み=2', again)
        with self.assertRaises(CommandError):
            self.run_cmd(str(self.path), '--apply', '--yes', '--expect-imported', '2')
        self.assertEqual(RealEstateTransaction.objects.count(), 2)

    def test_rollback_removes_only_untouched_imported_records(self):
        self.run_cmd(str(self.path), '--apply', '--yes', '--expect-imported', '2', '--output-dir', str(self.dir))
        manual = self.create_tx(party_name='手入力', property_name='別物件')
        first, second = RealEstateTransaction.objects.exclude(pk=manual['id']).order_by('source_row')
        self.assertEqual(self.api(self.staff_a, 'patch', f'/api/real-estate/transactions/{second.pk}/',
                                  {'note': '取込後に編集'}).status_code, 200)
        preview = self.run_cmd('--rollback', str(self.csv_path()))
        self.assertIn('取り消せる 1 件 / 取り消さない 1 件', preview)
        self.assertEqual(RealEstateTransaction.objects.count(), 3)  # dry-run は消さない
        self.run_cmd('--rollback', str(self.csv_path()), '--apply', '--yes')
        remaining = set(RealEstateTransaction.objects.values_list('pk', flat=True))
        self.assertEqual(remaining, {second.pk, manual['id']})
        self.assertTrue(AuditLog.objects.filter(action='list_import_rolled_back', object_id=str(first.pk)).exists())
        self.assertEqual(AuditLog.objects.get(action='list_import_rollback').extra['removed'], 1)
