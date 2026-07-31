#!/usr/bin/env bash
# ATM-ERP 一次性开启本地 git 门禁
# 用法: bash scripts/setup-hooks.sh [--check] [--help]
#
# 把 git 的钩子目录指向仓库内的 .githooks/，从而启用：
#   pre-commit  拦直接提交 main、拦未过 ruff 的 backend/ + scripts/ci/ 改动
#   pre-push    按改动自动选 CI 测试分组，在隔离测试栈上先跑一遍
#
# 为什么需要单独一个脚本: core.hooksPath 存在 .git/config 里，**不随仓库同步**。
# 每个 clone 都要自己执行一次，否则 .githooks/ 下的钩子形同虚设——文件在仓库里
# 躺着，git 却从来不调用它们，而且没有任何提示。
set -euo pipefail

c_info(){ printf '\033[0;36m[i]\033[0m %s\n' "$1"; }
c_ok(){   printf '\033[0;32m[\xe2\x9c\x93]\033[0m %s\n' "$1"; }
c_warn(){ printf '\033[0;33m[!]\033[0m %s\n' "$1"; }
c_err(){  printf '\033[0;31m[\xe2\x9c\x97]\033[0m %s\n' "$1" >&2; }

WANT_CHECK=0

usage(){
  cat <<EOF
ATM-ERP 一次性开启本地 git 门禁
用法: bash scripts/setup-hooks.sh [选项]

选项:
  --check   只检查当前是否已开启，不做任何修改
  --help    显示本帮助

退出码:
  0   已开启（--check 下表示检查通过）
  1   未开启且无法自动开启（--check 下表示尚未开启）
  2   参数错误
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) WANT_CHECK=1; shift ;;
    --help)  usage; exit 0 ;;
    *)       c_err "未知参数: $1"; usage >&2; exit 2 ;;
  esac
done

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  c_err '不在 git 仓库内'
  exit 1
fi

DESIRED='.githooks'
# 未设置时 git config 以退出码 1 表示"无此项"，不是错误
CURRENT="$(git -C "$REPO_ROOT" config core.hooksPath 2>/dev/null || true)"

if [[ $WANT_CHECK -eq 1 ]]; then
  if [[ "$CURRENT" == "$DESIRED" ]]; then
    c_ok "已开启: core.hooksPath = $CURRENT"
    exit 0
  fi
  c_warn "尚未开启（core.hooksPath = ${CURRENT:-<未设置>}）。开启: bash scripts/setup-hooks.sh"
  exit 1
fi

if [[ ! -d "$REPO_ROOT/$DESIRED" ]]; then
  c_err "$DESIRED/ 目录不存在，仓库检出不完整？"
  exit 1
fi

# 指向别处时不静默覆盖：那多半是使用者自己的定制，改掉会让其失效且无从察觉
if [[ -n "$CURRENT" && "$CURRENT" != "$DESIRED" ]]; then
  c_err "core.hooksPath 当前指向 '$CURRENT'，不是本仓库的 $DESIRED/。"
  c_err "确认可覆盖后手工执行: git config core.hooksPath $DESIRED"
  exit 1
fi

if [[ "$CURRENT" == "$DESIRED" ]]; then
  c_info "core.hooksPath 已是 $DESIRED，无需改动"
else
  git -C "$REPO_ROOT" config core.hooksPath "$DESIRED"
  c_ok "已设置 core.hooksPath = $DESIRED"
fi

# git 只执行有可执行位的钩子；没有则直接跳过，同样不报错。
# 正常 clone 会带上（仓库里就是 100755），这里兜底 core.fileMode=false 等情况。
for hook in pre-commit pre-push; do
  path="$REPO_ROOT/$DESIRED/$hook"
  [[ -f "$path" ]] || continue
  if [[ ! -x "$path" ]]; then
    chmod +x "$path"
    c_info "已补上可执行位: $DESIRED/$hook"
  fi
done

# core.hooksPath 一旦指向 .githooks，装在 .git/hooks/ 下的钩子(pre-commit 框架用的就是
# 这个位置)全部失效——两条路径互斥。这里只提示并列出文件，不替使用者做取舍：
# 那可能是 pre-commit 框架，也可能是本仓库钩子的手工副本，处理方式不同。
#
# 不能用 `rev-parse --git-path hooks` 定位这个目录：它**尊重 core.hooksPath**，
# 在上面刚设完之后返回的是 .githooks 本身，于是脚本会把自己刚启用的钩子报成"已失效"
# ——一条稳定的假警报(已实测)。--git-common-dir 不受该配置影响，且在 worktree 里
# 指向主仓库的 .git，正是钩子实际所在处；它可能返回相对路径，按 REPO_ROOT 补全。
git_common="$(git -C "$REPO_ROOT" rev-parse --git-common-dir)"
[[ "$git_common" == /* ]] || git_common="$REPO_ROOT/$git_common"
legacy="$git_common/hooks"
if [[ -d "$legacy" ]]; then
  # 用 -exec basename 而非 GNU 专有的 -printf，macOS 上的 BSD find 没有后者
  inert="$(find "$legacy" -maxdepth 1 -type f ! -name '*.sample' \
    -exec basename {} \; 2>/dev/null | tr '\n' ' ' || true)"
  if [[ -n "${inert// /}" ]]; then
    c_warn ".git/hooks/ 下的这些钩子从现在起不会再被调用: ${inert% }"
    c_warn '若来自 pre-commit 框架且想继续用它: git config --unset core.hooksPath'
  fi
fi

c_ok '门禁已生效: pre-commit(ruff + 禁提 main)、pre-push(按改动跑测试分组)'
c_info '临时绕过: git commit --no-verify / git push --no-verify'
