from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as DjangoMigrate
from django.db import connection

from apps.core.schema_guard import check_schema


class Command(DjangoMigrate):
    def handle(self, *args, **options):
        # Django's test database setup adds run_syncdb=True automatically.
        # Disable that shortcut: even test databases must use real migrations.
        if settings.TESTING and str(connection.settings_dict['NAME']).startswith('test_atm_erp_lean'):
            options['run_syncdb'] = False
        if any(
            options.get(key) for key in ('fake', 'fake_initial', 'prune', 'app_label', 'migration_name', 'run_syncdb')
        ):
            raise CommandError('仅支持完整正向迁移；禁止 fake、定向迁移、回滚或同步旧表。')
        if options.get('database', 'default') != 'default':
            raise CommandError('仅允许当前精简版数据库。')
        check_schema(migrating=True)
        result = super().handle(*args, **options)
        if not options.get('plan') and not options.get('check_unapplied'):
            check_schema()
        return result
