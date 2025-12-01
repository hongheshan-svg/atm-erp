# Generated migration for FIFO inventory lot models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0001_initial'),
        ('masterdata', '0001_initial'),
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryLot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('lot_no', models.CharField(max_length=50, unique=True, verbose_name='批次号')),
                ('initial_qty', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='初始数量')),
                ('remaining_qty', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='剩余数量')),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='单位成本')),
                ('receipt_date', models.DateField(auto_now_add=True, db_index=True, verbose_name='入库日期')),
                ('reference_type', models.CharField(blank=True, max_length=50, verbose_name='参考类型')),
                ('reference_id', models.IntegerField(blank=True, null=True, verbose_name='参考ID')),
                ('notes', models.TextField(blank=True, verbose_name='备注')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inventory_lots', to='masterdata.item', verbose_name='物料')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='inventory_lots', to='masterdata.warehouse', verbose_name='仓库')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': 'FIFO库存批次',
                'verbose_name_plural': 'FIFO库存批次',
                'db_table': 'inventory_lot',
                'ordering': ['item', 'warehouse', 'receipt_date'],
            },
        ),
        migrations.AddIndex(
            model_name='inventorylot',
            index=models.Index(fields=['item', 'warehouse', 'receipt_date'], name='inventory_l_item_id_abc123_idx'),
        ),
        migrations.AddIndex(
            model_name='inventorylot',
            index=models.Index(fields=['remaining_qty'], name='inventory_l_remaini_def456_idx'),
        ),
        migrations.CreateModel(
            name='LotConsumption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('qty', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='消耗数量')),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='单位成本')),
                ('total_cost', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='总成本')),
                ('consumption_date', models.DateTimeField(auto_now_add=True, verbose_name='消耗时间')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='consumptions', to='inventory.inventorylot', verbose_name='库存批次')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lot_consumptions', to='projects.project', verbose_name='项目')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '批次消耗记录',
                'verbose_name_plural': '批次消耗记录',
                'db_table': 'lot_consumption',
                'ordering': ['-consumption_date'],
            },
        ),
    ]
