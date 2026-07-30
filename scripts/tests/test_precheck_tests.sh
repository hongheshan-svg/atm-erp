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

# expect_plan_no_trailing_newline <用例名> <期望的两行输出> <单个改动文件>
# 与 expect_plan 的唯一差异: 用 printf '%s' (不追加换行) 写测试输入文件,
# 用来钉住 --from-files 读到不带末尾换行符的最后一行时不能漏判这个边界。
# 不复用/不改动 expect_plan 本身,避免影响已有 11 条用例的输入构造方式。
expect_plan_no_trailing_newline(){
  local name="$1" expected="$2" file_content="$3"
  local f="$TMP/changed_no_nl.txt"
  printf '%s' "$file_content" > "$f"
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

expect_plan_no_trailing_newline '文件末行无换行符时仍被分类(不被静默漏判)' \
  'groups: 4
integration: yes' \
  'backend/apps/finance/models.py'

echo
if [[ $FAIL -eq 0 ]]; then
  printf '\033[0;32m全部通过 (%d)\033[0m\n' "$PASS"; exit 0
else
  printf '\033[0;31m失败 %d / 共 %d\033[0m\n' "$FAIL" "$((PASS+FAIL))"; exit 1
fi
