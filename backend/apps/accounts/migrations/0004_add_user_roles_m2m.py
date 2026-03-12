# Generated manually for permission system redesign

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_overtimerequest_leaverequest_attendanceconfig_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='roles',
            field=models.ManyToManyField(
                blank=True,
                help_text='支持多角色分配',
                related_name='users_m2m',
                to='accounts.role',
                verbose_name='角色列表'
            ),
        ),
    ]
