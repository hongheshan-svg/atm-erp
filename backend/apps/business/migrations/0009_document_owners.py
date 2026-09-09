import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0008_operational_review')]
    operations = [
        migrations.AlterField(
            model_name='document',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='business.project',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='sale',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='business.salesorder',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='purchase',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='documents',
                to='business.purchaseorder',
            ),
        ),
        migrations.AddConstraint(
            model_name='document',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(project__isnull=False, sale__isnull=True, purchase__isnull=True)
                    | models.Q(project__isnull=True, sale__isnull=False, purchase__isnull=True)
                    | models.Q(project__isnull=True, sale__isnull=True, purchase__isnull=False)
                ),
                name='lean_document_one_owner',
            ),
        ),
    ]
