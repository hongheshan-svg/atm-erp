from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0003_sales_order')]
    operations = [
        migrations.AddField(model_name='project', name='budget_materials',
                            field=models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name='project', name='budget_labor',
                            field=models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name='project', name='budget_expenses',
                            field=models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name='project', name='budget_revision', field=models.PositiveIntegerField(default=0)),
        migrations.AddConstraint(model_name='project', constraint=models.CheckConstraint(
            condition=models.Q(budget_materials__isnull=True, budget_labor__isnull=True, budget_expenses__isnull=True)
            | models.Q(budget_materials__isnull=False, budget_materials__gte=0, budget_labor__isnull=False,
                       budget_labor__gte=0, budget_expenses__isnull=False, budget_expenses__gte=0),
            name='lean_project_budget_valid')),
    ]
