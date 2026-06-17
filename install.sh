#!/usr/bin/env bash
# ATM-ERP 一键安装脚本 (Docker, Linux/macOS)
# 用法: bash install.sh [--tag <版本>] [--native] [--help]
#
# 环境变量钩子:
#   ERP_LOCAL_SRC=<目录>  从本地目录复制 docker-compose.yml / .env.example
#                         而非从 GitHub Release 下载（离线部署/测试时使用）
#   ERP_DIR=<目录>        指定工作目录（默认 ~/atm-erp）
set -euo pipefail

REPO="hongheshan-svg/atm-erp"
REL_BASE="https://github.com/${REPO}/releases"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/main"

TAG="latest"
NATIVE=0

c_info(){ printf '\033[0;36m[i]\033[0m %s\n' "$1"; }
c_ok(){   printf '\033[0;32m[\xe2\x9c\x93]\033[0m %s\n' "$1"; }
c_warn(){ printf '\033[1;33m[!]\033[0m %s\n' "$1"; }
c_err(){  printf '\033[0;31m[\xe2\x9c\x97]\033[0m %s\n' "$1" >&2; }

usage(){
  cat <<EOF
ATM-ERP 一键安装 (Docker, Linux/macOS)
用法: bash install.sh [选项]

选项:
  --tag <版本>   指定镜像版本 (默认 latest，如 0.2.0)
  --native       仅 Linux：改用原生(非 Docker)部署，委托 scripts/deploy-native-ubuntu.sh
  -h, --help     显示此帮助

环境变量:
  ERP_LOCAL_SRC=<目录>  从本地目录复制 docker-compose.yml/.env.example（离线部署）
  ERP_DIR=<目录>        指定工作目录（默认 ~/atm-erp）
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="${2:?--tag 需要版本号}"; shift 2;;
    --native) NATIVE=1; shift;;
    -h|--help) usage; exit 0;;
    *) c_err "未知参数: $1"; usage; exit 1;;
  esac
done

OS="$(uname -s)"

# --- Windows shell (Git-Bash/MSYS/Cygwin) 引导到 PowerShell 脚本 ---
case "$OS" in
  MINGW*|CYGWIN*|MSYS*)
    c_err "检测到 Windows 环境。请改用 PowerShell 一键脚本 install.ps1："
    c_err "  irm https://github.com/${REPO}/releases/latest/download/install.ps1 | iex"
    c_err "（在纯 Linux 的 WSL2 中运行本脚本则无需切换）"
    exit 1
    ;;
esac

# --- --native 委托原生 Ubuntu 脚本 ---
if [ "$NATIVE" = "1" ]; then
  [ "$OS" = "Linux" ] || { c_err "--native 仅支持 Linux"; exit 1; }
  [ -f scripts/deploy-native-ubuntu.sh ] || { c_err "未找到 scripts/deploy-native-ubuntu.sh（请在源码目录运行）"; exit 1; }
  exec sudo bash scripts/deploy-native-ubuntu.sh
fi

# --- 确保 Docker 已安装 ---
if ! command -v docker >/dev/null 2>&1; then
  case "$OS" in
    Linux)
      c_info "未检测到 Docker，正在通过 get.docker.com 安装..."
      curl -fsSL https://get.docker.com | sh
      sudo systemctl enable --now docker 2>/dev/null || true
      ;;
    Darwin)
      c_err "未检测到 Docker Desktop，请安装后重试："
      c_err "  https://www.docker.com/products/docker-desktop/"
      command -v brew >/dev/null 2>&1 && c_warn "或运行: brew install --cask docker"
      exit 1
      ;;
    *)
      c_err "不支持的操作系统: $OS"
      exit 1
      ;;
  esac
fi

# --- 检测 docker 是否需要 sudo ---
SUDO=""
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    SUDO="sudo"
  else
    c_err "Docker 未运行。Linux 请启动 docker 服务；macOS 请启动 Docker Desktop。"
    exit 1
  fi
fi

# --- 检测 compose 命令 ---
if $SUDO docker compose version >/dev/null 2>&1; then
  DC="$SUDO docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="$SUDO docker-compose"
else
  c_err "未找到 docker compose 插件，请升级 Docker 或安装 docker-compose"
  exit 1
fi
c_ok "Docker 就绪 ($(docker --version | head -1))"

# --- 工作目录 ---
WORKDIR="${ERP_DIR:-$HOME/atm-erp}"
mkdir -p "$WORKDIR/docker/ssl"
cd "$WORKDIR"
c_info "工作目录: $WORKDIR"

# --- 生成自签名 SSL 证书（nginx 启动必需；浏览器会显示安全警告，可忽略）---
SSL_DIR="$WORKDIR/docker/ssl"
if [ ! -f "$SSL_DIR/server.crt" ] || [ ! -f "$SSL_DIR/server.key" ]; then
  c_info "生成自签名 SSL 证书..."
  if command -v openssl >/dev/null 2>&1; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
      -keyout "$SSL_DIR/server.key" \
      -out    "$SSL_DIR/server.crt" \
      -subj "/C=CN/ST=Shanghai/L=Shanghai/O=ATM-ERP/CN=localhost" \
      >/dev/null 2>&1 || true
  else
    c_warn "未找到本地 openssl，改用 Docker 容器生成证书..."
    $SUDO docker run --rm -v "$SSL_DIR:/certs" alpine/openssl \
      req -x509 -nodes -newkey rsa:2048 -days 3650 \
      -keyout /certs/server.key -out /certs/server.crt \
      -subj "/C=CN/ST=Shanghai/L=Shanghai/O=ATM-ERP/CN=localhost" >/dev/null 2>&1 || true
  fi
  # nginx 监听 443 时硬依赖证书，缺失会导致容器反复重启 —— 生成失败必须中止
  if [ -f "$SSL_DIR/server.crt" ] && [ -f "$SSL_DIR/server.key" ]; then
    c_ok "SSL 证书已生成 (自签名，3650 天有效期)"
  else
    c_err "SSL 证书生成失败：nginx 需要证书才能启动，安装中止。"
    c_err "请安装 openssl，或确认可拉取 alpine/openssl 镜像后重试。"
    exit 1
  fi
else
  c_info "SSL 证书已存在，跳过生成"
fi

# --- 获取部署文件 ---
fetch(){
  # fetch <relpath> <dest>
  local rel="$1" dest="$2"

  # ERP_LOCAL_SRC 钩子：离线/本地源优先
  if [ -n "${ERP_LOCAL_SRC:-}" ]; then
    local src="${ERP_LOCAL_SRC}/${rel}"
    if [ -f "$src" ]; then
      c_info "本地源: 复制 ${rel} 从 ${ERP_LOCAL_SRC}"
      cp "$src" "$dest"
      return
    else
      c_warn "ERP_LOCAL_SRC 中未找到 ${rel}，回退到网络下载"
    fi
  fi

  # 从 GitHub Release 下载，失败则回退 raw main
  local url
  if [ "$TAG" = "latest" ]; then
    url="${REL_BASE}/latest/download/${rel}"
  else
    url="${REL_BASE}/download/v${TAG#v}/${rel}"
  fi
  if ! curl -fsSL "$url" -o "$dest" 2>/dev/null; then
    c_warn "Release 资产不存在，回退到源码 main: ${rel}"
    curl -fsSL "${RAW_BASE}/${rel}" -o "$dest"
  fi
}

c_info "获取部署文件 (tag=${TAG})..."
fetch "docker-compose.yml" "docker-compose.yml"
fetch ".env.example"       ".env.example"

# --- 生成随机值工具 ---
rand(){
  openssl rand -hex "$1" 2>/dev/null \
    || python3 -c "import secrets,sys;print(secrets.token_hex(int(sys.argv[1])))" "$1"
}
randpw(){
  # 生成 16 字符纯字母数字密码（避免 shell 特殊字符干扰 .env 解析）
  openssl rand -base64 18 2>/dev/null | tr -dc 'A-Za-z0-9' | cut -c1-16 \
    || python3 -c "import secrets;print(secrets.token_urlsafe(12))"
}

# --- 检测宿主机 IP ---
if [ "$OS" = "Darwin" ]; then
  HOSTIP="$(ipconfig getifaddr en0 2>/dev/null || echo 127.0.0.1)"
else
  HOSTIP="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
[ -n "${HOSTIP:-}" ] || HOSTIP="127.0.0.1"

# IMAGE_TAG: 去掉前导 v（"v0.2.0" → "0.2.0"；"local" 保持 "local"）
IMAGE_TAG_VAL="${TAG#v}"

# --- 生成 .env（首次安装） ---
if [ ! -f .env ]; then
  c_info "生成 .env..."
  ADMIN_PASSWORD="$(randpw)"
  cat > .env <<EOF
DEBUG=False
SECRET_KEY=$(rand 32)
ALLOWED_HOSTS=localhost,127.0.0.1,${HOSTIP}
DB_NAME=erp_db
DB_USER=erp_user
DB_PASSWORD=$(rand 16)
CORS_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,http://${HOSTIP}
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,http://${HOSTIP}
FRONTEND_URL=http://localhost
IMAGE_TAG=${IMAGE_TAG_VAL}
HTTP_PORT=80
HTTPS_PORT=443
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
SEED_DEMO_DATA=0
EOF
  c_ok ".env 已生成（ADMIN_PASSWORD 见下方横幅，请妥善保存）"
else
  c_warn ".env 已存在，跳过生成（沿用现有配置）"
fi

# 读取最终密码（无论是新生成还是已有）
ADMIN_PASSWORD="$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)"

# --- 拉取镜像并启动 ---
c_info "拉取镜像 (tag=${IMAGE_TAG_VAL})..."
# pull 失败不中止：本地镜像 / 离线场景下 pull 会报错，但 up -d 仍可用已有镜像
$DC pull || c_warn "镜像拉取失败（可能是本地/离线标签），继续使用本地已有镜像..."

c_info "启动服务..."
$DC up -d
c_ok "容器已启动"

# --- 等待后端 API 就绪（首次启动含迁移+种子数据，最长约 12 分钟）---
c_info "等待后端就绪（首次启动需要迁移数据库，可能需要数分钟...）"
HEALTH_URL="http://localhost/api/v1/health/"
READY=0
MAX_ATTEMPTS=240   # 240 × 3s = 720s ≈ 12 分钟
for attempt in $(seq 1 $MAX_ATTEMPTS); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    READY=1
    break
  fi
  # 每 10 次（约 30 秒）打印一次进度
  if [ $(( attempt % 10 )) -eq 0 ]; then
    c_info "等待中... (${attempt}/${MAX_ATTEMPTS} 次，已等待 $(( attempt * 3 ))s)，可用 '$DC logs -f backend' 查看进度"
  fi
  sleep 3
done

if [ "$READY" = "1" ]; then
  c_ok "后端 API 已就绪"
else
  c_warn "健康检查超时，服务可能仍在初始化中"
  c_warn "请稍后运行: curl $HEALTH_URL"
  c_warn "或查看日志: cd ${WORKDIR} && ${DC} logs -f backend"
fi

# --- 确定访问地址 ---
HTTP_PORT_VAL="$(grep '^HTTP_PORT=' .env | cut -d= -f2- || echo 80)"
if [ "${HTTP_PORT_VAL}" = "80" ]; then
  ACCESS_URL="http://localhost/erp/"
  ACCESS_URL_IP="http://${HOSTIP}/erp/"
else
  ACCESS_URL="http://localhost:${HTTP_PORT_VAL}/erp/"
  ACCESS_URL_IP="http://${HOSTIP}:${HTTP_PORT_VAL}/erp/"
fi

cat <<EOF

============================================================
  ATM-ERP 安装完成！
------------------------------------------------------------
  访问地址 (本机) : ${ACCESS_URL}
  访问地址 (局域网): ${ACCESS_URL_IP}
  管理员账号      : admin
  管理员密码      : ${ADMIN_PASSWORD}
  工作目录        : ${WORKDIR}
------------------------------------------------------------
  常用命令:
    cd ${WORKDIR}
    ${DC} ps              # 查看容器状态
    ${DC} logs -f backend # 查看后端日志
    ${DC} down            # 停止并移除容器
    ${DC} down -v         # 停止并清除所有数据
============================================================
EOF
