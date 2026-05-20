import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finance', '0014_accountcategory_chartofaccount_fiscalperiod_and_more'),
    ]

    operations = [
        # ExchangeRateHistory: previously had created_at, switch to BaseModel adds updated_at, soft delete, user tracking
        migrations.AddField(
            model_name='exchangeratehistory',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='更新时间'),
        ),
        migrations.AddField(
            model_name='exchangeratehistory',
            name='is_deleted',
            field=models.BooleanField(default=False, verbose_name='已删除'),
        ),
        migrations.AddField(
            model_name='exchangeratehistory',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='删除时间'),
        ),
        migrations.AddField(
            model_name='exchangeratehistory',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='创建人'),
        ),
        migrations.AddField(
            model_name='exchangeratehistory',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='更新人'),
        ),
    ]
