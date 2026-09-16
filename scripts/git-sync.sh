#!/usr/bin/env bash

set -euo pipefail

REMOTE="${GIT_REMOTE:-origin}"
SERVER_PATH_DEFAULT="/www/wwwroot/0629code"

usage() {
  cat <<'EOF'
用法:
  ./scripts/git-sync.sh pull
      拉取当前分支的最新代码（仅允许 fast-forward）。

  ./scripts/git-sync.sh push
      推送已经提交到本地的提交，不会自动 add 或 commit。

  ./scripts/git-sync.sh upload "提交说明"
      显示当前改动，确认后 add -A、commit 并 push。

  ./scripts/git-sync.sh server-pull <user@host> [项目目录] [分支]
      通过 SSH 让服务器从 GitHub 拉取最新代码。

也可以使用环境变量:
  DEPLOY_HOST=user@host
  DEPLOY_PATH=/www/wwwroot/0629code
  DEPLOY_BRANCH=main

示例:
  ./scripts/git-sync.sh pull
  ./scripts/git-sync.sh upload "更新签证申请页面"
  DEPLOY_HOST=root@43.139.37.150 ./scripts/git-sync.sh server-pull
EOF
}

die() {
  echo "错误: $*" >&2
  exit 1
}

git_root() {
  git rev-parse --show-toplevel 2>/dev/null || die "当前目录不是 Git 仓库"
}

current_branch() {
  local branch
  branch="$(git branch --show-current)"
  [[ -n "$branch" ]] || die "当前处于 detached HEAD，无法自动选择分支"
  printf '%s\n' "$branch"
}

require_clean_worktree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "当前工作区有未提交或未跟踪文件:" >&2
    git status --short >&2
    die "请先提交、暂存或保存这些改动后再执行 pull"
  fi
}

pull_local() {
  local branch
  branch="$(current_branch)"
  require_clean_worktree
  git pull --ff-only "$REMOTE" "$branch"
}

push_local() {
  local branch
  branch="$(current_branch)"
  git push "$REMOTE" "$branch"
}

upload_local() {
  local message="${1:-}"
  [[ -n "$message" ]] || die 'upload 需要提交说明，例如: ./scripts/git-sync.sh upload "修复登录问题"'

  if [[ -z "$(git status --porcelain)" ]]; then
    die "没有检测到本地改动"
  fi

  echo "将要提交以下改动:"
  git status --short
  printf '确认 add -A、commit 并上传到 %s？[y/N] ' "$REMOTE"
  read -r answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || die "已取消"

  git add -A
  git commit -m "$message"
  push_local
}

server_pull() {
  local host="${1:-${DEPLOY_HOST:-}}"
  local path="${2:-${DEPLOY_PATH:-$SERVER_PATH_DEFAULT}}"
  local branch="${3:-${DEPLOY_BRANCH:-main}}"

  [[ -n "$host" ]] || die "请提供服务器地址，例如: DEPLOY_HOST=root@43.139.37.150 ./scripts/git-sync.sh server-pull"

  echo "服务器: $host"
  echo "目录:   $path"
  echo "分支:   $branch"
  printf '确认让服务器拉取最新代码？[y/N] '
  read -r answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || die "已取消"

  # %q 让路径和分支作为单个 shell 参数传给远端，避免空格或特殊字符造成误解析。
  local quoted_path quoted_branch
  printf -v quoted_path '%q' "$path"
  printf -v quoted_branch '%q' "$branch"
  ssh "$host" "cd -- $quoted_path && git pull --ff-only $REMOTE $quoted_branch"
}

main() {
  cd "$(git_root)"

  case "${1:-}" in
    pull)
      pull_local
      ;;
    push)
      push_local
      ;;
    upload)
      upload_local "${2:-}"
      ;;
    server-pull)
      server_pull "${2:-}" "${3:-}" "${4:-}"
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
