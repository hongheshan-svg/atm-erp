"""Prepare an isolated database and administrator for browser E2E tests."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django = importlib.import_module('django')


def main() -> int:
    username = os.environ.get('E2E_USERNAME', 'admin')
    password = os.environ.get('E2E_PASSWORD')
    if not password:
        raise SystemExit('E2E_PASSWORD is required')

    django.setup()
    get_user_model = importlib.import_module('django.contrib.auth').get_user_model
    call_command = importlib.import_module('django.core.management').call_command
    call_command('migrate', interactive=False)
    call_command('init_permissions')
    call_command('sync_frontend_menu_permissions')
    call_command('init_roles', force=True)
    call_command('init_dashboard_widgets')
    call_command('init_workflows')

    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(username=username)
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()
    print(f'E2E administrator ready: {username}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
