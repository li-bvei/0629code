# 旧コード（P3 以前）が P4 で追加した列を送らなくても INSERT できるよう、DB 既定値を設定する（データは書き換えない）。
from django.db import migrations

from apps.common.db_defaults import set_defaults

forward, backward = set_defaults('cases_p4')


class Migration(migrations.Migration):
    # MySQL は DDL をトランザクションで巻き戻せないため、非 atomic で実行する
    atomic = False
    dependencies = [('cases', '0022_workflow_templates')]

    operations = [migrations.RunPython(forward, backward)]
