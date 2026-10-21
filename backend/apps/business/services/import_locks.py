"""Acquire a whole batch's shared resources before any row starts writing."""

from django.db import connection

from apps.accounts.models import User
from apps.core.periods import mutation_lock

from ..models import Entry, Item, Project, Stock, Task


def ids(values):
    return {int(value) for value in values if str(value).isdigit() and 0 < int(value) <= 9223372036854775807}


def batch_projects(resource, records):
    rows = [record['data'] for record in records]
    if resource == 'payments':
        return Project.objects.filter(
            pk__in=Entry.objects.filter(pk__in=ids(r.get('entry') for r in rows)).values('project_id')
        )
    if resource == 'time':
        return Project.objects.filter(
            pk__in=Task.objects.filter(pk__in=ids(r.get('task') for r in rows)).values('project_id')
        )
    return Project.objects.filter(code__in=[row['project'] for row in rows if row.get('project')])


def lock_batch(actor, resource, records):
    # Match single-action ordering: accounting period -> all projects -> all items / people.
    # Sorting rows alone is insufficient: a prior row can retain an item/person lock
    # while a later row waits for a project held by a single-project writer.
    mutation_lock()
    projects = list(batch_projects(resource, records).order_by('pk').select_for_update())
    rows = [record['data'] for record in records]
    item_ids = set()
    if resource == 'moves':
        item_ids.update(
            Stock.objects.filter(pk__in=ids(r.get('stock') for r in rows)).values_list('item_id', flat=True)
        )
    elif resource in {'stocks', 'purchases'}:
        lines = [line for row in rows for line in row.get('lines', [])] if resource == 'purchases' else rows
        item_ids.update(Item.objects.filter(code__in=[r.get('item') for r in lines]).values_list('pk', flat=True))
    list(Item.objects.filter(pk__in=item_ids).order_by('pk').select_for_update())
    if resource == 'time':
        from .transfers import resolve_person

        people = set()
        for row in rows:
            # Invalid references stay row-level errors in the ordinary service validation.
            from rest_framework.exceptions import ValidationError

            try:
                people.add(resolve_person(row['user']) if row.get('user') else actor.pk)
            except ValidationError:
                continue
        # Serialize daily totals/rate changes, while permitting deferred actor/audit
        # foreign-key KEY SHARE checks. Inner time services must keep this lock mode.
        list(User.objects.filter(pk__in=people).order_by('pk').select_for_update(no_key=True))
    return projects


def lock_content(digest):
    # A transaction-scoped cross-user mutex; successful ActionReceipts are the durable evidence.
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [int.from_bytes(bytes.fromhex(digest[:16]), signed=True)])
