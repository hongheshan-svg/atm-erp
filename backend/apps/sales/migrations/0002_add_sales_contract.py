# Generated migration for SalesContract model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('masterdata', '0001_initial'),
        ('projects', '0001_initial'),
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalesContract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('contract_no', models.CharField(max_length=50, unique=True, verbose_name='合同编号')),
                ('title', models.CharField(max_length=200, verbose_name='合同标题')),
                ('contract_date', models.DateField(verbose_name='合同日期')),
                ('effective_date', models.DateField(blank=True, null=True, verbose_name='生效日期')),
                ('expiry_date', models.DateField(blank=True, null=True, verbose_name='到期日期')),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='合同金额')),
                ('tax_rate', models.IntegerField(default=13, verbose_name='税率(%)')),
                ('tax_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='税额')),
                ('total_with_tax', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='含税总额')),
                ('payment_terms', models.TextField(blank=True, verbose_name='付款条款')),
                ('delivery_terms', models.TextField(blank=True, verbose_name='交货条款')),
                ('quality_terms', models.TextField(blank=True, verbose_name='质量条款')),
                ('warranty_terms', models.TextField(blank=True, verbose_name='质保条款')),
                ('buyer_signer', models.CharField(blank=True, max_length=100, verbose_name='甲方签署人')),
                ('seller_signer', models.CharField(blank=True, max_length=100, verbose_name='乙方签署人')),
                ('signed_date', models.DateField(blank=True, null=True, verbose_name='签署日期')),
                ('status', models.CharField(choices=[('DRAFT', '草稿'), ('PENDING', '待审批'), ('APPROVED', '已审批'), ('SIGNED', '已签署'), ('COMPLETED', '已完成'), ('CANCELLED', '已取消')], default='DRAFT', max_length=20, verbose_name='状态')),
                ('notes', models.TextField(blank=True, verbose_name='备注')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sales_contracts', to='masterdata.customer', verbose_name='客户')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales_contracts', to='projects.project', verbose_name='关联项目')),
                ('so', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='sales.salesorder', verbose_name='销售订单')),
            ],
            options={
                'verbose_name': '销售合同',
                'verbose_name_plural': '销售合同',
                'db_table': 'sales_contract',
                'ordering': ['-created_at'],
            },
        ),
    ]

