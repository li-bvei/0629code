# 旧コード（P0 以前）が新しい列を送らなくても INSERT できるよう、DB 既定値を設定する（データは書き換えない）。
from django.db import migrations

from apps.common.db_defaults import set_defaults

forward, backward = set_defaults('accounting')


class Migration(migrations.Migration):
    # MySQL は DDL をトランザクションで巻き戻せないため、非 atomic で実行する
    atomic = False
    dependencies = [('accounting', '0018_business_documents_c11')]

    operations = [migrations.RunPython(forward, backward)]
