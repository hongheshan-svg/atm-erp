from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.permissions import ADMIN, WAREHOUSE, require_role

from ..models import BOMLine, Entry, Project, PurchaseLine, PurchaseOrder, Stock, StockMove, Task
from .bom import claimed_by_others, issued
from .common import (
    ZERO,
    audit,
    fields,
    identity,
    location_value,
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


def take_value(stock, qty):
    if qty > stock.quantity:
        raise Conflict('可用库存不足，请刷新后重试。')
    return stock.value if qty == stock.quantity else rounded(stock.value * qty / stock.quantity)


def opening(actor, key, data):
    def execute(user):
        fields(data, {'item', 'location', 'quantity', 'unit_cost', 'reason'})
        from ..models import Item

        item = lookup(Item, data.get('item'), 'item', is_active=True)
        # 期初由管理员在上线时建立库位，不要求逐个确认新库位。
        location = location_value(data, allow_new=True)
        stock = lock_stocks([item.pk], location, user)[item.pk]
        if stock.quantity or stock.value or stock.moves.exists():
            raise Conflict('此物料库位已有库存历史，请使用盘点。')
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        unit_cost = number(data.get('unit_cost'), 'unit_cost')
        value = number(rounded(qty * unit_cost), 'value')
        reason = text(data, 'reason', default='') or '期初库存'
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
            try:
                require_role(user, ADMIN)
            except PermissionDenied as exc:
                raise PermissionDenied('零库存盘盈需管理员填写单位成本，请联系管理员在库存页面完成盘点。') from exc
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


def shared_arrival(project, item_id, qty, confirm_shared, action):
    """库存不按项目预留：领料、采购退货扣减后若不足以覆盖其他项目已到货未领用量，须确认并留痕。"""
    claims = claimed_by_others(project, item_id)
    claimed = sum(claims.values(), ZERO)
    on_hand = Stock.objects.filter(item_id=item_id).aggregate(total=Sum('quantity'))['total'] or ZERO
    if on_hand - qty >= claimed:
        return []
    shared = [
        {'project': code, 'quantity': str(claims[pk])}
        for pk, code in Project.objects.filter(pk__in=claims).order_by('code').values_list('pk', 'code')
    ]
    if not confirm_shared:
        summary = '、'.join(f'{row["project"]} {row["quantity"]}' for row in shared)
        raise Conflict(
            f'本次{action}会占用其他项目已到货、尚未领用的物料（{summary}）。'
            '确认挪用请勾选「确认占用其他项目到货」后重新提交，并通知相关项目补采。'
        )
    return shared


def bom_remaining(project, item_id):
    """本项目该物料按 BOM 还能领多少：各单元需求合计减已领（售后领料不计）。领料与按 BOM 批量领料共用。"""
    required = (
        BOMLine.objects.filter(project=project, item_id=item_id).aggregate(total=Sum('quantity'))['total'] or ZERO
    )
    return required - issued(project, item_id)


def take_issue(user, project, source, qty, *, task, reason, remark, confirm_shared):
    """在已加锁的项目内出库一条领料：校验 BOM 剩余（售后任务除外）、库存与共享到货，写库存流水和审计。"""
    service = task is not None and task.kind == 'service'
    if not service and qty > bom_remaining(project, source.item_id):
        raise Conflict(f'{source.item.name}：领料超过 BOM 剩余需求，请先修订 BOM。')
    stock = lock_stocks([source.item_id], source.location, user)[source.item_id]
    value = take_value(stock, qty)
    shared = shared_arrival(project, source.item_id, qty, confirm_shared, '领料')
    stock.quantity -= qty
    stock.value -= value
    save(stock, user)
    move = save(
        StockMove(
            stock=stock,
            project=project,
            task=task,
            kind='issue',
            quantity=-qty,
            value=-value,
            reason=reason,
            remark=remark,
        ),
        user,
    )
    audit(user, 'stock.issue', move, shared_from=shared)
    return move


def confirmation(data):
    confirm_shared = data.get('confirm_shared', False)
    if not isinstance(confirm_shared, bool):
        raise ValidationError({'confirm_shared': '必须为布尔值。'})
    return confirm_shared


def issue(actor, key, data):
    def execute(user, project):
        fields(data, {'project', 'stock', 'task', 'quantity', 'reason', 'confirm_shared', 'remark'})
        confirm_shared = confirmation(data)
        state(project, {'active', 'delivering', 'warranty'})
        source = lookup(Stock, data.get('stock'), 'stock')
        task = (
            lookup(Task, data['task'], 'task', project=project, status='open') if data.get('task') is not None else None
        )
        service = task is not None and task.kind == 'service'
        if project.status == 'warranty' and not service:
            raise ValidationError({'task': '已验收项目领料必须关联未完成的售后任务。'})
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        # 正常领料的说明选填，缺省记为动作名；退料、采购退货等纠错动作仍须写明原因。
        reason = text(data, 'reason', default='') or ('售后领料' if service else '项目领料')
        remark = text(data, 'remark', default='')
        move = take_issue(
            user, project, source, qty, task=task, reason=reason, remark=remark, confirm_shared=confirm_shared
        )
        return {'id': move.pk}

    return project_action(actor, key, 'stock.issue', data.get('project'), data, WAREHOUSE, execute)


def bom_issue_lines(project):
    """按 BOM 批量领料的候选：本项目还有未领 BOM 需求、且有库存的物料，按库位逐行列出并预填本次领用量。

    BOM 领料按物料合计校验（多单元同物料不拆分），同一物料多个库位时按库位顺序依次填满还可领数量。
    """
    totals = {}
    units = {}
    for line in BOMLine.objects.filter(project=project).order_by('item_id', 'pk'):
        totals[line.item_id] = totals.get(line.item_id, ZERO) + line.quantity
        if line.assembly_unit and line.assembly_unit not in units.setdefault(line.item_id, []):
            units[line.item_id].append(line.assembly_unit)
    used = {
        row['stock__item_id']: -row['total']
        for row in StockMove.objects.filter(
            project=project, stock__item_id__in=list(totals), kind__in=['issue', 'return']
        )
        .exclude(task__kind='service')
        .values('stock__item_id')
        .annotate(total=Sum('quantity'))
    }
    remaining = {pk: total - used.get(pk, ZERO) for pk, total in totals.items()}
    stocks = (
        Stock.objects.filter(item_id__in=[pk for pk, value in remaining.items() if value > ZERO], quantity__gt=0)
        .select_related('item')
        .order_by('item__code', 'item_id', 'location', 'pk')
    )
    result, left, missing = [], dict(remaining), {pk for pk, value in remaining.items() if value > ZERO}
    for stock in stocks:
        missing.discard(stock.item_id)
        take = min(stock.quantity, max(ZERO, left[stock.item_id]))
        left[stock.item_id] -= take
        item = stock.item
        result.append(
            {
                'stock': stock.pk,
                'item': item.pk,
                'item_code': item.code,
                'item_name': item.name,
                'specification': item.specification,
                'drawing_number': item.drawing_number,
                'drawing_revision': item.drawing_revision,
                'brand': item.brand,
                'product_category': item.product_category,
                'part_type': item.part_type,
                'unit': item.unit,
                'location': stock.location,
                'assembly_units': '、'.join(units.get(item.pk, [])),
                'required_quantity': str(totals[item.pk]),
                'issued_quantity': str(used.get(item.pk, ZERO)),
                'bom_remaining': str(remaining[item.pk]),
                'available': str(stock.quantity),
                'quantity': str(take),
            }
        )
    return {
        'project': project.pk,
        'project_code': project.code,
        'project_name': project.name,
        'lines': result,
        'pending_items': len([pk for pk, value in remaining.items() if value > ZERO]),
        'missing_items': len(missing),
    }


def issue_batch(actor, key, data):
    """按项目 BOM 一次领多行：同一事务内逐行沿用单行领料的全部校验，任一行不通过整单不出库。"""

    def execute(user, project):
        fields(data, {'project', 'lines', 'reason', 'confirm_shared'})
        confirm_shared = confirmation(data)
        state(project, {'active', 'delivering'})
        reason = text(data, 'reason', default='') or '项目领料'
        prepared, seen = [], set()
        for index, row in enumerate(rows(data)):
            try:
                fields(row, {'stock', 'quantity', 'remark'})
                stock_id = identity(row.get('stock'), 'stock')
                qty = number(row.get('quantity'), 'quantity', 3, positive=True)
                remark = text(row, 'remark', default='')
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
            if stock_id in seen:
                raise ValidationError({'lines': {index: {'stock': '同一库存行不能重复领料。'}}})
            seen.add(stock_id)
            prepared.append((lookup(Stock, stock_id, 'stock'), qty, remark))
        # 先按物料顺序统一加锁，再逐库位扣减，与单行领料、收货的加锁顺序一致，避免互相等待。
        lock_items({source.item_id for source, _, _ in prepared})
        moves = []
        for source, qty, remark in sorted(prepared, key=lambda row: (row[0].item_id, row[0].location, row[0].pk)):
            move = take_issue(
                user, project, source, qty, task=None, reason=reason, remark=remark, confirm_shared=confirm_shared
            )
            moves.append(move.pk)
        return {'moves': moves, 'count': len(moves)}

    return project_action(actor, key, 'stock.issue_batch', data.get('project'), data, WAREHOUSE, execute)


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
                required_total = (
                    BOMLine.objects.filter(project=project, item_id=original.stock.item_id).aggregate(
                        total=Sum('quantity')
                    )['total']
                    or ZERO
                )
                if required_total:
                    from .execution import delivered_materials

                    required = delivered_materials(project).get(original.stock.item_id, ZERO)
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
        fields(data, {'quantity', 'reason', 'confirm_shared'})
        confirm_shared = data.get('confirm_shared', False)
        if not isinstance(confirm_shared, bool):
            raise ValidationError({'confirm_shared': '必须为布尔值。'})
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
        shared = shared_arrival(project, original.stock.item_id, qty, confirm_shared, '采购退货')
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
        return audit(user, 'stock.return_purchase', move, shared_from=shared)

    return project_action(
        actor, key, 'stock.return_purchase', source.project_id, {'source': source.pk, 'data': data}, WAREHOUSE, execute
    )
