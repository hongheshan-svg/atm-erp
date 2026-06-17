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
        ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
        ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
        if [ -z "$ADMIN_PASSWORD" ]; then
            echo "WARNING: ADMIN_PASSWORD not set; skipping admin creation"
        else
            python manage.py shell <<'PYEOF'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('ADMIN_USERNAME', 'admin')
password = os.environ.get('ADMIN_PASSWORD', '')
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
        fi

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
