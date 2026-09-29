#!/usr/bin/env bash
# 旧コード互換性の回帰チェック（発布前に毎回実行する）。
#   最新コードで migrate → 旧コード（P0 以前の基線）で列の洗い出し・実際の書き込み → 最新コードで読み取り・更新。
# 使い方：
#   scripts/rollback_compat/run.sh <旧コードの backend ディレクトリ> [--recreate]
# 前提：最新コード・旧コードとも backend/.env（または環境変数）で同じ MySQL に接続できること。
# 安全策：接続先は gyoseishoshi_erp_rollback_compat_preview だけ。--recreate はこの名前の DB だけを作り直す。
set -euo pipefail
NEW_BACKEND="$(cd "$(dirname "$0")/../.." && pwd)"
OLD_BACKEND="$(cd "${1:?旧コードの backend ディレクトリを指定してください}" && pwd)"
RECREATE="${2:-}"
DB=gyoseishoshi_erp_rollback_compat_preview
SCRIPTS="$NEW_BACKEND/scripts/rollback_compat"
OUT="${ROLLBACK_COMPAT_OUT:-$(mktemp -d)}"
PY_NEW="${PY_NEW:-$NEW_BACKEND/.venv/bin/python}"
PY_OLD="${PY_OLD:-$OLD_BACKEND/.venv/bin/python}"
export ROLLBACK_COMPAT_DB="$DB" MYSQL_DATABASE="$DB"

if [[ "$RECREATE" == "--recreate" ]]; then
  ( cd "$NEW_BACKEND" && "$PY_NEW" - <<PY
import os, sys
sys.path.insert(0, os.getcwd()); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()
from django.conf import settings
import pymysql
cfg = settings.DATABASES['default']
assert cfg['NAME'] == '$DB', cfg['NAME']
conn = pymysql.connect(host=cfg['HOST'], port=int(cfg['PORT'] or 3306), user=cfg['USER'], password=cfg['PASSWORD'])
with conn.cursor() as c:
    c.execute('DROP DATABASE IF EXISTS \`$DB\`')
    c.execute('CREATE DATABASE \`$DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
print('recreated $DB')
PY
  )
fi

if [[ "$RECREATE" == "--recreate" ]]; then
  # 本番と同じ経路：まず旧コードの migration で旧スキーマを作り、そこから最新へ上げる
  echo "== 0. 旧コードで旧スキーマを作成"; ( cd "$OLD_BACKEND" && "$PY_OLD" manage.py migrate --noinput | tail -1 )
  echo "== 0'. 最新コードの migrate --plan（旧スキーマからの差分）"; ( cd "$NEW_BACKEND" && "$PY_NEW" manage.py migrate --plan > "$OUT/migrate_plan.txt" ) && grep -c '^  ' "$OUT/migrate_plan.txt" || true
fi
echo "== 1. 最新コードで migrate"; ( cd "$NEW_BACKEND" && "$PY_NEW" manage.py migrate --noinput | tail -3 && "$PY_NEW" manage.py migrate --check && echo "未適用の migration なし" )
echo "== 2. 旧コードで列の洗い出し"; ( cd "$OLD_BACKEND" && "$PY_OLD" "$SCRIPTS/inventory.py" > "$OUT/inventory.json" ) && echo OK || { cat "$OUT/inventory.json"; exit 1; }
echo "== 3. 旧コードで実際の書き込み"; ( cd "$OLD_BACKEND" && "$PY_OLD" "$SCRIPTS/old_code_writer.py" > "$OUT/old_writer.json" 2> "$OUT/old_writer.log" ) && echo OK || { cat "$OUT/old_writer.json"; exit 1; }
echo "== 4. 最新コードで読み取り・更新"; ( cd "$NEW_BACKEND" && ROLLBACK_COMPAT_MEDIA_ROOT="${ROLLBACK_COMPAT_MEDIA_ROOT:-$OLD_BACKEND/media}" "$PY_NEW" "$SCRIPTS/new_code_reader.py" "$OUT/old_writer.json" > "$OUT/new_reader.json" 2> "$OUT/new_reader.log" ) && echo OK || { cat "$OUT/new_reader.json"; exit 1; }
echo "結果：$OUT（inventory.json / old_writer.json / new_reader.json）"
