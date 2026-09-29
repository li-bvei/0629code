"""旧コード互換性チェックの共通部（新旧どちらのコードの Django でも動く最小限の処理だけを書く）。"""
import os
import sys

EXPECTED_DB = 'gyoseishoshi_erp_rollback_compat_preview'


def setup(expected_db=None):
    """指定の作業ディレクトリ（新旧どちらかの backend）で Django を起動し、接続先 DB を厳密に確認する。"""
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django

    django.setup()
    from django.db import connection

    expected = expected_db or os.environ.get('ROLLBACK_COMPAT_DB', EXPECTED_DB)
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE()')
        name = cursor.fetchone()[0]
    if name != expected or connection.settings_dict['NAME'] != expected:
        raise SystemExit(f'接続先が想定外です（{name}）。{expected} 以外では実行しません。')
    return name
