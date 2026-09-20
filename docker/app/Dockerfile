ARG FRONTEND_MODE=build
ARG PYTHON_IMAGE=python:3.11-slim-trixie
ARG POSTGRES_CLIENT_IMAGE=postgres:15-trixie
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM scratch AS frontend-prebuilt
COPY frontend/dist/ /frontend/dist/

FROM frontend-${FRONTEND_MODE} AS frontend

FROM ${POSTGRES_CLIENT_IMAGE} AS pg-client
RUN mkdir -p /opt/pg/bin /opt/pg/lib \
    && cp /usr/lib/postgresql/15/bin/pg_dump /usr/lib/postgresql/15/bin/pg_restore /opt/pg/bin/ \
    && ldd /opt/pg/bin/pg_dump /opt/pg/bin/pg_restore | awk '$3 ~ /^\// {print $3}' | sort -u | xargs -I '{}' cp -L '{}' /opt/pg/lib/

FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nginx supervisor && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=pg-client /opt/pg /opt/pg
COPY backend/apps/ ./apps/
COPY backend/config/ ./config/
COPY backend/manage.py ./
COPY --from=frontend /frontend/dist/ /var/www/erp/
COPY docker/app/nginx.conf /etc/nginx/nginx.conf
COPY docker/app/supervisord.conf /etc/supervisord.conf
COPY docker/app/entrypoint.sh /entrypoint.sh
COPY docker/app/watchdog.py /watchdog.py
COPY scripts/restore_uploads.py /restore_uploads.py
COPY scripts/container_runtime.py scripts/container_ota.py scripts/ota_runner.py scripts/release_install.py /opt/erp/
RUN groupadd -g 10001 erp && useradd -u 10001 -g erp --no-create-home erp && mkdir -p /app/uploads /app/runtime /tmp/nginx && chown -R erp:erp /app/uploads /app/runtime /tmp/nginx && chmod +x /entrypoint.sh
USER erp
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
