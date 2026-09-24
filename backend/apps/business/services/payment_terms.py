"""Receipt facts determine maturity; no second editable payable ledger."""

import calendar
from collections import defaultdict
from datetime import timedelta

from django.db.models import Case, DateField, DecimalField, F, Func, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Cast, Coalesce, Greatest, TruncDate
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import PaymentTerm, StockMove
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
    if not entry.purchase_id:
        return [{'due_date': entry.due_date, 'amount': remaining}] if remaining else []
    purchase = entry.purchase
    # 指定日期账期也只对已合格收货的部分到期：未到货的货款付不出去（普通对账额度以收货净额为限），
    # 算进到期或逾期只会让报表和工作台提示一笔无法办理的应付。
    manual = purchase.payment_term == 'manual'
    moves = [move for line in purchase.lines.all() for move in line.stockmove_set.all()]
    credits = defaultdict(lambda: ZERO)
    for move in moves:
        if move.kind == 'purchase_return':
            credits[move.source_id] += move.supplier_credit
    buckets = defaultdict(lambda: ZERO)
    for move in moves:
        if move.kind == 'receipt':
            received = move.received_date or timezone.localdate(move.created_at)
            maturity = entry.due_date if manual else due_date(received, purchase.payment_term, purchase.payment_days)
            buckets[maturity] += max(ZERO, move.value - credits[move.pk])
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


def with_balances(queryset):
    """带上净收付并在数据库里筛掉已结清的款项。

    余额为零的款项既不产生到期批次也不进入余额汇总；不先筛掉的话，报表和关注视图
    会把历史上每一张早已结清的单据都拉进内存，而且 paid() 缺少注解时每条还要再查一次。
    """
    money = DecimalField(max_digits=18, decimal_places=2)
    return (
        with_sources(queryset)
        .annotate(net_paid=Coalesce(Sum('payments__amount'), Value(ZERO), output_field=money))
        .exclude(amount=F('credit_amount') + F('net_paid'))
    )


def due_entries(queryset, today):
    """Filter maturity before pagination, using the same receipt/credit FIFO facts as schedule."""
    money = DecimalField(max_digits=18, decimal_places=2)
    credits = (
        StockMove.objects.filter(kind='purchase_return', source_id=OuterRef('pk'))
        .order_by()
        .values('source_id')
        .annotate(total=Sum('supplier_credit'))
        .values('total')
    )
    base = (
        StockMove.objects.filter(kind='receipt', purchase_line__purchase_id=OuterRef('purchase_id'))
        .annotate(
            received=Coalesce('received_date', TruncDate('created_at')),
            returned_credit=Coalesce(Subquery(credits), Value(ZERO), output_field=money),
        )
        .annotate(
            maturity=Case(
                When(purchase_line__purchase__payment_term='cash', then=F('received')),
                default=Cast(
                    Func(
                        F('received'),
                        template="(date_trunc('month', %(expressions)s) + interval '1 month - 1 day')",
                        output_field=DateField(),
                    )
                    + F('purchase_line__purchase__payment_days') * Value(timedelta(days=1)),
                    DateField(),
                ),
                output_field=DateField(),
            ),
            net_value=Greatest(Value(ZERO), F('value') - F('returned_credit'), output_field=money),
        )
        .order_by()
    )

    def total(receipts):
        return Coalesce(
            Subquery(receipts.values('purchase_line__purchase_id').annotate(total=Sum('net_value')).values('total')),
            Value(ZERO),
            output_field=money,
        )

    manual = Q(purchase__payment_term='manual')
    return queryset.annotate(matured=total(base.filter(maturity__lte=today)), received_net=total(base)).filter(
        Q(remaining__lt=0)
        | (
            Q(remaining__gt=0)
            & (
                (Q(purchase__isnull=True) & Q(due_date__lte=today))
                | (manual & Q(due_date__lte=today) & Q(received_net__gt=F('net_paid')))
                | (~manual & Q(purchase__isnull=False) & Q(matured__gt=F('net_paid')))
            )
        )
    )
