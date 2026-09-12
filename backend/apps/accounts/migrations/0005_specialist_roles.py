from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models

ROLE_CHOICES = [
    ('admin', '管理员'),
    ('manager', '项目经理'),
    ('sales_manager', '销售经理'),
    ('purchase_manager', '采购经理'),
    ('purchaser', '采购员'),
    ('warehouse', '仓管'),
    ('finance', '财务'),
    ('mechanical_engineer', '机械工程师'),
    ('electrical_engineer', '电气工程师'),
    ('member', '普通成员'),
]


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_user_additional_roles')]
    operations = [
        migrations.RemoveConstraint(model_name='user', name='lean_fixed_role'),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=ROLE_CHOICES, default='member', max_length=20),
        ),
        migrations.AlterField(
            model_name='user',
            name='additional_roles',
            field=ArrayField(
                models.CharField(choices=ROLE_CHOICES, max_length=20), default=list, blank=True, size=None
            ),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                condition=models.Q(role__in=[value for value, _ in ROLE_CHOICES]), name='lean_fixed_role'
            ),
        ),
    ]
