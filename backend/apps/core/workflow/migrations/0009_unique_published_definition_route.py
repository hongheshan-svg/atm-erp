from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def deactivate_duplicate_routes(apps, schema_editor):
    WorkflowDefinition = apps.get_model('workflow', 'WorkflowDefinition')
    duplicates = (
        WorkflowDefinition.objects.filter(is_active=True, is_deleted=False)
        .values('business_type', 'amount_threshold')
        .annotate(total=models.Count('id'))
        .filter(total__gt=1)
    )
    for duplicate in duplicates:
        definitions = WorkflowDefinition.objects.filter(
            business_type=duplicate['business_type'],
            amount_threshold=duplicate['amount_threshold'],
            is_active=True,
            is_deleted=False,
        ).order_by('created_at', 'id')
        keep = definitions.first()
        if keep:
            definitions.exclude(pk=keep.pk).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0008_workflow_event'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(deactivate_duplicate_routes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='workflowevent',
            name='actor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='workflow_events',
                to=settings.AUTH_USER_MODEL,
                verbose_name='操作人',
            ),
        ),
        migrations.AddConstraint(
            model_name='workflowdefinition',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True, is_deleted=False, amount_threshold__isnull=True),
                fields=('business_type',),
                name='workflow_unique_active_default',
            ),
        ),
        migrations.AddConstraint(
            model_name='workflowdefinition',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True, is_deleted=False, amount_threshold__isnull=False),
                fields=('business_type', 'amount_threshold'),
                name='workflow_unique_active_threshold',
            ),
        ),
    ]
