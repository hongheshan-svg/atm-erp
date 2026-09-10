from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import F, Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import Entry, PurchaseLine, Stock
from .payment_terms import schedule, with_sources


def projection(params):
    view = params.get('view', 'cash30')
    today = timezone.localdate()
    rows = []
    if view in {'cash30', 'aging'}:
        for entry in with_sources(Entry.objects.select_related('project')).prefetch_related('payments'):
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
        definition = (
            '按原应收应付的剩余到期批次列示，净付款先抵最早到期；未收货自动账期采购不预估日期，不含负余额退款。'
        )
    elif view == 'late_purchase':
        for line in PurchaseLine.objects.filter(
            purchase__status__in=['approved', 'partial'], quantity__gt=F('received_quantity') + F('cancelled_quantity')
        ).select_related('purchase__project', 'item'):
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
            Stock.objects.filter(quantity__gt=0).annotate(last_move=Max('moves__created_at')).select_related('item')
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
