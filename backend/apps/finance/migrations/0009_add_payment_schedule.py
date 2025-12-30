# Generated manually for PaymentSchedule model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
        ('projects', '0001_initial'),
        ('finance', '0008_add_project_relations'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('schedule_no', models.CharField(max_length=50, unique=True, verbose_name='计划编号')),
                ('milestone_type', models.CharField(
                    choices=[
                        ('PREPAY', '预付款'),
                        ('ON_DELIVERY', '发货款'),
                        ('ON_ACCEPTANCE', '验收款'),
                        ('WARRANTY', '质保金'),
                        ('PROGRESS', '进度款'),
                        ('FINAL', '尾款'),
                        ('CUSTOM', '自定义'),
                    ],
                    default='CUSTOM',
                    max_length=20,
                    verbose_name='付款节点类型'
                )),
                ('milestone_name', models.CharField(max_length=100, verbose_name='付款节点名称')),
                ('milestone_order', models.IntegerField(default=1, verbose_name='节点顺序')),
                ('percentage', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='付款比例(%)')),
                ('amount_due', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='应收金额')),
                ('amount_paid', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='已收金额')),
                ('due_date', models.DateField(verbose_name='计划收款日期')),
                ('actual_paid_date', models.DateField(blank=True, null=True, verbose_name='实际收款日期')),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', '待收款'),
                        ('PARTIAL', '部分收款'),
                        ('PAID', '已收款'),
                        ('OVERDUE', '已逾期'),
                        ('CANCELLED', '已取消'),
                    ],
                    default='PENDING',
                    max_length=20,
                    verbose_name='状态'
                )),
                ('reminder_status', models.CharField(
                    choices=[
                        ('NONE', '无需提醒'),
                        ('PENDING', '待提醒'),
                        ('REMINDED', '已提醒'),
                        ('COLLECTED', '已收款'),
                    ],
                    default='PENDING',
                    max_length=20,
                    verbose_name='提醒状态'
                )),
                ('reminder_days_before', models.IntegerField(default=7, verbose_name='提前提醒天数')),
                ('last_reminded_at', models.DateTimeField(blank=True, null=True, verbose_name='最后提醒时间')),
                ('notes', models.TextField(blank=True, verbose_name='备注')),
                ('sales_order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_schedules',
                    to='sales.salesorder',
                    verbose_name='销售订单'
                )),
                ('project', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payment_schedules',
                    to='projects.project',
                    verbose_name='项目'
                )),
                ('account_receivable', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payment_schedules',
                    to='finance.accountreceivable',
                    verbose_name='关联应收账款'
                )),
            ],
            options={
                'verbose_name': '付款计划',
                'verbose_name_plural': '付款计划',
                'db_table': 'payment_schedule',
                'ordering': ['sales_order', 'milestone_order'],
            },
        ),
        migrations.AddIndex(
            model_name='paymentschedule',
            index=models.Index(fields=['sales_order', 'milestone_order'], name='payment_sch_sales_o_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentschedule',
            index=models.Index(fields=['status', 'due_date'], name='payment_sch_status_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentschedule',
            index=models.Index(fields=['reminder_status', 'due_date'], name='payment_sch_remind_idx'),
        ),
    ]

