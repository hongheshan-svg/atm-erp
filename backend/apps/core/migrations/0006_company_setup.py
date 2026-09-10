from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0005_company_period')]
    operations = [
        migrations.AddField('company', 'setup_required', models.BooleanField(default=False)),
        migrations.AddField('company', 'setup_completed_at', models.DateTimeField(null=True, blank=True)),
    ]
