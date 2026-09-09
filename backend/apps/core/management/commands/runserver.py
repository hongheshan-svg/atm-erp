from django.core.management.commands.runserver import Command as DjangoRunserver

from apps.core.schema_guard import check_schema


class Command(DjangoRunserver):
    def inner_run(self, *args, **options):
        check_schema()
        return super().inner_run(*args, **options)
