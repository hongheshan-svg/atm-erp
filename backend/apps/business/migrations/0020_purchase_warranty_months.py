from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0019_hot_path_indexes')]
    operations = [
        migrations.AddField(
            model_name='purchaseorder',
            name='warranty_months',
            field=models.PositiveSmallIntegerField(default=12),
        ),
        migrations.AddConstraint(
            model_name='purchaseorder',
            constraint=models.CheckConstraint(
                condition=models.Q(('warranty_months__gte', 1), ('warranty_months__lte', 120)),
                name='lean_purchase_warranty_months',
            ),
        ),
    ]
