from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0001_initial')]
    operations = [migrations.AddField(model_name='task', name='service_date', field=models.DateField(blank=True, null=True))]
