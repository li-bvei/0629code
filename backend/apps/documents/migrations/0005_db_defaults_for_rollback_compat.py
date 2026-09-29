# 旧コード（P0 以前）が新しい列を送らなくても INSERT できるよう、DB 既定値を設定する（データは書き換えない）。
from django.db import migrations

from apps.common.db_defaults import set_defaults

forward, backward = set_defaults('documents')


class Migration(migrations.Migration):
    # MySQL は DDL をトランザクションで巻き戻せないため、非 atomic で実行する
    atomic = False
    dependencies = [('documents', '0004_document_metadata_archive_replacements')]

    operations = [migrations.RunPython(forward, backward)]
