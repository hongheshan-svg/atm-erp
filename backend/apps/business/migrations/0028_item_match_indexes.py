from django.contrib.postgres.indexes import HashIndex
from django.db import migrations, models
from django.db.models import CharField, Func, Value
from django.db.models.functions import Lower

FULLWIDTH = ''.join(chr(i) for i in range(0xFF01, 0xFF5F)) + '　'
HALFWIDTH = ''.join(chr(i) for i in range(0x21, 0x7F)) + ' '


def comparison(field):
    # 冻结的 business.models.comparison_expression：物料查重查询正是按这个表达式等值比较。
    translated = Func(field, Value(FULLWIDTH), Value(HALFWIDTH), function='TRANSLATE', output_field=CharField())
    return Lower(
        Func(
            translated,
            Value('[[:space:]]+'),
            Value(''),
            Value('g'),
            function='REGEXP_REPLACE',
            output_field=CharField(),
        )
    )


class Migration(migrations.Migration):
    dependencies = [('business', '0027_issue_slip')]
    operations = [
        # 旧索引的 LOWER(TRIM(name)) 没有任何查询使用，只增加写入开销。
        migrations.RemoveIndex(model_name='item', name='lean_item_name_key'),
        migrations.AddIndex(model_name='item', index=models.Index(comparison('name'), name='lean_item_name_match')),
        migrations.AddIndex(
            model_name='item', index=HashIndex(comparison('specification'), name='lean_item_spec_match')
        ),
    ]
