import re
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role
from apps.core.permission_models_new import Permission


class PermissionBootstrapTests(TestCase):
    def test_frontend_routes_and_default_roles_are_synchronized(self):
        call_command('init_permissions', verbosity=0)
        call_command('sync_frontend_menu_permissions', verbosity=0)
        call_command('init_roles', force=True, verbosity=0)

        router_path = Path(__file__).resolve().parents[4] / 'frontend' / 'src' / 'router' / 'index.ts'
        route_codes = set(re.findall(r"menuId:\s*'([^']+)'", router_path.read_text(encoding='utf-8')))
        active_menu_codes = set(
            Permission.objects.filter(type='menu', is_active=True, is_deleted=False).values_list('code', flat=True)
        )

        self.assertTrue(route_codes <= active_menu_codes, sorted(route_codes - active_menu_codes))
        self.assertTrue(Role.objects.get(code='admin').permissions_new.filter(code='workflow:config').exists())
        self.assertFalse(
            Role.objects.exclude(code='admin').filter(permissions_new__code='workflow:config').distinct().exists()
        )
        self.assertTrue(Role.objects.get(code='salesperson').permissions_new.filter(code='sales:order').exists())
