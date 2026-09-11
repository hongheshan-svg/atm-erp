import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.core.models import AuditLog, CodeRule, Company
from apps.core.schema_guard import check_schema


class Command(BaseCommand):
    help = '初始化公司、编码和首位管理员；重复运行不会覆盖密码或已有资料。'

    def handle(self, **options):
        check_schema()
        with transaction.atomic():
            Company.objects.get_or_create(pk=1, defaults={'setup_required': True})
            Company.objects.select_for_update().get(pk=1)
            for key, prefix in [
                ('project', 'ATM'),
                ('sale', 'SO'),
                ('purchase', 'PO'),
                ('delivery', 'DEL'),
                ('item', 'MAT'),
                ('partner', 'PTY'),
                ('reconciliation', 'DZ'),
            ]:
                defaults = {'prefix': prefix}
                if key == 'project':
                    defaults.update(date_format='YY', padding=2, reset_cycle='year')
                CodeRule.objects.get_or_create(key=key, defaults=defaults)
            if not User.objects.exists():
                password = os.environ.get('ADMIN_PASSWORD', '')
                user = User(username='admin', display_name='管理员', role='admin', is_staff=True, is_superuser=True)
                try:
                    validate_password(password, user)
                except ValidationError as exc:
                    raise CommandError('ADMIN_PASSWORD 无效：' + '；'.join(exc.messages)) from exc
                user.set_password(password)
                user.save()
                AuditLog.objects.create(actor=user, operation='system.initialize', resource='company:1')
        self.stdout.write('初始化完成，已有用户及密码保持不变。')
