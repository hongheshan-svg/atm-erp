#!/usr/bin/env bash
# scripts/setup-hooks.sh 的回归测试。
# 全部跑在 mktemp 出来的一次性 git 仓库里,绝不读写开发者本机的真实 git 配置
# ——被测对象本身就是写 core.hooksPath 的脚本,在真仓库里跑等于让测试改你的门禁。
# 纯 bash,不需要 Docker,秒级完成。
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/scripts/setup-hooks.sh"

PASS=0; FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# check <用例名> <期望描述> <实际> <期望>
check(){
  local name="$1" actual="$2" expected="$3"
  if [[ "$actual" == "$expected" ]]; then
    printf '  ok   %s\n' "$name"; PASS=$((PASS+1))
  else
    printf '  FAIL %s\n       期望: %s\n       实际: %s\n' "$name" "$expected" "$actual"
    FAIL=$((FAIL+1))
  fi
}

# fresh_repo: 建一个带 .githooks/ 的空仓库并 cd 进去,回显路径
fresh_repo(){
  local d
  d="$(mktemp -d "$TMP/repo-XXXXXX")"
  git -C "$d" init -q
  mkdir -p "$d/.githooks"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$d/.githooks/pre-commit"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$d/.githooks/pre-push"
  chmod +x "$d/.githooks/pre-commit" "$d/.githooks/pre-push"
  printf '%s\n' "$d"
}

# run <仓库> <参数...> —— 在目标仓库里执行被测脚本,结果写全局 RC / OUT。
# 不走 "rc|输出" 单字符串 + cut 的写法: 输出是多行的,cut 会对每一行都切一次,
# 把没有分隔符的后续行原样带进"实际值",断言看起来诡异(期望 2、实际 2 却判失败)。
RC=0; OUT=''
run(){
  local d="$1"; shift
  OUT="$(cd "$d" && bash "$SCRIPT" "$@" 2>&1)" && RC=0 || RC=$?
}

hooks_path(){ git -C "$1" config core.hooksPath 2>/dev/null || printf '<unset>'; }

echo "setup-hooks 测试:"

# --- 参数与环境 ---
R="$(fresh_repo)"
run "$R" --nope;  check '未知参数退出码 2' "$RC" '2'
run "$R" --help;  check '--help 退出码 0'  "$RC" '0'

check '不在 git 仓库内退出码 1' \
  "$(cd "$TMP" && bash "$SCRIPT" >/dev/null 2>&1; echo $?)" '1'

# --- 主路径 ---
R="$(fresh_repo)"
run "$R" --check
check '未设置时 --check 退出码 1' "$RC" '1'
check '  且不写入配置'           "$(hooks_path "$R")" '<unset>'

run "$R"; check '首次执行退出码 0' "$RC" '0'
check '  已写入 .githooks' "$(hooks_path "$R")" '.githooks'
run "$R"; check '幂等重跑退出码 0'   "$RC" '0'
check '  配置保持不变'     "$(hooks_path "$R")" '.githooks'
run "$R" --check; check '已开启后 --check 退出码 0' "$RC" '0'

# 启用后不得把 .githooks/ 自己报成失效:rev-parse --git-path hooks 会跟随
# core.hooksPath,一旦用它定位旧钩子目录就会产生这条稳定假警报。
check '  不把刚启用的 .githooks 报成失效' \
  "$(printf '%s' "$OUT" | grep -c '不会再被调用')" '0'

# --- 拒绝静默覆盖别人的定制 ---
R="$(fresh_repo)"
git -C "$R" config core.hooksPath .mycustomhooks
run "$R"; check '指向别处时退出码 1' "$RC" '1'
check '  且不覆盖原值'     "$(hooks_path "$R")" '.mycustomhooks'

# --- 仓库检出不完整 ---
R="$(fresh_repo)"; rm -rf "$R/.githooks"
run "$R"; check '缺 .githooks 目录时退出码 1' "$RC" '1'
check '  且不写入配置'               "$(hooks_path "$R")" '<unset>'

# --- 可执行位兜底(core.fileMode=false 等情况下钩子会被 git 静默跳过) ---
R="$(fresh_repo)"; chmod -x "$R/.githooks/pre-push"
run "$R"
check '丢失可执行位时自动补上' \
  "$([[ -x "$R/.githooks/pre-push" ]] && echo yes || echo no)" 'yes'

# --- .git/hooks 冲突提示 ---
R="$(fresh_repo)"
printf '#!/bin/sh\nexit 0\n' > "$R/.git/hooks/pre-commit"
run "$R"
check '.git/hooks 下有钩子时提示失效' \
  "$(printf '%s' "$OUT" | grep -c '不会再被调用')" '1'
check '  并点名到具体文件' \
  "$(printf '%s' "$OUT" | grep '不会再被调用' | grep -c 'pre-commit')" '1'

R="$(fresh_repo)"
run "$R"
check '.git/hooks 只有 sample 时不误报' \
  "$(printf '%s' "$OUT" | grep -c '不会再被调用')" '0'

echo
if [[ $FAIL -eq 0 ]]; then
  printf '\033[0;32m全部通过 (%d)\033[0m\n' "$PASS"; exit 0
else
  printf '\033[0;31m失败 %d / 共 %d\033[0m\n' "$FAIL" "$((PASS+FAIL))"; exit 1
fi
