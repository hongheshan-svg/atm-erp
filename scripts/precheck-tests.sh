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
c_warn(){ printf '\033[0;33m[!]\033[0m %s\n' "$1" >&2; }
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

# CI 的 checkout 里没有 backend/.env 与仓库根 .env(被 .gitignore 忽略,也不是标准 onboarding
# 产物——仓库里没有 backend/.env.example,干净 clone 通常没有这两个文件),本地机器上可能有。
# backend/config/settings.py 用 python-decouple 的 config() 读取约 50 个键,本脚本只用 -e
# 显式注入并覆盖了 11 个(DJANGO_SETTINGS_MODULE/SECRET_KEY/DEBUG/DB_*/REDIS_*,os.environ
# 优先于 .env,安全)。其余键(PASSWORD_MIN_LENGTH/MAX_LOGIN_ATTEMPTS/INVENTORY_COSTING_METHOD
# 等测试可能断言的配置)不屏蔽的话,本地会取 .env 里的值、CI 取代码默认值——同一次改动
# 本地绿、CI 红,而且因机器而异(.env 是否存在、内容是否相同)。
#
# 只在宿主机上该文件确实存在时才挂载 /dev/null 屏蔽它:父挂载 -v "$REPO_ROOT:/repo:ro"
# 是只读的,docker 要在挂载点位置创建一个文件才能盖上 /dev/null,只读文件系统上创建不了
# ——文件不存在时这个挂载会让 docker run 直接 exit 125(已实测复现,不是"安全的空操作")。
# 文件不存在时,容器内本来就读不到它,已经和 CI 一致,不需要额外处理。
ENV_ISOLATION_MOUNTS=()
if [[ -e "$REPO_ROOT/backend/.env" ]]; then
  ENV_ISOLATION_MOUNTS+=(-v /dev/null:/repo/backend/.env:ro)
fi
if [[ -e "$REPO_ROOT/.env" ]]; then
  ENV_ISOLATION_MOUNTS+=(-v /dev/null:/repo/.env:ro)
fi

MODE='auto'
CUR_MODE_FLAG=''
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

# --all/--plan-only/--up/--down/--clean/--list-groups 互斥:同一次调用只能选一个模式,
# 后写覆盖先写会让 `--plan-only --all` 这类组合默默按最后一个参数执行(其中一个方向
# 会真的跑一次全量测试)。用互斥检测报错,而不是猜用户想要哪种。
# --fresh-db / --from-files 不经过这里——它们是修饰符,可以和任意模式叠加。
set_mode(){
  if [[ "$MODE" != 'auto' ]]; then
    c_err "模式开关互斥: 已指定 $CUR_MODE_FLAG,不能再加 $2(--fresh-db/--from-files 是修饰符,不受此限制)"
    exit 2
  fi
  MODE="$1"
  CUR_MODE_FLAG="$2"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)         set_mode 'all' '--all'; shift ;;
    --plan-only)   set_mode 'plan' '--plan-only'; shift ;;
    --from-files)
      if [[ $# -lt 2 ]]; then
        c_err "--from-files 需要一个参数(文件路径)"
        usage >&2
        exit 2
      fi
      FROM_FILES="$2"; shift 2 ;;
    --fresh-db)    FRESH_DB=1; shift ;;
    --up)          set_mode 'up' '--up'; shift ;;
    --down)        set_mode 'down' '--down'; shift ;;
    --clean)       set_mode 'clean' '--clean'; shift ;;
    --list-groups) set_mode 'list-groups' '--list-groups'; shift ;;
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
    # resolve_base_image 失败时会 exit 1;必须先落到一个独立的赋值语句里(分两行写,
    # 不能 local base="$(resolve_base_image)" 那样合并——合并写法的返回值是 local 自身
    # 的 0,set -e 不会触发,失败会被静默吞掉)。不要把它内联进下面的 docker run 参数列表,
    # 否则它跑在更深一层的 command substitution 子 shell 里,失败只会终止那层子 shell、
    # 产出空字符串,被当成空镜像名传给 docker run,导致报错来自 docker 而不是这里,
    # 退出码也变成 docker 的而不是承诺的 1。
    local base
    base="$(resolve_base_image)"
    raw="$(docker run --rm --entrypoint python \
      -v "$REPO_ROOT:/repo:ro" -w /repo/backend \
      "${ENV_ISOLATION_MOUNTS[@]+"${ENV_ISOLATION_MOUNTS[@]}"}" \
      -e PYTHONDONTWRITEBYTECODE=1 \
      "$base" -c '
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

# ── 改动分类(纯 bash,零外部依赖)──
# 采用白名单语义: 只有明确列出的路径才触发测试,未列出的一律放行。
# 这样新增目录默认不会拖慢 push,代价由 CI 全量兜底。
classify_changes(){
  WANT_FULL=0
  WANT_INTEGRATION=0
  WANT_MODULES=()
  local f app
  # `|| [[ -n "$f" ]]`: read 读到不带末尾换行符的最后一行时,内容进了 $f 但 read 自身返回
  # 非零,裸 `while read` 会把这次判假当成 EOF、直接漏掉这一行。--from-files 场景下,调用方
  # 用 "$(git diff --name-only ...)" 写临时文件时命令替换会去掉尾随换行,这个坑真实存在。
  while IFS= read -r f || [[ -n "$f" ]]; do
    [[ -z "$f" ]] && continue
    case "$f" in
      # apps/core 提供全站 BaseModel/权限 Mixin/审计/工作流,config 是 settings 与根 urls,
      # 两者影响所有模块。全量只比单跑分组① 多约 40 秒(分组①本身就是耗时大头),值得。
      backend/apps/core/*|backend/config/*|backend/manage.py|backend/requirements*.txt|backend/pyproject.toml)
        WANT_FULL=1; WANT_INTEGRATION=1 ;;
      backend/apps/*/*)
        app="${f#backend/apps/}"; app="${app%%/*}"
        WANT_MODULES+=("apps.$app"); WANT_INTEGRATION=1 ;;
      backend/tests/*)
        WANT_INTEGRATION=1 ;;
      # 分组① 的 test_menu_sync_toplevel / test_permission_bootstrap 直接读这个文件核对菜单权限。
      # 改前端路由却忘了同步菜单权限,是本项目真实踩过的坑。
      # 这里用 apps.core 代表该分组,而不是硬编码序号 1 —— CI 调整分组顺序时仍然正确。
      frontend/src/router/index.ts)
        WANT_MODULES+=('apps.core') ;;
      *) ;;
    esac
  done
}

# 把 WANT_MODULES / WANT_FULL 解析成升序去重的分组序号,写入全局 SELECTED_GROUPS
select_groups(){
  SELECTED_GROUPS=()
  local line idx modules m want
  for line in "${GROUPS_RAW[@]}"; do
    IFS='|' read -r idx _ modules _ <<< "$line"
    want=0
    if [[ $WANT_FULL -eq 1 ]]; then
      want=1
    else
      for m in "${WANT_MODULES[@]+"${WANT_MODULES[@]}"}"; do
        # 逗号包裹后做子串匹配,避免 apps.core 误命中 apps.core_extra 之类前缀
        case ",$modules," in *",$m,"*) want=1; break ;; esac
      done
    fi
    # 用 if 而非 `[[ ]] && cmd`: 当循环处理到 GROUPS_RAW 最后一个元素且 want=0 时,
    # 裸的 `test && cmd` 列表其自身退出码就是 test 的失败状态(1)。这是 for 循环里的
    # 最后一条语句,于是 select_groups 这个函数调用(裸语句,没包在 if/&&里)的退出码
    # 也变成 1,在 set -e 下把整个脚本静默杀死、且不打印任何报错——已用手工复现确认。
    if [[ $want -eq 1 ]]; then
      SELECTED_GROUPS+=("$idx")
    fi
  done
}

# 取本次要检查的改动文件列表
collect_changed_files(){
  if [[ -n "$FROM_FILES" ]]; then
    cat "$FROM_FILES"
  elif [[ -n "${ERP_TEST_DIFF_BASE:-}" ]]; then
    git diff --name-only "$ERP_TEST_DIFF_BASE" HEAD
  else
    git diff --name-only origin/main HEAD
  fi
}

print_plan(){
  if [[ ${#SELECTED_GROUPS[@]} -eq 0 ]]; then
    echo 'groups: none'
  else
    echo "groups: ${SELECTED_GROUPS[*]}"
  fi
  if [[ $WANT_INTEGRATION -eq 1 ]]; then echo 'integration: yes'; else echo 'integration: no'; fi
}

# ── 测试栈生命周期 ──
# 全部资源前缀 erp-testenv-,不属于任何 compose project,不会被 docker compose down 误伤;
# 不映射宿主机端口,与生产的 erp-postgres/erp-redis 无任何交集。
container_state(){
  # running / exists / absent
  if docker ps --format '{{.Names}}' | grep -qx "$1"; then echo running
  elif docker ps -a --format '{{.Names}}' | grep -qx "$1"; then echo exists
  else echo absent; fi
}

ensure_stack(){
  need_docker
  docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null
  # 数据卷独立于容器: 那约 7 分钟建好的测试库因此能在容器被删后存活
  docker volume inspect "$PG_VOLUME" >/dev/null 2>&1 || docker volume create "$PG_VOLUME" >/dev/null

  case "$(container_state "$PG_NAME")" in
    running) ;;
    exists)  docker start "$PG_NAME" >/dev/null ;;
    absent)
      c_info "创建测试数据库容器 $PG_NAME ($PG_IMAGE)"
      docker run -d --name "$PG_NAME" --network "$NET" \
        -e POSTGRES_DB="$DB_NAME" -e POSTGRES_USER="$DB_USER" -e POSTGRES_PASSWORD="$DB_PASSWORD" \
        -v "$PG_VOLUME:/var/lib/postgresql/data" \
        "$PG_IMAGE" >/dev/null ;;
  esac

  case "$(container_state "$REDIS_NAME")" in
    running) ;;
    exists)  docker start "$REDIS_NAME" >/dev/null ;;
    absent)
      c_info "创建测试缓存容器 $REDIS_NAME ($REDIS_IMAGE)"
      docker run -d --name "$REDIS_NAME" --network "$NET" "$REDIS_IMAGE" >/dev/null ;;
  esac

  local i
  for i in $(seq 1 60); do
    if docker exec "$PG_NAME" pg_isready -U "$DB_USER" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  c_err "测试数据库 60 秒内未就绪,可用 docker logs $PG_NAME 排查"
  exit 1
}

psql_maint(){ docker exec "$PG_NAME" psql -U "$DB_USER" -d postgres -tAc "$1"; }

test_db_exists(){
  [[ "$(psql_maint "SELECT 1 FROM pg_database WHERE datname='$TEST_DB_NAME'" 2>/dev/null || true)" == '1' ]]
}

drop_test_db(){
  # FORCE 断开残留连接(PG 13+)。没有它,上一次异常中断留下的连接会让 DROP 卡住。
  psql_maint "DROP DATABASE IF EXISTS $TEST_DB_NAME WITH (FORCE)" >/dev/null
  c_ok "已删除测试库 $TEST_DB_NAME"
}

stack_down(){
  need_docker
  docker rm -f "$PG_NAME" "$REDIS_NAME" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  c_ok "测试栈容器已删除(数据卷 $PG_VOLUME 保留,测试库仍在)"
}

stack_clean(){
  stack_down
  docker volume rm "$PG_VOLUME" >/dev/null 2>&1 || true
  c_ok "数据卷已删除,下次运行会重新建库(约 7 分钟)"
}

# up/down/clean 分派统一放在脚本末尾(晚于函数定义)—— bash 顺序解释,分派块调用的函数必须已定义。

if [[ "$MODE" == 'plan' || "$MODE" == 'auto' || "$MODE" == 'all' ]]; then
  if [[ "$MODE" == 'all' ]]; then
    WANT_FULL=1; WANT_INTEGRATION=1; WANT_MODULES=()
  else
    # 不用 `classify_changes < <(collect_changed_files)`:进程替换(`< <(...)`)不传播
    # 子进程的退出码。collect_changed_files 内部三条分支(cat "$FROM_FILES" / git diff
    # 基线1 / git diff 基线2)任意一条失败,classify_changes 读到的只是空输入,产出
    # WANT_FULL=0/WANT_INTEGRATION=0/WANT_MODULES=() ——和"确实没有改动"完全同一个结果,
    # 命中下面的零命中分支,打印绿色"跳过测试预检"退出 0。"算不出该测什么"绝不能等价于
    # "不用测",所以改成落临时文件、显式检查 collect_changed_files 自身的退出码。
    changed_list="$(mktemp)"; trap 'rm -f "$changed_list"' EXIT
    if ! collect_changed_files > "$changed_list"; then
      c_err "无法获取改动文件列表(基线不可用?)。可用 --from-files 显式指定,或 git push --no-verify 跳过。"
      exit 1
    fi
    classify_changes < "$changed_list"
  fi

  # 无任何命中时立即退出,不加载分组定义(那会启动容器)。
  # docs/ 之类的改动因此完全零开销 —— 这是 pre-push 不惹人烦的关键。
  if [[ $WANT_FULL -eq 0 && $WANT_INTEGRATION -eq 0 && ${#WANT_MODULES[@]} -eq 0 ]]; then
    if [[ "$MODE" == 'plan' ]]; then
      echo 'groups: none'; echo 'integration: no'
    else
      c_ok '本次改动不涉及后端代码,跳过测试预检'
    fi
    exit 0
  fi

  load_groups
  select_groups

  # 改动映射到了模块(WANT_MODULES 非空),但没有一个 CI 分组声明覆盖它——多半是新 app
  # 尚未加进 scripts/ci/backend_test_matrix.py 的 GROUPS。这是合法的中间状态(新 app 会先
  # 落地再补分组),不应该让预检报错,但必须让人知道"这部分改动本地实际上没有被测试覆盖",
  # 而不是静默并入 integration-only 结果、最后照样打印"测试预检通过"。
  if [[ ${#WANT_MODULES[@]} -gt 0 && ${#SELECTED_GROUPS[@]} -eq 0 ]]; then
    for m in "${WANT_MODULES[@]}"; do
      c_warn "模块 $m 不属于任何 CI 分组(可能需要更新 scripts/ci/backend_test_matrix.py),其测试未在本地执行"
    done
  fi

  if [[ "$MODE" == 'plan' ]]; then
    print_plan
    exit 0
  fi
fi

if [[ "$MODE" == 'up' ]]; then
  ensure_stack
  if [[ $FRESH_DB -eq 1 ]]; then drop_test_db; fi
  if test_db_exists; then
    c_ok "测试栈就绪,测试库 $TEST_DB_NAME 已存在"
  else
    c_info "测试库尚未创建,首次运行测试时会自动创建(约需 7 分钟,执行全量迁移)"
  fi
  exit 0
elif [[ "$MODE" == 'down' ]]; then
  stack_down
  exit 0
elif [[ "$MODE" == 'clean' ]]; then
  stack_clean
  exit 0
fi

LOG_DIR="$(mktemp -d -t erp-precheck-XXXXXX)"

# 与 CI 的差异只有 --keepdb 一处(CI 每次新建库)。
# 代价: 改写/删除既有迁移文件后本地库会陈旧,用 --fresh-db 重建。新增迁移无妨,keepdb 仍会 apply。
docker_test_run(){
  docker run --rm --network "$NET" \
    -v "$REPO_ROOT:/repo:ro" -w /repo/backend \
    "${ENV_ISOLATION_MOUNTS[@]+"${ENV_ISOLATION_MOUNTS[@]}"}" \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e DJANGO_SETTINGS_MODULE=config.settings \
    -e SECRET_KEY="$TEST_SECRET_KEY" \
    -e DEBUG=False \
    -e DB_HOST="$PG_NAME" -e DB_NAME="$DB_NAME" -e DB_USER="$DB_USER" \
    -e DB_PASSWORD="$DB_PASSWORD" -e DB_PORT=5432 \
    -e REDIS_URL="redis://$REDIS_NAME:6379/0" -e REDIS_HOST="$REDIS_NAME" \
    "$@"
}

run_django_group(){
  local want_idx="$1" line idx name targets
  for line in "${GROUPS_RAW[@]}"; do
    IFS='|' read -r idx name _ targets <<< "$line"
    [[ "$idx" == "$want_idx" ]] || continue
    local -a tlist
    IFS=',' read -r -a tlist <<< "$targets"
    c_info "分组${idx}: ${name}"
    if docker_test_run --entrypoint python "$RUNNER_IMAGE" \
        -W error::DeprecationWarning manage.py test --noinput --keepdb "${tlist[@]}" \
        > "$LOG_DIR/group-$idx.log" 2>&1; then
      c_ok "分组${idx} 通过  $(grep -E '^Ran ' "$LOG_DIR/group-$idx.log" | tail -1)"
      return 0
    else
      c_err "分组${idx} 失败"
      grep -E '^(FAIL|ERROR):' "$LOG_DIR/group-$idx.log" | head -20 >&2 || true
      c_err "完整日志: $LOG_DIR/group-$idx.log"
      return 1
    fi
    done
  c_err "分组序号 $want_idx 不存在"
  return 1
}

# 薄镜像 tag 里同时编码了 pytest 版本与基础镜像版本 ——
# 任何一方变化都会 miss 并触发重建,不需要人记得刷新。
# 相比每次容器内 pip install(约 6 秒),薄镜像还能离线运行。
resolve_runner_image(){
  local pytest_ver django_ver base base_tag tag
  # requirements-dev.txt 不可读时(稀疏检出等),pipefail 会让 sed|head 的非零退出码直接
  # 传给 set -e,在下面已写好的判空报错之前就杀掉脚本/子 shell——同类风险
  # resolve_base_image() 已用 || true 处理过,这里照做,把报错交给下面的 if 分支。
  pytest_ver="$(sed -n 's/^pytest==\([0-9][^[:space:]]*\).*/\1/p' \
    "$REPO_ROOT/backend/requirements-dev.txt" | head -1)" || true
  django_ver="$(sed -n 's/^pytest-django==\([0-9][^[:space:]]*\).*/\1/p' \
    "$REPO_ROOT/backend/requirements-dev.txt" | head -1)" || true
  if [[ -z "$pytest_ver" || -z "$django_ver" ]]; then
    c_err "无法从 backend/requirements-dev.txt 解析 pytest / pytest-django 版本"
    exit 1
  fi
  base="$1"
  base_tag="${base##*:}"
  tag="erp-test-runner:${pytest_ver}-${base_tag}"
  if ! docker image inspect "$tag" >/dev/null 2>&1; then
    # 本函数的返回值走 stdout(调用方用 RUNNER_IMAGE="$(resolve_runner_image ...)" 捕获),
    # c_info 默认写 stdout——不重定向到 stderr 的话,这条提示会和 tag 一起被吞进变量,
    # 拼成多行字符串传给 docker run,报 "invalid reference format"(已手工复现)。
    c_info "构建测试镜像 $tag(生产镜像 + pytest,仅首次)" >&2
    # -t 必须给:没有它 docker build 只产出一个匿名(<none>:<none>)镜像,既不会被下面的
    # image inspect 缓存命中(每次都重建),docker run 时也找不到本地同名镜像,转而向
    # Docker Hub 拉取 "erp-test-runner" 这个不存在的公共仓库,报 403/未知镜像(已手工复现)。
    docker build -q -t "$tag" \
      --build-arg "BASE_IMAGE=$base" \
      --build-arg "PYTEST_SPEC=pytest==$pytest_ver pytest-django==$django_ver" \
      -f "$REPO_ROOT/docker/test-runner.Dockerfile" \
      "$REPO_ROOT" >/dev/null
  fi
  printf '%s\n' "$tag"
}

# 对应 CI 的: pytest tests/integration -v --tb=short -W error::DeprecationWarning
#   --reuse-db        等价于 Django 的 --keepdb,复用测试库
#   -p no:cacheprovider  仓库是只读挂载,写不了 .pytest_cache,不禁用会有一条干扰性 warning
run_integration(){
  c_info 'integration (pytest)'
  if docker_test_run --entrypoint pytest "$RUNNER_IMAGE" \
      tests/integration -q --tb=short -W error::DeprecationWarning \
      --reuse-db -p no:cacheprovider \
      > "$LOG_DIR/integration.log" 2>&1; then
    c_ok "integration 通过  $(grep -E '[0-9]+ passed' "$LOG_DIR/integration.log" | tail -1)"
    return 0
  fi
  c_err 'integration 失败'
  grep -E '^(FAILED|ERROR)' "$LOG_DIR/integration.log" | head -20 >&2 || true
  c_err "完整日志: $LOG_DIR/integration.log"
  return 1
}

BASE_IMAGE="$(resolve_base_image)"
RUNNER_IMAGE="$(resolve_runner_image "$BASE_IMAGE")"
ensure_stack
if [[ $FRESH_DB -eq 1 ]]; then drop_test_db; fi
if ! test_db_exists; then
  c_info "首次运行:正在创建测试库并执行全量迁移,约需 7 分钟。之后会复用,不再重复。"
fi

failed=0
for idx in "${SELECTED_GROUPS[@]+"${SELECTED_GROUPS[@]}"}"; do
  run_django_group "$idx" || failed=1
done

if [[ $WANT_INTEGRATION -eq 1 ]]; then
  run_integration || failed=1
fi

if [[ $failed -eq 1 ]]; then
  c_err "测试预检未通过。修复后重试,确需跳过用 git push --no-verify。"
  exit 1
fi
c_ok "测试预检通过"
exit 0
