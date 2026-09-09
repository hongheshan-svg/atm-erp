from decimal import ROUND_CEILING, Decimal

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.permissions import ADMIN, WAREHOUSE, require_role

from ..models import BOMLine, Entry, PurchaseLine, PurchaseOrder, Stock, StockMove, Task
from .bom import issued
from .common import ZERO, audit, fields, lock_stocks, lookup, number, project_action, rounded, save, state, text


def take_value(stock, qty):
    if qty > stock.quantity:
        raise Conflict('可用库存不足，请刷新后重试。')
    return stock.value if qty == stock.quantity else rounded(stock.value * qty / stock.quantity)


def opening(actor, key, data):
    def execute(user):
        fields(data, {'item', 'location', 'quantity', 'unit_cost', 'reason'})
        from ..models import Item

        item = lookup(Item, data.get('item'), 'item', is_active=True)
        location = text(data, 'location', default='主仓', maximum=80)
        if not location:
            raise ValidationError({'location': '库位不能为空。'})
        stock = lock_stocks([item.pk], location, user)[item.pk]
        if stock.quantity or stock.value or stock.moves.exists():
            raise Conflict('此物料库位已有库存历史，请使用盘点。')
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        unit_cost = number(data.get('unit_cost'), 'unit_cost')
        value = number(rounded(qty * unit_cost), 'value')
        reason = text(data, 'reason')
        stock.quantity, stock.value = qty, value
        save(stock, user)
        move = save(StockMove(stock=stock, kind='opening', quantity=qty, value=value, reason=reason), user)
        return audit(user, 'stock.opening', move)

    return perform(
        actor=actor,
        key=key,
        operation='stock.opening',
        payload=data,
        authorize=lambda user: require_role(user, ADMIN),
        execute=execute,
    )


def count(actor, key, stock_id, data):
    def execute(user):
        fields(data, {'quantity', 'expected_quantity', 'expected_updated_at', 'unit_cost', 'reason'})
        source = lookup(Stock, stock_id)
        stock = lock_stocks([source.item_id], source.location, user)[source.item_id]
        expected = number(data.get('expected_quantity'), 'expected_quantity', 3)
        try:
            timestamp = parse_datetime(text(data, 'expected_updated_at', maximum=50))
        except ValueError:
            timestamp = None
        if stock.quantity != expected or timestamp != stock.updated_at:
            raise Conflict('盘点期间库存发生变化，请重新读取后盘点。')
        qty = number(data.get('quantity'), 'quantity', 3)
        reason = text(data, 'reason')
        if stock.quantity == 0 and qty > 0:
            require_role(user, ADMIN)
            value = rounded(qty * number(data.get('unit_cost'), 'unit_cost'))
        else:
            if 'unit_cost' in data:
                raise ValidationError({'unit_cost': '只有零库存盘盈可由管理员指定成本。'})
            value = rounded(stock.value * qty / stock.quantity) if stock.quantity else ZERO
        delta_qty, delta_value = qty - stock.quantity, value - stock.value
        if delta_qty:
            stock.quantity, stock.value = qty, value
            save(stock, user)
            save(StockMove(stock=stock, kind='count', quantity=delta_qty, value=delta_value, reason=reason), user)
        return audit(user, 'stock.count', stock, quantity=str(qty), delta=str(delta_qty), reason=reason)

    return perform(
        actor=actor,
        key=key,
        operation='stock.count',
        payload={'stock': stock_id, 'data': data},
        authorize=lambda user: require_role(user, WAREHOUSE),
        execute=execute,
    )


def issue(actor, key, data):
    def execute(user, project):
        fields(data, {'project', 'stock', 'task', 'quantity', 'reason'})
        state(project, {'active', 'delivering', 'warranty'})
        source = lookup(Stock, data.get('stock'), 'stock')
        task = (
            lookup(Task, data['task'], 'task', project=project, status='open') if data.get('task') is not None else None
        )
        service = task is not None and task.kind == 'service'
        if project.status == 'warranty' and not service:
            raise ValidationError({'task': '已验收项目领料必须关联未完成的售后任务。'})
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        if not service:
            bom = BOMLine.objects.filter(project=project, item_id=source.item_id).first()
            if bom is None or qty > bom.quantity - issued(project, source.item_id):
                raise Conflict('领料超过 BOM 剩余需求，请先修订 BOM。')
        reason = text(data, 'reason')
        stock = lock_stocks([source.item_id], source.location, user)[source.item_id]
        value = take_value(stock, qty)
        stock.quantity -= qty
        stock.value -= value
        save(stock, user)
        move = save(
            StockMove(
                stock=stock, project=project, task=task, kind='issue', quantity=-qty, value=-value, reason=reason
            ),
            user,
        )
        return audit(user, 'stock.issue', move)

    return project_action(actor, key, 'stock.issue', data.get('project'), data, WAREHOUSE, execute)


def return_material(actor, key, source_id, data):
    source = lookup(StockMove, source_id, kind='issue')

    def execute(user, project):
        fields(data, {'quantity', 'reason'})
        state(project, {'active', 'delivering', 'warranty'})
        original = get_object_or_404(StockMove.objects, pk=source.pk, project=project, kind='issue')
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        returned = original.returns.filter(kind='return').aggregate(total=Sum('quantity'))['total'] or ZERO
        if qty + returned > -original.quantity:
            raise Conflict('退料数量超过原领料可退余量。')
        if original.task_id is None or original.task.kind != 'service':
            shipped = project.deliveries.aggregate(total=Sum('quantity'))['total'] or 0
            if shipped:
                bom = BOMLine.objects.filter(project=project, item_id=original.stock.item_id).first()
                if bom:
                    required = (bom.quantity * Decimal(shipped) / project.equipment_quantity).quantize(
                        Decimal('0.001'), rounding=ROUND_CEILING
                    )
                    if issued(project, original.stock.item_id) - qty < required:
                        raise Conflict('已交付设备对应的领料不能退回，请只退回未使用余料。')
        stock = lock_stocks([original.stock.item_id], original.stock.location, user)[original.stock.item_id]
        value = rounded((-original.value) * (returned + qty) / (-original.quantity)) - rounded(
            (-original.value) * returned / (-original.quantity)
        )
        stock.quantity += qty
        stock.value += value
        save(stock, user)
        move = save(
            StockMove(
                stock=stock,
                project=project,
                task=original.task,
                source=original,
                kind='return',
                quantity=qty,
                value=value,
                reason=text(data, 'reason'),
            ),
            user,
        )
        return audit(user, 'stock.return_material', move)

    return project_action(
        actor, key, 'stock.return_material', source.project_id, {'source': source.pk, 'data': data}, WAREHOUSE, execute
    )


def return_purchase(actor, key, source_id, data):
    source = lookup(StockMove, source_id, kind='receipt')

    def execute(user, project):
        fields(data, {'quantity', 'reason'})
        state(project, {'active', 'delivering', 'warranty'})
        original = get_object_or_404(StockMove.objects, pk=source.pk, project=project, kind='receipt')
        purchase = PurchaseOrder.objects.select_for_update().get(pk=original.purchase_line.purchase_id, project=project)
        line = PurchaseLine.objects.select_for_update().get(pk=original.purchase_line_id, purchase=purchase)
        entry = Entry.objects.select_for_update().get(purchase=purchase)
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        returned = -(original.returns.filter(kind='purchase_return').aggregate(total=Sum('quantity'))['total'] or ZERO)
        if qty + returned > original.quantity:
            raise Conflict('采购退货数量超过原收货可退余量。')
        stock = lock_stocks([original.stock.item_id], original.stock.location, user)[original.stock.item_id]
        value = take_value(stock, qty)
        credit = rounded(original.value * (returned + qty) / original.quantity) - rounded(
            original.value * returned / original.quantity
        )
        stock.quantity -= qty
        stock.value -= value
        save(stock, user)
        line.returned_quantity += qty
        save(line, user)
        entry.credit_amount += credit
        save(entry, user)
        move = save(
            StockMove(
                stock=stock,
                project=project,
                purchase_line=line,
                source=original,
                kind='purchase_return',
                quantity=-qty,
                value=-value,
                supplier_credit=credit,
                reason=text(data, 'reason'),
            ),
            user,
        )
        return audit(user, 'stock.return_purchase', move)

    return project_action(
        actor, key, 'stock.return_purchase', source.project_id, {'source': source.pk, 'data': data}, WAREHOUSE, execute
    )
