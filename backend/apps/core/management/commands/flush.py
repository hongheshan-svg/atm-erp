from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.commands.flush import Command as DjangoFlush
from django.db import connection


class Command(DjangoFlush):
    def handle(self, **options):
        if not settings.TESTING or not str(connection.settings_dict['NAME']).startswith('test_atm_erp_lean'):
            raise CommandError('禁止清空业务数据库。')
        return super().handle(**options)
