# Generated manually for adding project relations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
        ('finance', '0007_invoice_item_model'),
    ]

    operations = [
        # Add project to AccountPayable
        migrations.AddField(
            model_name='accountpayable',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='payables',
                to='projects.project',
                verbose_name='项目'
            ),
        ),
        # Add project to Invoice
        migrations.AddField(
            model_name='invoice',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='invoices',
                to='projects.project',
                verbose_name='关联项目'
            ),
        ),
        # Add project to BankStatement
        migrations.AddField(
            model_name='bankstatement',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bank_statements',
                to='projects.project',
                verbose_name='关联项目'
            ),
        ),
    ]

