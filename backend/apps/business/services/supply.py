from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import MANAGERS, PURCHASERS, WAREHOUSE

from ..models import BOMLine, Entry, Partner, PurchaseLine, PurchaseOrder, StockMove
from .bom import demand, incoming, issued
from .common import (
    ZERO,
    audit,
    day,
    fields,
    identity,
    lock_items,
    lock_stocks,
    lookup,
    number,
    project_action,
    rounded,
    rows,
    save,
    state,
    text,
)


def total(purchase):
    return sum((rounded(line.quantity * line.unit_price) for line in purchase.lines.all()), ZERO)


def create_purchase(actor, key, data):
    def execute(user, project):
        fields(data, {'project', 'supplier', 'due_date', 'note', 'lines', 'from_demand'})
        state(project, {'active', 'delivering', 'warranty'})
        supplier = lookup(Partner, data.get('supplier'), 'supplier', is_active=True, kind__in=['supplier', 'both'])
        from_demand = data.get('from_demand', False)
        if not isinstance(from_demand, bool):
            raise ValidationError({'from_demand': '必须为布尔值。'})
        prepared = {}
        for row in rows(data):
            fields(row, {'item', 'bom_line', 'quantity', 'unit_price'})
            item_id = identity(row.get('item'), 'item')
            if item_id in prepared:
                raise ValidationError('同一采购单不能重复添加同一物料。')
            prepared[item_id] = row
        items = lock_items(prepared)
        shortage = {row['item']: Decimal(row['shortage']) for row in demand(project)} if from_demand else {}
        purchase = save(
            PurchaseOrder(
                code=CodeRule.generate_code('purchase'),
                project=project,
                supplier=supplier,
                due_date=day(data, 'due_date'),
                note=text(data, 'note', default=''),
            ),
            user,
        )
        for item_id, row in prepared.items():
            if not items[item_id].is_active:
                raise ValidationError('已停用物料不能新建采购。')
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            price = number(row.get('unit_price'), 'unit_price')
            bom = None
            if row.get('bom_line') is not None:
                bom = lookup(BOMLine, row['bom_line'], 'bom_line', project=project, item_id=item_id)
                if qty > max(ZERO, bom.quantity - issued(project, item_id) - incoming(project, item_id)):
                    raise Conflict('采购数量超过当前 BOM 剩余需求，请刷新后重新确认。')
            if from_demand and (not bom or qty > shortage.get(item_id, ZERO)):
                raise Conflict('采购数量超过当前缺口，请刷新需求后重试。')
            number(rounded(qty * price), 'line_amount')
            save(
                PurchaseLine(purchase=purchase, item=items[item_id], bom_line=bom, quantity=qty, unit_price=price), user
            )
        number(total(purchase), 'total_amount')
        return audit(user, 'purchase.create', purchase)

    return project_action(actor, key, 'purchase.create', data.get('project'), data, PURCHASERS, execute)


def purchase_action(actor, key, operation, purchase_id, data, roles, execute):
    purchase = lookup(PurchaseOrder, purchase_id)

    def perform(user, project):
        current = get_object_or_404(PurchaseOrder.objects.select_for_update(), pk=purchase.pk, project=project)
        return execute(user, current)

    return project_action(
        actor, key, operation, purchase.project_id, {'purchase': purchase.pk, 'data': data}, roles, perform
    )


def submit(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, set())
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft'})
        if not purchase.lines.exists():
            raise ValidationError('采购单没有明细。')
        purchase.status = 'submitted'
        save(purchase, user)
        return audit(user, 'purchase.submit', purchase)

    return purchase_action(actor, key, 'purchase.submit', purchase_id, data, PURCHASERS, execute)


def approve(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, set())
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        save(
            Entry(
                project=purchase.project,
                purchase=purchase,
                kind='payable',
                title=f'采购 {purchase.code}',
                amount=total(purchase),
                due_date=purchase.due_date,
            ),
            user,
        )
        purchase.status = 'approved'
        save(purchase, user)
        return audit(user, 'purchase.approve', purchase)

    return purchase_action(actor, key, 'purchase.approve', purchase_id, data, MANAGERS, execute)


def receive(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'location', 'lines', 'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'approved', 'partial'})
        location = text(data, 'location', default='主仓', maximum=80)
        if not location:
            raise ValidationError({'location': '库位不能为空。'})
        reason = text(data, 'reason')
        lines = {line.pk: line for line in purchase.lines.select_for_update().order_by('item_id', 'pk')}
        selected = {}
        for row in rows(data):
            fields(row, {'line', 'quantity'})
            line_id = identity(row.get('line'), 'line')
            if line_id in selected or line_id not in lines:
                raise ValidationError('收货明细重复或不属于此采购单。')
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            line = lines[line_id]
            if qty > line.quantity - line.received_quantity - line.cancelled_quantity:
                raise Conflict('收货数量超过未收余量，请刷新后重试。')
            selected[line_id] = qty
        stocks = lock_stocks([lines[line_id].item_id for line_id in selected], location, user)
        for line_id, qty in selected.items():
            line = lines[line_id]
            value = rounded((line.received_quantity + qty) * line.unit_price) - rounded(
                line.received_quantity * line.unit_price
            )
            stock = stocks[line.item_id]
            stock.quantity += qty
            stock.value += value
            save(stock, user)
            save(
                StockMove(
                    stock=stock,
                    project=purchase.project,
                    purchase_line=line,
                    kind='receipt',
                    quantity=qty,
                    value=value,
                    reason=reason,
                ),
                user,
            )
            line.received_quantity += qty
            save(line, user)
        purchase.status = (
            'received'
            if all(line.received_quantity + line.cancelled_quantity == line.quantity for line in lines.values())
            else 'partial'
        )
        save(purchase, user)
        return audit(user, 'purchase.receive', purchase, lines={str(k): str(v) for k, v in selected.items()})

    return purchase_action(actor, key, 'purchase.receive', purchase_id, data, WAREHOUSE, execute)


def cancel_remainder(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'reason'})
        reason = text(data, 'reason')
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft', 'submitted', 'approved', 'partial'})
        lines = list(purchase.lines.select_for_update().order_by('item_id', 'pk'))
        credit = ZERO
        for line in lines:
            if line.quantity > line.received_quantity + line.cancelled_quantity:
                credit += rounded(line.quantity * line.unit_price) - rounded(line.received_quantity * line.unit_price)
                line.cancelled_quantity = line.quantity - line.received_quantity
                save(line, user)
        entry = Entry.objects.select_for_update().filter(purchase=purchase).first()
        if entry:
            entry.credit_amount += credit
            save(entry, user)
        purchase.status = 'received' if any(line.received_quantity for line in lines) else 'cancelled'
        save(purchase, user)
        return audit(user, 'purchase.cancel_remainder', purchase, credit=str(credit), reason=reason)

    return purchase_action(actor, key, 'purchase.cancel_remainder', purchase_id, data, PURCHASERS, execute)
