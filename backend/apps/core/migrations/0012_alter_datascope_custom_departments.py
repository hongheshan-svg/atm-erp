from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_alter_user_roles'),
        ('core', '0011_reconcile_datascope_m2m_table'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datascope',
            name='custom_departments',
            field=models.ManyToManyField(
                blank=True,
                help_text='仅当 scope_type 为 custom 时使用',
                related_name='custom_data_scopes',
                to='accounts.department',
                verbose_name='自定义部门',
            ),
        ),
    ]