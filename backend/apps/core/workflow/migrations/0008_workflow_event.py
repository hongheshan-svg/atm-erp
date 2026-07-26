from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0007_unique_pending_workflow_instance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'event_type',
                    models.CharField(
                        choices=[
                            ('STARTED', '已发起'),
                            ('APPROVED', '已批准'),
                            ('REJECTED', '已拒绝'),
                            ('RETURNED', '已退回'),
                            ('WITHDRAWN', '已撤回'),
                            ('CANCELLED', '已取消'),
                        ],
                        max_length=20,
                        verbose_name='事件类型',
                    ),
                ),
                ('from_status', models.CharField(blank=True, max_length=20, verbose_name='原状态')),
                ('to_status', models.CharField(blank=True, max_length=20, verbose_name='新状态')),
                ('comment', models.TextField(blank=True, verbose_name='操作意见')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='事件数据')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='发生时间')),
                (
                    'actor',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='workflow_events',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='操作人',
                    ),
                ),
                (
                    'instance',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='events',
                        to='workflow.workflowinstance',
                        verbose_name='审批实例',
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='events',
                        to='workflow.workflowtask',
                        verbose_name='审批任务',
                    ),
                ),
            ],
            options={
                'verbose_name': '审批流事件',
                'verbose_name_plural': '审批流事件',
                'db_table': 'workflow_event',
                'ordering': ['created_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowevent',
            index=models.Index(fields=['instance', 'created_at'], name='workflow_ev_instanc_f7291b_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowevent',
            index=models.Index(fields=['actor', 'event_type'], name='workflow_ev_actor_i_177085_idx'),
        ),
    ]
