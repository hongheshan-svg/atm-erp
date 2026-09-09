from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0002_schema_generation')]
    operations = [
        migrations.AddField(model_name='coderule', name='date_format', field=models.CharField(blank=True, choices=[('', '无日期'), ('YYYY', '年'), ('YYYYMM', '年月'), ('YYYYMMDD', '年月日')], default='', max_length=8)),
        migrations.AddField(model_name='coderule', name='padding', field=models.PositiveSmallIntegerField(default=6)),
        migrations.AddField(model_name='coderule', name='reset_cycle', field=models.CharField(choices=[('never', '不重置'), ('year', '每年'), ('month', '每月'), ('day', '每天')], default='never', max_length=5)),
        migrations.AddField(model_name='coderule', name='period', field=models.CharField(blank=True, default='', max_length=8)),
        migrations.AddField(model_name='coderule', name='revision', field=models.PositiveIntegerField(default=0)),
    ]
