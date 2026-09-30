#!/usr/bin/env bash
# 発布・回滚用：nginx の安全設定とフロント静的ファイル・backend イメージを分けて切り替える。
#
#   release.sh verify-config                  稼働中 nginx の設定に受保護メディアの規則があるか確認（無ければ失敗）
#   release.sh verify-http                    HTTP で確認：/media/・/sun/media/・/_protected_media/ が 404、/sun/ と /sun/api/auth/csrf/ が正常
#   release.sh wait-backend                   backend の起動完了を待つ（/api/auth/csrf/ を WAIT_TIMEOUT 秒まで轮询、時間切れはログ保存して失敗）
#   release.sh frontend-assets current        現在のリポジトリから静的ファイルを作り直して公開
#   release.sh frontend-assets --from-image IMG   既存のフロントイメージ（旧版を含む）の静的ファイルだけを公開
#   release.sh frontend-assets --from-ref REF     git の任意の版（旧版を含む）から静的ファイルだけを作って公開
#   release.sh backend --image IMG            backend を指定イメージで起動（旧イメージへの回滚）
#
# 静的ファイルの切り替えは nginx 設定に一切触れない（frontend サービスは nginx/default.conf を読み取り専用で
# マウントしている）。切り替えの前に verify-config、後に verify-http を必ず実行し、失敗したら非 0 で終了する。
#
# 環境変数：COMPOSE_ARGS（既定 "--env-file .env.prod"。隔離検証では -p や -f を追加）、BASE_URL（既定 http://127.0.0.1:8081）
set -euo pipefail
cd "$(dirname "$0")/../.."
read -r -a COMPOSE_ARGS_ARR <<< "${COMPOSE_ARGS:---env-file .env.prod}"
dc() { docker compose "${COMPOSE_ARGS_ARR[@]}" "$@"; }
BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"
VITE_BASE_PATH="${VITE_BASE_PATH:-/sun/}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-/sun/api/}"

project_name() { dc config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])'; }
dist_volume() { echo "$(project_name)_frontend_dist"; }

verify_config() {
  local conf
  conf="$(dc exec -T frontend nginx -T 2>/dev/null)" || { echo "NG: frontend(nginx) が起動していないか nginx -T に失敗"; return 1; }
  python3 - "$conf" <<'PY'
import re, sys
conf = sys.argv[1]
def block(prefix):
    m = re.search(r'location\s+\^~\s+' + re.escape(prefix) + r'\s*\{([^}]*)\}', conf)
    return m.group(1) if m else None
problems = []
for path in ('/media/', '/sun/media/'):
    b = block(path)
    if b is None or 'return 404' not in b:
        problems.append(f'{path} が 404 になっていない')
b = block('/_protected_media/')
if b is None or 'internal' not in b:
    problems.append('/_protected_media/ が internal になっていない')
if problems:
    print('NG: nginx の安全設定が不足：' + '、'.join(problems)); sys.exit(1)
print('OK: nginx 安全設定（/media/・/sun/media/ 404、/_protected_media/ internal）')
PY
}

verify_http() {
  local fail=0 code
  for path in /media/case_documents/x.pdf /sun/media/case_documents/x.pdf /_protected_media/case_documents/x.pdf; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL$path")
    if [[ "$code" == "404" ]]; then echo "OK: $path → 404"; else echo "NG: $path → $code"; fail=1; fi
  done
  code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/sun/"); [[ "$code" == "200" ]] && echo "OK: /sun/ → 200" || { echo "NG: /sun/ → $code"; fail=1; }
  if csrf_ready; then
    echo "OK: /sun/api/auth/csrf/（backend 応答・CSRF 取得）"
  else
    echo "NG: /sun/api/auth/csrf/ が応答しない"; fail=1
  fi
  return $fail
}

# 新旧どちらの backend にもある /api/auth/csrf/ で起動完了を判定する（旧版には /api/health/ が無い）。
# HTTP 200・本文 "CSRF cookie set"・csrftoken Cookie の 3 点がそろったときだけ「起動済み」とみなす。
csrf_ready() {
  local headers body code
  headers="$(mktemp)"; body="$(mktemp)"
  code=$(curl -s --max-time 5 -D "$headers" -o "$body" -w '%{http_code}' "$BASE_URL/sun/api/auth/csrf/" || echo 000)
  local ok=1
  if [[ "$code" == "200" ]] && grep -q 'CSRF cookie set' "$body" && grep -qi '^set-cookie: *csrftoken=' "$headers"; then ok=0; fi
  rm -f "$headers" "$body"
  return $ok
}

# 起動待ち：WAIT_TIMEOUT 秒（既定 180）まで WAIT_INTERVAL 秒（既定 3）ごとに確認する。
# 1 回の失敗では判定しない。時間切れの場合は backend のログを保存して非 0 で終了する（コンテナは止めない）。
wait_backend() {
  local timeout="${WAIT_TIMEOUT:-180}" interval="${WAIT_INTERVAL:-3}" waited=0
  echo "backend の起動を待っています（最大 ${timeout} 秒）…"
  while (( waited < timeout )); do
    if csrf_ready; then echo "OK: backend 起動済み（${waited} 秒）"; return 0; fi
    sleep "$interval"; waited=$(( waited + interval ))
  done
  local log_dir="${RELEASE_LOG_DIR:-p0_ops}"; mkdir -p "$log_dir"
  local log_file="$log_dir/backend_timeout_$(date +%Y%m%d_%H%M%S).log"
  { dc ps -a; echo '--- backend logs (tail 300) ---'; dc logs --no-color --tail 300 backend; } > "$log_file" 2>&1 || true
  echo "NG: backend が ${timeout} 秒以内に起動しませんでした。ログ：$log_file（パスワード等は出力しない設定のまま）"
  return 1
}

publish_from_image() {  # $1 = イメージ。assets イメージ（/opt/frontend-dist）と旧 nginx 同梱イメージ（/usr/share/nginx/html）の両方に対応
  docker run --rm --entrypoint sh -v "$(dist_volume):/dist" "$1" -c '
    if [ -f /opt/frontend-dist/index.html ]; then SRC=/opt/frontend-dist; else SRC=/usr/share/nginx/html; fi
    test -f "$SRC/index.html" || { echo "index.html が見つかりません"; exit 1; }
    find /dist -mindepth 1 -delete && cp -a "$SRC/." /dist/ && rm -rf /dist/media && mkdir -p /dist/static
    echo "published from $SRC"'
}

cmd="${1:-}"; shift || true
case "$cmd" in
  verify-config) verify_config ;;
  verify-http) verify_http ;;
  wait-backend) wait_backend ;;
  frontend-assets)
    verify_config
    case "${1:-current}" in
      current) dc build frontend-assets && dc run --rm --no-deps frontend-assets ;;
      --from-image) publish_from_image "${2:?イメージ名を指定してください}" ;;
      --from-ref)
        ref="${2:?git の版を指定してください}"; tmp="$(mktemp -d)"
        git archive "$ref" frontend | tar -x -C "$tmp"
        tag="sunrise-frontend-build:$(git rev-parse --short "$ref")"
        docker build -q --target build --build-arg VITE_BASE_PATH="$VITE_BASE_PATH" --build-arg VITE_API_BASE_URL="$VITE_API_BASE_URL" \
          -f "$tmp/frontend/Dockerfile" -t "$tag" "$tmp" >/dev/null
        docker run --rm --entrypoint sh -v "$(dist_volume):/dist" "$tag" -c \
          'find /dist -mindepth 1 -delete && cp -a /app/dist/. /dist/ && mkdir -p /dist/static && echo "published from ref"'
        rm -rf "$tmp" ;;
      *) echo "frontend-assets current | --from-image IMG | --from-ref REF"; exit 2 ;;
    esac
    verify_config && verify_http ;;
  backend)
    [[ "${1:-}" == "--image" ]] || { echo "backend --image IMG"; exit 2; }
    BACKEND_IMAGE="${2:?イメージ名}" dc up -d --no-build backend
    wait_backend || exit 1
    verify_config && verify_http ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
