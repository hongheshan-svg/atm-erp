#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py init_system
exec "$@"
