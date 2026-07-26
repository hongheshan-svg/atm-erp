from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0023_alter_accountpayable_ap_no_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='journalvoucher',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False) & ~models.Q(source_type='') & models.Q(source_id__isnull=False),
                fields=('source_type', 'source_id'),
                name='uq_journal_voucher_source_active',
            ),
        ),
    ]
