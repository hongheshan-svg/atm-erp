from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0008_audit_index')]
    operations = [
        migrations.AddIndex(
            model_name='auditlog', index=models.Index(fields=['operation', 'id'], name='lean_audit_operation')
        ),
        migrations.AddIndex(
            model_name='actionreceipt',
            index=models.Index(fields=['operation', 'fingerprint'], name='lean_receipt_fingerprint'),
        ),
    ]
