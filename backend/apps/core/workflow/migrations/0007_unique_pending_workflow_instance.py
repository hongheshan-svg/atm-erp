from django.db import migrations, models
from django.utils import timezone


def close_duplicate_pending_instances(apps, schema_editor):
    WorkflowInstance = apps.get_model('workflow', 'WorkflowInstance')
    WorkflowTask = apps.get_model('workflow', 'WorkflowTask')
    duplicates = (
        WorkflowInstance.objects.filter(status='PENDING', is_deleted=False)
        .values('business_type', 'business_id')
        .annotate(total=models.Count('id'))
        .filter(total__gt=1)
    )
    for duplicate in duplicates:
        instances = WorkflowInstance.objects.filter(
            business_type=duplicate['business_type'],
            business_id=duplicate['business_id'],
            status='PENDING',
            is_deleted=False,
        ).order_by('submit_time', 'id')
        keep = instances.first()
        if keep:
            cancelled_ids = list(instances.exclude(pk=keep.pk).values_list('id', flat=True))
            now = timezone.now()
            WorkflowInstance.objects.filter(id__in=cancelled_ids).update(status='CANCELLED', completed_at=now)
            WorkflowTask.objects.filter(instance_id__in=cancelled_ids, status='PENDING').update(
                status='SKIPPED',
                action_time=now,
            )


class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0006_alter_workflowtask_status'),
    ]

    operations = [
        migrations.RunPython(close_duplicate_pending_instances, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='workflowinstance',
            constraint=models.UniqueConstraint(
                condition=models.Q(status='PENDING', is_deleted=False),
                fields=('business_type', 'business_id'),
                name='workflow_unique_pending_business',
            ),
        ),
    ]
