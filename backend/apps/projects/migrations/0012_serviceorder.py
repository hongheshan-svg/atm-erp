# Migration to create ServiceOrder model (matching existing DB table)
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('masterdata', '0005_automation_bom_fields'),
        ('projects', '0011_add_pr_tracking_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('order_no', models.CharField(max_length=50, unique=True, verbose_name='服务单号')),
                ('service_type', models.CharField(max_length=20, verbose_name='服务类型')),
                ('title', models.CharField(max_length=200, verbose_name='服务标题')),
                ('description', models.TextField(blank=True, verbose_name='服务描述')),
                ('service_address', models.TextField(verbose_name='服务地址')),
                ('contact_name', models.CharField(max_length=50, verbose_name='联系人')),
                ('contact_phone', models.CharField(max_length=20, verbose_name='联系电话')),
                ('status', models.CharField(default='DRAFT', max_length=20, verbose_name='状态')),
                ('priority', models.CharField(default='NORMAL', max_length=20, verbose_name='优先级')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='service_orders', to='masterdata.customer', verbose_name='客户')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_orders', to='projects.project', verbose_name='关联项目')),
                ('equipment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_orders', to='projects.equipment', verbose_name='关联设备')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '服务工单',
                'verbose_name_plural': '服务工单',
                'db_table': 'projects_serviceorder',
            },
        ),
    ]
