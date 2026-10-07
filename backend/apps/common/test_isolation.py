"""テストのファイル保存先・削除の安全装置（2026-10-07：P6 のテストが backend/media を削除した事故を受けて追加）。

- テスト実行中の MEDIA_ROOT は IsolatedMediaTestRunner が一時ディレクトリに切り替える
  （各テストが override_settings を書き忘れても、実際の backend/media に保存・削除しない）。
- テストでディレクトリを削除するときは shutil.rmtree ではなく safe_rmtree を使う。
  システムの一時ディレクトリ配下だけを削除し、プロジェクトの media・プロジェクト・ホーム・空のパスは拒否する。
"""
import os
import shutil
import tempfile

from django.conf import settings


class UnsafeDeletePath(AssertionError):
    """テストが一時ディレクトリ以外を削除しようとした。"""


def project_media_root():
    return os.path.realpath(os.path.join(str(settings.BASE_DIR), 'media'))


def assert_safe_to_delete(path):
    """削除してよいパス（システムの一時ディレクトリ配下で、プロジェクトの media ではない）なら実パスを返す。"""
    if path is None or not str(path).strip():
        raise UnsafeDeletePath('削除先のパスが空です。')
    real = os.path.realpath(str(path))
    temp_root = os.path.realpath(tempfile.gettempdir())
    media = project_media_root()
    project = os.path.realpath(str(settings.BASE_DIR))
    forbidden = {os.path.realpath(os.sep), os.path.realpath(os.path.expanduser('~')), project,
                 os.path.dirname(project), media, temp_root}
    if real in forbidden:
        raise UnsafeDeletePath(f'このパスは削除できません：{real}')
    if real == media or real.startswith(media + os.sep):
        raise UnsafeDeletePath(f'プロジェクトの media 配下は削除できません：{real}')
    if not real.startswith(temp_root + os.sep):
        raise UnsafeDeletePath(f'システムの一時ディレクトリ以外は削除できません：{real}')
    return real


def safe_rmtree(path, ignore_errors=True):
    shutil.rmtree(assert_safe_to_delete(path), ignore_errors=ignore_errors)
