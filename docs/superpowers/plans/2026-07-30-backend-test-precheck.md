# 后端测试本地预检 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `git push` 之前,自动跑完与本次改动相关的 CI 后端测试分组,把「推上 GitHub 才发现测试挂了」提前到本地拦截。

**Architecture:** 一个 bash 主脚本 `scripts/precheck-tests.sh` 负责三件事——管理一套与生产完全隔离的 postgres+redis 测试栈、把改动文件映射到 CI 分组、在生产镜像里执行测试。`.githooks/pre-push` 作为触发器计算改动范围并调用它。分组定义不写死,从 `scripts/ci/backend_test_matrix.py` 动态导出,保证与 CI 不漂移。

**Tech Stack:** bash 4+、Docker、`postgres:15`、`redis:7`、生产镜像 `ghcr.io/hongheshan-svg/atm-erp-app:<tag>`、Django test runner、pytest。

**设计文档:** [后端测试本地预检 · 设计](../specs/2026-07-30-backend-test-precheck-design.md)

## Global Constraints

以下取自设计文档,**每个任务都隐含包含**,违反任何一条都会让预检不可信:

- 执行测试时必须挂**仓库根**:`-v "$REPO_ROOT:/repo:ro" -w /repo/backend`。绝不可只挂 `backend/`,那会盖掉镜像里的 `/app/frontend`,导致分组① 4 个用例报「找不到前端路由文件」。
- 必须设 `PYTHONDONTWRITEBYTECODE=1`。只读挂载下缺它会有 17 倍性能损失(7m33s vs 27s)。
- Django 测试必须带 `-W error::DeprecationWarning`(CI 用了它);pytest 同样带 `-W error::DeprecationWarning`。
- postgres 与 redis 两个容器都必须在,redis 是硬依赖。
- 测试栈镜像固定为 `postgres:15` 与 `redis:7`(**非 alpine**),与 CI 逐字一致,避免 musl/glibc 的 collation 差异。
- 测试栈资源命名前缀一律 `erp-testenv-`,禁止与生产的 `erp-postgres`/`erp-redis`/`erp-network` 重名,且不映射任何宿主机端口。
- 脚本输出风格沿用 `scripts/precheck.sh`:`set -euo pipefail`,`c_info`/`c_ok`/`c_err` 三个着色函数,中文注释说明「为什么」而非「做什么」。
- 版本号(pytest、pytest-django)一律从 `backend/requirements-dev.txt` 动态解析,禁止在脚本里写死。
- 全部工作在分支 `chore/local-test-precheck` 上进行,禁止提交到 `main`。

## 文件结构

| 文件 | 职责 |
|---|---|
| `scripts/precheck-tests.sh` | 主脚本。测试栈生命周期 + 改动映射 + 测试执行。单文件,与既有 `precheck.sh` 的形态一致 |
| `scripts/tests/test_precheck_tests.sh` | 映射逻辑的回归测试。纯 bash,不依赖 Docker/python |
| `docker/test-runner.Dockerfile` | 在生产镜像上补 pytest 的薄镜像 |
| `.githooks/pre-push` | 触发器。解析 stdin、算改动范围、调主脚本 |
| `CLAUDE.md` | 使用说明(在既有「本地 CI 预检」一节后追加) |

`precheck-tests.sh` 保持单文件是刻意的:既有 `precheck.sh` 就是单文件,拆 `lib/` 会引入本仓库目前没有的目录结构。预计 300 行以内,可控。

---

### Task 1: 脚本骨架与分组定义动态导出

建立主脚本的参数解析、基础镜像解析和「从 CI 配置导出分组」的能力。此任务不碰数据库,不跑测试。

**Files:**
- Create: `scripts/precheck-tests.sh`

**Interfaces:**
- Produces:
  - `resolve_base_image()` → stdout 输出生产镜像全名,如 `ghcr.io/hongheshan-svg/atm-erp-app:0.3.0`
  - `load_groups()` → 设置全局数组 `GROUPS_RAW`,每个元素形如 `1|platform, permissions and accounts|apps.core,apps.core.workflow,apps.accounts,apps.ai|apps.core.tests,apps.core.workflow,apps.accounts.tests,apps.ai.tests`(序号|名称|模块|测试目标,后两者逗号分隔)
  - 环境变量注入点 `ERP_TEST_BASE_IMAGE`(覆盖镜像)、`ERP_TEST_GROUPS`(覆盖分组数据,换行分隔,供测试跳过 Docker)
  - 选项 `--list-groups`(打印分组)、`--help`

- [ ] **Step 1: 写验证命令,确认当前失败**

Run: `bash scripts/precheck-tests.sh --list-groups`
Expected: FAIL —— `No such file or directory`(脚本还不存在)

- [ ] **Step 2: 创建脚本骨架**

创建 `scripts/precheck-tests.sh`:

```bash
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
    --from-files)  FROM_FILES="${2:-}"; shift 2 ;;
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
  tag="$(sed -n 's/.*"image_tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
    "$REPO_ROOT/manifest.json" | head -1)"
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
```

- [ ] **Step 3: 运行验证命令,确认通过**

Run: `bash scripts/precheck-tests.sh --list-groups`
Expected: 输出 4 行,第 1 行以 `1|platform, permissions and accounts|apps.core,apps.core.workflow,apps.accounts,apps.ai|` 开头,第 4 行以 `4|finance, reporting and office|` 开头。

- [ ] **Step 4: 验证注入点可用(后续任务的测试依赖它)**

Run:
```bash
ERP_TEST_GROUPS='1|a|apps.core|apps.core.tests
2|b|apps.sales|apps.sales.tests' bash scripts/precheck-tests.sh --list-groups
```
Expected: 输出正好这 2 行,且**不启动任何容器**(命令应在 1 秒内返回)。

- [ ] **Step 5: 验证 --help 与未知参数**

Run: `bash scripts/precheck-tests.sh --help; bash scripts/precheck-tests.sh --nope; echo "exit=$?"`
Expected: 帮助正常打印;未知参数报错且 `exit=2`。

- [ ] **Step 6: 提交**

```bash
chmod +x scripts/precheck-tests.sh
git add scripts/precheck-tests.sh
git commit -m "feat(precheck): 测试预检脚本骨架与分组定义动态导出"
```

---

### Task 2: 改动 → 分组映射

把改动文件列表映射到需要执行的分组。这是全套逻辑里唯一值得单独写回归测试的部分——规则细碎、易错、且日后会改。

**Files:**
- Modify: `scripts/precheck-tests.sh`
- Create: `scripts/tests/test_precheck_tests.sh`

**Interfaces:**
- Consumes: Task 1 的 `GROUPS_RAW` 数组与 `ERP_TEST_GROUPS` 注入点
- Produces:
  - `--plan-only --from-files <F>` 输出**恰好两行**,格式固定:
    ```
    groups: 1 4
    integration: yes
    ```
    无命中时为 `groups: none` / `integration: no`。分组序号升序、空格分隔。
  - 内部函数 `classify_changes()` 读 stdin 文件列表,设置全局 `WANT_FULL`(0/1)、`WANT_INTEGRATION`(0/1)、`WANT_MODULES`(数组,元素形如 `apps.finance`)

- [ ] **Step 1: 写失败的测试**

创建 `scripts/tests/test_precheck_tests.sh`:

```bash
#!/usr/bin/env bash
# scripts/precheck-tests.sh 改动映射逻辑的回归测试。
# 纯 bash,通过 ERP_TEST_GROUPS 注入分组定义,不需要 Docker,秒级完成。
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/scripts/precheck-tests.sh"

# 固定的分组定义,与 CI 当前的 4 组同构。刻意写死在测试里:
# 被测的是映射逻辑,不是 CI 配置本身,注入固定值才能得到稳定断言。
export ERP_TEST_GROUPS='1|platform|apps.core,apps.core.workflow,apps.accounts,apps.ai|apps.core.tests,apps.core.workflow,apps.accounts.tests,apps.ai.tests
2|projects|apps.masterdata,apps.projects,apps.sales|apps.masterdata.tests,apps.projects.tests,apps.sales.tests
3|supply|apps.purchase,apps.inventory,apps.production|apps.purchase.tests,apps.inventory.tests,apps.production.tests
4|finance|apps.finance,apps.reports,apps.analytics,apps.oa|apps.finance.tests,apps.reports.tests,apps.analytics.tests,apps.oa'

PASS=0; FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# expect_plan <用例名> <期望的两行输出> <改动文件...>
expect_plan(){
  local name="$1" expected="$2"; shift 2
  local f="$TMP/changed.txt"
  printf '%s\n' "$@" > "$f"
  local actual
  actual="$(bash "$SCRIPT" --plan-only --from-files "$f" 2>&1)"
  if [[ "$actual" == "$expected" ]]; then
    printf '  ok   %s\n' "$name"; PASS=$((PASS+1))
  else
    printf '  FAIL %s\n       期望: %s\n       实际: %s\n' \
      "$name" "$(printf '%s' "$expected" | tr '\n' '/')" "$(printf '%s' "$actual" | tr '\n' '/')"
    FAIL=$((FAIL+1))
  fi
}

echo "改动映射测试:"

expect_plan '单个业务 app 只触发所属分组' \
  'groups: 4
integration: yes' \
  'backend/apps/finance/models.py'

expect_plan '两个 app 触发两个分组,序号升序' \
  'groups: 2 3
integration: yes' \
  'backend/apps/sales/views.py' 'backend/apps/inventory/models.py'

expect_plan 'apps/core 放大为全量' \
  'groups: 1 2 3 4
integration: yes' \
  'backend/apps/core/models.py'

expect_plan 'config 放大为全量' \
  'groups: 1 2 3 4
integration: yes' \
  'backend/config/settings.py'

expect_plan 'requirements 放大为全量' \
  'groups: 1 2 3 4
integration: yes' \
  'backend/requirements.txt'

expect_plan '仅 integration 测试目录' \
  'groups: none
integration: yes' \
  'backend/tests/integration/test_purchase_chain.py'

expect_plan '前端路由触发 apps.core 所在分组' \
  'groups: 1
integration: no' \
  'frontend/src/router/index.ts'

expect_plan '无关改动零命中' \
  'groups: none
integration: no' \
  'docs/README.md' 'nginx/nginx.conf' 'miniprogram/pages/index.js'

expect_plan 'backend 下的非代码目录不触发' \
  'groups: none
integration: no' \
  'backend/logs/app.log' 'backend/uploads/x.xlsx'

expect_plan '前端非路由文件不触发' \
  'groups: none
integration: no' \
  'frontend/src/views/finance/APList.vue'

expect_plan '混合改动合并去重' \
  'groups: 1 4
integration: yes' \
  'backend/apps/finance/models.py' 'frontend/src/router/index.ts' 'docs/x.md'

echo
if [[ $FAIL -eq 0 ]]; then
  printf '\033[0;32m全部通过 (%d)\033[0m\n' "$PASS"; exit 0
else
  printf '\033[0;31m失败 %d / 共 %d\033[0m\n' "$FAIL" "$((PASS+FAIL))"; exit 1
fi
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `bash scripts/tests/test_precheck_tests.sh`
Expected: 11 条全部 FAIL,实际输出为 `尚未实现: plan`

- [ ] **Step 3: 实现映射逻辑**

在 `scripts/precheck-tests.sh` 中,把末尾的 `c_err "尚未实现: $MODE"` 两行替换为以下内容:

```bash
# ── 改动分类(纯 bash,零外部依赖)──
# 采用白名单语义: 只有明确列出的路径才触发测试,未列出的一律放行。
# 这样新增目录默认不会拖慢 push,代价由 CI 全量兜底。
classify_changes(){
  WANT_FULL=0
  WANT_INTEGRATION=0
  WANT_MODULES=()
  local f app
  while IFS= read -r f; do
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
    [[ $want -eq 1 ]] && SELECTED_GROUPS+=("$idx")
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

if [[ "$MODE" == 'plan' || "$MODE" == 'auto' || "$MODE" == 'all' ]]; then
  if [[ "$MODE" == 'all' ]]; then
    WANT_FULL=1; WANT_INTEGRATION=1; WANT_MODULES=()
  else
    classify_changes < <(collect_changed_files)
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

  if [[ "$MODE" == 'plan' ]]; then
    print_plan
    exit 0
  fi
fi

c_err "尚未实现: $MODE"
exit 1
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `bash scripts/tests/test_precheck_tests.sh`
Expected: `全部通过 (11)`,退出码 0

- [ ] **Step 5: 确认零命中路径不启动 Docker**

Run:
```bash
printf 'docs/x.md\n' > /tmp/c.txt
time bash scripts/precheck-tests.sh --plan-only --from-files /tmp/c.txt
```
Expected: 输出 `groups: none` / `integration: no`,`real` 时间小于 0.2 秒(证明没起容器)

- [ ] **Step 6: 提交**

```bash
chmod +x scripts/tests/test_precheck_tests.sh
git add scripts/precheck-tests.sh scripts/tests/test_precheck_tests.sh
git commit -m "feat(precheck): 改动到 CI 分组的映射与回归测试"
```

---

### Task 3: 测试栈生命周期

拉起与生产完全隔离的 postgres+redis,并管理它们的增删。

**Files:**
- Modify: `scripts/precheck-tests.sh`

**Interfaces:**
- Produces:
  - `ensure_stack()` —— 幂等:缺网络/卷/容器就建,容器停了就 start,已在跑直接返回。返回后 postgres 已可接受连接
  - `test_db_exists()` —— 测试库存在返回 0,否则返回 1
  - `--up` / `--down` / `--clean` / `--fresh-db` 四个开关生效

- [ ] **Step 1: 写验证命令,确认当前失败**

Run: `bash scripts/precheck-tests.sh --up`
Expected: FAIL —— `尚未实现: up`

- [ ] **Step 2: 实现栈管理**

在 `scripts/precheck-tests.sh` 里,**在 `if [[ "$MODE" == 'plan' ...` 那段之前**插入:

```bash
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
  # 数据卷独立于容器: 那 7 分钟建好的测试库因此能在容器被删后存活
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

case "$MODE" in
  down)  stack_down; exit 0 ;;
  clean) stack_clean; exit 0 ;;
esac
```

再在参数解析之后、`plan/auto/all` 分支**之前**加入 `--up` 的处理:

```bash
if [[ "$MODE" == 'up' ]]; then
  ensure_stack
  [[ $FRESH_DB -eq 1 ]] && drop_test_db
  if test_db_exists; then
    c_ok "测试栈就绪,测试库 $TEST_DB_NAME 已存在"
  else
    c_info "测试库尚未创建,首次运行测试时会自动创建(约需 7 分钟,执行全量迁移)"
  fi
  exit 0
fi
```

- [ ] **Step 3: 验证拉起与幂等**

Run: `bash scripts/precheck-tests.sh --up && bash scripts/precheck-tests.sh --up`
Expected: 第一次打印创建两个容器;第二次秒回,不重复创建。两次都以 `[✓]` 或 `[i]` 结尾且退出码 0。

- [ ] **Step 4: 验证与生产栈无交集**

Run:
```bash
docker ps --format '{{.Names}}' | grep -E 'erp-testenv|erp-postgres|erp-redis'
docker port erp-testenv-pg 2>&1 || echo "(无端口映射,符合预期)"
```
Expected: `erp-testenv-pg`/`erp-testenv-redis` 与 `erp-postgres`/`erp-redis` 同时存在且互不影响;`docker port` 无输出。

- [ ] **Step 5: 验证 down 保留卷、clean 删卷**

Run:
```bash
bash scripts/precheck-tests.sh --down
docker volume inspect erp-testenv-pgdata >/dev/null && echo "卷仍在(正确)"
bash scripts/precheck-tests.sh --up
```
Expected: `--down` 后卷仍在;`--up` 能重新拉起。

- [ ] **Step 6: 提交**

```bash
git add scripts/precheck-tests.sh
git commit -m "feat(precheck): 隔离测试栈的生命周期管理"
```

---

### Task 4: 执行 Django 分组测试

打通默认模式:选出分组后真正跑起来。

**Files:**
- Modify: `scripts/precheck-tests.sh`

**Interfaces:**
- Consumes: Task 2 的 `SELECTED_GROUPS`、Task 3 的 `ensure_stack()`
- Produces: `run_django_group <序号>` —— 跑一个分组,通过返回 0,失败返回 1;日志落到 `$LOG_DIR/group-<序号>.log`

- [ ] **Step 1: 写验证命令,确认当前失败**

Run:
```bash
printf 'backend/apps/finance/models.py\n' > /tmp/c.txt
bash scripts/precheck-tests.sh --from-files /tmp/c.txt
```
Expected: FAIL —— `尚未实现: auto`

- [ ] **Step 2: 实现执行**

把脚本末尾的 `c_err "尚未实现: $MODE"` / `exit 1` 两行替换为:

```bash
LOG_DIR="$(mktemp -d -t erp-precheck-XXXXXX)"

# 与 CI 的差异只有 --keepdb 一处(CI 每次新建库)。
# 代价: 改写/删除既有迁移文件后本地库会陈旧,用 --fresh-db 重建。新增迁移无妨,keepdb 仍会 apply。
docker_test_run(){
  docker run --rm --network "$NET" \
    -v "$REPO_ROOT:/repo:ro" -w /repo/backend \
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
    if docker_test_run --entrypoint python "$BASE_IMAGE" \
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

BASE_IMAGE="$(resolve_base_image)"
ensure_stack
[[ $FRESH_DB -eq 1 ]] && drop_test_db
if ! test_db_exists; then
  c_info "首次运行:正在创建测试库并执行全量迁移,约需 7 分钟。之后会复用,不再重复。"
fi

failed=0
for idx in "${SELECTED_GROUPS[@]+"${SELECTED_GROUPS[@]}"}"; do
  run_django_group "$idx" || failed=1
done

if [[ $failed -eq 1 ]]; then
  c_err "测试预检未通过。修复后重试,确需跳过用 git push --no-verify。"
  exit 1
fi
c_ok "测试预检通过"
exit 0
```

- [ ] **Step 3: 验证单分组执行**

Run:
```bash
printf 'backend/apps/finance/models.py\n' > /tmp/c.txt
time bash scripts/precheck-tests.sh --from-files /tmp/c.txt
```
Expected: 打印「分组4: finance, reporting and office」并通过,`Ran 186 tests`。若测试库已存在约 10 秒;若是首次,约 7 分钟。此时 integration 尚未实现,不应报错(下一个任务补)。

- [ ] **Step 4: 验证失败能被拦住**

Run:
```bash
cat >> backend/apps/analytics/tests/test_precheck_canary.py <<'EOF'
from django.test import SimpleTestCase


class PrecheckCanaryTest(SimpleTestCase):
    def test_deliberate_failure(self):
        self.assertEqual(1, 2)
EOF
printf 'backend/apps/finance/models.py\n' > /tmp/c.txt
bash scripts/precheck-tests.sh --from-files /tmp/c.txt; echo "exit=$?"
rm backend/apps/analytics/tests/test_precheck_canary.py
```
Expected: `exit=1`,并打印 `FAIL: test_deliberate_failure` 与日志路径。删除文件后恢复。

- [ ] **Step 5: 提交**

```bash
git add scripts/precheck-tests.sh
git commit -m "feat(precheck): 执行 Django 分组测试"
```

---

### Task 5: 薄测试镜像与 integration

生产镜像不装 dev 依赖(没有 pytest),用一层薄镜像补上,并接入 integration 执行。

**Files:**
- Create: `docker/test-runner.Dockerfile`
- Modify: `scripts/precheck-tests.sh`

**Interfaces:**
- Consumes: Task 4 的 `docker_test_run()`、`BASE_IMAGE`
- Produces:
  - `resolve_runner_image()` → stdout 输出薄镜像 tag `erp-test-runner:<pytest版本>-<基础镜像版本>`,镜像不存在时自动构建
  - `run_integration()` → 通过返回 0,失败返回 1

- [ ] **Step 1: 写验证命令,确认当前失败**

Run: `docker image inspect erp-test-runner 2>&1 | tail -1`
Expected: FAIL —— `No such image`

- [ ] **Step 2: 创建薄镜像 Dockerfile**

创建 `docker/test-runner.Dockerfile`:

```dockerfile
# 本地测试预检专用镜像(scripts/precheck-tests.sh 自动构建,不参与部署)。
#
# 生产镜像只装 requirements.txt,不含 dev 依赖,因此没有 pytest,跑不了
# CI 的 "Backend / integration" 那个 job。这里在其之上补最小依赖。
#
# 版本由脚本从 backend/requirements-dev.txt 解析后经 build-arg 传入,
# 不在此写死 —— 依赖一变,镜像 tag 随之变化并自动重建。
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTEST_SPEC
RUN pip install --no-cache-dir ${PYTEST_SPEC}
```

- [ ] **Step 3: 实现镜像解析与 integration 执行**

在 `scripts/precheck-tests.sh` 中,于 `BASE_IMAGE="$(resolve_base_image)"` 那一行**之前**插入:

```bash
# 薄镜像 tag 里同时编码了 pytest 版本与基础镜像版本 ——
# 任何一方变化都会 miss 并触发重建,不需要人记得刷新。
# 相比每次容器内 pip install(约 6 秒),薄镜像还能离线运行。
resolve_runner_image(){
  local pytest_ver django_ver base base_tag tag
  pytest_ver="$(sed -n 's/^pytest==\([0-9][^[:space:]]*\).*/\1/p' \
    "$REPO_ROOT/backend/requirements-dev.txt" | head -1)"
  django_ver="$(sed -n 's/^pytest-django==\([0-9][^[:space:]]*\).*/\1/p' \
    "$REPO_ROOT/backend/requirements-dev.txt" | head -1)"
  if [[ -z "$pytest_ver" || -z "$django_ver" ]]; then
    c_err "无法从 backend/requirements-dev.txt 解析 pytest / pytest-django 版本"
    exit 1
  fi
  base="$1"
  base_tag="${base##*:}"
  tag="erp-test-runner:${pytest_ver}-${base_tag}"
  if ! docker image inspect "$tag" >/dev/null 2>&1; then
    c_info "构建测试镜像 $tag(生产镜像 + pytest,仅首次)"
    docker build -q \
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
```

然后在 `BASE_IMAGE="$(resolve_base_image)"` 之后补一行,并在分组循环之后加入 integration:

```bash
BASE_IMAGE="$(resolve_base_image)"
RUNNER_IMAGE="$(resolve_runner_image "$BASE_IMAGE")"
```

```bash
for idx in "${SELECTED_GROUPS[@]+"${SELECTED_GROUPS[@]}"}"; do
  run_django_group "$idx" || failed=1
done

if [[ $WANT_INTEGRATION -eq 1 ]]; then
  run_integration || failed=1
fi
```

同时把 `run_django_group` 里的 `"$BASE_IMAGE"` 改为 `"$RUNNER_IMAGE"` —— 薄镜像完全兼容生产镜像,统一用它可以少维护一条路径。

- [ ] **Step 4: 验证镜像构建与 integration 执行**

Run:
```bash
printf 'backend/tests/integration/test_purchase_chain.py\n' > /tmp/c.txt
time bash scripts/precheck-tests.sh --from-files /tmp/c.txt
```
Expected: 首次打印「构建测试镜像 erp-test-runner:9.0.3-0.3.0」,随后 `integration 通过  36 passed`。整体约 30 秒(含构建),再次运行约 25 秒。

- [ ] **Step 5: 验证 tag 随依赖变化**

Run:
```bash
docker images erp-test-runner --format '{{.Repository}}:{{.Tag}}'
```
Expected: 输出 `erp-test-runner:9.0.3-0.3.0`(版本与 `requirements-dev.txt` 及运行中的 `erp-app` 镜像一致)

- [ ] **Step 6: 提交**

```bash
git add docker/test-runner.Dockerfile scripts/precheck-tests.sh
git commit -m "feat(precheck): 薄测试镜像与 integration 执行"
```

---

### Task 6: pre-push hook 与文档

把预检接到 `git push` 上,并写清使用方式。

**Files:**
- Create: `.githooks/pre-push`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `scripts/precheck-tests.sh --from-files <F>`
- Produces: 一个可执行的 `.githooks/pre-push`;`core.hooksPath` 已指向 `.githooks`,无需额外配置

- [ ] **Step 1: 写验证命令,确认当前失败**

Run: `ls -l .githooks/pre-push`
Expected: FAIL —— `No such file or directory`

- [ ] **Step 2: 创建 hook**

创建 `.githooks/pre-push`:

```bash
#!/usr/bin/env bash
# ATM-ERP 推送前门禁(随仓库版本化,通过 git config core.hooksPath .githooks 启用)
#
# 跑与本次改动相关的 CI 后端测试分组。存在的理由和 pre-commit 一样:
# 最近 40 次 CI run 里有 4 次挂在真实测试失败(分组①②④ 与 integration 都挂过),
# 而本地没有任何等价的执行路径,只能推上去才发现。
#
# 分组按改动自动挑选: 改单个业务 app 约 30 秒,改 apps/core 或 config 则全量约 6 分半。
# 与后端无关的改动(docs/、nginx/ 等)秒级放行,完全不启动 Docker。
#
# 绕过: git push --no-verify
# 预热(首次建库约 7 分钟,建议先手动跑一次): bash scripts/precheck-tests.sh --up
set -euo pipefail

c_info(){ printf '\033[0;36m[i]\033[0m %s\n' "$1"; }
c_err(){  printf '\033[0;31m[\xe2\x9c\x97]\033[0m %s\n' "$1" >&2; }

REPO_ROOT="$(git rev-parse --show-toplevel)"
ZERO='^0*$'

changed="$(mktemp)"
trap 'rm -f "$changed"' EXIT

# git 通过 stdin 传入每个待推送 ref: <local_ref> <local_sha> <remote_ref> <remote_sha>
while read -r _local_ref local_sha _remote_ref remote_sha; do
  # local_sha 全 0 = 删除远程分支,没有代码变更可查
  [[ "$local_sha" =~ $ZERO ]] && continue

  if [[ "$remote_sha" =~ $ZERO ]]; then
    # remote_sha 全 0 = 该分支在远端尚不存在,以 main 为基线
    base="$(git rev-parse --verify --quiet origin/main || git rev-parse --verify --quiet main || true)"
  else
    base="$remote_sha"
  fi

  if [[ -z "$base" ]]; then
    # 没有可用基线(例如全新仓库),放行交给 CI
    continue
  fi
  git diff --name-only "$base" "$local_sha" >> "$changed" 2>/dev/null || true
done

if [[ ! -s "$changed" ]]; then
  exit 0
fi

sort -u "$changed" -o "$changed"

if ! bash "$REPO_ROOT/scripts/precheck-tests.sh" --from-files "$changed"; then
  c_err '推送已中止。确需跳过预检用: git push --no-verify'
  exit 1
fi
```

- [ ] **Step 3: 验证无关改动秒级放行**

Run:
```bash
chmod +x .githooks/pre-push
printf '%s %s %s %s\n' refs/heads/x "$(git rev-parse HEAD)" refs/heads/x "$(git rev-parse HEAD~1)" \
  | time bash .githooks/pre-push
echo "exit=$?"
```
Expected: 退出码 0。若 `HEAD~1..HEAD` 只改了 docs,应在 1 秒内返回且不启动容器。

- [ ] **Step 4: 验证新分支场景(remote_sha 全 0)**

Run:
```bash
printf '%s %s %s %s\n' refs/heads/x "$(git rev-parse HEAD)" refs/heads/x 0000000000000000000000000000000000000000 \
  | bash .githooks/pre-push; echo "exit=$?"
```
Expected: 以 `origin/main` 为基线计算改动;因本分支目前只改了 `scripts/`、`docker/`、`docs/`、`.githooks/`,应零命中并秒级放行,退出码 0。

- [ ] **Step 5: 更新 CLAUDE.md**

在 `CLAUDE.md` 的「### 本地 CI 预检（推荐，无需装 Python 包）」一节**之后**插入:

````markdown
### 本地测试预检（pre-push，按改动自动选分组）

lint 只覆盖 CI 失败的一半。另一半是真实的测试失败（分组①②④ 与 integration 都挂过），
由 `scripts/precheck-tests.sh` 在 `git push` 前拦下：

```bash
bash scripts/precheck-tests.sh              # 按 origin/main..HEAD 的改动自动选分组
bash scripts/precheck-tests.sh --all        # 全部 4 组 + integration（约 6 分半）
bash scripts/precheck-tests.sh --plan-only  # 只看会跑哪些，不执行
bash scripts/precheck-tests.sh --up         # 预热：拉起测试栈（首次建库约 7 分钟）
bash scripts/precheck-tests.sh --fresh-db   # 改写/删除既有迁移文件后重建测试库
bash scripts/precheck-tests.sh --down       # 删容器留数据卷
bash scripts/precheck-tests.sh --clean      # 连数据卷一起删
```

改动映射：改单个业务 app → 该 app 所属分组 + integration（约 30 秒）；改
`backend/apps/core/`、`backend/config/`、`requirements*.txt` → **全部 4 组**（它们是全站
基类与配置）；改 `frontend/src/router/index.ts` → 分组①（菜单同步测试直接读这个文件）；
其余改动零开销放行，不启动 Docker。

**测试栈与生产库完全隔离**：独立的 `erp-testenv-pg` / `erp-testenv-redis` 容器与
`erp-testenv-pgdata` 数据卷，不映射宿主机端口，与 `erp-postgres` / `erp-redis` 无交集。
镜像用 `postgres:15` / `redis:7`（非 alpine），与 CI 逐字一致。

与 CI 的唯一差异是本地用 `--keepdb` 复用测试库。**改写或删除既有迁移文件后需跑一次
`--fresh-db`**（新增迁移无妨，`--keepdb` 会正常 apply）。

映射规则本身有回归测试：`bash scripts/tests/test_precheck_tests.sh`（纯 bash，秒级，不需要 Docker）。

启用同样靠 `git config core.hooksPath .githooks`（与 pre-commit 是同一个开关，配一次即可）。
绕过用 `git push --no-verify`。
````

- [ ] **Step 6: 提交**

```bash
git add .githooks/pre-push CLAUDE.md
git commit -m "feat(precheck): pre-push 门禁与使用文档"
```

---

### Task 7: 端到端验收与清理

逐条验证设计文档第 8 节的 6 项,并清理排查阶段遗留的临时资源。

**Files:**
- 无新增。仅验证与清理。

**Interfaces:**
- Consumes: 前 6 个任务的全部产出

- [ ] **Step 1: 验证「能拦住真实失败」**

Run:
```bash
cat > backend/apps/finance/tests/test_precheck_canary.py <<'EOF'
from django.test import SimpleTestCase


class PrecheckCanaryTest(SimpleTestCase):
    def test_deliberate_failure(self):
        self.assertEqual(1, 2)
EOF
printf 'backend/apps/finance/tests/test_precheck_canary.py\n' > /tmp/c.txt
bash scripts/precheck-tests.sh --from-files /tmp/c.txt; echo "exit=$?"
rm backend/apps/finance/tests/test_precheck_canary.py
```
Expected: `exit=1`,输出含 `FAIL: test_deliberate_failure` 与日志路径

- [ ] **Step 2: 验证「映射精确」**

Run:
```bash
printf 'backend/apps/finance/models.py\n' > /tmp/c.txt
bash scripts/precheck-tests.sh --plan-only --from-files /tmp/c.txt
```
Expected: 恰好 `groups: 4` / `integration: yes`

- [ ] **Step 3: 验证「core 放大生效」**

Run:
```bash
printf 'backend/apps/core/models.py\n' > /tmp/c.txt
bash scripts/precheck-tests.sh --plan-only --from-files /tmp/c.txt
```
Expected: 恰好 `groups: 1 2 3 4` / `integration: yes`

- [ ] **Step 4: 验证「无关改动零开销」**

Run:
```bash
printf 'docs/README.md\n' > /tmp/c.txt
time bash scripts/precheck-tests.sh --from-files /tmp/c.txt
```
Expected: 打印「本次改动不涉及后端代码,跳过测试预检」,`real` < 0.2 秒

- [ ] **Step 5: 验证「逃生门可用」**

Run: `git push --no-verify --dry-run origin chore/local-test-precheck`
Expected: 不触发预检,直接完成 dry-run

- [ ] **Step 6: 验证「生产库未被触碰」**

Run:
```bash
docker exec erp-postgres psql -U erp_user -d postgres -tAc \
  "SELECT datname FROM pg_database WHERE datname LIKE 'test%'"
```
Expected: 输出中**不包含**本次预检产生的新库。已有的历史测试库属于遗留问题,见 Step 8。

- [ ] **Step 7: 清理排查阶段的临时资源**

排查期间手工建过一套 `erp-precheck-*` 资源(命名与最终方案不同),已无用:

```bash
docker rm -f erp-precheck-pg erp-precheck-redis 2>/dev/null || true
docker network rm erp-precheck-net 2>/dev/null || true
docker ps -a --format '{{.Names}}' | grep erp-precheck || echo "(已清理干净)"
```

- [ ] **Step 8: 汇报遗留事项**

生产 PG 实例中残留 6 个历史测试库(约 320MB),来自本设计之前的手工试跑。**不要自行删除**——它们与生产数据同库共存,属于设计文档第 9 节记录的待用户拍板事项。向用户汇报数据库名与占用空间,由用户决定。

Run:
```bash
docker exec erp-postgres psql -U erp_user -d postgres -c \
  "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname LIKE 'test%' ORDER BY datname"
```

- [ ] **Step 9: 跑一次完整的 lint 预检并提交**

Run: `bash scripts/precheck.sh`
Expected: 通过(本次改动没有 Python 文件,应当无影响,但确认一次)

```bash
git add -A
git commit -m "chore(precheck): 端到端验收" --allow-empty
```

---

## 自审记录

**Spec 覆盖检查** —— 逐条对照设计文档:

| 设计章节 | 对应任务 |
|---|---|
| 4.1 组件 | Task 1(主脚本)、Task 5(Dockerfile)、Task 6(hook + 文档)、Task 2(测试) |
| 4.2 分组动态读取 | Task 1 Step 2 的 `load_groups()` |
| 4.3 改动映射(含白名单语义) | Task 2 全部 |
| 4.4 测试栈生命周期(4 个开关) | Task 3 全部 |
| 4.5 执行参数(4 个必须条件) | Task 4 Step 2 的 `docker_test_run()`;Global Constraints 重申 |
| 4.6 薄镜像 | Task 5 |
| 5 触发与流程 | Task 6 |
| 6 失败与边界 | Task 3(60 秒超时)、Task 4(首次建库提示、失败摘要)、Task 6(Docker 缺失拦截) |
| 7 已知差异(`--fresh-db`) | Task 3 的 `drop_test_db()`、Task 6 的文档 |
| 8 验证策略 6 条 | Task 7 Step 1-6 |
| 9 遗留事项 | Task 7 Step 8 |

**类型一致性检查** —— 跨任务引用的符号:`GROUPS_RAW`(Task 1 定义 → Task 2、4 使用)、`WANT_FULL`/`WANT_INTEGRATION`/`WANT_MODULES`(Task 2 定义 → Task 5 使用 `WANT_INTEGRATION`)、`SELECTED_GROUPS`(Task 2 定义 → Task 4 使用)、`ensure_stack`/`test_db_exists`/`drop_test_db`(Task 3 定义 → Task 4 使用)、`docker_test_run`/`BASE_IMAGE`/`LOG_DIR`(Task 4 定义 → Task 5 使用)、`RUNNER_IMAGE`(Task 5 定义 → Task 4 的 `run_django_group` 在 Task 5 Step 3 改为使用它)。命名前后一致。

**已知的实现顺序约束**:Task 5 会回头修改 Task 4 写下的 `run_django_group`(把 `$BASE_IMAGE` 换成 `$RUNNER_IMAGE`)。这是刻意的——Task 4 单独完成时必须能跑通,不能依赖尚不存在的薄镜像。
