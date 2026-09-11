#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env.lean"
BUILD=true
OTA=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="${2:?Missing env file path}"; shift 2 ;;
    --skip-build) BUILD=false; shift ;;
    --no-ota) OTA=false; shift ;;
    --help) echo 'Usage: install.sh [--env-file PATH] [--skip-build] [--no-ota (isolated CI only)]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
PYTHON_BIN="${PYTHON:-python3.11}"
if [[ "$OTA" == true ]]; then
  "$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] == (3, 11), "需要宿主机 Python 3.11"'
fi
command -v docker >/dev/null
docker compose version >/dev/null
docker info >/dev/null
if [[ ! -f "$ENV_FILE" ]]; then
  command -v openssl >/dev/null
  umask 077
  (set -o noclobber
    cat > "$ENV_FILE" <<EOF
LEAN_PROJECT_NAME=${LEAN_PROJECT_NAME:-atm-erp-lean}
LEAN_IMAGE=${LEAN_IMAGE:-atm-erp-lean:local}
LEAN_HTTP_PORT=${LEAN_HTTP_PORT:-8080}
LEAN_BIND_ADDRESS=${LEAN_BIND_ADDRESS:-127.0.0.1}
LEAN_ALLOWED_HOSTS=${LEAN_ALLOWED_HOSTS:-localhost,127.0.0.1}
LEAN_ENVIRONMENT=${LEAN_ENVIRONMENT:-production}
LEAN_DB_PASSWORD=$(openssl rand -hex 32)
LEAN_SECRET_KEY=$(openssl rand -hex 32)
LEAN_OTA_AGENT_TOKEN=$(openssl rand -hex 32)
LEAN_ADMIN_PASSWORD=Lean-$(openssl rand -hex 24)
EOF
  )
fi
if ! grep -q '^LEAN_OTA_AGENT_TOKEN=.' "$ENV_FILE"; then
  printf '\nLEAN_OTA_AGENT_TOKEN=%s\n' "$(openssl rand -hex 32)" >> "$ENV_FILE"
fi
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT/docker-compose.yml")
"${COMPOSE[@]}" config --quiet
if [[ -f "$ROOT/INSTALL-MANIFEST.json" ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/release_install.py" --root "$ROOT" --config "$ENV_FILE"
elif [[ "$BUILD" == true ]]; then
  "${COMPOSE[@]}" build app
fi
"${COMPOSE[@]}" up -d --no-build --wait --wait-timeout 180
if [[ "$OTA" == true ]]; then
  "$PYTHON_BIN" "$ROOT/scripts/ota_service.py" install --mode docker --root "$ROOT" --config "$ENV_FILE"
fi
echo "安装完成。管理员用户名：admin；首次密码保存在 $ENV_FILE 的 LEAN_ADMIN_PASSWORD。"
echo '使用配置中的端口访问 /erp/，首次登录自动进入快速安装向导：修改初始密码、填写公司、可选添加人员和调整编号，完成后即可使用。重复安装保留现有账户与数据。'
