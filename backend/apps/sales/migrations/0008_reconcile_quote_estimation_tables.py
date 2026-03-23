from django.db import migrations


QUOTE_MODELS_IN_ORDER = [
    'CostCategory',
    'LaborRate',
    'QuoteEstimation',
    'ProjectCostHistory',
    'EstimationMaterialItem',
    'EstimationLaborItem',
    'EstimationOutsourceItem',
    'EstimationOtherCost',
]


def create_missing_quote_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    for model_name in QUOTE_MODELS_IN_ORDER:
        model = apps.get_model('sales', model_name)
        if model._meta.db_table in existing_tables:
            continue
        schema_editor.create_model(model)
        existing_tables.add(model._meta.db_table)


def drop_quote_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())
    for model_name in reversed(QUOTE_MODELS_IN_ORDER):
        model = apps.get_model('sales', model_name)
        if model._meta.db_table not in existing_tables:
            continue
        schema_editor.delete_model(model)
        existing_tables.discard(model._meta.db_table)


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0007_costcategory_customerportalaccount_and_more'),
    ]

    operations = [
        migrations.RunPython(create_missing_quote_tables, drop_quote_tables),
    ]
