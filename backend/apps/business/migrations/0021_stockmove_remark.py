from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0020_purchase_warranty_months')]
    operations = [
        migrations.AddField(
            model_name='stockmove',
            name='remark',
            field=models.CharField(max_length=500, blank=True, default=''),
        ),
    ]
