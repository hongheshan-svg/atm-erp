# ERP Backend Dockerfile
# Django + Daphne (ASGI) + Celery

FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=5

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Configure pip to use Chinese mirror (faster in China)
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

# Install Python dependencies with retry
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn \
    || pip install --no-cache-dir -r requirements.txt gunicorn \
    || pip install --no-cache-dir -r requirements.txt gunicorn

# Copy backend code
COPY backend/ /app/

# Create necessary directories with proper permissions
RUN mkdir -p /app/staticfiles /app/logs /app/uploads \
    && chmod -R 755 /app/staticfiles /app/logs /app/uploads

# Create non-root user for security
RUN groupadd -r erp && useradd -r -g erp erp \
    && chown -R erp:erp /app

# Copy entrypoint script
COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER erp

# Expose port
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]

