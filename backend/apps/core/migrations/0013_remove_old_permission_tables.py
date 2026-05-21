"""
删除旧的权限配置表（已被 Permission/RolePermission/DataScope 替代）
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_alter_datascope_custom_departments'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS role_module_permission CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS module_permission_rule CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
