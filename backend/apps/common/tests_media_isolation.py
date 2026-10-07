"""テストが実際の media を削除しないことの回帰テスト（2026-10-07 の誤削除事故の再発防止）。

実際の backend/media にはファイルを作らない。「既定の media」の代わりに一時ディレクトリに哨兵ファイルを置き、
それを MEDIA_ROOT にした状態で P5・P6 の PDF テストを実行して、哨兵が残ることを確認する
（各テストクラスが自分の一時 MEDIA_ROOT を使い、片付けもその一時ディレクトリだけに限られることの確認）。
"""
import io
import os
import tempfile
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from apps.common.test_isolation import UnsafeDeletePath, assert_safe_to_delete, project_media_root, safe_rmtree

PDF_TESTS = [
    # P6：返签 visa 表の字体サブセット化（事故の原因になったクラス）
    'apps.accounting.tests_p6_visa_size.VisaSizeTests.test_batch_zip_path_uses_the_same_optimized_generation',
    'apps.accounting.tests_p6_visa_size.VisaSizeTests.test_subset_failure_is_a_clear_error_and_no_success_record',
    # P5：清風通知書の生成と保存
    'apps.accounting.tests_seifu_notice.SeifuGenerationTests',
    # P1：返签 visa 表の生成記録
    'apps.accounting.tests_p1_vouchers_visa.VisaMainFlowTests.test_broken_template_file_returns_readable_error',
]


class SafeDeleteGuardTests(TestCase):
    def test_test_runner_points_media_root_to_a_temporary_directory(self):
        media = os.path.realpath(str(settings.MEDIA_ROOT))
        self.assertNotEqual(media, project_media_root())
        self.assertTrue(media.startswith(os.path.realpath(tempfile.gettempdir()) + os.sep), media)

    def test_guard_rejects_project_media_project_home_and_empty_paths(self):
        base = Path(settings.BASE_DIR)
        for path in (None, '', '   ', os.sep, os.path.expanduser('~'), base, base.parent, base / 'media',
                     base / 'media' / 'p5_seifu_input', tempfile.gettempdir()):
            with self.subTest(path=path), self.assertRaises(UnsafeDeletePath):
                assert_safe_to_delete(path)
        with self.assertRaises(UnsafeDeletePath):
            safe_rmtree(base / 'media')  # 例外になり、何も削除しない

    def test_guard_allows_only_directories_created_under_the_temp_root(self):
        folder = tempfile.mkdtemp(prefix='guard_ok_')
        Path(folder, 'x.txt').write_text('x')
        safe_rmtree(folder)
        self.assertFalse(os.path.exists(folder))


class MediaSentinelTests(SimpleTestCase):
    # 内側の PDF テスト（TestCase）が自分のトランザクションで動けるように、外側はトランザクションで包まない
    databases = {'default'}

    def test_pdf_tests_do_not_delete_files_in_the_default_media(self):
        default_media = tempfile.mkdtemp(prefix='default_media_')
        self.addCleanup(safe_rmtree, default_media)
        sentinel = Path(default_media, 'p5_seifu_input', 'sentinel.txt')
        sentinel.parent.mkdir()
        sentinel.write_text('sentinel')
        with override_settings(MEDIA_ROOT=default_media):
            suite = unittest.defaultTestLoader.loadTestsFromNames(PDF_TESTS)
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertTrue(result.wasSuccessful(), [str(e[1])[-500:] for e in result.errors + result.failures])
        self.assertGreaterEqual(result.testsRun, 4)
        self.assertTrue(sentinel.exists(), 'PDF テストが既定の media を削除した')
        self.assertEqual(sentinel.read_text(), 'sentinel')

    def test_a_test_without_its_own_media_root_cannot_delete_the_project_media(self):
        # 事故当時の書き方（override なしで settings.MEDIA_ROOT を削除）を再現：安全装置が拒否する
        with override_settings(MEDIA_ROOT=Path(settings.BASE_DIR) / 'media'):
            with self.assertRaises(UnsafeDeletePath):
                safe_rmtree(settings.MEDIA_ROOT)
