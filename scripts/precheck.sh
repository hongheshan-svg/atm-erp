#!/usr/bin/env bash
# ATM-ERP 本地 CI 预检 (lint + format)
# 用法: bash scripts/precheck.sh [--fix] [--help]
#
# 复刻 .github/workflows/ci.yml 中 "Backend / preflight → Lint and formatting" 这一步：
#     ruff check . ../scripts/ci
#     ruff format --check . ../scripts/ci
# 检查范围与 CI 逐字一致（backend/ 与 scripts/ci/ 两个路径，后者容易漏）。
#
# 为什么走 Docker: 本机与 erp-app 容器均未安装 ruff（ruff 只在 backend/requirements-dev.txt
# 里，生产镜像不装 dev 依赖），官方镜像是唯一无需污染本机环境的一致来源。
# ruff 版本从 requirements-dev.txt 动态读取，避免与 CI 漂移。
set -euo pipefail

c_info(){ printf '\033[0;36m[i]\033[0m %s\n' "$1"; }
c_ok(){   printf '\033[0;32m[\xe2\x9c\x93]\033[0m %s\n' "$1"; }
c_err(){  printf '\033[0;31m[\xe2\x9c\x97]\033[0m %s\n' "$1" >&2; }

FIX=0

usage(){
  cat <<EOF
ATM-ERP 本地 CI 预检 (lint + format)
用法: bash scripts/precheck.sh [选项]

选项:
  --fix     自动修复可修项 (ruff check --fix + ruff format 写回)
            不加此选项时只做检查，与 CI 门禁行为一致
  --help    显示本帮助

退出码:
  0   预检通过
  1   存在 lint 或格式问题
  127 缺少 docker
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fix)  FIX=1; shift ;;
    --help) usage; exit 0 ;;
    *)      c_err "未知参数: $1"; usage >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"

# 与 CI 使用同一版本：CI 装的是 requirements-dev.txt 里钉住的 ruff
RUFF_VERSION="$(sed -n 's/^ruff==\([0-9][^[:space:]]*\).*/\1/p' \
  "$REPO_ROOT/backend/requirements-dev.txt" | head -1)"
if [[ -z "$RUFF_VERSION" ]]; then
  c_err "无法从 backend/requirements-dev.txt 解析 ruff 版本（预期形如 ruff==0.16.0）"
  exit 1
fi
RUFF_IMAGE="ghcr.io/astral-sh/ruff:${RUFF_VERSION}"

if ! command -v docker >/dev/null 2>&1; then
  c_err "预检需要 docker（本机未安装 ruff）。确认无法运行时可用 git commit --no-verify 跳过。"
  exit 127
fi

# --user  : 保证 --fix 写回的文件属主是当前用户，而非 root
# RUFF_CACHE_DIR: 指向容器内 tmpfs，不落宿主 backend/.ruff_cache。
#   否则一旦该目录下存在 root 属主的残留（早期不带 --user 跑过就会产生），
#   降权后的容器写不进缓存，ruff 会以 "Permission denied" 直接崩掉——
#   表现为预检失败但原因与代码无关，属于假警报。
run_ruff(){
  docker run --rm \
    --user "$(id -u):$(id -g)" \
    --tmpfs /tmp/ruff-cache:exec \
    -e RUFF_CACHE_DIR=/tmp/ruff-cache \
    -v "$REPO_ROOT":/repo \
    -w /repo/backend \
    "$RUFF_IMAGE" "$@"
}

c_info "ruff ${RUFF_VERSION} 预检范围: backend/ + scripts/ci/"

if [[ $FIX -eq 1 ]]; then
  run_ruff check --fix . ../scripts/ci
  run_ruff format . ../scripts/ci
  c_ok "已自动修复，请复查 git diff 后重新 add"
else
  run_ruff check . ../scripts/ci
  run_ruff format --check . ../scripts/ci
  c_ok "预检通过（等价于 CI 的 Lint and formatting 步骤）"
fi
