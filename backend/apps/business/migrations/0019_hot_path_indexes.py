from django.db import migrations, models
from django.db.models.functions import Lower, Trim


class Migration(migrations.Migration):
    dependencies = [('business', '0018_product_coding_bom_dates')]
    operations = [
        migrations.AddIndex(model_name='item', index=models.Index(Lower(Trim('name')), name='lean_item_name_key')),
        migrations.AddIndex(
            model_name='item',
            index=models.Index(Lower('drawing_number'), Lower('drawing_revision'), name='lean_item_drawing_key'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                condition=models.Q(('is_deleted', False)),
                fields=['project', 'assignee', 'status'],
                name='lean_task_todo',
            ),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(
                condition=models.Q(('is_deleted', False)), fields=['project', 'kind', 'status'], name='lean_task_stage'
            ),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(
                condition=models.Q(('is_deleted', False)), fields=['project', 'kind'], name='lean_move_project_kind'
            ),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(
                condition=models.Q(('is_deleted', False)), fields=['stock', 'kind'], name='lean_move_stock_kind'
            ),
        ),
        migrations.AddIndex(
            model_name='entry',
            index=models.Index(
                condition=models.Q(('is_deleted', False)),
                fields=['project', 'kind', 'cancelled'],
                name='lean_entry_project_kind',
            ),
        ),
        migrations.AddIndex(
            model_name='timeentry',
            index=models.Index(
                condition=models.Q(('is_deleted', False)), fields=['user', 'date'], name='lean_time_user_date'
            ),
        ),
        migrations.AddIndex(
            model_name='purchaseorder',
            index=models.Index(
                condition=models.Q(('is_deleted', False)),
                fields=['project', 'status'],
                name='lean_purchase_project_status',
            ),
        ),
    ]
