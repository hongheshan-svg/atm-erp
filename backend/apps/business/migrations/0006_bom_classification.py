from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('business', '0005_contract_number')]
    operations = [
        migrations.AddField(model_name='item', name='brand', field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name='item', name='part_type', field=models.CharField(blank=True, choices=[('standard', '标准件'), ('custom', '非标件')], default='', max_length=20)),
        migrations.AddField(model_name='bomline', name='assembly_unit', field=models.CharField(blank=True, max_length=100)),
    ]
