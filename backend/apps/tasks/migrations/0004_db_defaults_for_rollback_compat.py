# 旧コード（P3 以前）が新しい列を送らなくてもタスクを INSERT できるよう、DB 既定値を設定する（データは書き換えない）。
from django.db import migrations

from apps.common.db_defaults import set_defaults

forward, backward = set_defaults('tasks')


class Migration(migrations.Migration):
    # MySQL は DDL をトランザクションで巻き戻せないため、非 atomic で実行する
    atomic = False
    dependencies = [('tasks', '0003_daily_plan_and_reports')]

    operations = [migrations.RunPython(forward, backward)]
