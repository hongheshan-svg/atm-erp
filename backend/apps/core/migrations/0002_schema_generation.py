from django.db import migrations


def mark_generation(apps, schema_editor):
    apps.get_model('core', 'SchemaVersion').objects.using(schema_editor.connection.alias).create(pk=1, generation='lean-erp-v1')


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial'), ('business', '0001_initial')]
    operations = [migrations.RunPython(mark_generation)]
