from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0004_project_budget')]
    operations = [migrations.AddField(model_name='salesorder', name='contract_number', field=models.CharField(blank=True, max_length=80, null=True, unique=True))]
