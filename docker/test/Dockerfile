# 仅用于在容器内跑后端测试：装齐运行时依赖 + dev 依赖(pytest)。
# 源码通过 bind mount 挂入 /app，改代码无需重建镜像。
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
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url ${PIP_INDEX_URL} \
    && pip config set global.trusted-host ${PIP_TRUSTED_HOST}

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt -r /tmp/requirements-dev.txt

# 源码在运行时以 -v ./backend:/app 挂入，这里不 COPY 源码。
CMD ["pytest", "tests/integration/test_bom_import.py", "tests/integration/test_drawing_import.py", "-v"]
