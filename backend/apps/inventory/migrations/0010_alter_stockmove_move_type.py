from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0009_alter_stockadjustment_adjustment_no_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmove',
            name='move_type',
            field=models.CharField(
                choices=[
                    ('IN_PURCHASE', '采购入库'),
                    ('OUT_SALES', '销售出库'),
                    ('OUT_PROJECT', '项目领料'),
                    ('OUT_RETURN', '采购退货出库'),
                    ('OUT_OUTSOURCE', '外协发料出库'),
                    ('IN_OUTSOURCE', '外协加工入库'),
                    ('TRANSFER', '调拨'),
                    ('ADJUSTMENT', '调整'),
                ],
                max_length=20,
                verbose_name='移动类型',
            ),
        ),
    ]
