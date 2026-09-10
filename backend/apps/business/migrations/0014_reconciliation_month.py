from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0013_purchasecontractversion')]
    operations = [migrations.AddField(model_name='reconciliation', name='settlement_month', field=models.CharField(blank=True, max_length=7))]
