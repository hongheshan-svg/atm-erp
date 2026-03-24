#!/bin/bash
set -e

echo "=== ERP Backend Starting ==="

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
while ! nc -z ${DB_HOST:-postgres} ${DB_PORT:-5432}; do
    sleep 1
done
echo "PostgreSQL is ready!"

# Wait for Redis
echo "Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} 6379; do
    sleep 1
done
echo "Redis is ready!"

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Initialize default workflow definitions
echo "Initializing workflow definitions..."
python manage.py init_workflows 2>/dev/null || echo "Workflow initialization skipped (may need migration first)"

# Create superuser if not exists
echo "Checking for admin user..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    user = User(
        username='admin',
        email='admin@example.com',
        employee_id='ADMIN001',
        is_staff=True,
        is_superuser=True,
        is_active=True,
        first_name='系统',
        last_name='管理员'
    )
    user.set_password('admin123')
    user.save()
    print('Admin user created: admin / admin123')
else:
    print('Admin user already exists')
EOF

echo "=== Starting Server ==="
exec "$@"

