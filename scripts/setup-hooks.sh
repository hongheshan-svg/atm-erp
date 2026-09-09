#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
chmod +x "$ROOT/.githooks/pre-commit" "$ROOT/.githooks/pre-push"
git config core.hooksPath .githooks
echo '已启用功能分支保护和推送前检查。'
