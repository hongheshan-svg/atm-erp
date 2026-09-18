from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0007_product_coding')]
    operations = [
        migrations.AddIndex(
            model_name='auditlog', index=models.Index(fields=['resource', 'operation'], name='lean_audit_resource')
        )
    ]
