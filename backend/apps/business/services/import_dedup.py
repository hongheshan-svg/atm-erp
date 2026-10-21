"""Compare business content independently of file format, headers, filename or row order."""

import hashlib
import json
from decimal import Decimal

from apps.core.models import ActionReceipt

from ..models import Partner, Project
from .common import location_value
from .masterdata import normalized
from .payment_terms import terms


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def normalized_record(actor, resource, raw, people):
    from .transfers import payload

    data = payload(raw, dict(people or {}))
    data.pop('group', None)
    if resource == 'purchases':
        data['lines'] = [payload(line) for line in raw['lines']]
        data.update(terms(data, Partner.objects.get(pk=data['supplier'])))
    elif resource == 'partners':
        data.update(terms(data, Partner()))
    if resource in {'sales', 'projects'}:
        data.setdefault('equipment_quantity', '1')
        data.setdefault('warranty_months', '12')
    if resource == 'projects':
        data['members'] = sorted(set(data.get('members', [])))
    if resource == 'time':
        data.setdefault('user', actor.pk)
    if resource == 'deliveries':
        manager = Project.objects.get(pk=data['project']).manager_id
        data.setdefault('installer', manager)
        data.setdefault('acceptor', manager)
    if resource == 'stocks':
        data['location'] = location_value(data, allow_new=True)
    if resource == 'items':
        for key in ('name', 'specification', 'brand', 'unit'):
            if key in data:
                data[key] = normalized(data[key])

    numeric = {
        'amount',
        'quantity',
        'unit_cost',
        'unit_price',
        'hours',
        'equipment_quantity',
        'warranty_months',
        'payment_days',
        'stock',
        'task',
        'entry',
        'document',
        'reconciliation',
    }

    def canonical(row):
        return {
            key: str(Decimal(str(value)).normalize()) if key in numeric else value
            for key, value in row.items()
            if value not in ('', None)
        }

    if 'lines' in data:
        data['lines'] = sorted((canonical(line) for line in data['lines']), key=encoded)
    return canonical(data)


def content_digest(resource, records):
    return hashlib.sha256(
        encoded(
            {
                'resource': resource,
                'rows': sorted(
                    (record['normalized'] for record in records),
                    key=encoded,
                ),
            }
        ).encode()
    ).hexdigest()


def receipt_payload(digest):
    return {'content': digest}


def imported(resource, digest):
    fingerprint = hashlib.sha256(encoded(receipt_payload(digest)).encode()).hexdigest()
    return ActionReceipt.objects.filter(
        operation='import.' + resource, fingerprint=fingerprint, result__isnull=False
    ).exists()


DUPLICATE_MESSAGE = '相同业务归属和内容已成功导入。请先核对现有记录；确需再次新增，请明确确认再次导入。'
