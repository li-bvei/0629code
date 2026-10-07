# 旧コード（P5 以前）が P6 で追加した列を送らなくても INSERT できるよう、DB 既定値を設定する（データは書き換えない）。
from django.db import migrations

from apps.common.db_defaults import set_defaults

forward, backward = set_defaults('documents_p6')


class Migration(migrations.Migration):
    # MySQL は DDL をトランザクションで巻き戻せないため、非 atomic で実行する
    atomic = False
    dependencies = [('documents', '0006_document_content_label')]

    operations = [migrations.RunPython(forward, backward)]
