FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nginx supervisor && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/apps/ ./apps/
COPY backend/config/ ./config/
COPY backend/manage.py ./
COPY --from=frontend /frontend/dist/ /var/www/erp/
COPY docker/app/nginx.conf /etc/nginx/nginx.conf
COPY docker/app/supervisord.conf /etc/supervisord.conf
COPY docker/app/entrypoint.sh /entrypoint.sh
RUN groupadd -g 10001 erp && useradd -u 10001 -g erp --no-create-home erp && mkdir -p /app/uploads /tmp/nginx && chown -R erp:erp /app/uploads /tmp/nginx && chmod +x /entrypoint.sh
USER erp
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisord.conf"]
