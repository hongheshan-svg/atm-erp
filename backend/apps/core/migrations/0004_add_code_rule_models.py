# Generated migration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0003_security_webhook_dashboard'),
    ]

    operations = [
        migrations.CreateModel(
            name='CodeRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='是否删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('rule_type', models.CharField(choices=[('PROJECT', '项目编号'), ('ITEM', '物料编码'), ('PURCHASE_CONTRACT', '采购合同'), ('SALES_CONTRACT', '销售合同'), ('PURCHASE_REQUEST', '采购申请'), ('PURCHASE_ORDER', '采购订单'), ('SALES_ORDER', '销售订单'), ('SALES_QUOTE', '销售报价'), ('DELIVERY_ORDER', '发货单'), ('INVOICE', '发票'), ('GOODS_RECEIPT', '收货单'), ('STOCK_MOVE', '库存移动'), ('STOCK_ADJUSTMENT', '库存调整')], max_length=50, unique=True, verbose_name='规则类型')),
                ('rule_name', models.CharField(max_length=100, verbose_name='规则名称')),
                ('prefix', models.CharField(blank=True, default='', max_length=20, verbose_name='固定前缀')),
                ('date_format', models.CharField(blank=True, default='', help_text='日期格式：YYYY-年，YY-年后两位，MM-月，DD-日', max_length=50, verbose_name='日期格式')),
                ('seq_length', models.IntegerField(default=4, help_text='序列号长度（不足补0）', verbose_name='序列号长度')),
                ('seq_start', models.IntegerField(default=1, help_text='序列号起始值', verbose_name='序列号起始值')),
                ('current_seq', models.IntegerField(default=0, help_text='当前序列号', verbose_name='当前序列号')),
                ('reset_mode', models.CharField(choices=[('NONE', '不重置'), ('YEARLY', '每年重置'), ('MONTHLY', '每月重置'), ('DAILY', '每日重置')], default='YEARLY', help_text='序列号重置模式', max_length=20, verbose_name='重置模式')),
                ('separator', models.CharField(blank=True, default='', help_text='分隔符（如：- 或 _）', max_length=5, verbose_name='分隔符')),
                ('example', models.CharField(blank=True, editable=False, max_length=100, verbose_name='示例编码')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('description', models.TextField(blank=True, verbose_name='说明')),
                ('last_reset_date', models.DateField(blank=True, null=True, verbose_name='最后重置日期')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '编码规则',
                'verbose_name_plural': '编码规则',
                'db_table': 'code_rule',
                'ordering': ['rule_type'],
            },
        ),
        migrations.CreateModel(
            name='CodeHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('generated_code', models.CharField(max_length=100, verbose_name='生成的编码')),
                ('sequence_number', models.IntegerField(verbose_name='序列号')),
                ('generated_at', models.DateTimeField(auto_now_add=True, verbose_name='生成时间')),
                ('business_model', models.CharField(blank=True, max_length=100, verbose_name='业务模型')),
                ('business_id', models.IntegerField(blank=True, null=True, verbose_name='业务ID')),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='生成人')),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='core.coderule', verbose_name='编码规则')),
            ],
            options={
                'verbose_name': '编码历史',
                'verbose_name_plural': '编码历史',
                'db_table': 'code_history',
                'ordering': ['-generated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='codehistory',
            index=models.Index(fields=['rule', '-generated_at'], name='code_histor_rule_id_b7e8a5_idx'),
        ),
        migrations.AddIndex(
            model_name='codehistory',
            index=models.Index(fields=['generated_code'], name='code_histor_generat_0a3d4e_idx'),
        ),
    ]

