import hashlib
import re

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
    for line in BOMLine.objects.filter(project=project).select_related('item').order_by('item_id'):
        used = issued(project, line.item_id)
        ordered = incoming(project, line.item_id)
        available = Stock.objects.filter(item_id=line.item_id).aggregate(total=Sum('quantity'))['total'] or ZERO
        needed = max(ZERO, line.quantity - used)
        result.append(
            {
                'bom_line': line.pk,
                'item': line.item_id,
                'item_code': line.item.code,
                'item_name': line.item.name,
                'quantity': str(line.quantity),
                'issued': str(used),
                'incoming': str(ordered),
                'available': str(available),
                'shortage': str(max(ZERO, needed - ordered - available)),
            }
        )
    return result


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
        for row in rows(data):
            fields(row, {'item', 'quantity', 'change_note'})
            item_id = identity(row.get('item'), 'item')
            if item_id in planned:
                raise ValidationError('一次修订中同一物料只能出现一次。')
            planned[item_id] = row
        items = lock_items(planned)
        for item_id, row in planned.items():
            if not items[item_id].is_active:
                raise ValidationError('BOM 不能添加或修改为已停用物料。')
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            current = BOMLine.objects.filter(project=project, item_id=item_id).first()
            note = text(row, 'change_note', default='' if current is None else None)
            if qty < issued(project, item_id) + incoming(project, item_id):
                raise Conflict('BOM 数量不能小于已领用和在途采购数量，请先处理相关单据。')
            before = str(current.quantity) if current else None
            line = current or BOMLine(project=project, item=items[item_id])
            line.quantity, line.change_note = qty, note
            save(line, user)
            audit(user, 'bom.revise', line, before=before, after=str(qty), reason=note)
        return {'id': project.pk, 'revision': revision(project)}

    return project_action(actor, key, 'bom.revise', project_id, data, MANAGERS, execute)
