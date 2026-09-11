from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0006_company_setup')]
    operations = [
        migrations.AddField(model_name='coderule', name='product_counters', field=models.JSONField(default=dict, editable=False)),
        migrations.AlterField(model_name='coderule', name='date_format', field=models.CharField(blank=True, choices=[('', '无日期'), ('YY', '两位年'), ('YYYY', '年'), ('YYYYMM', '年月'), ('YYYYMMDD', '年月日')], default='', max_length=8)),
    ]
