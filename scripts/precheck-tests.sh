#!/usr/bin/env bash
# ATM-ERP 后端测试本地预检
# 用法: bash scripts/precheck-tests.sh [选项]
#
# 复刻 .github/workflows/ci.yml 的 "Backend / <分组>" 与 "Backend / integration" 两类 job,
# 按本次改动自动挑选需要跑的分组,在 push 前拦下会让 CI 变红的测试失败。
#
# 为什么走 Docker: 本机没有 Python 虚拟环境,生产容器不装 dev 依赖。与 scripts/precheck.sh
# (lint 侧)同一原则——一切经容器,不污染本机。
#
# 测试栈与生产库完全隔离: 独立网络/容器/数据卷,前缀 erp-testenv-,不映射宿主机端口。
set -euo pipefail

c_info(){ printf '\033[0;36m[i]\033[0m %s\n' "$1"; }
c_ok(){   printf '\033[0;32m[\xe2\x9c\x93]\033[0m %s\n' "$1"; }
c_err(){  printf '\033[0;31m[\xe2\x9c\x97]\033[0m %s\n' "$1" >&2; }

REPO_ROOT="$(git rev-parse --show-toplevel)"

NET='erp-testenv-net'
PG_NAME='erp-testenv-pg'
REDIS_NAME='erp-testenv-redis'
PG_VOLUME='erp-testenv-pgdata'
PG_IMAGE='postgres:15'
REDIS_IMAGE='redis:7'

# 测试栈只在自有 Docker 网络内可达、不映射宿主机端口、只装测试数据,
# 因此沿用 CI workflow 里同样明文写死的这套口令。
DB_NAME='erp_db'
DB_USER='erp_user'
DB_PASSWORD='erp_password'
TEST_DB_NAME="test_${DB_NAME}"
TEST_SECRET_KEY='precheck-only-secret-not-for-production'

MODE='auto'
FROM_FILES=''
FRESH_DB=0

usage(){
  cat <<'EOF'
ATM-ERP 后端测试本地预检
用法: bash scripts/precheck-tests.sh [选项]

选项:
  (无)             按改动自动选分组并执行(改动范围取 origin/main..HEAD)
  --all            跑全部分组 + integration
  --plan-only      只打印将要执行的计划,不跑测试
  --from-files F   改动文件列表从 F 读取(每行一个),而非用 git 计算
  --fresh-db       先删除并重建测试库(改写/删除既有迁移文件后需要)
  --up             仅拉起测试栈并建库(用于预热)
  --down           删除测试栈容器,保留数据卷
  --clean          删除测试栈容器与数据卷
  --list-groups    打印从 CI 配置导出的分组定义
  --help           显示本帮助

退出码:
  0   通过,或本次改动无需跑测试
  1   测试失败
  127 缺少 docker
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)         MODE='all'; shift ;;
    --plan-only)   MODE='plan'; shift ;;
    --from-files)
      if [[ $# -lt 2 ]]; then
        c_err "--from-files 需要一个参数(文件路径)"
        usage >&2
        exit 2
      fi
      FROM_FILES="$2"; shift 2 ;;
    --fresh-db)    FRESH_DB=1; shift ;;
    --up)          MODE='up'; shift ;;
    --down)        MODE='down'; shift ;;
    --clean)       MODE='clean'; shift ;;
    --list-groups) MODE='list-groups'; shift ;;
    --help)        usage; exit 0 ;;
    *)             c_err "未知参数: $1"; usage >&2; exit 2 ;;
  esac
done

need_docker(){
  if ! command -v docker >/dev/null 2>&1; then
    c_err "预检需要 docker(本机没有 Python 环境)。确认无法运行时可用 git push --no-verify 跳过。"
    exit 127
  fi
}

# 基础镜像取正在运行的 erp-app 所用镜像 —— 与实际部署完全一致。
# erp-app 没在跑时回落到 manifest.json 记录的版本。
resolve_base_image(){
  if [[ -n "${ERP_TEST_BASE_IMAGE:-}" ]]; then
    printf '%s\n' "$ERP_TEST_BASE_IMAGE"; return 0
  fi
  local img
  img="$(docker inspect erp-app --format '{{.Config.Image}}' 2>/dev/null || true)"
  if [[ -n "$img" ]]; then printf '%s\n' "$img"; return 0; fi
  local tag
  # manifest.json 缺失(浅克隆/稀疏检出)时 sed 非零退出,pipefail 会让这行赋值
  # 直接终止脚本(在下面的 if 判空之前),让「无法确定基础镜像」的友好报错永远打印不出来。
  # 用 || true 兜底,把判空交给下面已经写好的 if。
  tag="$(sed -n 's/.*"image_tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$REPO_ROOT/manifest.json" | head -1)" || true
  if [[ -z "$tag" ]]; then
    c_err "无法确定基础镜像:erp-app 未运行且 manifest.json 里读不到 image_tag。可用 ERP_TEST_BASE_IMAGE 指定。"
    exit 1
  fi
  printf 'ghcr.io/hongheshan-svg/atm-erp-app:%s\n' "$tag"
}

# 分组定义从 scripts/ci/backend_test_matrix.py 的 GROUPS 动态导出,不在此处复制一份。
# 与 precheck.sh 动态解析 ruff 版本同一原则:CI 改了分组,预检自动跟随。
# 导出成「序号|名称|模块|目标」的管道分隔行,bash 可零依赖解析(不需要 jq 或本机 python)。
load_groups(){
  local raw
  if [[ -n "${ERP_TEST_GROUPS:-}" ]]; then
    raw="$ERP_TEST_GROUPS"
  else
    need_docker
    raw="$(docker run --rm --entrypoint python \
      -v "$REPO_ROOT:/repo:ro" -w /repo/backend \
      -e PYTHONDONTWRITEBYTECODE=1 \
      "$(resolve_base_image)" -c '
import sys
sys.path.insert(0, "/repo/scripts/ci")
import backend_test_matrix as m
for i, g in enumerate(m.GROUPS, 1):
    print("%d|%s|%s|%s" % (i, g["name"], ",".join(g["modules"]), ",".join(g["targets"])))
')"
  fi
  GROUPS_RAW=()
  local line
  while IFS= read -r line; do
    [[ -n "$line" ]] && GROUPS_RAW+=("$line")
  done <<< "$raw"
  if [[ ${#GROUPS_RAW[@]} -eq 0 ]]; then
    c_err "分组定义为空,无法继续"
    exit 1
  fi
}

if [[ "$MODE" == 'list-groups' ]]; then
  load_groups
  for line in "${GROUPS_RAW[@]}"; do
    printf '%s\n' "$line"
  done
  exit 0
fi

c_err "尚未实现: $MODE"
exit 1
