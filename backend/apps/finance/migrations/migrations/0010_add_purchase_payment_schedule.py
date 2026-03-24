# Generated manually for PurchasePaymentSchedule model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0001_initial'),
        ('projects', '0001_initial'),
        ('finance', '0009_add_payment_schedule'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchasePaymentSchedule',
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
                        ('ON_DELIVERY', '到货款'),
                        ('ON_INSPECTION', '验收款'),
                        ('FINAL', '尾款'),
                        ('PROGRESS', '进度款'),
                        ('CUSTOM', '自定义'),
                    ],
                    default='CUSTOM',
                    max_length=20,
                    verbose_name='付款节点类型'
                )),
                ('milestone_name', models.CharField(max_length=100, verbose_name='付款节点名称')),
                ('milestone_order', models.IntegerField(default=1, verbose_name='节点顺序')),
                ('percentage', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='付款比例(%)')),
                ('amount_due', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='应付金额')),
                ('amount_paid', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='已付金额')),
                ('due_date', models.DateField(verbose_name='计划付款日期')),
                ('actual_paid_date', models.DateField(blank=True, null=True, verbose_name='实际付款日期')),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', '待付款'),
                        ('PARTIAL', '部分付款'),
                        ('PAID', '已付款'),
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
                        ('PAID', '已付款'),
                    ],
                    default='PENDING',
                    max_length=20,
                    verbose_name='提醒状态'
                )),
                ('reminder_days_before', models.IntegerField(default=3, verbose_name='提前提醒天数')),
                ('last_reminded_at', models.DateTimeField(blank=True, null=True, verbose_name='最后提醒时间')),
                ('notes', models.TextField(blank=True, verbose_name='备注')),
                ('purchase_order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_schedules',
                    to='purchase.purchaseorder',
                    verbose_name='采购订单'
                )),
                ('project', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='purchase_payment_schedules',
                    to='projects.project',
                    verbose_name='项目'
                )),
                ('account_payable', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payment_schedules',
                    to='finance.accountpayable',
                    verbose_name='关联应付账款'
                )),
            ],
            options={
                'verbose_name': '采购付款计划',
                'verbose_name_plural': '采购付款计划',
                'db_table': 'purchase_payment_schedule',
                'ordering': ['purchase_order', 'milestone_order'],
            },
        ),
        migrations.AddIndex(
            model_name='purchasepaymentschedule',
            index=models.Index(fields=['purchase_order', 'milestone_order'], name='pps_po_order_idx'),
        ),
        migrations.AddIndex(
            model_name='purchasepaymentschedule',
            index=models.Index(fields=['status', 'due_date'], name='pps_status_idx'),
        ),
        migrations.AddIndex(
            model_name='purchasepaymentschedule',
            index=models.Index(fields=['reminder_status', 'due_date'], name='pps_remind_idx'),
        ),
    ]

