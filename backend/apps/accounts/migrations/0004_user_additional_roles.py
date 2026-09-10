from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0003_sales_manager')]
    operations = [
        migrations.AddField(
            model_name='user', name='additional_roles',
            field=ArrayField(models.CharField(max_length=20, choices=[
                ('admin', '管理员'), ('manager', '项目经理'), ('sales_manager', '销售经理'),
                ('purchaser', '采购'), ('warehouse', '仓库'), ('finance', '财务'), ('member', '成员'),
            ]), default=list, blank=True, size=None),
        ),
    ]
