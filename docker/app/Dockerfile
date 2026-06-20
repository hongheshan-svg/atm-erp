# ERP 全合一镜像:Django(Daphne ASGI) + Celery(worker+beat) + 升级进度中转 + 前端静态 + Nginx。
# 由 supervisord 统一拉起;首启迁移/初始化由 entrypoint 完成。替代原 backend + frontend + celery +
# celery-beat + nginx + upgrade-relay 六个服务,部署只需 postgres + redis + app + updater 共 4 个。

# ============ Stage 1: 构建前端 ============
FROM node:20-alpine AS fe
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm config set registry ${NPM_REGISTRY} && npm install --legacy-peer-deps
COPY frontend/ ./
ENV VITE_API_BASE_URL=/api
RUN npm run build

# ============ Stage 2: 应用 + nginx + supervisor ============
FROM python:3.11-slim-bookworm
ARG APT_MIRROR=mirrors.aliyun.com
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=5
WORKDIR /app

RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl netcat-openbsd nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url ${PIP_INDEX_URL} \
    && pip config set global.trusted-host ${PIP_TRUSTED_HOST}

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn \
    || pip install --no-cache-dir -r requirements.txt gunicorn

# 后端代码 + 前端路由(菜单同步命令用)
COPY backend/ /app/
COPY frontend/src/router/index.ts /app/frontend/src/router/index.ts

# 前端构建产物 → nginx 站点根
COPY --from=fe /fe/dist /var/www/erp

# nginx 配置(把 upstream backend 指到容器内 127.0.0.1:8000)+ supervisord
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
RUN sed -i 's#server backend:8000;#server 127.0.0.1:8000;#' /etc/nginx/nginx.conf
COPY docker/app/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 复用后端 entrypoint(等 pg/redis + RUN_BOOTSTRAP 迁移/初始化/建超管,最后 exec "$@")
COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/staticfiles /app/logs /app/uploads /var/log/nginx /var/cache/nginx /var/lib/nginx

EXPOSE 80 443
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf", "-n"]
