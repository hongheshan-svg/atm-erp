import hashlib
import re
from decimal import Decimal

from django.db.models import F, Sum
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.permissions import BOM_WRITERS, require_project

from ..models import BOMLine, PurchaseLine, Stock, StockMove
from .common import (
    ZERO,
    audit,
    day,
    fields,
    identity,
    lock_items,
    number,
    project_action,
    rows,
    save,
    state,
    text,
)


def incoming(project, item_id):
    return (
        PurchaseLine.objects.filter(purchase__project=project, purchase__is_deleted=False, item_id=item_id)
        .exclude(purchase__status='cancelled')
        .aggregate(total=Sum(F('quantity') - F('received_quantity') - F('cancelled_quantity')))['total']
        or ZERO
    )


def linked_incoming(bom_line, *, exclude_line=None):
    """挂在这条 BOM 行上、尚未收货或取消的采购数量。"""
    queryset = PurchaseLine.objects.filter(bom_line=bom_line, purchase__is_deleted=False).exclude(
        purchase__status='cancelled'
    )
    if exclude_line is not None:
        queryset = queryset.exclude(pk=exclude_line)
    return (
        queryset.aggregate(total=Sum(F('quantity') - F('received_quantity') - F('cancelled_quantity')))['total'] or ZERO
    )


def check_line_limit(bom_line, quantity, *, exclude_line=None):
    """多单元同物料时，采购必须落到实际需要它的那一行，不能借用其他单元的用量。"""
    if quantity > bom_line.quantity - linked_incoming(bom_line, exclude_line=exclude_line):
        raise Conflict(
            f'采购数量超过该 BOM 行（{bom_line.assembly_unit or "未分单元"}）的剩余需求；'
            '其他单元的用量请分别挂到对应 BOM 行。'
        )


def issued(project, item_id):
    return -(
        StockMove.objects.filter(project=project, stock__item_id=item_id, kind__in=['issue', 'return'])
        .exclude(task__kind='service')
        .aggregate(total=Sum('quantity'))['total']
        or ZERO
    )


def revision(project):
    content = '|'.join(
        f'{line.pk}:{line.item_id}:{line.quantity}:{line.updated_at.isoformat()}'
        for line in BOMLine.objects.filter(project=project).order_by('pk')
    )
    return hashlib.sha256(content.encode()).hexdigest()


def competing_demand(project, item_ids):
    """其他在执行项目对同一物料还没领走的需求量。

    库存是共享的、不预留的，两个项目各自看到同一批库存都会算成「可用」，于是两边都不下单。
    把冲突显式摆到缺料行上，采购员才有机会判断这批库存到底该归谁。
    """
    outstanding = {}
    for row in (
        BOMLine.objects.filter(item_id__in=item_ids, project__status__in=['active', 'delivering'])
        .exclude(project=project)
        .values('item_id', 'project_id')
        .annotate(total=Sum('quantity'))
    ):
        outstanding[(row['project_id'], row['item_id'])] = row['total']
    for row in (
        StockMove.objects.filter(stock__item_id__in=item_ids, kind__in=['issue', 'return'])
        .exclude(task__kind='service')
        .exclude(project=project)
        .values('project_id', 'stock__item_id')
        .annotate(total=Sum('quantity'))
    ):
        key = (row['project_id'], row['stock__item_id'])
        if key in outstanding:
            outstanding[key] += row['total']
    result = {}
    for (_, item_id), quantity in outstanding.items():
        if quantity > ZERO:
            current = result.setdefault(item_id, {'quantity': ZERO, 'projects': 0})
            current['quantity'] += quantity
            current['projects'] += 1
    return result


def claimed_by_others(project, item_id):
    """其他在执行项目为自己采购到货、还没领走且仍在其 BOM 需求内的数量，按项目列出。

    库存不预留；这里只把「别人的到货」显式算出来，领料挪用时让仓管确认并留痕。
    """
    received = {
        row['project_id']: row['total']
        for row in StockMove.objects.filter(
            stock__item_id=item_id,
            kind__in=['receipt', 'purchase_return'],
            project__status__in=['active', 'delivering'],
        )
        .exclude(project=project)
        .values('project_id')
        .annotate(total=Sum('quantity'))
    }
    if not received:
        return {}
    used = {
        row['project_id']: -row['total']
        for row in StockMove.objects.filter(
            stock__item_id=item_id, kind__in=['issue', 'return'], project_id__in=list(received)
        )
        .exclude(task__kind='service')
        .values('project_id')
        .annotate(total=Sum('quantity'))
    }
    needed = {
        row['project_id']: row['total']
        for row in BOMLine.objects.filter(item_id=item_id, project_id__in=list(received))
        .values('project_id')
        .annotate(total=Sum('quantity'))
    }
    result = {}
    for project_id, quantity in received.items():
        taken = used.get(project_id, ZERO)
        claim = min(quantity - taken, needed.get(project_id, ZERO) - taken)
        if claim > ZERO:
            result[project_id] = claim
    return result


def demand(project):
    result = []
    lines = list(BOMLine.objects.filter(project=project).select_related('item').order_by('item_id', 'pk'))
    item_ids = {line.item_id for line in lines}
    competing = competing_demand(project, item_ids)
    remaining_used = {pk: ZERO for pk in item_ids}
    remaining_stock = {pk: ZERO for pk in item_ids}
    remaining_incoming = {pk: ZERO for pk in item_ids}
    line_incoming = {}
    line_ids = {line.pk for line in lines}
    for row in (
        StockMove.objects.filter(project=project, stock__item_id__in=item_ids, kind__in=['issue', 'return'])
        .exclude(task__kind='service')
        .values('stock__item_id')
        .annotate(total=Sum('quantity'))
    ):
        remaining_used[row['stock__item_id']] = -row['total']
    for row in Stock.objects.filter(item_id__in=item_ids).values('item_id').annotate(total=Sum('quantity')):
        remaining_stock[row['item_id']] = row['total']
    for row in (
        PurchaseLine.objects.filter(purchase__project=project, purchase__is_deleted=False, item_id__in=item_ids)
        .exclude(purchase__status='cancelled')
        .values('item_id', 'bom_line_id')
        .annotate(total=Sum(F('quantity') - F('received_quantity') - F('cancelled_quantity')))
    ):
        if row['bom_line_id'] in line_ids:
            line_incoming[row['bom_line_id']] = row['total']
        else:
            remaining_incoming[row['item_id']] += row['total']
    for line in lines:
        # 按行校验之前的历史采购可能在某一行上挂超；多出的在途仍是同一物料，交给其他单元共享。
        excess = line_incoming.get(line.pk, ZERO) - line.quantity
        if excess > ZERO:
            remaining_incoming[line.item_id] += excess
    for line in lines:
        assigned = min(line.quantity, line_incoming.get(line.pk, ZERO))
        used = min(line.quantity - assigned, remaining_used[line.item_id])
        remaining_used[line.item_id] -= used
        shared = min(line.quantity - used - assigned, remaining_incoming[line.item_id])
        ordered = assigned + shared
        remaining_incoming[line.item_id] -= shared
        available = min(line.quantity - used - ordered, remaining_stock[line.item_id])
        remaining_stock[line.item_id] -= available
        needed = max(ZERO, line.quantity - used)
        result.append(
            {
                'bom_line': line.pk,
                'item': line.item_id,
                'item_code': line.item.code,
                'item_name': line.item.name,
                'specification': line.item.specification,
                'drawing_number': line.item.drawing_number,
                'drawing_revision': line.item.drawing_revision,
                'product_category': line.item.product_category,
                'required_date': line.required_date.isoformat() if line.required_date else None,
                'application_date': line.application_date.isoformat() if line.application_date else None,
                'applicant': line.applicant,
                'brand': line.item.brand,
                'part_type': line.item.part_type,
                'assembly_unit': line.assembly_unit,
                'unit': line.item.unit,
                'is_active': line.item.is_active,
                'quantity': str(line.quantity),
                'change_note': line.change_note,
                'issued': str(used),
                'incoming': str(ordered),
                'available': str(available),
                'other_demand': str(competing.get(line.item_id, {}).get('quantity', ZERO)),
                'other_projects': competing.get(line.item_id, {}).get('projects', 0),
                'shortage': str(max(ZERO, needed - ordered - available)),
            }
        )
    return result


def preview_revision(actor, project, data):
    import uuid

    from django.db import transaction
    from rest_framework.exceptions import APIException

    require_project(actor, project, BOM_WRITERS)
    fields(data, {'expected_revision', 'lines'})
    before = impact(project)
    before_lines = {line.pk: line for line in project.bom_lines.all()}
    totals = {row['item']: Decimal(row['quantity']) for row in before['items']}
    for row in rows(data):
        item = identity(row.get('item'), 'item')
        current = (
            before_lines.get(identity(row['id'], 'id'))
            if row.get('id')
            else next(
                (
                    line
                    for line in before_lines.values()
                    if line.item_id == item and line.assembly_unit == row.get('assembly_unit', line.assembly_unit)
                ),
                None,
            )
        )
        totals[item] = (
            totals.get(item, ZERO)
            + number(row.get('quantity'), 'quantity', 3, positive=True)
            - (current.quantity if current else ZERO)
        )
    blockers = []
    try:
        with transaction.atomic():
            revise_bom(actor, str(uuid.uuid4()), project.pk, data)
            transaction.set_rollback(True)
    except APIException as exc:

        def explain(value):
            if isinstance(value, dict):
                return '；'.join(explain(item) for item in value.values())
            if isinstance(value, list):
                return '；'.join(explain(item) for item in value)
            return str(value)

        blockers.append(explain(exc.detail))
    for row in before['items']:
        target = totals.get(row['item'], ZERO)
        row['after'] = str(target)
        row['difference'] = str(target - Decimal(row['quantity']))
        row['unresolved_quantity'] = str(max(ZERO, Decimal(row['minimum']) - target))
    return {**before, 'project': project.pk, 'can_apply': not blockers, 'blockers': blockers}


def impact(project):
    """Read-only source links for resolving an engineering change, never a second ledger."""
    items = {}
    for line in demand(project):
        item = items.setdefault(
            line['item'],
            {
                'item': line['item'],
                'item_code': line['item_code'],
                'item_name': line['item_name'],
                'quantity': ZERO,
                'issued': ZERO,
                'incoming': ZERO,
            },
        )
        item['quantity'] += number(line['quantity'], 'quantity', 3)
        item['issued'] += number(line['issued'], 'issued', 3)
        item['incoming'] += number(line['incoming'], 'incoming', 3)
    return {
        'revision': revision(project),
        'items': [
            {
                **row,
                'quantity': str(row['quantity']),
                'issued': str(row['issued']),
                'incoming': str(row['incoming']),
                'minimum': str(row['issued'] + row['incoming']),
            }
            for row in items.values()
        ],
        'purchases': list(
            project.purchases.exclude(status__in=['received', 'cancelled']).values('id', 'code', 'status')
        ),
        'note': '减少总量前先取消采购余量、处理隔离到货和退回未用材料；替换型号请新增物料行。已交付所需材料不能退回。单元的已领、在途和库存为按行顺序分摊显示，不代表单元专属库存。',
    }


def revise_bom(actor, key, project_id, data):
    def execute(user, project):
        fields(data, {'lines', 'expected_revision'})
        state(project, {'draft', 'quoted', 'active', 'delivering'})
        expected = data.get('expected_revision')
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValidationError({'expected_revision': '请提供读取 BOM 时的版本，刷新后重试。'})
        if expected != revision(project):
            raise Conflict('BOM 已改变，请重新预览。')
        planned = {}
        existing = list(BOMLine.objects.filter(project=project))
        for row in rows(data):
            fields(
                row,
                {
                    'item',
                    'quantity',
                    'change_note',
                    'assembly_unit',
                    'id',
                    'required_date',
                    'application_date',
                    'applicant',
                },
            )
            item_id = identity(row.get('item'), 'item')
            matching = [line for line in existing if line.item_id == item_id]
            unit = (
                text(row, 'assembly_unit', default='', maximum=100)
                if 'assembly_unit' in row
                else (matching[0].assembly_unit if len(matching) == 1 else '')
            )
            line_key = (item_id, unit)
            if line_key in planned:
                raise ValidationError('同一物料在同一单元只能出现一次。')
            planned[line_key] = row
        items = lock_items({item_id for item_id, unit in planned})
        totals = {}
        for line in existing:
            totals[line.item_id] = totals.get(line.item_id, ZERO) + line.quantity
        prepared = []
        seen_ids = set()
        for (item_id, unit), row in planned.items():
            if not items[item_id].is_active:
                raise ValidationError('BOM 不能添加或修改为已停用物料。')
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            if row.get('id') is not None:
                line_id = identity(row['id'], 'id')
                current = next((line for line in existing if line.pk == line_id and line.item_id == item_id), None)
                if current is None or line_id in seen_ids:
                    raise ValidationError('BOM 行不存在、重复或物料已改变。替换物料请新增行并处理原行。')
                if any(
                    line.pk != line_id and line.item_id == item_id and line.assembly_unit == unit for line in existing
                ):
                    raise ValidationError('目标单元已存在此物料。')
            else:
                current = next(
                    (line for line in existing if line.item_id == item_id and line.assembly_unit == unit), None
                )
            if current:
                if current.pk in seen_ids:
                    raise ValidationError('同一 BOM 行不能在一次修订中重复修改。')
                seen_ids.add(current.pk)
            note = text(row, 'change_note', default='' if current is None else None)
            if current:
                if qty < linked_incoming(current):
                    raise Conflict('单元用量不能小于该 BOM 行在途采购，请先取消相关余量。')
            totals[item_id] = totals.get(item_id, ZERO) + qty - (current.quantity if current else ZERO)
            prepared.append((item_id, unit, qty, note, current))
        for item_id, qty in totals.items():
            if qty < issued(project, item_id) + incoming(project, item_id):
                raise Conflict('BOM 数量不能小于已领用和在途采购数量，请先处理相关单据。')
        for item_id, unit, qty, note, current in prepared:
            before = str(current.quantity) if current else None
            line = current or BOMLine(project=project, item=items[item_id])
            line.quantity, line.change_note = qty, note
            before_unit = line.assembly_unit
            line.assembly_unit = unit
            row = planned[(item_id, unit)]
            before_request = {
                field: str(getattr(line, field) or '') for field in ('required_date', 'application_date', 'applicant')
            }
            for field in ('required_date', 'application_date'):
                if field in row:
                    setattr(line, field, day(row, field, optional=True))
            if 'applicant' in row:
                line.applicant = text(row, 'applicant', default='', maximum=80)
            save(line, user)
            audit(
                user,
                'bom.revise',
                line,
                before=before,
                after=str(qty),
                reason=note,
                before_unit=before_unit,
                after_unit=line.assembly_unit,
                before_request=before_request,
                after_request={field: str(getattr(line, field) or '') for field in before_request},
            )
        return {'id': project.pk, 'revision': revision(project)}

    return project_action(actor, key, 'bom.revise', project_id, data, BOM_WRITERS, execute)
