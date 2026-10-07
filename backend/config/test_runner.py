"""テストランナー：実行中の MEDIA_ROOT を一時ディレクトリにする（実際の backend/media に触れない）。"""
import tempfile

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

from apps.common.test_isolation import safe_rmtree


class IsolatedMediaTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._test_media = tempfile.mkdtemp(prefix='erp_test_media_')
        self._media_override = override_settings(MEDIA_ROOT=self._test_media)
        self._media_override.enable()  # setting_changed で既定ストレージの保存先も切り替わる

    def teardown_test_environment(self, **kwargs):
        self._media_override.disable()
        safe_rmtree(self._test_media)
        super().teardown_test_environment(**kwargs)
