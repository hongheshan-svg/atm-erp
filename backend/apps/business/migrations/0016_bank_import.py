from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0015_purchasewarranty')]
    operations = [
        migrations.AddField(
            'bankrecord', 'import_fingerprint', models.CharField(max_length=64, null=True, blank=True, unique=True)
        ),
        migrations.AddField('bankrecord', 'source', models.JSONField(default=dict, blank=True)),
        migrations.AddField('bankrecord', 'needs_review', models.BooleanField(default=False)),
    ]
