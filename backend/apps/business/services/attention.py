from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import F, Max, Q
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import Entry, PurchaseLine, Stock
from .payment_terms import due_entries, schedule, with_balances


def projection(params):
    view = params.get('view', 'cash30')
    today = timezone.localdate()
    rows = []
    if view in {'cash30', 'aging'}:
        entries = with_balances(Entry.objects.select_related('project')).annotate(
            remaining=F('amount') - F('credit_amount') - F('net_paid')
        )
        # Narrow in SQL with the same receipt/credit FIFO facts as schedule(), which still decides every row:
        # only entries with a batch due by the view's last day are loaded (with their receipts) at all.
        if view == 'aging':
            entries = due_entries(entries, today - timedelta(days=1))
        else:
            # A plain or manual-term entry has a single due date, so one already overdue has no batch in the window.
            entries = due_entries(entries, today + timedelta(days=30)).filter(
                Q(due_date__gte=today) | (Q(purchase__isnull=False) & ~Q(purchase__payment_term='manual'))
            )
        for entry in entries:
            for part in schedule(entry):
                due = part['due_date']
                if (view == 'cash30' and today <= due <= today + timedelta(days=30)) or (
                    view == 'aging' and due < today
                ):
                    days = (today - due).days
                    rows.append(
                        {
                            'id': entry.pk,
                            'source': entry.title,
                            'project': entry.project.name,
                            'date': str(due),
                            'amount': str(part['amount']),
                            'status': ('待收' if entry.kind == 'receivable' else '待付')
                            + (f' · 逾期 {days} 天' if days > 0 else ''),
                            'age_band': '1–30天'
                            if days <= 30
                            else '31–60天'
                            if days <= 60
                            else '61–90天'
                            if days <= 90
                            else '90天以上',
                        }
                    )
        definition = '按原应收应付的剩余到期批次列示，净付款先抵最早到期；采购未收货部分不计入到期，不含负余额退款。'
    elif view == 'late_purchase':
        for line in (
            PurchaseLine.objects.filter(
                purchase__status__in=['approved', 'partial'],
                quantity__gt=F('received_quantity') + F('cancelled_quantity') + F('pending_quantity'),
            )
            .alias(due=Coalesce('due_date', 'purchase__due_date'))
            .filter(due__lt=today)
            .select_related('purchase__project', 'item')
        ):
            due = line.due_date or line.purchase.due_date
            if due < today:
                rows.append(
                    {
                        'id': line.pk,
                        'source': f'{line.purchase.code} · {line.item.code} · {line.item.name}',
                        'project': line.purchase.project.name,
                        'date': str(due),
                        'amount': str(line.quantity - line.received_quantity - line.cancelled_quantity),
                        'status': f'未收数量 · 逾期 {(today - due).days} 天',
                    }
                )
        definition = '批准且未完成的采购明细，按最近维护的逐行承诺交期判断；数量包含待检隔离后尚未合格入库部分。'
    elif view == 'stale_stock':
        for stock in (
            Stock.objects.filter(quantity__gt=0)
            .annotate(last_move=Max('moves__created_at'))
            # Same local calendar day as below; recently moved balances never leave the database.
            .alias(last_day=TruncDate(Coalesce('last_move', 'created_at')))
            .filter(last_day__lte=today - timedelta(days=90))
            .select_related('item')
        ):
            last = timezone.localdate(stock.last_move or stock.created_at)
            if (today - last).days >= 90:
                rows.append(
                    {
                        'id': stock.pk,
                        'source': f'{stock.item.code} · {stock.item.name} · {stock.location}',
                        'project': '共享库存',
                        'date': str(last),
                        'amount': str(stock.quantity),
                        'status': f'{stock.item.unit} · {(today - last).days} 天无移动',
                    }
                )
        definition = '有库存且90天无库存移动的库位余额；这是呆滞候选，不等于不可用、减值或某项目专属库存。'
    else:
        raise ValidationError({'view': '未知报表视图。'})
    try:
        page, size = int(params.get('page', 1)), int(params.get('page_size', 10))
        if page < 1 or not 1 <= size <= 200:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError('页码及每页数量无效。')
    rows.sort(key=lambda r: (r['date'], r['id']))
    selected = Paginator(rows, size).get_page(page)
    return {'results': list(selected), 'count': len(rows), 'page': selected.number, 'definition': definition}
