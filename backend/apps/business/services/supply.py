import copy
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.api import Conflict
from apps.core.models import AuditLog, CodeRule
from apps.core.periods import check_dates
from apps.core.permissions import PURCHASE_APPROVERS, PURCHASERS, WAREHOUSE, has_role

from ..models import BOMLine, Entry, Partner, PurchaseLine, PurchaseOrder, StockMove
from .approval import independent_approval
from .bom import check_line_limit, demand, incoming, issued
from .common import (
    ZERO,
    audit,
    day,
    fields,
    identity,
    integer,
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
from .payment_terms import terms


def total(purchase):
    return sum((rounded(line.quantity * line.unit_price) for line in purchase.lines.all()), ZERO)


def receiving_status(lines):
    """已批准采购的收货状态：全部收完或取消为已收货/已取消；否则有合格收货或隔离中为部分收货，都没有回到已批准。"""
    if all(line.received_quantity + line.cancelled_quantity == line.quantity for line in lines):
        return 'received' if any(line.received_quantity for line in lines) else 'cancelled'
    return 'partial' if any(line.received_quantity or line.pending_quantity for line in lines) else 'approved'


def _amount_changed(detail):
    """草稿编辑是否改了数量或单价（明细增删也算）；无法解析的历史记录按已修改处理。"""
    try:
        before = {str(row['id']): row for row in detail['before']}
        after = {str(row['id']): row for row in detail['after']['lines']}
        return set(before) != set(after) or any(
            Decimal(str(before[pk][field])) != Decimal(str(after[pk][field]))
            for pk in before
            for field in ('quantity', 'unit_price')
        )
    except (KeyError, TypeError, AttributeError, ArithmeticError, ValueError):
        return True


def _applicants(creators):
    result = {pk: {creator} if creator else set() for pk, creator in creators.items()}
    resources = {f'purchaseorder:{pk}': pk for pk in creators}
    submitters = {}
    logs = (
        AuditLog.objects.filter(resource__in=resources, operation__in=['purchase.submit', 'purchase.edit'])
        .order_by('id')
        .values_list('resource', 'operation', 'actor_id', 'detail')
    )
    for resource, operation, actor, detail in logs:
        if operation == 'purchase.submit':
            submitters[resources[resource]] = actor
        elif _amount_changed(detail):
            result[resources[resource]].add(actor)
    for pk, actor in submitters.items():
        result[pk].add(actor)
    return result


def purchase_applicants(purchase):
    """单条采购的申请人ID集合：创建人、最近一次提交人、待审批前改过数量或单价的人。

    申请人不能审批本单（管理员例外须填原因，见 approval.independent_approval）。
    """
    return _applicants({purchase.pk: purchase.created_by_id})[purchase.pk]


def review_budget_adjusters(purchase, amount):
    """本单首次提交后调整过本项目预算、且按调整前预算本单会超预算的人（普通批准时视同申请人）。

    提交前的预算调整不受影响；待审期间与本单是否超预算无关的调整也不限制调整人。
    """
    from .budgets import CATEGORIES, analysis

    resource = f'purchaseorder:{purchase.pk}'
    first = AuditLog.objects.filter(operation='purchase.submit', resource=resource).order_by('id').first()
    if first is None:
        return set()
    revisions = list(
        AuditLog.objects.filter(operation='project.budget', resource=f'project:{purchase.project_id}', id__gt=first.pk)
        .order_by('id')
        .values_list('actor_id', 'detail')
    )
    adjusters = {actor for actor, _ in revisions}
    if not revisions:
        return adjusters
    before = revisions[0][1].get('before')
    if not isinstance(before, dict) or not set(CATEGORIES) <= set(before):
        return adjusters
    baseline = copy.copy(purchase.project)
    for category in CATEGORIES:
        value = before[category]
        setattr(baseline, f'budget_{category}', None if value in (None, 'None') else Decimal(value))
    return adjusters if analysis(baseline, amount)['over_budget'] else set()


def applicants_by_purchase(purchases):
    """{采购ID: 申请人ID集合}，口径同 purchase_applicants；固定两次查询，供列表/工作台使用，避免逐行回查审计。"""
    if hasattr(purchases, 'values_list'):
        creators = dict(purchases.order_by().values_list('pk', 'created_by_id'))
    else:
        creators = {purchase.pk: purchase.created_by_id for purchase in purchases}
    return _applicants(creators)


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
                'warranty_months',
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
            bom_id = identity(row['bom_line'], 'bom_line') if row.get('bom_line') is not None else None
            row_key = (item_id, bom_id)
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
                warranty_months=integer(data, 'warranty_months', 12, minimum=1, maximum=120),
                **agreed,
            ),
            user,
        )
        for index, ((item_id, _), row) in enumerate(prepared.items()):
            if not items[item_id].is_active:
                raise ValidationError('已停用物料不能新建采购。')
            try:
                qty = number(row.get('quantity'), 'quantity', 3, positive=True)
                price = number(row.get('unit_price'), 'unit_price')
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
            bom = None
            if row.get('bom_line') is not None:
                bom = lookup(BOMLine, row['bom_line'], 'bom_line', project=project, item_id=item_id)
                check_line_limit(bom, qty)
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
        from .budgets import purchase_check, purchase_visibility

        fields(data, {'reason', 'expected_snapshot', 'confirmed'} if override else {'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        report = purchase_check(purchase)
        reason = text(data, 'reason', default='')
        self_approval = independent_approval(user, purchase_applicants(purchase), reason)
        budget_adjuster_approval = False
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
            warnings = purchase_visibility(user, report, purchase.project)['warnings']
            raise Conflict('；'.join(warnings) + '。请重新打开审批，填写超预算批准原因。')
        else:
            budget_adjuster_approval = independent_approval(
                user,
                review_budget_adjusters(purchase, Decimal(report['purchase_amount'])),
                reason,
                denied='你在本单提交后调整过项目预算，按调整前预算本单会超预算，不能由你批准；'
                '请交由其他有权限的人员审批，管理员例外须填写原因。',
                reason_required='管理员调整预算后批准本单，必须填写例外审批原因并保留审计。',
            )
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
        return audit(
            user,
            'purchase.approve',
            purchase,
            over_budget=override,
            reason=reason,
            self_approval=self_approval,
            budget_adjuster_approval=budget_adjuster_approval,
            budget_check=report,
        )

    operation = 'purchase.approve_over_budget' if override else 'purchase.approve'
    return purchase_action(actor, key, operation, purchase_id, data, PURCHASE_APPROVERS, execute)


def receive(actor, key, purchase_id, data, *, from_quarantine=False):
    def execute(user, purchase):
        fields(data, {'location', 'new_location', 'lines', 'reason', 'received_date', 'backfill_reason'})
        received_date = day(data, 'received_date') if data.get('received_date') else timezone.localdate()
        if received_date > timezone.localdate():
            raise ValidationError({'received_date': '实际收货日期不能晚于今天。'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'approved', 'partial'})
        # Also check quarantine-only arrivals, which do not create a StockMove yet.
        check_dates(received_date)
        backfill_reason = text(data, 'backfill_reason', default='')
        if received_date < timezone.localdate(purchase.created_at) and not backfill_reason:
            raise ValidationError({'backfill_reason': '收货日期早于采购创建日期，请填写补录原因。'})
        location = location_value(data)
        reason = text(data, 'reason')
        lines = {line.pk: line for line in purchase.lines.select_for_update().order_by('item_id', 'pk')}
        selected, seen, remarks = {}, set(), {}
        for index, row in enumerate(rows(data)):
            fields(row, {'line', 'quantity', 'pending_quantity', 'remark'})
            try:
                remark = text(row, 'remark', default='')
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
            line_id = identity(row.get('line'), 'line')
            if line_id in seen or line_id not in lines:
                raise ValidationError('收货明细重复或不属于此采购单。')
            seen.add(line_id)
            qty = number(row.get('quantity'), 'quantity', 3)
            pending = number(row.get('pending_quantity', '0'), 'pending_quantity', 3)
            line = lines[line_id]
            if not from_quarantine and qty == ZERO and pending == ZERO:
                continue
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
            remarks[line_id] = remark
        if not selected:
            raise ValidationError('请至少填写一条到货数量。')
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
                    remark=remarks[line_id],
                ),
                user,
            )
            line.received_quantity += qty
            save(line, user)
        purchase.status = receiving_status(lines.values())
        save(purchase, user)
        return audit(
            user,
            'purchase.quality_accept' if from_quarantine else 'purchase.receive',
            purchase,
            lines=data['lines'],
            reason=f'{reason}；补录原因：{backfill_reason}' if backfill_reason else reason,
            received_date=received_date.isoformat(),
            backfill_reason=backfill_reason,
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
        fields(data, {'reason', 'lines'})
        reason = text(data, 'reason')
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft', 'submitted', 'approved', 'partial'})
        lines = list(purchase.lines.select_for_update().order_by('item_id', 'pk'))
        by_id = {line.pk: line for line in lines}
        selected = {}
        if 'lines' in data:
            if purchase.status in {'draft', 'submitted'}:
                raise ValidationError({'lines': '未批准采购请整单作废；按明细取消仅适用于已批准采购。'})
            for index, row in enumerate(rows(data)):
                fields(row, {'line', 'quantity'})
                pk = identity(row.get('line'), 'line')
                if pk not in by_id or pk in selected:
                    raise ValidationError({'lines': {index: {'line': '明细重复或不属于本采购单。'}}})
                line = by_id[pk]
                remaining = line.quantity - line.received_quantity - line.cancelled_quantity
                try:
                    qty = number(row['quantity'], 'quantity', 3, positive=True) if 'quantity' in row else remaining
                except ValidationError as exc:
                    raise ValidationError({'lines': {index: exc.detail}}) from exc
                if qty <= ZERO or qty > remaining:
                    raise Conflict('取消数量超过该明细未收余量，请刷新后重试。')
                selected[pk] = qty
        else:
            selected = {
                line.pk: line.quantity - line.received_quantity - line.cancelled_quantity
                for line in lines
                if line.quantity > line.received_quantity + line.cancelled_quantity
            }
        # Pending goods still belong to the supplier commitment. Only selected lines are checked;
        # quarantined goods on other lines must not prevent cancelling an unrelated shortage.
        if any(by_id[pk].pending_quantity for pk in selected):
            raise Conflict('请先处理所选明细隔离中的不合格到货，再取消未收余量。')
        credit = ZERO
        for pk, qty in selected.items():
            line = by_id[pk]
            retained = line.quantity - line.cancelled_quantity
            # Difference of cumulative rounded amounts avoids losing a cent across partial cancellations.
            credit += rounded(retained * line.unit_price) - rounded((retained - qty) * line.unit_price)
            line.cancelled_quantity += qty
            save(line, user)
        entry = Entry.objects.select_for_update().filter(purchase=purchase).first()
        if entry:
            entry.credit_amount += credit
            save(entry, user)
        if all(line.received_quantity + line.cancelled_quantity == line.quantity for line in lines):
            purchase.status = 'received' if any(line.received_quantity for line in lines) else 'cancelled'
        save(purchase, user)
        return audit(
            user,
            'purchase.cancel_remainder',
            purchase,
            credit=str(credit),
            reason=reason,
            lines=[{'line': pk, 'quantity': str(qty)} for pk, qty in selected.items()],
        )

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

    return purchase_action(actor, key, 'purchase.reject', purchase_id, data, PURCHASE_APPROVERS, execute)


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
                'warranty_months',
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
        for index, (pk, row) in enumerate(selected.items()):
            line = lines[pk]
            before.append(
                {
                    'id': pk,
                    'quantity': str(line.quantity),
                    'unit_price': str(line.unit_price),
                    'due_date': str(line.due_date),
                }
            )
            try:
                qty = number(row.get('quantity'), 'quantity', 3, positive=True)
                price = number(row.get('unit_price'), 'unit_price')
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
            if line.bom_line_id:
                check_line_limit(line.bom_line, qty, exclude_line=line.pk)
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
            line.unit_price = price
            line.due_date = day(row, 'due_date')
            number(rounded(qty * line.unit_price), 'line_amount')
            save(line, user)
        purchase.due_date = day(data, 'due_date')
        if 'payment_due_date' in data:
            purchase.payment_due_date = day(data, 'payment_due_date') if data.get('payment_due_date') else None
        purchase.note = text(data, 'note', default='')
        if 'warranty_months' in data:
            purchase.warranty_months = integer(data, 'warranty_months', 12, minimum=1, maximum=120)
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
        # 隔离品退回后按合格已收与仍隔离数量重算；全部退回且无合格收货时回到已批准待收货。
        purchase.status = receiving_status(purchase.lines.all())
        save(purchase, user)
        return audit(user, 'purchase.quality_return', purchase, lines=data['lines'], reason=reason)

    return purchase_action(actor, key, 'purchase.quality_return', purchase_id, data, WAREHOUSE, execute)
