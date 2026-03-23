from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_add_role_permissions_m2m'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(
                blank=True,
                db_table='user_roles',
                help_text='支持多角色分配',
                related_name='users_m2m',
                to='accounts.role',
                verbose_name='角色列表',
            ),
        ),
    ]