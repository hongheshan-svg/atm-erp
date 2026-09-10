from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0004_upgradejob')]
    operations = [
        migrations.AddField(model_name='company', name='locked_through', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='company', name='period_revision', field=models.PositiveIntegerField(default=0)),
    ]
