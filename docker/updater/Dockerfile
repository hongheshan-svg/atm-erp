FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io postgresql-client curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# debian 的 docker.io 自带 docker CLI,但**不含 compose v2 插件**;升级 agent 依赖 `docker compose`,
# 补装官方 compose 插件二进制到 CLI 插件目录(按构建架构 x86_64/aarch64 自动选择)。
ARG COMPOSE_VERSION=v2.29.7
RUN mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
RUN pip install --no-cache-dir redis requests
COPY deploy/updater/ /opt/updater/deploy/updater/
ENV PYTHONPATH=/opt/updater
WORKDIR /opt/updater
CMD ["python", "-m", "deploy.updater.agent"]
