from django.core.management.base import BaseCommand

from apps.core.schema_guard import check_schema


class Command(BaseCommand):
    help = '验证数据库属于当前精简版且迁移完整。'

    def handle(self, **options):
        check_schema()
        self.stdout.write('精简版数据库检查通过。')
