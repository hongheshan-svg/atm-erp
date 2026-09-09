from django.apps import apps
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

GENERATION = 'lean-erp-v1'


def check_schema(*, migrating=False):
    """Only an empty database or this generation's tables may be used."""
    expected = {model._meta.db_table for model in apps.get_models(include_auto_created=True)} | {'django_migrations'}
    tables = set(connection.introspection.table_names())
    unexpected = tables - expected
    if unexpected:
        raise CommandError('检测到旧版或其他系统的数据表，拒绝操作。请使用全新独立数据库。')
    if not tables:
        if migrating:
            return
        raise CommandError('数据库尚未初始化，请运行 migrate。')
    if 'lean_schema' in tables:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id, generation FROM lean_schema')
            markers = cursor.fetchall()
        if markers and markers != [(1, GENERATION)]:
            raise CommandError('数据库版本标识不匹配，拒绝操作。')
        if not markers and not migrating:
            raise CommandError('精简版数据库初始化未完成，请运行 migrate。')
    elif not migrating:
        raise CommandError('数据库缺少精简版标识，拒绝操作。')
    executor = MigrationExecutor(connection)
    unknown = set(executor.loader.applied_migrations) - set(executor.loader.disk_migrations)
    if unknown:
        raise CommandError('检测到旧迁移历史，拒绝操作。请使用全新独立数据库。')
    if not migrating and executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise CommandError('数据库有未应用迁移，请先运行 migrate。')
