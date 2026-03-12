# Generated manually for permission system redesign

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_add_role_permission_data_scope'),
        ('accounts', '0005_migrate_role_to_roles_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='permissions_new',
            field=models.ManyToManyField(
                blank=True,
                help_text='通过 RolePermission 关联的结构化权限',
                related_name='roles',
                through='core.RolePermission',
                to='core.permission',
                verbose_name='权限列表'
            ),
        ),
    ]
