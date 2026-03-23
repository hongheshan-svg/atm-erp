from django.db import migrations


OLD_TABLE = 'core_data_scope_departments'
NEW_TABLE = 'core_data_scope_custom_departments'


def reconcile_m2m_table(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    if OLD_TABLE in existing_tables and NEW_TABLE not in existing_tables:
        with connection.cursor() as cursor:
            cursor.execute(f'ALTER TABLE "{OLD_TABLE}" RENAME TO "{NEW_TABLE}"')


def reverse_reconcile_m2m_table(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    if NEW_TABLE in existing_tables and OLD_TABLE not in existing_tables:
        with connection.cursor() as cursor:
            cursor.execute(f'ALTER TABLE "{NEW_TABLE}" RENAME TO "{OLD_TABLE}"')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_fix_datascope_fields'),
    ]

    operations = [
        migrations.RunPython(reconcile_m2m_table, reverse_reconcile_m2m_table),
    ]