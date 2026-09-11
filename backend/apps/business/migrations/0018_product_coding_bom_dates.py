from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0017_entry_cancellation_credit')]
    operations = [
        migrations.AddField(model_name='bomline', name='applicant', field=models.CharField(blank=True, default='', max_length=80)),
        migrations.AddField(model_name='bomline', name='application_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='bomline', name='required_date', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='item', name='drawing_number', field=models.CharField(blank=True, default='', max_length=100)),
        migrations.AddField(model_name='item', name='drawing_revision', field=models.CharField(blank=True, default='', max_length=30)),
        migrations.AddField(model_name='item', name='product_category', field=models.CharField(blank=True, choices=[('11', '有图·机加'), ('12', '有图·钣金'), ('13', '有图·特殊工艺'), ('19', '有图·其它'), ('21', '无图·标准件'), ('22', '无图·耗材辅料'), ('23', '无图·办公用品'), ('29', '无图·其它')], default='', max_length=2)),
        migrations.AlterField(model_name='item', name='specification', field=models.CharField(blank=True, max_length=2000)),
    ]
