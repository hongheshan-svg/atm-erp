import hashlib
import re
from decimal import Decimal

from django.db.models import F, Sum
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.permissions import MANAGERS

from ..models import BOMLine, PurchaseLine, Stock, StockMove
from .common import (
    ZERO,
    audit,
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


def demand(project):
    result = []
    lines = list(BOMLine.objects.filter(project=project).select_related('item').order_by('item_id', 'pk'))
    item_ids = {line.item_id for line in lines}
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
                'brand': line.item.brand,
                'part_type': line.item.part_type,
                'assembly_unit': line.assembly_unit,
                'unit': line.item.unit,
                'is_active': line.item.is_active,
                'quantity': str(line.quantity),
                'issued': str(used),
                'incoming': str(ordered),
                'available': str(available),
                'shortage': str(max(ZERO, needed - ordered - available)),
            }
        )
    return result


def preview_revision(actor, project, data):
    import uuid

    from django.db import transaction
    from rest_framework.exceptions import APIException

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
            fields(row, {'item', 'quantity', 'change_note', 'assembly_unit', 'id'})
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
                pending = (
                    PurchaseLine.objects.filter(bom_line=current, purchase__is_deleted=False)
                    .exclude(purchase__status='cancelled')
                    .aggregate(total=Sum(F('quantity') - F('received_quantity') - F('cancelled_quantity')))['total']
                    or ZERO
                )
                if qty < pending:
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
            )
        return {'id': project.pk, 'revision': revision(project)}

    return project_action(actor, key, 'bom.revise', project_id, data, MANAGERS, execute)
