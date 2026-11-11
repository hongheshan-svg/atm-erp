#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"
if [[ -f "$ROOT/.env.lean" && ! -f "$ENV_FILE" ]]; then ENV_FILE="$ROOT/.env.lean"; fi
BUILD=true
OTA=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="${2:?缺少配置文件路径}"; shift 2 ;;
    --skip-build) BUILD=false; shift ;;
    --no-ota) OTA=false; shift ;;
    --with-ota) OTA=true; shift ;;
    --help) echo '用法：install.sh [--env-file 配置文件路径] [--skip-build 跳过构建] [--with-ota 注册可选网页升级服务] [--no-ota 不注册升级服务]'; exit 0 ;;
    *) echo "无法识别的参数：$1" >&2; exit 2 ;;
  esac
done
PYTHON_BIN="${PYTHON:-python3.11}"
RELEASE=false
if [[ -f "$ROOT/INSTALL-MANIFEST.json" ]]; then RELEASE=true; fi
# 发布包的镜像校验导入和可选升级服务都需要宿主机 Python 3.11；在生成配置或改动容器前确认。
if [[ "$OTA" == true || "$RELEASE" == true ]]; then
  "$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] == (3, 11), "需要宿主机 Python 3.11"'
fi
command -v docker >/dev/null
docker compose version >/dev/null
docker info >/dev/null
if [[ ! -f "$ENV_FILE" ]]; then
  command -v openssl >/dev/null
  # 发布包留空 LEAN_IMAGE，沿用 Compose 内置的固定摘要，校验导入后由 release_install.py 写入；
  # 写入本地构建镜像名会遮蔽该摘要，安装中断后直接 Compose 启动就会找不到镜像。
  IMAGE=""
  if [[ "$RELEASE" == false ]]; then IMAGE="${LEAN_IMAGE:-atm-erp-lean:local}"; fi
  umask 077
  (set -o noclobber
    cat > "$ENV_FILE" <<EOF
LEAN_PROJECT_NAME=${LEAN_PROJECT_NAME:-atm-erp-lean}
LEAN_IMAGE=$IMAGE
LEAN_HTTP_PORT=${LEAN_HTTP_PORT:-8080}
LEAN_BIND_ADDRESS=${LEAN_BIND_ADDRESS:-127.0.0.1}
LEAN_ALLOWED_HOSTS=${LEAN_ALLOWED_HOSTS:-localhost,127.0.0.1}
LEAN_ENVIRONMENT=${LEAN_ENVIRONMENT:-production}
LEAN_DB_PASSWORD=$(openssl rand -hex 32)
LEAN_SECRET_KEY=$(openssl rand -hex 32)
LEAN_OTA_AGENT_TOKEN=$(if [[ "$OTA" == true ]]; then openssl rand -hex 32; fi)
LEAN_ADMIN_PASSWORD=Lean-$(openssl rand -hex 24)
EOF
  )
fi
if [[ "$OTA" == true ]] && ! grep -q '^LEAN_OTA_AGENT_TOKEN=.' "$ENV_FILE"; then
  printf '\nLEAN_OTA_AGENT_TOKEN=%s\n' "$(openssl rand -hex 32)" >> "$ENV_FILE"
fi
if [[ "$OTA" == true ]]; then
  "$PYTHON_BIN" -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); lines=p.read_text().splitlines(); p.write_text("\n".join(x for x in lines if not x.startswith("LEAN_OTA_MODE="))+"\nLEAN_OTA_MODE=host\n")' "$ENV_FILE"
fi
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT/docker-compose.yml")
"${COMPOSE[@]}" config --quiet
if [[ "$RELEASE" == true ]]; then
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
echo "忘记管理员密码时重设：docker compose --env-file $ENV_FILE -f $ROOT/docker-compose.yml exec app python /opt/erp/container_runtime.py manage changepassword admin"
