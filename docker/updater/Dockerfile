FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io postgresql-client curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir redis requests
COPY deploy/updater/ /opt/updater/deploy/updater/
ENV PYTHONPATH=/opt/updater
WORKDIR /opt/updater
CMD ["python", "-m", "deploy.updater.agent"]
