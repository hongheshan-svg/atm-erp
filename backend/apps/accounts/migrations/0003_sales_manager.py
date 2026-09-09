from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_management_reports')]
    operations = [
        migrations.RemoveConstraint(model_name='user', name='lean_fixed_role'),
        migrations.AlterField(model_name='user', name='role', field=models.CharField(
            choices=[('admin', '管理员'), ('manager', '项目经理'), ('sales_manager', '销售经理'),
                     ('purchaser', '采购'), ('warehouse', '仓库'), ('finance', '财务'), ('member', '成员')],
            default='member', max_length=20)),
        migrations.AddConstraint(model_name='user', constraint=models.CheckConstraint(
            condition=models.Q(role__in=['admin', 'manager', 'sales_manager', 'purchaser', 'warehouse', 'finance', 'member']),
            name='lean_fixed_role')),
    ]
