from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0016_bank_import')]
    operations = [
        migrations.AddField(
            model_name='entry', name='cancellation_credit',
            field=models.DecimalField(max_digits=18, decimal_places=2, null=True, editable=False),
        ),
    ]
