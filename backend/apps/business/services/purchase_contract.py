"""Printable purchase agreement projected from the current order, without a second ledger."""

from django.utils import timezone

from apps.core.models import Company
from apps.core.permissions import MONEY_READERS, PURCHASERS, require_role

from .common import ZERO, rounded
from .supply import total


def preview(actor, purchase):
    require_role(actor, MONEY_READERS | PURCHASERS)
    company = Company.objects.first()
    supplier = purchase.supplier
    lines = list(purchase.lines.all())
    cancelled = sum((rounded(line.cancelled_quantity * line.unit_price) for line in lines), ZERO)
    return {
        'id': purchase.pk,
        'code': purchase.code,
        'status': purchase.status,
        'status_label': purchase.get_status_display(),
        'draft': purchase.status in {'draft', 'submitted'},
        'date': timezone.localdate(purchase.created_at),
        'updated_at': purchase.updated_at,
        'project': purchase.project.name,
        'buyer': {
            'name': company.name if company else '',
            'address': company.address if company else '',
            'phone': company.phone if company else '',
        },
        'supplier': {
            'name': supplier.name,
            'address': supplier.address,
            'contact': supplier.contact,
            'phone': supplier.phone,
        },
        'due_date': purchase.due_date,
        'payment_term': purchase.payment_term,
        'payment_days': purchase.payment_days,
        'payment_due_date': purchase.payment_due_date or purchase.due_date
        if purchase.payment_term == 'manual'
        else None,
        'note': purchase.note,
        'total': str(total(purchase)),
        'cancelled_amount': str(cancelled),
        'lines': [
            {
                'number': index,
                'code': line.item.code,
                'name': line.item.name,
                'specification': line.item.specification,
                'brand': line.item.brand,
                'unit': line.item.unit,
                'quantity': str(line.quantity),
                'unit_price': str(line.unit_price),
                'amount': str(rounded(line.quantity * line.unit_price)),
                'due_date': line.due_date or purchase.due_date,
                'cancelled_quantity': str(line.cancelled_quantity),
            }
            for index, line in enumerate(lines, 1)
        ],
    }
