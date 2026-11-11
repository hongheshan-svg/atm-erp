import copy
from datetime import date
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.api import Conflict
from apps.core.models import AuditLog, CodeRule
from apps.core.periods import check_dates
from apps.core.permissions import PURCHASE_APPROVERS, PURCHASERS, WAREHOUSE, has_role, require_project, require_role

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
from .purchase_changes import pending_requests, require_no_request


def total(purchase):
    return sum((rounded(line.quantity * line.unit_price) for line in purchase.lines.all()), ZERO)


def receiving_status(lines):
    """已批准采购的收货状态：全部收完或取消为已收货/已取消；否则有合格收货或隔离中为部分收货，都没有回到已批准。"""
    if all(line.received_quantity + line.cancelled_quantity == line.quantity for line in lines):
        return 'received' if any(line.received_quantity for line in lines) else 'cancelled'
    return 'partial' if any(line.received_quantity or line.pending_quantity for line in lines) else 'approved'


def quarantine_arrivals(purchase):
    """{明细ID: 最近一次隔离到货日期}，取自收货审计（隔离到货不产生库存流水）。"""
    result = {}
    logs = AuditLog.objects.filter(operation='purchase.receive', resource=f'purchaseorder:{purchase.pk}')
    for detail, created_at in logs.values_list('detail', 'created_at'):
        try:
            arrived = date.fromisoformat(detail['received_date'])
        except (KeyError, TypeError, ValueError):
            arrived = timezone.localdate(created_at)
        for row in detail.get('lines') or []:
            try:
                line_id, pending = int(row['line']), Decimal(str(row.get('pending_quantity', '0')))
            except (KeyError, TypeError, ValueError, ArithmeticError):
                continue
            if pending > ZERO and arrived > result.get(line_id, date.min):
                result[line_id] = arrived
    return result


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
    return applicants_by_purchase([purchase])[purchase.pk]


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
    """{采购ID: 申请人ID集合}，含当前修改申请人；批量回查审计，供列表/工作台使用。"""
    if hasattr(purchases, 'values_list'):
        purchases = purchases.only('id', 'created_by_id', 'status').select_related(None).prefetch_related(None)
    purchases = list(purchases)
    result = _applicants({purchase.pk: purchase.created_by_id for purchase in purchases})
    for pk, pending in pending_requests(purchases).items():
        result[pk].add(pending['requested_by_id'])
    return result


def bom_cover(project, item_id, *, exclude_line=None):
    """本项目 BOM 对该物料的需求、已领、本项目已到货、在途与还可采购量；物料不在本项目 BOM 内返回 None。

    与关联 BOM 行的采购上限同一口径（需求 − 已领 − 在途），并扣除本项目已到货未领的部分，
    已收货待领的物料不会被当成缺口再买一遍；共享库存不预留，不计入。exclude_line 用于修改草稿时扣除本行。
    """
    needed = BOMLine.objects.filter(project=project, item_id=item_id).aggregate(total=Sum('quantity'))['total']
    if needed is None:
        return None
    lines = PurchaseLine.objects.filter(purchase__project=project, purchase__is_deleted=False, item_id=item_id)
    if exclude_line is not None:
        lines = lines.exclude(pk=exclude_line)
    totals = lines.aggregate(
        pending=Sum(
            F('quantity') - F('received_quantity') - F('cancelled_quantity'), filter=~Q(purchase__status='cancelled')
        ),
        received=Sum(F('received_quantity') - F('returned_quantity')),
    )
    used = issued(project, item_id)
    pending, received = totals['pending'] or ZERO, totals['received'] or ZERO
    return {
        'needed': needed,
        'issued': used,
        'received': received,
        'incoming': pending,
        'shortage': max(ZERO, needed - max(used, received) - pending),
    }


def bom_overrun(project, item, qty, *, exclude_line=None, cover=None):
    """未关联 BOM 行的采购明细超出本项目该物料缺口时返回说明；不在 BOM 内或未超出返回 None。"""
    cover = bom_cover(project, item.pk, exclude_line=exclude_line) if cover is None else cover
    if cover is None or qty <= cover['shortage']:
        return None
    return {
        'item': item.pk,
        'label': f'{item.code} {item.name}',
        'quantity': str(qty),
        'excess': str(qty - cover['shortage']),
        **{key: str(value) for key, value in cover.items()},
    }


def overrun_text(row):
    return (
        f'{row["label"]}：BOM 需求 {row["needed"]}、已领 {row["issued"]}、本项目已到货 {row["received"]}、'
        f'在途 {row["incoming"]}，还可采购 {row["shortage"]}，本单 {row["quantity"]}（超出 {row["excess"]}）'
    )


def require_overrun_reason(overruns, reason):
    """手工采购不得悄悄绕过 BOM 缺口：超出时不拒绝（备件、损耗补买），但必须写明原因并留审计。"""
    if overruns and not reason:
        raise ValidationError(
            {
                'over_bom_reason': '以下物料超出本项目 BOM 缺口：'
                + '；'.join(overrun_text(row) for row in overruns)
                + '。按 BOM 补缺请改用「从 BOM 多选下单」；确需超量采购（备件、损耗补买等）请填写超 BOM 采购原因。'
            }
        )


def bom_review(purchase):
    """审批时按最新 BOM 复核本单未关联 BOM 行的明细：超出本项目缺口或不在 BOM 内的逐条列出，附申请时填写的原因。"""
    notes, warnings, over, outside = {}, [], [], []
    for line in purchase.lines.select_related('item').order_by('pk'):
        open_quantity = line.quantity - line.cancelled_quantity - line.received_quantity
        if line.bom_line_id or open_quantity <= ZERO:
            continue
        cover = bom_cover(purchase.project, line.item_id, exclude_line=line.pk)
        if cover is None:
            outside.append(line.item.name)
            notes[str(line.pk)] = '不在本项目 BOM'
            continue
        row = bom_overrun(purchase.project, line.item, open_quantity, cover=cover)
        if row:
            over.append(f'{line.item.name} +{row["excess"]}')
            notes[str(line.pk)] = f'超出 BOM 缺口 +{row["excess"]}（还可采购 {row["shortage"]}）'
    if over:
        warnings.append(f'本单含 {len(over)} 行超出 BOM 需求：{"、".join(over)}')
    if outside:
        warnings.append(f'本单含 {len(outside)} 行物料不在本项目 BOM：{"、".join(outside)}')
    reason = ''
    if warnings:
        log = (
            AuditLog.objects.filter(
                resource=f'purchaseorder:{purchase.pk}',
                operation__in=['purchase.create', 'purchase.edit'],
                detail__has_key='over_bom_reason',
            )
            .order_by('-id')
            .first()
        )
        reason = log.detail['over_bom_reason'] if log else ''
    return {'bom_warnings': warnings, 'bom_lines': notes, 'over_bom_reason': reason}


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
                'code',
                'warranty_months',
                'over_bom_reason',
            },
        )
        state(project, {'active', 'delivering', 'warranty'})
        over_bom_reason = text(data, 'over_bom_reason', default='')
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
        overruns = []
        purchase = save(
            PurchaseOrder(
                code=CodeRule.generate_code('purchase', custom=text(data, 'code', default='', maximum=30)),
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
            if bom is None:
                # 先于本行落库计算，本单前面已保存的同物料明细计入在途。
                overrun = bom_overrun(project, items[item_id], qty)
                if overrun:
                    overruns.append(overrun)
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
        require_overrun_reason(overruns, over_bom_reason)
        if overruns:
            return audit(user, 'purchase.create', purchase, over_bom=overruns, over_bom_reason=over_bom_reason)
        return audit(user, 'purchase.create', purchase)

    return project_action(actor, key, 'purchase.create', data.get('project'), data, PURCHASERS, execute)


def purchase_action(actor, key, operation, purchase_id, data, roles, execute, *, authorize_action=None):
    purchase = lookup(PurchaseOrder, purchase_id)

    def perform(user, project):
        current = get_object_or_404(PurchaseOrder.objects.select_for_update(), pk=purchase.pk, project=project)
        return execute(user, current)

    return project_action(
        actor,
        key,
        operation,
        purchase.project_id,
        {'purchase': purchase.pk, 'data': data},
        roles,
        perform,
        authorize_action=authorize_action,
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
        require_no_request(purchase)
        report = purchase_check(purchase)
        reason = text(data, 'reason', default='')
        # 管理员审批本人申请的例外仍须写明原因：按用户实际填写的内容判断，不用缺省动作名凑数。
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
        reason = reason or '批准采购'
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
            bom_check=bom_review(purchase),
        )

    operation = 'purchase.approve_over_budget' if override else 'purchase.approve'
    return purchase_action(actor, key, operation, purchase_id, data, PURCHASE_APPROVERS, execute)


def _cancel_requested(data):
    """收货请求里是否有「余量不再到货」的明细；用于在授权阶段追加采购权限校验。"""
    lines = data.get('lines') if isinstance(data, dict) else None
    return isinstance(lines, list) and any(
        isinstance(row, dict) and row.get('cancel_remainder') is True for row in lines
    )


def _require_cancel_permission(user, project):
    """取消未收余量属于采购职责：收货时一并取消也要有采购岗位及本项目范围，与 cancel-remainder 相同。"""
    try:
        require_role(user, PURCHASERS)
        require_project(user, project, PURCHASERS)
    except PermissionDenied as exc:
        raise PermissionDenied(
            '「余量不再到货」会取消未收余量并冲减应付，需要采购权限；请由采购在「取消未收余量」处理。'
        ) from exc


def receive(actor, key, purchase_id, data, *, from_quarantine=False):
    def execute(user, purchase):
        allowed = {'location', 'new_location', 'lines', 'reason', 'received_date', 'backfill_reason'}
        fields(data, allowed if from_quarantine else allowed | {'cancel_reason'})
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
        # 正常到货的说明选填（可写送货单号），缺省记为动作名；补录、退货、取消等纠错动作仍须写明原因。
        reason = text(data, 'reason', default='') or ('隔离品合格入库' if from_quarantine else '采购收货')
        lines = {line.pk: line for line in purchase.lines.select_for_update().order_by('item_id', 'pk')}
        selected, seen, remarks = {}, set(), {}
        # 「余量不再到货」：本次收货后取消该明细剩余未收数量，{明细ID: 请求中的行号}。
        cancels = {}
        row_fields = {'line', 'quantity', 'pending_quantity', 'remark'}
        for index, row in enumerate(rows(data)):
            fields(row, row_fields if from_quarantine else row_fields | {'cancel_remainder'})
            try:
                remark = text(row, 'remark', default='')
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
            cancel = row.get('cancel_remainder', False)
            if not isinstance(cancel, bool):
                raise ValidationError({'lines': {index: {'cancel_remainder': '必须为布尔值。'}}})
            line_id = identity(row.get('line'), 'line')
            if line_id in seen or line_id not in lines:
                raise ValidationError('收货明细重复或不属于此采购单。')
            seen.add(line_id)
            qty = number(row.get('quantity'), 'quantity', 3)
            pending = number(row.get('pending_quantity', '0'), 'pending_quantity', 3)
            line = lines[line_id]
            if cancel:
                cancels[line_id] = index
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
        if not selected and not cancels:
            raise ValidationError('请至少填写一条到货数量。')
        if cancels:
            cancel_reason = text(data, 'cancel_reason')
        elif 'cancel_reason' in data:
            raise ValidationError({'cancel_reason': '没有勾选「余量不再到货」的明细，无需填写取消原因。'})
        if from_quarantine:
            arrivals = quarantine_arrivals(purchase)
            for line_id in selected:
                arrived = arrivals.get(line_id)
                if arrived and received_date < arrived:
                    raise ValidationError(
                        {
                            'received_date': f'合格入库日期不能早于{lines[line_id].item.name}的隔离到货日期 '
                            f'{arrived.isoformat()}，请填写该日期当天或之后的检验合格日期。'
                        }
                    )
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
        operation = 'purchase.quality_accept' if from_quarantine else 'purchase.receive'
        result = {'id': purchase.pk}
        if selected:
            result = audit(
                user,
                operation,
                purchase,
                lines=data['lines'],
                reason=f'{reason}；补录原因：{backfill_reason}' if backfill_reason else reason,
                received_date=received_date.isoformat(),
                backfill_reason=backfill_reason,
            )
        if cancels:
            # 与「取消未收余量」同一套规则：只取消本次收货后的剩余数量，隔离中的明细先处理，应付按累计舍入差冲减。
            remainder = {}
            for line_id, index in cancels.items():
                line = lines[line_id]
                remainder[line_id] = line.quantity - line.received_quantity - line.cancelled_quantity
                if remainder[line_id] <= ZERO:
                    raise ValidationError({'lines': {index: {'cancel_remainder': '本次已收足，没有余量可取消。'}}})
            cancel_lines(user, purchase, list(lines.values()), remainder, cancel_reason)
            result = {**result, 'cancelled': [{'line': pk, 'quantity': str(qty)} for pk, qty in remainder.items()]}
        return result

    return purchase_action(
        actor,
        key,
        'purchase.quality_accept' if from_quarantine else 'purchase.receive',
        purchase_id,
        data,
        WAREHOUSE,
        execute,
        authorize_action=None if from_quarantine or not _cancel_requested(data) else _require_cancel_permission,
    )


def cancel_lines(user, purchase, lines, selected, reason):
    """取消所选明细的未收余量，「取消未收余量」与收货时「余量不再到货」共用。

    lines 是本单已加锁的全部明细，selected 是 {明细ID: 取消数量}。所选明细有隔离数量时先处理隔离品；
    应付按累计舍入差冲减，明细全部收完或取消时结束采购，并写入 purchase.cancel_remainder 审计。
    """
    by_id = {line.pk: line for line in lines}
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


def cancel_remainder(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'reason', 'lines'})
        reason = text(data, 'reason')
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft', 'submitted', 'approved', 'partial'})
        # 待审批单按草稿规则整单作废（尚无应付）；修改申请待审批人处理时不替对方关闭申请。
        if purchase.status == 'submitted' and pending_requests([purchase]):
            raise Conflict('已有待处理的修改申请，请先由审批人处理后再作废。')
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
        return cancel_lines(user, purchase, lines, selected, reason)

    return purchase_action(actor, key, 'purchase.cancel_remainder', purchase_id, data, PURCHASERS, execute)


def reject(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'reason'})
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'submitted'})
        require_no_request(purchase)
        reason = text(data, 'reason')
        self_approval = independent_approval(user, purchase_applicants(purchase), reason)
        purchase.status = 'draft'
        save(purchase, user)
        return audit(user, 'purchase.reject', purchase, reason=reason, self_approval=self_approval)

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
        reason = text(data, 'reason', default='') or '更新到货计划'
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
                'over_bom_reason',
            },
        )
        state(purchase.project, {'active', 'delivering', 'warranty'})
        state(purchase, {'draft'})
        over_bom_reason = text(data, 'over_bom_reason', default='')
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
        before, overruns = [], []
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
            elif qty > line.quantity:
                overrun = bom_overrun(purchase.project, line.item, qty, exclude_line=line.pk)
                if overrun:
                    overruns.append(overrun)
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
        require_overrun_reason(overruns, over_bom_reason)
        save(purchase, user)
        extra = {'over_bom': overruns, 'over_bom_reason': over_bom_reason} if overruns else {}
        return audit(user, 'purchase.edit', purchase, before=before, after=data, reason=reason, **extra)

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
