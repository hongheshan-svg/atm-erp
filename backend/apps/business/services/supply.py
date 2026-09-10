from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import MANAGERS, PURCHASERS, WAREHOUSE, has_role

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
from .payment_terms import terms


def total(purchase):
    return sum((rounded(line.quantity * line.unit_price) for line in purchase.lines.all()), ZERO)


def create_purchase(actor, key, data):
    def execute(user, project):
        fields(
            data,
            {
                'project',
                'supplier',
                'due_date',
                'payment_due_date',
                'payment_term',
                'payment_days',
                'note',
                'lines',
                'from_demand',
            },
        )
        state(project, {'active', 'delivering', 'warranty'})
        supplier = lookup(Partner, data.get('supplier'), 'supplier', is_active=True, kind__in=['supplier', 'both'])
        agreed = terms(data, supplier)
        if agreed['payment_term'] != 'manual' and data.get('payment_due_date'):
            raise ValidationError({'payment_due_date': '自动账期按实际收货计算，请清空指定付款日期。'})
        from_demand = data.get('from_demand', False)
        if not isinstance(from_demand, bool):
            raise ValidationError({'from_demand': '必须为布尔值。'})
        prepared = {}
        for row in rows(data):
            fields(row, {'item', 'bom_line', 'quantity', 'unit_price', 'due_date'})
            item_id = identity(row.get('item'), 'item')
            row_key = (item_id, row.get('bom_line'))
            if row_key in prepared:
                raise ValidationError('同一采购单不能重复添加同一 BOM 行或未关联 BOM 的物料。')
            prepared[row_key] = row
        items = lock_items({item_id for item_id, _ in prepared})
        shortage = {row['bom_line']: Decimal(row['shortage']) for row in demand(project)} if from_demand else {}
        purchase = save(
            PurchaseOrder(
                code=CodeRule.generate_code('purchase'),
                project=project,
                supplier=supplier,
                due_date=day(data, 'due_date'),
                payment_due_date=day(data, 'payment_due_date') if data.get('payment_due_date') else None,
                note=text(data, 'note', default=''),
                **agreed,
            ),
            user,
        )
        for (item_id, _), row in prepared.items():
            if not items[item_id].is_active:
                raise ValidationError('已停用物料不能新建采购。')
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            price = number(row.get('unit_price'), 'unit_price')
            bom = None
            if row.get('bom_line') is not None:
                bom = lookup(BOMLine, row['bom_line'], 'bom_line', project=project, item_id=item_id)
                needed = sum((line.quantity for line in BOMLine.objects.filter(project=project, item_id=item_id)), ZERO)
                if qty > max(ZERO, needed - issued(project, item_id) - incoming(project, item_id)):
                    raise Conflict('采购数量超过当前 BOM 剩余需求，请刷新后重新确认。')
            if from_demand and (not bom or qty > shortage.get(bom.pk, ZERO)):
                raise Conflict('采购数量超过当前缺口，请刷新需求后重试。')
            number(rounded(qty * price), 'line_amount')
            save(
                PurchaseLine(
                    purchase=purchase,
                    item=items[item_id],
                    bom_line=bom,
                    quantity=qty,
                    unit_price=price,
                    due_date=day(row, 'due_date') if row.get('due_date') else purchase.due_date,
                ),
                user,
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


def approve(actor, key, purchase_id, data, *, override=False):
    def execute(user, purchase):
        from .budgets import purchase_check

        fields(data, {'reason', 'expected_snapshot', 'confirmed'} if override else set())
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        report = purchase_check(purchase)
        reason = ''
        if override:
            reason = text(data, 'reason')
            if data.get('confirmed') is not True:
                raise ValidationError({'confirmed': '请明确确认超预算批准。'})
            if not isinstance(data.get('expected_snapshot'), str) or len(data['expected_snapshot']) != 64:
                raise ValidationError({'expected_snapshot': '请先查看最新预算检查结果。'})
            if data['expected_snapshot'] != report['snapshot']:
                raise Conflict('预算或成本已变化，请重新打开采购审批。')
            if not report['over_budget']:
                raise Conflict('当前没有超预算，请使用普通批准。')
            if not has_role(user, {'admin'}) and user.pk == purchase.project.budget_changed_by_id:
                raise PermissionDenied('预算调整人不能批准本项目超预算采购，请由其他经理审批；管理员例外必须填写原因。')
        elif report['over_budget']:
            raise Conflict('；'.join(report['warnings']) + '。请重新打开审批，填写超预算批准原因。')
        save(
            Entry(
                project=purchase.project,
                purchase=purchase,
                kind='payable',
                title=f'采购 {purchase.code}',
                amount=total(purchase),
                due_date=purchase.payment_due_date or purchase.due_date,
            ),
            user,
        )
        purchase.status = 'approved'
        save(purchase, user)
        return audit(user, 'purchase.approve', purchase, over_budget=override, reason=reason, budget_check=report)

    operation = 'purchase.approve_over_budget' if override else 'purchase.approve'
    return purchase_action(actor, key, operation, purchase_id, data, MANAGERS, execute)


def receive(actor, key, purchase_id, data, *, from_quarantine=False):
    def execute(user, purchase):
        fields(data, {'location', 'lines', 'reason', 'received_date'})
        received_date = day(data, 'received_date') if data.get('received_date') else timezone.localdate()
        if received_date > timezone.localdate():
            raise ValidationError({'received_date': '实际收货日期不能晚于今天。'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'approved', 'partial'})
        location = text(data, 'location', default='主仓', maximum=80)
        if not location:
            raise ValidationError({'location': '库位不能为空。'})
        reason = text(data, 'reason')
        lines = {line.pk: line for line in purchase.lines.select_for_update().order_by('item_id', 'pk')}
        selected = {}
        for row in rows(data):
            fields(row, {'line', 'quantity', 'pending_quantity'})
            line_id = identity(row.get('line'), 'line')
            if line_id in selected or line_id not in lines:
                raise ValidationError('收货明细重复或不属于此采购单。')
            qty = number(row.get('quantity'), 'quantity', 3)
            pending = number(row.get('pending_quantity', '0'), 'pending_quantity', 3)
            line = lines[line_id]
            if from_quarantine:
                if pending or qty <= ZERO or qty > line.pending_quantity:
                    raise Conflict('处理数量超过待处理数量。')
                line.pending_quantity -= qty
            elif (
                qty + pending <= ZERO
                or qty + pending
                > line.quantity - line.received_quantity - line.cancelled_quantity - line.pending_quantity
            ):
                raise Conflict('收货数量超过未收余量，请刷新后重试。')
            line.pending_quantity += pending
            save(line, user)
            selected[line_id] = qty
        stocks = lock_stocks([lines[line_id].item_id for line_id, qty in selected.items() if qty], location, user)
        for line_id, qty in selected.items():
            if not qty:
                continue
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
                    received_date=received_date,
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
        return audit(
            user,
            'purchase.quality_accept' if from_quarantine else 'purchase.receive',
            purchase,
            lines=data['lines'],
            reason=reason,
        )

    return purchase_action(
        actor,
        key,
        'purchase.quality_accept' if from_quarantine else 'purchase.receive',
        purchase_id,
        data,
        WAREHOUSE,
        execute,
    )


def cancel_remainder(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'reason'})
        reason = text(data, 'reason')
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft', 'submitted', 'approved', 'partial'})
        lines = list(purchase.lines.select_for_update().order_by('item_id', 'pk'))
        credit = ZERO
        for line in lines:
            if line.pending_quantity:
                raise Conflict('请先处理隔离中的不合格到货，再取消未收余量。')
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


def reject(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        reason = text(data, 'reason')
        purchase.status = 'draft'
        save(purchase, user)
        return audit(user, 'purchase.reject', purchase, reason=reason)

    return purchase_action(actor, key, 'purchase.reject', purchase_id, data, MANAGERS, execute)


def delivery_plan(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'lines', 'reason', 'expected_updated_at'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'approved', 'partial'})
        try:
            expected = parse_datetime(data.get('expected_updated_at', ''))
        except (ValueError, TypeError):
            expected = None
        if expected != purchase.updated_at:
            raise Conflict('采购已变化，请刷新到货计划。')
        reason = text(data, 'reason')
        before, after, seen = [], [], set()
        for row in rows(data):
            fields(row, {'id', 'due_date'})
            pk = identity(row.get('id'), 'id')
            if pk in seen:
                raise ValidationError('明细重复。')
            seen.add(pk)
            line = get_object_or_404(purchase.lines.select_for_update(), pk=pk)
            if line.received_quantity + line.cancelled_quantity >= line.quantity:
                raise Conflict('已完成的明细不能更改到货计划。')
            before.append({'id': pk, 'due_date': str(line.due_date)})
            line.due_date = day(row, 'due_date')
            after.append({'id': pk, 'due_date': str(line.due_date)})
            save(line, user)
        save(purchase, user)
        return audit(user, 'purchase.delivery_plan', purchase, before=before, after=after, reason=reason)

    return purchase_action(actor, key, 'purchase.delivery_plan', purchase_id, data, PURCHASERS, execute)


def edit(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(
            data,
            {
                'expected_updated_at',
                'reason',
                'due_date',
                'payment_due_date',
                'payment_term',
                'payment_days',
                'note',
                'lines',
            },
        )
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft'})
        version = data.get('expected_updated_at')
        try:
            expected = parse_datetime(version) if isinstance(version, str) else None
        except ValueError:
            expected = None
        if expected != purchase.updated_at:
            raise Conflict('采购单已更新，请刷新后重试。')
        reason = text(data, 'reason')
        lines = {line.pk: line for line in purchase.lines.select_for_update()}
        agreed = terms(data, purchase)
        if agreed['payment_term'] != 'manual' and data.get('payment_due_date'):
            raise ValidationError({'payment_due_date': '自动账期按实际收货计算，请清空指定付款日期。'})
        for field, value in agreed.items():
            setattr(purchase, field, value)
        if purchase.payment_term != 'manual':
            purchase.payment_due_date = None
        selected = {}
        for row in rows(data):
            fields(row, {'id', 'quantity', 'unit_price', 'due_date'})
            pk = identity(row.get('id'), 'id')
            if pk not in lines or pk in selected:
                raise ValidationError('采购明细不属于本单或重复。')
            selected[pk] = row
        if set(selected) != set(lines):
            raise ValidationError('请保留所有采购明细；不再需要的采购请取消后重建。')
        before = []
        for pk, row in selected.items():
            line = lines[pk]
            before.append(
                {
                    'id': pk,
                    'quantity': str(line.quantity),
                    'unit_price': str(line.unit_price),
                    'due_date': str(line.due_date),
                }
            )
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            if line.bom_line_id:
                needed = sum(
                    (b.quantity for b in BOMLine.objects.filter(project=purchase.project, item_id=line.item_id)), ZERO
                )
                if (
                    qty
                    > needed
                    - issued(purchase.project, line.item_id)
                    - incoming(purchase.project, line.item_id)
                    + line.quantity
                ):
                    raise Conflict('修改数量超过 BOM 剩余需求。')
            line.quantity = qty
            line.unit_price = number(row.get('unit_price'), 'unit_price')
            line.due_date = day(row, 'due_date')
            number(rounded(qty * line.unit_price), 'line_amount')
            save(line, user)
        purchase.due_date = day(data, 'due_date')
        if 'payment_due_date' in data:
            purchase.payment_due_date = day(data, 'payment_due_date') if data.get('payment_due_date') else None
        purchase.note = text(data, 'note', default='')
        number(total(purchase), 'total_amount')
        save(purchase, user)
        return audit(user, 'purchase.edit', purchase, before=before, after=data, reason=reason)

    return purchase_action(actor, key, 'purchase.edit', purchase_id, data, PURCHASERS, execute)


def quality_return(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'lines', 'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'approved', 'partial'})
        reason = text(data, 'reason')
        seen = set()
        for row in rows(data):
            fields(row, {'line', 'quantity'})
            pk = identity(row.get('line'), 'line')
            if pk in seen:
                raise ValidationError('明细重复。')
            seen.add(pk)
            line = get_object_or_404(purchase.lines.select_for_update(), pk=pk)
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            if qty > line.pending_quantity:
                raise Conflict('退回数量超过隔离中的到货。')
            line.pending_quantity -= qty
            save(line, user)
        return audit(user, 'purchase.quality_return', purchase, lines=data['lines'], reason=reason)

    return purchase_action(actor, key, 'purchase.quality_return', purchase_id, data, WAREHOUSE, execute)
