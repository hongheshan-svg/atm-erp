#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env.lean"
BUILD=true
OTA=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="${2:?缺少配置文件路径}"; shift 2 ;;
    --skip-build) BUILD=false; shift ;;
    --no-ota) OTA=false; shift ;;
    --help) echo '用法：install.sh [--env-file 配置文件路径] [--skip-build 跳过构建] [--no-ota 仅隔离 CI：不注册升级服务]'; exit 0 ;;
    *) echo "无法识别的参数：$1" >&2; exit 2 ;;
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
# Advisory only: a mismatch here is the difference between "connects" and "connects then 400s".
"$PYTHON_BIN" "$ROOT/scripts/network_check.py" --config "$ENV_FILE" || true
echo "安装完成。管理员用户名：admin；全新安装的初始密码保存在 $ENV_FILE 的 LEAN_ADMIN_PASSWORD，完成安装向导修改密码后该值即失效。"
echo '使用配置中的端口访问 /erp/，首次登录自动进入快速安装向导：修改初始密码、填写公司、可选添加人员和调整编号，完成后即可使用。重复安装保留现有账户与数据。'
echo "忘记管理员密码时重设：docker compose --env-file $ENV_FILE -f $ROOT/docker-compose.yml exec app python manage.py changepassword admin"
