# Generated migration for security, webhook, and dashboard models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0002_attachment'),
    ]

    operations = [
        # Login Log
        migrations.CreateModel(
            name='LoginLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150, verbose_name='用户名')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')),
                ('user_agent', models.TextField(blank=True, verbose_name='用户代理')),
                ('status', models.CharField(choices=[('SUCCESS', '成功'), ('FAILED', '失败'), ('LOCKED', '账户锁定')], max_length=20, verbose_name='状态')),
                ('failure_reason', models.CharField(blank=True, max_length=200, verbose_name='失败原因')),
                ('login_time', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='登录时间')),
                ('location', models.CharField(blank=True, max_length=200, verbose_name='登录地点')),
                ('device_type', models.CharField(blank=True, max_length=50, verbose_name='设备类型')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='login_logs', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '登录日志',
                'verbose_name_plural': '登录日志',
                'db_table': 'login_log',
                'ordering': ['-login_time'],
            },
        ),
        migrations.AddIndex(
            model_name='loginlog',
            index=models.Index(fields=['username', '-login_time'], name='login_log_usernam_idx'),
        ),
        migrations.AddIndex(
            model_name='loginlog',
            index=models.Index(fields=['ip_address', '-login_time'], name='login_log_ip_addr_idx'),
        ),
        
        # Sensitive Operation Log
        migrations.CreateModel(
            name='SensitiveOperationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_type', models.CharField(choices=[('DELETE', '删除'), ('BULK_DELETE', '批量删除'), ('EXPORT', '数据导出'), ('PASSWORD_RESET', '密码重置'), ('ROLE_CHANGE', '角色变更'), ('PERMISSION_CHANGE', '权限变更'), ('SYSTEM_CONFIG', '系统配置')], max_length=30, verbose_name='操作类型')),
                ('target_model', models.CharField(max_length=100, verbose_name='目标模型')),
                ('target_id', models.CharField(blank=True, max_length=100, verbose_name='目标ID')),
                ('target_desc', models.CharField(max_length=500, verbose_name='目标描述')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')),
                ('confirmed', models.BooleanField(default=False, verbose_name='已确认')),
                ('confirmed_at', models.DateTimeField(blank=True, null=True, verbose_name='确认时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sensitive_operations', to=settings.AUTH_USER_MODEL, verbose_name='操作用户')),
            ],
            options={
                'verbose_name': '敏感操作日志',
                'verbose_name_plural': '敏感操作日志',
                'db_table': 'sensitive_operation_log',
                'ordering': ['-created_at'],
            },
        ),
        
        # Webhook Endpoint
        migrations.CreateModel(
            name='WebhookEndpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='名称')),
                ('url', models.URLField(verbose_name='回调URL')),
                ('secret', models.CharField(blank=True, max_length=200, verbose_name='签名密钥')),
                ('events', models.JSONField(default=list, verbose_name='订阅事件')),
                ('headers', models.JSONField(blank=True, default=dict, verbose_name='自定义请求头')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('max_retries', models.IntegerField(default=3, verbose_name='最大重试次数')),
                ('retry_delay', models.IntegerField(default=60, verbose_name='重试间隔(秒)')),
                ('timeout', models.IntegerField(default=30, verbose_name='超时时间(秒)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'Webhook端点',
                'verbose_name_plural': 'Webhook端点',
                'db_table': 'webhook_endpoint',
            },
        ),
        
        # Webhook Delivery
        migrations.CreateModel(
            name='WebhookDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=50, verbose_name='事件类型')),
                ('payload', models.JSONField(verbose_name='请求数据')),
                ('status', models.CharField(choices=[('PENDING', '待发送'), ('SUCCESS', '成功'), ('FAILED', '失败'), ('RETRYING', '重试中')], default='PENDING', max_length=20, verbose_name='状态')),
                ('response_status', models.IntegerField(blank=True, null=True, verbose_name='响应状态码')),
                ('response_body', models.TextField(blank=True, verbose_name='响应内容')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('attempts', models.IntegerField(default=0, verbose_name='尝试次数')),
                ('next_retry_at', models.DateTimeField(blank=True, null=True, verbose_name='下次重试时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('delivered_at', models.DateTimeField(blank=True, null=True, verbose_name='送达时间')),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='core.webhookendpoint', verbose_name='端点')),
            ],
            options={
                'verbose_name': 'Webhook投递记录',
                'verbose_name_plural': 'Webhook投递记录',
                'db_table': 'webhook_delivery',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='webhookdelivery',
            index=models.Index(fields=['status', 'next_retry_at'], name='webhook_del_status_idx'),
        ),
        
        # Dashboard Widget
        migrations.CreateModel(
            name='DashboardWidget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='组件名称')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='组件编码')),
                ('widget_type', models.CharField(choices=[('stat_card', '统计卡片'), ('line_chart', '折线图'), ('bar_chart', '柱状图'), ('pie_chart', '饼图'), ('table', '数据表格'), ('progress', '进度条'), ('list', '列表'), ('gauge', '仪表盘')], max_length=30, verbose_name='组件类型')),
                ('data_source', models.CharField(choices=[('project_stats', '项目统计'), ('sales_stats', '销售统计'), ('purchase_stats', '采购统计'), ('inventory_stats', '库存统计'), ('finance_stats', '财务统计'), ('ar_aging', '应收账龄'), ('ap_aging', '应付账龄'), ('cash_flow', '现金流'), ('project_profit', '项目利润'), ('inventory_turnover', '库存周转'), ('custom_sql', '自定义SQL'), ('api_endpoint', 'API接口')], max_length=30, verbose_name='数据源')),
                ('config', models.JSONField(default=dict, verbose_name='配置')),
                ('custom_query', models.TextField(blank=True, verbose_name='自定义查询')),
                ('default_width', models.IntegerField(default=6, verbose_name='默认宽度(1-12)')),
                ('default_height', models.IntegerField(default=200, verbose_name='默认高度(px)')),
                ('refresh_interval', models.IntegerField(default=300, verbose_name='刷新间隔(秒)')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('is_system', models.BooleanField(default=False, verbose_name='系统组件')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '仪表盘组件',
                'verbose_name_plural': '仪表盘组件',
                'db_table': 'dashboard_widget',
                'ordering': ['name'],
            },
        ),
        
        # User Dashboard
        migrations.CreateModel(
            name='UserDashboard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('layout', models.JSONField(default=list, verbose_name='布局配置')),
                ('theme', models.CharField(default='light', max_length=20, verbose_name='主题')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='dashboard', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户仪表盘',
                'verbose_name_plural': '用户仪表盘',
                'db_table': 'user_dashboard',
            },
        ),
    ]
