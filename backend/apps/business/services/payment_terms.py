"""Receipt facts determine maturity; no second editable payable ledger."""

import calendar
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import PaymentTerm
from .common import ZERO


def terms(data, source):
    term = data.get('payment_term') or source.payment_term
    if term not in PaymentTerm.values:
        raise ValidationError({'payment_term': '请选择有效采购账期。'})
    raw = data.get('payment_days')
    raw = source.payment_days if raw in (None, '') else raw
    if isinstance(raw, bool) or not str(raw).isdigit() or not 0 <= int(raw) <= 365:
        raise ValidationError({'payment_days': '月结天数须为0到365的整数。'})
    days = int(raw) if term == 'custom' else int(term[5:]) if term.startswith('month') else 0
    return {'payment_term': term, 'payment_days': days}


def due_date(received, term, days):
    if term == 'cash':
        return received
    return received.replace(day=calendar.monthrange(received.year, received.month)[1]) + timedelta(days=days)


def schedule(entry):
    from .finance import balance, paid

    remaining = max(ZERO, balance(entry))
    if not entry.purchase_id or entry.purchase.payment_term == 'manual':
        return [{'due_date': entry.due_date, 'amount': remaining}] if remaining else []
    purchase = entry.purchase
    moves = [move for line in purchase.lines.all() for move in line.stockmove_set.all()]
    credits = defaultdict(lambda: ZERO)
    for move in moves:
        if move.kind == 'purchase_return':
            credits[move.source_id] += move.supplier_credit
    buckets = defaultdict(lambda: ZERO)
    for move in moves:
        if move.kind == 'receipt':
            received = move.received_date or timezone.localdate(move.created_at)
            buckets[due_date(received, purchase.payment_term, purchase.payment_days)] += max(
                ZERO, move.value - credits[move.pk]
            )
    offset = max(ZERO, paid(entry))
    result = []
    for date, amount in sorted(buckets.items()):
        consumed = min(offset, amount)
        offset -= consumed
        amount = min(remaining, amount - consumed)
        if amount > ZERO:
            result.append({'due_date': date, 'amount': amount})
            remaining -= amount
    return result


def next_due(entry):
    rows = schedule(entry)
    return rows[0]['due_date'] if rows else None


def due_amount(entry, today, *, inclusive=False):
    return sum(
        (r['amount'] for r in schedule(entry) if r['due_date'] < today or (inclusive and r['due_date'] == today)), ZERO
    )


def with_sources(queryset):
    return queryset.select_related('purchase').prefetch_related('purchase__lines__stockmove_set')
