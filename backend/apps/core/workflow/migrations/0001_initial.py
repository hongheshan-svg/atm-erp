# Generated migration for workflow models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('name', models.CharField(max_length=100, verbose_name='流程名称')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='流程编码')),
                ('business_type', models.CharField(choices=[('PURCHASE_REQUEST', '采购申请'), ('EXPENSE', '费用报销'), ('SALES_ORDER', '销售订单'), ('PROJECT', '项目立项'), ('STOCK_ADJUSTMENT', '库存调整')], max_length=30, verbose_name='业务类型')),
                ('description', models.TextField(blank=True, verbose_name='描述')),
                ('is_active', models.BooleanField(default=True, verbose_name='启用')),
                ('amount_threshold', models.DecimalField(blank=True, decimal_places=2, help_text='超过此金额时使用此流程', max_digits=15, null=True, verbose_name='金额阈值')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '审批流程定义',
                'verbose_name_plural': '审批流程定义',
                'db_table': 'workflow_definition',
                'ordering': ['business_type', 'amount_threshold'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('step_order', models.IntegerField(verbose_name='步骤顺序')),
                ('name', models.CharField(max_length=100, verbose_name='步骤名称')),
                ('approver_type', models.CharField(choices=[('USER', '指定用户'), ('ROLE', '指定角色'), ('DEPARTMENT_MANAGER', '部门经理'), ('PROJECT_MANAGER', '项目经理'), ('SUPERIOR', '直属上级')], default='USER', max_length=30, verbose_name='审批人类型')),
                ('action_type', models.CharField(choices=[('APPROVE', '审批'), ('REVIEW', '审核'), ('COUNTERSIGN', '会签')], default='APPROVE', max_length=20, verbose_name='操作类型')),
                ('timeout_hours', models.IntegerField(default=24, verbose_name='超时时间(小时)')),
                ('skip_amount_threshold', models.DecimalField(blank=True, decimal_places=2, help_text='低于此金额时跳过此步骤', max_digits=15, null=True, verbose_name='跳过金额阈值')),
                ('approver_role', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_steps', to='accounts.role', verbose_name='审批角色')),
                ('approver_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_steps', to=settings.AUTH_USER_MODEL, verbose_name='审批人')),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='workflow.workflowdefinition', verbose_name='所属流程')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '审批步骤',
                'verbose_name_plural': '审批步骤',
                'db_table': 'workflow_step',
                'ordering': ['workflow', 'step_order'],
                'unique_together': {('workflow', 'step_order')},
            },
        ),
        migrations.CreateModel(
            name='WorkflowInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('business_type', models.CharField(max_length=30, verbose_name='业务类型')),
                ('business_id', models.IntegerField(verbose_name='业务ID')),
                ('business_no', models.CharField(blank=True, max_length=50, verbose_name='业务单号')),
                ('submit_time', models.DateTimeField(auto_now_add=True, verbose_name='提交时间')),
                ('status', models.CharField(choices=[('PENDING', '审批中'), ('APPROVED', '已通过'), ('REJECTED', '已拒绝'), ('CANCELLED', '已取消'), ('WITHDRAWN', '已撤回')], default='PENDING', max_length=20, verbose_name='状态')),
                ('current_step', models.IntegerField(default=1, verbose_name='当前步骤')),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, verbose_name='金额')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('submitter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='submitted_workflows', to=settings.AUTH_USER_MODEL, verbose_name='提交人')),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='instances', to='workflow.workflowdefinition', verbose_name='流程定义')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '审批实例',
                'verbose_name_plural': '审批实例',
                'db_table': 'workflow_instance',
                'ordering': ['-submit_time'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['business_type', 'business_id'], name='workflow_in_busines_a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['status', 'submitter'], name='workflow_in_status_d4e5f6_idx'),
        ),
        migrations.CreateModel(
            name='WorkflowTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('status', models.CharField(choices=[('PENDING', '待处理'), ('APPROVED', '已通过'), ('REJECTED', '已拒绝'), ('SKIPPED', '已跳过'), ('TIMEOUT', '已超时')], default='PENDING', max_length=20, verbose_name='状态')),
                ('action_time', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                ('comment', models.TextField(blank=True, verbose_name='审批意见')),
                ('deadline', models.DateTimeField(blank=True, null=True, verbose_name='截止时间')),
                ('assignee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='workflow_tasks', to=settings.AUTH_USER_MODEL, verbose_name='处理人')),
                ('instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='workflow.workflowinstance', verbose_name='审批实例')),
                ('step', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tasks', to='workflow.workflowstep', verbose_name='审批步骤')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人')),
            ],
            options={
                'verbose_name': '审批任务',
                'verbose_name_plural': '审批任务',
                'db_table': 'workflow_task',
                'ordering': ['instance', 'step__step_order'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowtask',
            index=models.Index(fields=['assignee', 'status'], name='workflow_ta_assigne_g7h8i9_idx'),
        ),
    ]
