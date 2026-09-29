"""旧コード（例：de95411）で実行する：最新スキーマ上で旧コードの INSERT を妨げる列を洗い出す。

- 旧モデルのテーブルにあって旧モデルが知らない列のうち、NOT NULL・DB 既定値なし・自動採番でないもの → 不整合
- 旧コードが知らないテーブルから旧テーブルへの外部キー（旧コードで親を削除すると制約違反になりうる）→ 注意として列挙
終了コード：不整合があれば 1。
"""
import json

from _common import setup

db = setup()
from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402

known_tables, known_columns = set(), {}
for model in apps.get_models(include_auto_created=True):
    if not model._meta.managed or model._meta.proxy:
        continue
    table = model._meta.db_table
    known_tables.add(table)
    known_columns.setdefault(table, set()).update(f.column for f in model._meta.local_concrete_fields)

with connection.cursor() as cursor:
    cursor.execute(
        """SELECT table_name, column_name, column_type, is_nullable, column_default, extra
           FROM information_schema.columns WHERE table_schema = %s""", [db])
    columns = cursor.fetchall()
    cursor.execute(
        """SELECT table_name, column_name, referenced_table_name FROM information_schema.key_column_usage
           WHERE table_schema = %s AND referenced_table_name IS NOT NULL""", [db])
    fks = cursor.fetchall()

blocking, missing = [], []
db_cols = {}
for table, column, ctype, nullable, default, extra in columns:
    db_cols.setdefault(table, set()).add(column)
    if table not in known_tables or column in known_columns[table]:
        continue
    if nullable == 'NO' and default is None and 'auto_increment' not in (extra or ''):
        blocking.append({'table': table, 'column': column, 'type': ctype})
for table, cols in known_columns.items():
    for col in sorted(cols - db_cols.get(table, set())):
        missing.append({'table': table, 'column': col})
fk_notes = sorted({f'{t}.{c} -> {r}' for t, c, r in fks if t not in known_tables and r in known_tables})

print(json.dumps({'database': db, 'blocking_not_null_columns': blocking, 'columns_missing_for_old_code': missing,
                  'fks_from_new_tables_to_old_tables': fk_notes}, ensure_ascii=False, indent=1))
raise SystemExit(1 if blocking or missing else 0)
