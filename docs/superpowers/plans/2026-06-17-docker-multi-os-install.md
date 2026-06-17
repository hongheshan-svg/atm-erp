# Docker 多平台一键安装发布版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 v0.2.0 发布版在 Linux/macOS/Windows 三平台同等地位，通过一条命令用 Docker（GHCR 预构建多架构镜像）拉起完整 ERP。

**Architecture:** GitHub Actions 在打 tag 时构建 amd64/arm64 镜像推送到 GHCR（公开包）；`docker-compose.yml` 改为基于镜像、可移植（Celery 走桥接网络）；`install.sh`（Linux/macOS）与 `install.ps1`（Windows）两个瘦脚本完成检测 Docker→生成 .env→拉镜像→启动→健康等待→打印登录信息；backend entrypoint 做幂等首次初始化。

**Tech Stack:** Docker / Docker Compose v2、GitHub Actions（buildx + QEMU）、GHCR、Bash、PowerShell、Django manage 命令。

## Global Constraints

- 目标版本号：**v0.2.0**；镜像 tag 去掉前导 `v`（即 `0.2.0`）。
- 镜像命名：`ghcr.io/hongheshan-svg/atm-erp-backend`、`ghcr.io/hongheshan-svg/atm-erp-frontend`。
- 多架构：`linux/amd64,linux/arm64`。
- 基础 compose 仅向宿主机暴露 nginx `80`/`443`；不暴露 Postgres/Redis/ES。
- 三平台同等地位；Linux `host` 网络仅作可选 override，非前置条件。
- Admin 账号由 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 环境变量创建，密码随机生成、安装后打印一次。
- 默认不灌示例数据（`SEED_DEMO_DATA=0`）。
- 仅 `backend` 服务执行初始化（`RUN_BOOTSTRAP=1`）；celery/celery-beat 不初始化。
- 提交遵循仓库规范：feature 分支（本计划用 `feat/docker-multi-os-install`），commit message 结尾加
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`，**禁止直接提交 main**。
- 健康端点：nginx `GET /health` 返回 200；backend `GET /api/v1/health/`。

---

## File Structure

| 文件 | 责任 |
|------|------|
| `docker-compose.yml` | 可移植基础编排，引用 GHCR 镜像，仅暴露 nginx |
| `docker-compose.build.yml` | 从源码构建的 override（贡献者/离线/本地验证） |
| `docker-compose.linux-host.yml` | 可选 Linux host 网络 override（局域网设备边缘场景，自含端口暴露） |
| `docker-compose.expose.yml` | 可选向宿主机暴露 PG/Redis/ES 端口（调试） |
| `docker/backend/entrypoint.sh` | backend 容器入口：等待依赖 + 幂等首次初始化 |
| `.env.example` | 安装脚本/用户参考的环境变量模板 |
| `.github/workflows/release-images.yml` | 打 tag/手动触发时构建并推送多架构镜像；打 tag 时附加发布资产 |
| `install.sh` | Linux+macOS 一键安装脚本 |
| `install.ps1` | Windows 一键安装脚本 |
| `README.md` / `README.zh-CN.md` | 新增一键安装章节 |
| `frontend/package.json` | 版本号对齐到 0.2.0 |

---

## Task 1: 可移植的 docker-compose（基础 + 三个 override）

**Files:**
- Modify: `docker-compose.yml`（整体重写）
- Create: `docker-compose.build.yml`
- Create: `docker-compose.linux-host.yml`
- Create: `docker-compose.expose.yml`
- Modify: `.env.example`

**Interfaces:**
- Produces: 服务镜像变量 `REGISTRY`（默认 `ghcr.io`）、`IMAGE_OWNER`（默认 `hongheshan-svg`）、`IMAGE_TAG`（默认 `latest`）；backend 容器读取 `RUN_BOOTSTRAP`、`ADMIN_USERNAME`、`ADMIN_PASSWORD`、`SEED_DEMO_DATA`（Task 2 消费）。
- Consumes: 现有 `docker/backend/Dockerfile`、`docker/frontend/Dockerfile`。

- [ ] **Step 1: 重写 `docker-compose.yml`**

```yaml
# ATM-ERP 基础编排（可移植，三平台一致）
# 镜像来自 GHCR；本地构建用 docker-compose.build.yml override
services:
  postgres:
    image: postgres:15-alpine
    container_name: erp-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME:-erp_db}
      POSTGRES_USER: ${DB_USER:-erp_user}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-erp_password}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-erp_user} -d ${DB_NAME:-erp_db}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - erp-network

  redis:
    image: redis:7-alpine
    container_name: erp-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - erp-network

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.16
    container_name: erp-elasticsearch
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - erp-network

  backend:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-backend:${IMAGE_TAG:-latest}
    container_name: erp-backend
    restart: unless-stopped
    environment:
      - DEBUG=${DEBUG:-False}
      - SECRET_KEY=${SECRET_KEY:-django-insecure-change-this-in-production-123456}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1,backend}
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME:-erp_db}
      - DB_USER=${DB_USER:-erp_user}
      - DB_PASSWORD=${DB_PASSWORD:-erp_password}
      - REDIS_HOST=redis
      - REDIS_URL=redis://redis:6379/1
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - ELASTICSEARCH_HOST=elasticsearch:9200
      - CORS_ALLOWED_ORIGINS=${CORS_ALLOWED_ORIGINS:-http://localhost,http://127.0.0.1}
      - CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS:-http://localhost,http://127.0.0.1}
      - FRONTEND_URL=${FRONTEND_URL:-http://localhost}
      - RUN_BOOTSTRAP=1
      - ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
      - SEED_DEMO_DATA=${SEED_DEMO_DATA:-0}
      - WECHAT_WORK_WEBHOOK_URL=${WECHAT_WORK_WEBHOOK_URL:-}
      - WECHAT_WORK_CORP_ID=${WECHAT_WORK_CORP_ID:-}
      - WECHAT_WORK_CORP_SECRET=${WECHAT_WORK_CORP_SECRET:-}
      - WECHAT_WORK_AGENT_ID=${WECHAT_WORK_AGENT_ID:-}
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/uploads
      - backend_logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
    networks:
      - erp-network

  celery:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-backend:${IMAGE_TAG:-latest}
    container_name: erp-celery
    restart: unless-stopped
    command: celery -A config worker -l info --concurrency=2
    environment:
      - DEBUG=${DEBUG:-False}
      - SECRET_KEY=${SECRET_KEY:-django-insecure-change-this-in-production-123456}
      - RUN_BOOTSTRAP=0
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME:-erp_db}
      - DB_USER=${DB_USER:-erp_user}
      - DB_PASSWORD=${DB_PASSWORD:-erp_password}
      - REDIS_HOST=redis
      - REDIS_URL=redis://redis:6379/1
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - ELASTICSEARCH_HOST=elasticsearch:9200
      - WECHAT_WORK_WEBHOOK_URL=${WECHAT_WORK_WEBHOOK_URL:-}
      - WECHAT_WORK_CORP_ID=${WECHAT_WORK_CORP_ID:-}
      - WECHAT_WORK_CORP_SECRET=${WECHAT_WORK_CORP_SECRET:-}
      - WECHAT_WORK_AGENT_ID=${WECHAT_WORK_AGENT_ID:-}
    volumes:
      - media_files:/app/uploads
      - backend_logs:/app/logs
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - erp-network

  celery-beat:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-backend:${IMAGE_TAG:-latest}
    container_name: erp-celery-beat
    restart: unless-stopped
    command: celery -A config beat -l info
    environment:
      - DEBUG=${DEBUG:-False}
      - SECRET_KEY=${SECRET_KEY:-django-insecure-change-this-in-production-123456}
      - RUN_BOOTSTRAP=0
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME:-erp_db}
      - DB_USER=${DB_USER:-erp_user}
      - DB_PASSWORD=${DB_PASSWORD:-erp_password}
      - REDIS_HOST=redis
      - REDIS_URL=redis://redis:6379/1
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - WECHAT_WORK_WEBHOOK_URL=${WECHAT_WORK_WEBHOOK_URL:-}
      - WECHAT_WORK_CORP_ID=${WECHAT_WORK_CORP_ID:-}
      - WECHAT_WORK_CORP_SECRET=${WECHAT_WORK_CORP_SECRET:-}
      - WECHAT_WORK_AGENT_ID=${WECHAT_WORK_AGENT_ID:-}
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - erp-network

  nginx:
    image: ${REGISTRY:-ghcr.io}/${IMAGE_OWNER:-hongheshan-svg}/atm-erp-frontend:${IMAGE_TAG:-latest}
    container_name: erp-nginx
    restart: unless-stopped
    ports:
      - "${HTTP_PORT:-80}:80"
      - "${HTTPS_PORT:-443}:443"
    volumes:
      - static_files:/app/staticfiles:ro
      - media_files:/app/uploads:ro
      - nginx_logs:/var/log/nginx
      - ./docker/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - erp-network

volumes:
  postgres_data:
  redis_data:
  elasticsearch_data:
  static_files:
  media_files:
  backend_logs:
  nginx_logs:

networks:
  erp-network:
    driver: bridge
```

注意：`nginx` 仍挂载 `./docker/ssl`。一键安装脚本会在工作目录创建空 `docker/ssl/` 占位目录（HTTP 模式不需要证书，但挂载路径需存在）。

- [ ] **Step 2: 创建 `docker-compose.build.yml`**

```yaml
# 从源码本地构建镜像的 override
# 用法: docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
services:
  backend:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
  celery:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
  celery-beat:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile
  nginx:
    build:
      context: .
      dockerfile: docker/frontend/Dockerfile
```

- [ ] **Step 3: 创建 `docker-compose.expose.yml`**

```yaml
# 调试用：向宿主机暴露内部服务端口
# 用法: docker compose -f docker-compose.yml -f docker-compose.expose.yml up -d
services:
  postgres:
    ports:
      - "5433:5432"
  redis:
    ports:
      - "6380:6379"
  elasticsearch:
    ports:
      - "9201:9200"
```

- [ ] **Step 4: 创建 `docker-compose.linux-host.yml`**

```yaml
# 可选（仅 Linux）：Celery 走 host 网络以支持局域网设备 UDP 发现/广播等边缘场景。
# 自含 PG/Redis/ES 端口暴露，因为 host 网络下 Celery 需经宿主机端口访问这些服务。
# 用法: docker compose -f docker-compose.yml -f docker-compose.linux-host.yml up -d
services:
  postgres:
    ports:
      - "5433:5432"
  redis:
    ports:
      - "6380:6379"
  elasticsearch:
    ports:
      - "9201:9200"
  celery:
    network_mode: host
    environment:
      - DEBUG=${DEBUG:-False}
      - SECRET_KEY=${SECRET_KEY:-django-insecure-change-this-in-production-123456}
      - RUN_BOOTSTRAP=0
      - DB_HOST=127.0.0.1
      - DB_PORT=5433
      - DB_NAME=${DB_NAME:-erp_db}
      - DB_USER=${DB_USER:-erp_user}
      - DB_PASSWORD=${DB_PASSWORD:-erp_password}
      - REDIS_HOST=127.0.0.1
      - REDIS_URL=redis://127.0.0.1:6380/1
      - CELERY_BROKER_URL=redis://127.0.0.1:6380/0
      - CELERY_RESULT_BACKEND=redis://127.0.0.1:6380/0
      - ELASTICSEARCH_HOST=127.0.0.1:9201
```

注：host 网络模式下 compose 会忽略该服务的 `networks:` 设置（compose 会给出 warning，可接受）。

- [ ] **Step 5: 对齐 `.env.example`（在文件末尾追加镜像与一键安装相关变量）**

在现有 `.env.example` 末尾追加：

```bash
# ===========================================
# Docker 镜像（一键安装）
# ===========================================
# 镜像仓库与所有者（默认 GHCR 官方包）
REGISTRY=ghcr.io
IMAGE_OWNER=hongheshan-svg
# 镜像版本标签（如 0.2.0；latest 为最新）
IMAGE_TAG=latest

# 宿主机端口（如 80/443 被占用可改）
HTTP_PORT=80
HTTPS_PORT=443

# ===========================================
# 初始管理员（首次启动自动创建）
# ===========================================
ADMIN_USERNAME=admin
ADMIN_PASSWORD=
# 是否灌入示例数据：0=否 1=是
SEED_DEMO_DATA=0
```

- [ ] **Step 6: 校验 compose 语法**

Run: `docker compose -f docker-compose.yml config -q && echo OK`
Expected: 打印 `OK`，无报错（变量缺省时用默认值，校验通过）。

Run: `docker compose -f docker-compose.yml -f docker-compose.build.yml config -q && echo OK`
Expected: `OK`。

- [ ] **Step 7: 本地构建并启动全栈（用 build override 验证可移植性）**

```bash
# 临时 .env，仅本步验证用
cat > .env <<'EOF'
DEBUG=False
SECRET_KEY=test-secret-key-do-not-use-in-prod
ALLOWED_HOSTS=localhost,127.0.0.1,backend
DB_PASSWORD=testpass123
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Test123456
IMAGE_TAG=local
EOF
mkdir -p docker/ssl
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

- [ ] **Step 8: 验证 Web 可达**

Run: `sleep 60 && curl -fsS http://localhost/health`
Expected: 输出 `healthy`。

Run: `curl -fsS http://localhost/api/v1/health/`
Expected: 返回 JSON，含 `"status": "healthy"`。

说明：此时权限/角色可能尚未初始化（旧 entrypoint），属预期；Task 2 修复。

- [ ] **Step 9: 清理并提交**

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml down -v
rm -f .env
git add docker-compose.yml docker-compose.build.yml docker-compose.expose.yml docker-compose.linux-host.yml .env.example
git commit -m "feat(docker): 可移植基础 compose + build/expose/linux-host override

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: backend entrypoint 幂等首次初始化

**Files:**
- Modify: `docker/backend/entrypoint.sh`（整体重写）
- Test: 通过 `docker compose ... up` 全栈验证（无独立单测框架，验证为功能性）

**Interfaces:**
- Consumes: Task 1 compose 注入的 `RUN_BOOTSTRAP`、`ADMIN_USERNAME`、`ADMIN_PASSWORD`、`SEED_DEMO_DATA`、`DB_HOST`、`DB_PORT`、`REDIS_HOST`。
- Produces: 首次启动后数据库含权限树、角色、仪表盘 Widget、工作流，以及由 env 指定的 admin 账号；标记文件 `/app/logs/.bootstrapped`。

- [ ] **Step 1: 重写 `docker/backend/entrypoint.sh`**

```bash
#!/bin/bash
set -e

echo "=== ERP Backend Container Starting ==="

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do sleep 1; done
echo "PostgreSQL is ready!"

echo "Waiting for Redis at ${REDIS_HOST}:6379..."
while ! nc -z "$REDIS_HOST" 6379; do sleep 1; done
echo "Redis is ready!"

if [ "${RUN_BOOTSTRAP:-0}" = "1" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    MARKER="/app/logs/.bootstrapped"
    if [ ! -f "$MARKER" ]; then
        echo "First-time bootstrap: permissions / roles / widgets / workflows..."
        python manage.py init_permissions
        python manage.py init_roles --force
        python manage.py init_dashboard_widgets
        python manage.py init_workflows 2>/dev/null || echo "init_workflows skipped"

        if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
            echo "Seeding demo data..."
            python manage.py seed_data 2>/dev/null || echo "seed_data skipped"
        fi

        echo "Ensuring admin user..."
        python manage.py shell <<'PYEOF'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('ADMIN_USERNAME', 'admin')
password = os.environ.get('ADMIN_PASSWORD', 'admin123')
email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
if not User.objects.filter(username=username).exists():
    u = User(
        username=username, email=email, employee_id='ADMIN001',
        is_staff=True, is_superuser=True, is_active=True,
        first_name='系统', last_name='管理员',
    )
    u.set_password(password)
    u.save()
    print(f'Admin user created: {username}')
else:
    print(f'Admin user {username} already exists')
PYEOF

        touch "$MARKER"
        echo "Bootstrap complete."
    else
        echo "Bootstrap marker present; migrations applied, seed skipped."
    fi
else
    echo "RUN_BOOTSTRAP != 1; skipping migrations/bootstrap (non-backend service)."
fi

echo "=== Starting: $* ==="
exec "$@"
```

- [ ] **Step 2: 语法检查**

Run: `bash -n docker/backend/entrypoint.sh && echo OK`
Expected: `OK`。

- [ ] **Step 3: 全栈重建并启动（干净卷）**

```bash
cat > .env <<'EOF'
DEBUG=False
SECRET_KEY=test-secret-key-do-not-use-in-prod
ALLOWED_HOSTS=localhost,127.0.0.1,backend
DB_PASSWORD=testpass123
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Test123456
IMAGE_TAG=local
EOF
mkdir -p docker/ssl
docker compose -f docker-compose.yml -f docker-compose.build.yml down -v
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

- [ ] **Step 4: 验证初始化生效（权限被种入）**

Run: `sleep 75 && docker compose -f docker-compose.yml -f docker-compose.build.yml exec -T backend python manage.py shell -c "from apps.core.models import Permission; print('PERM_COUNT', Permission.objects.count())"`
Expected: 打印 `PERM_COUNT N`，且 `N > 0`。

> 注：若权限模型导入路径与上不符，先运行
> `docker compose ... exec -T backend python manage.py shell -c "from django.apps import apps; print([m.__name__ for m in apps.get_app_config('core').get_models()])"`
> 找到权限模型名后替换上面的导入。

- [ ] **Step 5: 验证可用生成密码登录**

Run:
```bash
curl -fsS -X POST http://localhost/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Test123456"}'
```
Expected: 返回含 JWT `access`/`refresh`（或该项目登录接口的成功响应）。

> 注：若登录路径不同，先 `grep -rn "login" backend/config/urls.py backend/apps/accounts/urls.py` 确认实际路径再替换。

- [ ] **Step 6: 验证幂等（重启不重复 seed）**

Run: `docker compose -f docker-compose.yml -f docker-compose.build.yml restart backend && sleep 30 && docker compose -f docker-compose.yml -f docker-compose.build.yml logs --tail=30 backend | grep -i bootstrap`
Expected: 日志出现 `Bootstrap marker present; ... seed skipped.`

- [ ] **Step 7: 清理并提交**

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml down -v
rm -f .env
git add docker/backend/entrypoint.sh
git commit -m "feat(docker): backend entrypoint 幂等首次初始化(权限/角色/widget/admin)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: CI 多架构镜像流水线

**Files:**
- Create: `.github/workflows/release-images.yml`

**Interfaces:**
- Produces: GHCR 镜像 `atm-erp-backend` / `atm-erp-frontend`，tag 为版本号（与 `latest`，仅正式 tag）。
- Consumes: 现有两个 Dockerfile 及其 build-args（`APT_MIRROR`/`PIP_INDEX_URL`/`PIP_TRUSTED_HOST`/`NPM_REGISTRY`）。

- [ ] **Step 1: 创建 `.github/workflows/release-images.yml`**

```yaml
name: Release Images

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:
    inputs:
      tag:
        description: '手动构建用的镜像 tag（如 0.2.0-test）'
        required: true
        default: 'dev'

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_OWNER: hongheshan-svg

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - name: backend
            dockerfile: docker/backend/Dockerfile
          - name: frontend
            dockerfile: docker/frontend/Dockerfile
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-qemu-action@v3

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_OWNER }}/atm-erp-${{ matrix.name }}
          tags: |
            type=semver,pattern={{version}}
            type=raw,value=latest,enable=${{ startsWith(github.ref, 'refs/tags/v') }}
            type=raw,value=${{ github.event.inputs.tag }},enable=${{ github.event_name == 'workflow_dispatch' }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ${{ matrix.dockerfile }}
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          build-args: |
            APT_MIRROR=deb.debian.org
            PIP_INDEX_URL=https://pypi.org/simple/
            PIP_TRUSTED_HOST=pypi.org
            NPM_REGISTRY=https://registry.npmjs.org
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 2: 校验 workflow YAML**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release-images.yml')); print('YAML OK')"`
Expected: `YAML OK`。

（如本机安装了 `actionlint`：`actionlint .github/workflows/release-images.yml` 预期无 error。）

- [ ] **Step 3: 提交并推送分支以便触发**

```bash
git add .github/workflows/release-images.yml
git commit -m "ci: GHCR 多架构镜像构建流水线(tag/手动触发)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push -u origin feat/docker-multi-os-install
```

- [ ] **Step 4: 手动触发一次构建（test tag）**

Run: `gh workflow run "Release Images" --ref feat/docker-multi-os-install -f tag=0.2.0-test`
Expected: 提示 workflow 已触发。

Run: `gh run watch $(gh run list --workflow="Release Images" --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status`
Expected: 两个矩阵作业（backend/frontend）均成功（exit 0）。

> 若失败，`gh run view --log-failed` 排查（常见：buildx arm64 QEMU 慢，或 Dockerfile build-arg 未消费的 warning——warning 不致失败）。

- [ ] **Step 5: 确认镜像已推送**

Run: `gh api "/users/hongheshan-svg/packages?package_type=container" --jq '.[].name'`
Expected: 列出 `atm-erp-backend` 与 `atm-erp-frontend`。

---

## Task 4: 将 GHCR 包设为公开并验证 pull 式部署

**Files:** 无（一次性配置 + 验证）

**Interfaces:**
- Consumes: Task 3 推送的镜像。
- Produces: 匿名可 `docker pull` 的公开镜像；验证基础 compose 无需构建即可运行。

- [ ] **Step 1: 把两个包设为 Public（一次性，UI 最可靠）**

操作（浏览器）：进入 `https://github.com/users/hongheshan-svg/packages` → 分别打开 `atm-erp-backend`、`atm-erp-frontend` → Package settings → Danger Zone → Change visibility → **Public** → 确认。

> 备选（如启用了细粒度 PAT，可尝试 API，但 UI 为准）：
> `gh api -X PATCH "/user/packages/container/atm-erp-backend" -f visibility=public` 可能不被支持，以 UI 为准。

- [ ] **Step 2: 匿名拉取验证（先登出 GHCR）**

```bash
docker logout ghcr.io
docker pull ghcr.io/hongheshan-svg/atm-erp-backend:0.2.0-test
docker pull ghcr.io/hongheshan-svg/atm-erp-frontend:0.2.0-test
```
Expected: 两个镜像均成功拉取，无需登录。

- [ ] **Step 3: 验证多架构 manifest**

Run: `docker buildx imagetools inspect ghcr.io/hongheshan-svg/atm-erp-backend:0.2.0-test`
Expected: 输出包含 `linux/amd64` 与 `linux/arm64` 两个平台。

- [ ] **Step 4: 纯 pull 模式跑基础 compose（不构建）**

```bash
TMP=$(mktemp -d); cp docker-compose.yml "$TMP"/; mkdir -p "$TMP/docker/ssl"; cd "$TMP"
cat > .env <<'EOF'
DEBUG=False
SECRET_KEY=test-secret-key-do-not-use-in-prod
ALLOWED_HOSTS=localhost,127.0.0.1,backend
DB_PASSWORD=testpass123
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Test123456
IMAGE_TAG=0.2.0-test
EOF
docker compose pull
docker compose up -d
sleep 75
curl -fsS http://localhost/health && echo " <= OK"
```
Expected: 末尾输出 `healthy <= OK`，全程未构建任何镜像。

- [ ] **Step 5: 清理**

```bash
docker compose down -v; cd -; rm -rf "$TMP"
```

（本任务无代码改动，无需提交。）

---

## Task 5: install.sh（Linux + macOS 一键安装）

**Files:**
- Create: `install.sh`（重写：当前文件是原生 Ubuntu 部署入口，改为 Docker 一键，`--native` 委托旧脚本）

**Interfaces:**
- Consumes: 发布资产 `docker-compose.yml`、`.env.example`；GHCR 公开镜像。
- Produces: 工作目录 `~/atm-erp`，生成 `.env`，启动全栈，打印登录信息。

- [ ] **Step 1: 写入 `install.sh`**

```bash
#!/usr/bin/env bash
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

usage(){ cat <<EOF
ATM-ERP 一键安装 (Docker, Linux/macOS)
用法: bash install.sh [--tag <版本>] [--native]
  --tag <版本>   指定镜像版本(默认 latest，如 0.2.0)
  --native       仅 Linux：改用原生(非 Docker)部署
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="${2:?}"; shift 2;;
    --native) NATIVE=1; shift;;
    -h|--help) usage; exit 0;;
    *) c_err "未知参数: $1"; usage; exit 1;;
  esac
done

OS="$(uname -s)"

if [ "$NATIVE" = "1" ]; then
  [ "$OS" = "Linux" ] || { c_err "--native 仅支持 Linux"; exit 1; }
  [ -f scripts/deploy-native-ubuntu.sh ] || { c_err "未找到 scripts/deploy-native-ubuntu.sh（请在源码目录运行）"; exit 1; }
  exec sudo bash scripts/deploy-native-ubuntu.sh
fi

# --- 确保 Docker ---
if ! command -v docker >/dev/null 2>&1; then
  case "$OS" in
    Linux)
      c_info "未检测到 Docker，正在通过 get.docker.com 安装..."
      curl -fsSL https://get.docker.com | sh
      sudo systemctl enable --now docker 2>/dev/null || true ;;
    Darwin)
      c_err "未检测到 Docker Desktop。请安装后重试："
      c_err "  https://www.docker.com/products/docker-desktop/"
      command -v brew >/dev/null 2>&1 && c_warn "或: brew install --cask docker"
      exit 1 ;;
    *) c_err "不支持的系统: $OS"; exit 1 ;;
  esac
fi

# docker 是否需要 sudo
SUDO=""
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then SUDO="sudo"; else
    c_err "Docker 未运行。Linux 请启动 docker 服务；macOS 请启动 Docker Desktop。"; exit 1
  fi
fi

# compose 命令
if $SUDO docker compose version >/dev/null 2>&1; then
  DC="$SUDO docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="$SUDO docker-compose"
else
  c_err "未找到 docker compose 插件"; exit 1
fi
c_ok "Docker 就绪"

# --- 工作目录 ---
WORKDIR="${ERP_DIR:-$HOME/atm-erp}"
mkdir -p "$WORKDIR/docker/ssl"
cd "$WORKDIR"

fetch(){ # fetch <relpath> <dest>
  local rel="$1" dest="$2" url
  if [ "$TAG" = "latest" ]; then url="${REL_BASE}/latest/download/${rel}"; else url="${REL_BASE}/download/v${TAG#v}/${rel}"; fi
  if ! curl -fsSL "$url" -o "$dest" 2>/dev/null; then
    c_warn "Release 资产缺失，回退到源码 main: ${rel}"
    curl -fsSL "${RAW_BASE}/${rel}" -o "$dest"
  fi
}

c_info "下载部署文件 (tag=$TAG)..."
fetch "docker-compose.yml" "docker-compose.yml"
fetch ".env.example" ".env.example"

# --- 生成 .env ---
rand(){ openssl rand -hex "$1" 2>/dev/null || python3 -c "import secrets,sys;print(secrets.token_hex(int(sys.argv[1])))" "$1"; }
randpw(){ openssl rand -base64 18 2>/dev/null | tr -dc 'A-Za-z0-9' | cut -c1-16 || python3 -c "import secrets;print(secrets.token_urlsafe(12))"; }

if [ "$OS" = "Darwin" ]; then HOSTIP="$(ipconfig getifaddr en0 2>/dev/null || echo 127.0.0.1)"; else HOSTIP="$(hostname -I 2>/dev/null | awk '{print $1}')"; fi
[ -n "${HOSTIP:-}" ] || HOSTIP="127.0.0.1"

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
IMAGE_TAG=${TAG#v}
HTTP_PORT=80
HTTPS_PORT=443
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
SEED_DEMO_DATA=0
EOF
  c_ok ".env 已生成"
else
  c_warn ".env 已存在，跳过生成"
fi
ADMIN_PASSWORD="$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)"

c_info "拉取镜像并启动（首次较慢）..."
$DC pull
$DC up -d

c_info "等待服务就绪..."
READY=0
for _ in $(seq 1 60); do
  if curl -fsS http://localhost/health >/dev/null 2>&1; then READY=1; break; fi
  sleep 3
done
[ "$READY" = "1" ] && c_ok "服务已就绪" || c_warn "健康检查超时，可稍后用 '$DC logs -f backend' 查看"

cat <<EOF

============================================================
  ATM-ERP 已启动 🎉
  访问地址 : http://localhost
  管理员   : admin
  密码     : ${ADMIN_PASSWORD}
  工作目录 : ${WORKDIR}
  常用命令 : cd ${WORKDIR} && ${DC} ps | logs -f | down
============================================================
EOF
```

- [ ] **Step 2: 语法检查**

Run: `bash -n install.sh && echo OK`
Expected: `OK`。

- [ ] **Step 3: 端到端验证（本机 macOS，Docker Desktop 已运行）**

```bash
ERP_DIR=$(mktemp -d)/atm-erp bash install.sh --tag 0.2.0-test
```
Expected: 最终打印登录横幅，`http://localhost` 可访问；账号 admin + 打印的密码。

- [ ] **Step 4: 验证登录信息可用**

Run: `curl -fsS http://localhost/health`
Expected: `healthy`。

（在浏览器用打印的 admin 密码登录 `http://localhost` 应成功。）

- [ ] **Step 5: 清理并提交**

```bash
( cd "$(dirname "$ERP_DIR")"/atm-erp 2>/dev/null && docker compose down -v ) || true
git add install.sh
git commit -m "feat(install): Docker 一键安装脚本(Linux/macOS), 保留 --native

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: install.ps1（Windows 一键安装）

**Files:**
- Create: `install.ps1`

**Interfaces:**
- Consumes: 发布资产 `docker-compose.yml`、`.env.example`；GHCR 公开镜像。
- Produces: 工作目录 `%USERPROFILE%\atm-erp`，生成 `.env`，启动全栈，打印登录信息。

- [ ] **Step 1: 写入 `install.ps1`**

```powershell
#Requires -Version 5
[CmdletBinding()]
param(
  [string]$Tag = "latest"
)
$ErrorActionPreference = "Stop"
$Repo = "hongheshan-svg/atm-erp"
$RelBase = "https://github.com/$Repo/releases"
$RawBase = "https://raw.githubusercontent.com/$Repo/main"

function Info($m){ Write-Host "[i] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[!] $m" -ForegroundColor Yellow }
function Err($m){  Write-Host "[x] $m" -ForegroundColor Red }

# --- 确保 Docker ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Err "未检测到 Docker Desktop。请安装后重试："
  Err "  https://www.docker.com/products/docker-desktop/"
  exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { Err "Docker 未运行，请启动 Docker Desktop 后重试。"; exit 1 }
Ok "Docker 就绪"

# --- 工作目录 ---
$WorkDir = Join-Path $env:USERPROFILE "atm-erp"
New-Item -ItemType Directory -Force -Path (Join-Path $WorkDir "docker\ssl") | Out-Null
Set-Location $WorkDir

function Fetch($rel, $dest) {
  if ($Tag -eq "latest") { $url = "$RelBase/latest/download/$rel" }
  else { $tagClean = $Tag.TrimStart('v'); $url = "$RelBase/download/v$tagClean/$rel" }
  try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest }
  catch {
    Warn "Release 资产缺失，回退源码 main: $rel"
    Invoke-WebRequest -UseBasicParsing -Uri "$RawBase/$rel" -OutFile $dest
  }
}

Info "下载部署文件 (tag=$Tag)..."
Fetch "docker-compose.yml" "docker-compose.yml"
Fetch ".env.example" ".env.example"

function Rand([int]$n) {
  $bytes = New-Object 'System.Byte[]' $n
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
}
function RandPw {
  $chars = (48..57) + (65..90) + (97..122)
  -join (1..16 | ForEach-Object { [char]($chars | Get-Random) })
}

if (-not (Test-Path ".env")) {
  Info "生成 .env..."
  $tagClean = $Tag.TrimStart('v')
  $adminPw = RandPw
  @"
DEBUG=False
SECRET_KEY=$(Rand 32)
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=erp_db
DB_USER=erp_user
DB_PASSWORD=$(Rand 16)
CORS_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1
FRONTEND_URL=http://localhost
IMAGE_TAG=$tagClean
HTTP_PORT=80
HTTPS_PORT=443
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$adminPw
SEED_DEMO_DATA=0
"@ | Out-File -Encoding ascii -FilePath ".env"
  Ok ".env 已生成"
} else {
  Warn ".env 已存在，跳过生成"
}
$adminPw = ((Select-String -Path ".env" -Pattern '^ADMIN_PASSWORD=').Line -replace 'ADMIN_PASSWORD=', '')

Info "拉取镜像并启动（首次较慢）..."
docker compose pull
docker compose up -d

Info "等待服务就绪..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try { Invoke-WebRequest -UseBasicParsing -Uri "http://localhost/health" -TimeoutSec 3 | Out-Null; $ready = $true; break }
  catch { Start-Sleep -Seconds 3 }
}
if ($ready) { Ok "服务已就绪" } else { Warn "健康检查超时，可用 'docker compose logs -f backend' 查看" }

Write-Host ""
Write-Host "============================================================"
Write-Host "  ATM-ERP 已启动"
Write-Host "  访问地址 : http://localhost"
Write-Host "  管理员   : admin"
Write-Host "  密码     : $adminPw"
Write-Host "  工作目录 : $WorkDir"
Write-Host "  常用命令 : docker compose ps | logs -f | down"
Write-Host "============================================================"
```

- [ ] **Step 2: 语法解析检查（如本机有 pwsh）**

Run: `command -v pwsh >/dev/null 2>&1 && pwsh -NoProfile -Command "\$null=[System.Management.Automation.Language.Parser]::ParseFile('install.ps1',[ref]\$null,[ref]\$e=\$null); if(\$e){\$e;exit 1}else{'PS PARSE OK'}" || echo "pwsh 不可用，跳过解析（Windows 上手动验证）"`
Expected: 输出 `PS PARSE OK`，或在无 pwsh 时打印跳过提示。

> Windows 真机验证（无法在本 macOS 自动执行，记录为手动步骤）：
> PowerShell 运行 `./install.ps1 -Tag 0.2.0-test`，预期 `http://localhost` 可访问并打印 admin 密码。

- [ ] **Step 3: 提交**

```bash
git add install.ps1
git commit -m "feat(install): Docker 一键安装脚本(Windows PowerShell)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 发布资产附加 + README 一键安装章节

**Files:**
- Modify: `.github/workflows/release-images.yml`（新增一个仅在 tag 时运行的 release job）
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes: 仓库内 `install.sh`、`install.ps1`、四个 compose 文件、`.env.example`。
- Produces: 正式 tag 时，GitHub Release 附带上述资产。

- [ ] **Step 1: 在 `release-images.yml` 末尾追加 release job**

在 `jobs:` 下、`build:` 之后追加：

```yaml
  release-assets:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Attach deploy assets to release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release upload "${GITHUB_REF_NAME}" \
            install.sh \
            install.ps1 \
            docker-compose.yml \
            docker-compose.build.yml \
            docker-compose.linux-host.yml \
            docker-compose.expose.yml \
            .env.example \
            --clobber
```

> 说明：该 job 需要 Release 已存在。Task 8 的发布流程会先 `gh release create` 再让 CI 上传资产；若 CI 早于 release 创建，`gh release upload` 会失败——故 Task 8 中先建 Release。

- [ ] **Step 2: 校验 workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release-images.yml')); print('YAML OK')"`
Expected: `YAML OK`。

- [ ] **Step 3: 在 `README.md`（英文）的 “Option 1: Docker Compose” 之前插入一键安装小节**

在 `### Option 1: Docker Compose (recommended)` 这一行**之前**插入：

```markdown
### One-click install (Linux / macOS / Windows)

Pre-built multi-arch images are published to GHCR; the installer detects Docker,
generates a `.env`, pulls images, starts the stack, and prints the admin login.

**Linux / macOS:**

```bash
curl -fsSL https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.ps1 | iex
```

Pin a version with `--tag 0.2.0` (Linux/macOS) or `-Tag 0.2.0` (Windows). To build
from source instead of pulling images, see [Option 1](#option-1-docker-compose-recommended)
with the `docker-compose.build.yml` override.

```

- [ ] **Step 4: 在 `README.zh-CN.md`（中文）的 “方式一：Docker Compose（推荐）” 之前插入一键安装小节**

在 `### 方式一：Docker Compose（推荐）` 这一行**之前**插入：

```markdown
### 一键安装（Linux / macOS / Windows）

预构建多架构镜像已发布到 GHCR；安装脚本会检测 Docker、生成 `.env`、拉取镜像、启动并打印管理员登录信息。

**Linux / macOS：**

```bash
curl -fsSL https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.sh | bash
```

**Windows（PowerShell）：**

```powershell
irm https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.ps1 | iex
```

指定版本：`--tag 0.2.0`（Linux/macOS）或 `-Tag 0.2.0`（Windows）。若想从源码构建而非拉取镜像，见
[方式一](#方式一docker-compose推荐) 配合 `docker-compose.build.yml` override。

```

- [ ] **Step 5: 提交**

```bash
git add .github/workflows/release-images.yml README.md README.zh-CN.md
git commit -m "feat(release): Release 附加部署资产 + README 一键安装章节

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 合并、发版 v0.2.0、端到端校验

**Files:**
- Modify: `frontend/package.json`（version → `0.2.0`）

**Interfaces:**
- Consumes: 前述全部产物。
- Produces: GitHub Release v0.2.0（含资产）、GHCR `:0.2.0` 与 `:latest` 镜像、可用的 latest 一键命令。

- [ ] **Step 1: 对齐前端版本号**

将 `frontend/package.json` 的 `"version": "1.0.0"` 改为 `"version": "0.2.0"`。

Run: `grep '"version"' frontend/package.json`
Expected: 显示 `"version": "0.2.0",`。

- [ ] **Step 2: 提交并推送，开 PR 合并到 main**

```bash
git add frontend/package.json
git commit -m "chore: 版本号对齐 0.2.0

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin feat/docker-multi-os-install
gh pr create --base main --head feat/docker-multi-os-install \
  --title "feat: Docker 多平台一键安装 (v0.2.0)" \
  --body "GHCR 多架构镜像 + install.sh/install.ps1 三平台一键安装；compose 重构；entrypoint 幂等初始化。详见 docs/superpowers/specs 与 plans。"
gh pr merge --squash --delete-branch
```
Expected: PR 创建并 squash 合并入 main。

- [ ] **Step 3: 同步本地 main**

```bash
git checkout main && git pull origin main --ff-only
```
Expected: main 含上述合并提交。

- [ ] **Step 4: 先创建 Release（草稿→正式），再让 CI 附加资产**

```bash
gh release create v0.2.0 \
  --title "v0.2.0 — Docker 多平台一键安装" \
  --notes "三平台(Linux/macOS/Windows)Docker 一键安装；GHCR 多架构预构建镜像；compose 重构与幂等初始化。详见 README 的「一键安装」章节。"
```
Expected: 创建 tag `v0.2.0` 与 Release。此 tag push 触发 `Release Images` 工作流。

- [ ] **Step 5: 等待 CI 构建镜像并上传资产**

Run: `gh run watch $(gh run list --workflow="Release Images" --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status`
Expected: `build`(backend/frontend) 与 `release-assets` 作业均成功。

Run: `gh release view v0.2.0 --json assets --jq '.assets[].name'`
Expected: 列出 `install.sh`、`install.ps1`、四个 compose、`.env.example`。

- [ ] **Step 6: 确认正式镜像可匿名拉取**

Run: `docker logout ghcr.io; docker pull ghcr.io/hongheshan-svg/atm-erp-backend:0.2.0`
Expected: 成功拉取。

> 若 `:0.2.0` 包是新建的且默认私有，按 Task 4 Step 1 再次将其设为 Public（包级可见性一次设定后通常对新 tag 继承；如遇 403 即重设）。

- [ ] **Step 7: 用 latest 一键命令做最终冒烟（本机 macOS）**

```bash
ERP_DIR=$(mktemp -d)/atm-erp bash -c 'curl -fsSL https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.sh | bash'
```
Expected: 打印登录横幅，`curl -fsS http://localhost/health` 返回 `healthy`，浏览器可用 admin 登录。

- [ ] **Step 8: 清理冒烟环境**

```bash
( cd "$(dirname "$ERP_DIR")"/atm-erp && docker compose down -v ) || true
```

---

## Self-Review

**Spec coverage（逐节核对 spec → 任务）：**
- §5.1 CI 镜像流水线 → Task 3 ✓
- §5.2 Compose 重构（镜像化/Celery 桥接/仅暴露 nginx/三个 override）→ Task 1 ✓
- §5.3 安装脚本（检测 Docker/生成 .env/拉取/健康等待/打印；`--tag`/`--native`/一键命令）→ Task 5（Linux/macOS）、Task 6（Windows）、README 一键命令 Task 7 ✓（注：`--https` 自签证书未单独实现，作为后续可选项，见下）
- §5.4 entrypoint 幂等初始化（仅 backend/标记文件/admin from env/默认不灌示例）→ Task 2 ✓
- §5.5 发布打包（附加资产）+ README → Task 7、Task 8 ✓
- §6 默认值（随机 admin 密码 / 不暴露 DB 端口）→ Task 1 + Task 5/6 ✓
- §7 验证计划（rc 构建 / 本机 pull 起栈 / install.sh 端到端 / README 链接）→ Task 3 Step4、Task 4 Step4、Task 5 Step3、Task 8 ✓
- GHCR 公开 → Task 4 ✓

**已知缩减（YAGNI / 明确记录）：** spec §5.3 提到的 `--https`（自签证书 + 443）未在脚本中实现，HTTP(80) 为默认一键体验；`scripts/generate-ssl.sh` 仍可手动启用 HTTPS。如需 `--https` 内置，作为后续小迭代追加，不阻塞本发布。

**Placeholder scan：** 无 TBD/TODO；所有文件均给出完整内容；两处“若路径不同先 grep 确认”的注记针对的是**验证命令**对项目既有接口（权限模型导入路径、登录 URL）的适配，非实现占位。

**Type/名称一致性：** 镜像名 `atm-erp-backend`/`atm-erp-frontend`、变量 `REGISTRY`/`IMAGE_OWNER`/`IMAGE_TAG`/`RUN_BOOTSTRAP`/`ADMIN_USERNAME`/`ADMIN_PASSWORD`/`SEED_DEMO_DATA`、标记文件 `/app/logs/.bootstrapped`、健康路径 `/health` 与 `/api/v1/health/` 在各任务间一致。
