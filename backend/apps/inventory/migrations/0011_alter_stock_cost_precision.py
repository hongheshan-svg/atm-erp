from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0010_alter_stockmove_move_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stock',
            name='weighted_avg_cost',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name='加权平均成本'),
        ),
        migrations.AlterField(
            model_name='stockmove',
            name='unit_cost',
            field=models.DecimalField(decimal_places=4, max_digits=18, verbose_name='单位成本'),
        ),
        migrations.AlterField(
            model_name='materialrequisitionline',
            name='unit_cost',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name='单位成本'),
        ),
        migrations.AlterField(
            model_name='materialreturnline',
            name='unit_cost',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=18, verbose_name='单位成本'),
        ),
    ]
