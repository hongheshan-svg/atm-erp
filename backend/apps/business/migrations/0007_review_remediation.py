import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def retain_originals(apps, schema_editor):
    projects = apps.get_model('business', 'Project')
    audits = apps.get_model('core', 'AuditLog')
    for project in projects.objects.filter(budget_materials__isnull=False).iterator():
        log = audits.objects.filter(operation='project.budget', resource=f'project:{project.pk}').order_by('-pk').first()
        if log:
            projects.objects.filter(pk=project.pk).update(budget_changed_by_id=log.actor_id)
    sales = apps.get_model('business', 'SalesOrder')
    sales.objects.filter(status='signed', original_contract_amount__isnull=True).update(original_contract_amount=models.F('contract_amount'))
    lines = apps.get_model('business', 'PurchaseLine')
    for line in lines.objects.filter(due_date__isnull=True).select_related('purchase').iterator():
        lines.objects.filter(pk=line.pk).update(due_date=line.purchase.due_date)


class Migration(migrations.Migration):
    dependencies = [('business', '0006_bom_classification'), ('core', '0003_code_configuration'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.RemoveConstraint(model_name='bomline', name='lean_live_bom_item'),
        migrations.AddConstraint(model_name='bomline', constraint=models.UniqueConstraint(condition=models.Q(is_deleted=False), fields=('project', 'item', 'assembly_unit'), name='lean_live_bom_unit')),
        migrations.AddField(model_name='payment', name='account', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='payment', name='reference', field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name='payment', name='method', field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name='payment', name='document', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='business.document')),
        migrations.AddField(model_name='project', name='budget_changed_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='project', name='forecast_revision', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='project', name='remaining_labor', field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
        migrations.AddField(model_name='project', name='remaining_expenses', field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
        migrations.AddField(model_name='purchaseline', name='due_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='purchaseline', name='pending_quantity', field=models.DecimalField(decimal_places=3, default=0, max_digits=18)),
        migrations.AddConstraint(model_name='purchaseline', constraint=models.CheckConstraint(condition=models.Q(pending_quantity__gte=0, quantity__gte=models.F('received_quantity') + models.F('cancelled_quantity') + models.F('pending_quantity')), name='lean_purchase_pending_limit')),
        migrations.AddField(model_name='salesorder', name='original_contract_amount', field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
        migrations.CreateModel(name='ContractAmendment', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('is_deleted', models.BooleanField(default=False)),
            ('deleted_at', models.DateTimeField(blank=True, null=True)),
            ('reason', models.CharField(max_length=500)),
            ('before', models.JSONField()), ('after', models.JSONField()), ('date', models.DateField()),
            ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ('document', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='business.document')),
            ('sale', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='amendments', to='business.salesorder')),
        ], options={'db_table': 'lean_contract_amendment', 'ordering': ['-id'], 'abstract': False}),
        migrations.RunPython(retain_originals),
    ]
