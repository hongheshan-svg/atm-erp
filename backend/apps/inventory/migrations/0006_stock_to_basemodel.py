import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0005_stockalertrule_stockalert_mrpplan_mrpline_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stock',
            name='last_updated',
        ),
        migrations.AddField(
            model_name='stock',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='创建时间'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='stock',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='更新时间'),
        ),
        migrations.AddField(
            model_name='stock',
            name='is_deleted',
            field=models.BooleanField(default=False, verbose_name='已删除'),
        ),
        migrations.AddField(
            model_name='stock',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='删除时间'),
        ),
        migrations.AddField(
            model_name='stock',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人'),
        ),
        migrations.AddField(
            model_name='stock',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人'),
        ),
    ]
