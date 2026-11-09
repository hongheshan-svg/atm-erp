from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0024_task_completed_date')]
    operations = [
        migrations.AddField(model_name='task', name='started_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='task', name='started_at', field=models.DateTimeField(blank=True, null=True)),
    ]
