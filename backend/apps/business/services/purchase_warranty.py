from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import AuditLog
from apps.core.permissions import MONEY_READERS, PURCHASERS, WAREHOUSE, require_role

from ..models import Entry, PurchaseWarranty, StockMove
from .common import ZERO, audit, day, fields, lookup, number, save, text
from .supply import purchase_action


def warranty_end(receipt):
    start = receipt.received_date or timezone.localdate(receipt.created_at)
    try:
        return start.replace(year=start.year + 1)
    except ValueError:
        return start.replace(year=start.year + 1, day=28)


def listing(purchase):
    receipts = StockMove.objects.filter(purchase_line__purchase=purchase, kind='receipt').select_related('stock__item')
    cases = PurchaseWarranty.objects.filter(receipt__purchase_line__purchase=purchase).select_related(
        'receipt__stock__item'
    )
    return {
        'receipts': [
            {'id': r.pk, 'item': r.stock.item.name, 'quantity': str(r.quantity), 'warranty_end': warranty_end(r)}
            for r in receipts
        ],
        'cases': [
            {
                'id': c.pk,
                'receipt': c.receipt_id,
                'item': c.receipt.stock.item.name,
                'date': c.date,
                'quantity': str(c.quantity),
                'description': c.description,
                'status': c.get_status_display(),
                'response': c.response,
                'replacement': c.replacement_id,
                'returned': c.returned_id,
                'expense': c.expense_id,
                'updated_at': c.updated_at,
                'warranty_end': warranty_end(c.receipt),
                'within_warranty': c.date <= warranty_end(c.receipt),
                'history': list(
                    AuditLog.objects.filter(resource=f'purchasewarranty:{c.pk}').values(
                        'created_at', 'actor_id', 'operation', 'detail'
                    )
                ),
            }
            for c in cases
        ],
    }


def record(actor, key, purchase_id, data):
    def execute(user, purchase):
        if 'case' not in data:
            fields(data, {'receipt', 'date', 'quantity', 'description'})
            receipt = lookup(
                StockMove, data.get('receipt'), 'receipt', purchase_line__purchase=purchase, kind='receipt'
            )
            date = day(data, 'date')
            if not (receipt.received_date or timezone.localdate(receipt.created_at)) <= date <= timezone.localdate():
                raise ValidationError({'date': '报修日期应在实际收货日至今天之间。'})
            qty = number(data.get('quantity'), 'quantity', 3, positive=True)
            occupied = (
                PurchaseWarranty.objects.filter(receipt=receipt, status__in=['open', 'repairing']).aggregate(
                    total=Sum('quantity')
                )['total']
                or ZERO
            )
            if qty > receipt.quantity - occupied:
                raise Conflict('本批次待处理报修数量超过原收货数量，请先处理已有质保单。')
            case = save(
                PurchaseWarranty(receipt=receipt, date=date, quantity=qty, description=text(data, 'description')), user
            )
        else:
            fields(data, {'case', 'expected_updated_at', 'status', 'response', 'replacement', 'returned', 'expense'})
            case = lookup(PurchaseWarranty, data.get('case'), 'case', receipt__purchase_line__purchase=purchase)
            if str(case.updated_at.isoformat()).replace('+00:00', 'Z') != data.get('expected_updated_at'):
                raise Conflict('质保记录已变化，请刷新后重试。')
            if case.status in {'closed', 'replaced'}:
                raise Conflict('此质保事项已完成；再次故障请登记新的报修记录。')
            status = data.get('status')
            if status not in {'repairing', 'replaced', 'closed'}:
                raise ValidationError({'status': '请选择维修中、已更换或已关闭。'})
            case.status, case.response = status, text(data, 'response')
            if data.get('replacement'):
                case.replacement = lookup(
                    StockMove,
                    data['replacement'],
                    'replacement',
                    kind='receipt',
                    project=purchase.project,
                    stock__item=case.receipt.stock.item,
                    purchase_line__purchase__supplier=purchase.supplier,
                )
                replacement_date = case.replacement.received_date or timezone.localdate(case.replacement.created_at)
                allocated = (
                    PurchaseWarranty.objects.filter(replacement=case.replacement)
                    .exclude(pk=case.pk)
                    .aggregate(total=Sum('quantity'))['total']
                    or ZERO
                )
                if (
                    case.replacement.pk == case.receipt_id
                    or case.replacement.quantity - allocated < case.quantity
                    or replacement_date < case.date
                ):
                    raise ValidationError({'replacement': '请选择数量足够的实际补换货收货记录。'})
            if status == 'replaced' and not case.replacement_id:
                raise ValidationError({'replacement': '更换完成必须关联实际补换货收货流水。'})
            if data.get('returned'):
                case.returned = lookup(
                    StockMove, data['returned'], 'returned', kind='purchase_return', source=case.receipt
                )
            if data.get('expense'):
                require_role(user, MONEY_READERS)
                case.expense = lookup(
                    Entry, data['expense'], 'expense', kind='expense', project=purchase.project, cancelled=False
                )
            save(case, user)
        return audit(user, 'purchase.warranty', case, data=data)

    return purchase_action(actor, key, 'purchase.warranty', purchase_id, data, PURCHASERS | WAREHOUSE, execute)
