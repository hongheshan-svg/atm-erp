from django.db import migrations, models
from django.db.models import Max


def restore_business_dates(apps, schema_editor):
    Task = apps.get_model('business', 'Task')
    Delivery = apps.get_model('business', 'Delivery')
    alias = schema_editor.connection.alias
    # 仅从真实交付日期补齐；旧手动任务的完成点击时间不是实际完成日期，不推算。
    for task in Task.objects.using(alias).filter(status='done', is_deleted=False).iterator():
        dates = Delivery.objects.using(alias).filter(project_id=task.project_id, is_deleted=False)
        value = None
        if task.kind == 'acceptance' and task.delivery_id:
            value = dates.filter(pk=task.delivery_id).values_list('accepted_date', flat=True).first()
        elif task.milestone == 'shipping_dispatch':
            value = dates.aggregate(value=Max('shipped_date'))['value']
        elif task.milestone == 'site_acceptance' and not dates.filter(accepted_date__isnull=True).exists():
            value = dates.aggregate(value=Max('accepted_date'))['value']
        if value:
            Task.objects.using(alias).filter(pk=task.pk).update(completed_date=value)


class Migration(migrations.Migration):
    dependencies = [('business', '0023_task_co_assignees')]
    operations = [
        migrations.AddField(model_name='task', name='completed_date', field=models.DateField(blank=True, null=True)),
        migrations.RunPython(restore_business_dates, migrations.RunPython.noop),
    ]
