"""换版（非标件升版或换型）：BOM 行换成新物料，旧版在途按新图改单，多出来的旧版实物转为「旧版待处理」。

- 换版不再因旧版在途或已领用被拦截。关联原 BOM 行、尚未到货的旧版采购转为新版：未批准的直接改这一行；
  已批准的取消旧版余量、同单新增新版明细，待采购向供应商确认（可调价）或取消，确认前不能收货。
- 「旧版待处理」按项目实时口径计算，不另记余额：已领用、到货未领中超出现 BOM 需求的旧版，扣除已登记的处理。
  在库的由仓管报废出库或留作公用备件；已装机的可登记报废；返修改制由采购另开返修采购单，
  在库旧版返修的收货时同数量旧版出库（送修改制），报废和送修出库都计入项目材料成本。
"""

import uuid
from decimal import Decimal

from django.db.models import F, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.permissions import (
    BOM_WRITERS,
    PURCHASE_APPROVERS,
    PURCHASERS,
    WAREHOUSE,
    has_role,
    projects_for,
    require_project,
    require_role,
)

from ..models import (
    BOMLine,
    Entry,
    Item,
    Project,
    PurchaseLine,
    PurchaseOrder,
    RevisionChange,
    RevisionDisposition,
    Stock,
    StockMove,
)
from .approval import independent_approval
from .bom import ARRIVAL_KINDS, BOM_STATES, incoming_by_item, issued_by_item, received_unissued_by_item
from .common import ZERO, audit, day, fields, identity, lock_items, number, project_action, rounded, save, state, text

REWORK_ROLES = {'rework_stock': 'stock', 'rework_issued': 'issued'}
SOURCE_LABELS = dict(RevisionDisposition.Source.choices)
KIND_LABELS = dict(RevisionDisposition.Kind.choices)
# 已装机旧版的报废由懂现场的人登记（仓管、工程师或项目经理）；在库旧版的出库和留用只由仓管登记。
DISPOSERS = WAREHOUSE | BOM_WRITERS
PARTS_READERS = DISPOSERS | PURCHASERS


def nested_key(key, *parts):
    """同一动作里再调用另一个带回执的动作时，由外层幂等键派生，重放时得到同一个内层键。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, ':'.join(str(part) for part in (key, *parts))))


def unreceived(line):
    """尚未到货的余量：不含已收、已取消和隔离待检（隔离的是已到的旧版实物，留在旧版明细上处理）。"""
    return line.quantity - line.received_quantity - line.cancelled_quantity - line.pending_quantity


def lock_convertible(old_lines):
    """按全局锁顺序（PurchaseOrder → PurchaseLine）锁定关联原 BOM 行且仍有未到货余量的采购明细。"""
    from .purchase_changes import pending_requests

    line_ids = [line.pk for line in old_lines]
    if not line_ids:
        return []
    purchase_ids = sorted(
        set(
            PurchaseLine.objects.filter(bom_line_id__in=line_ids, purchase__is_deleted=False)
            .exclude(purchase__status__in=['cancelled', 'received'])
            .values_list('purchase_id', flat=True)
        )
    )
    if purchase_ids:
        list(PurchaseOrder.objects.select_for_update().filter(pk__in=purchase_ids).order_by('pk'))
    lines = [
        line
        for line in PurchaseLine.objects.select_for_update(of=('self',))
        .select_related('purchase')
        .filter(bom_line_id__in=line_ids, purchase__is_deleted=False)
        .exclude(purchase__status__in=['cancelled', 'received'])
        .order_by('purchase_id', 'pk')
        if unreceived(line) > ZERO
    ]
    waiting = pending_requests([line.purchase for line in lines])
    if waiting:
        codes = '、'.join(sorted({line.purchase.code for line in lines if line.purchase.pk in waiting}))
        raise Conflict(f'采购单 {codes} 有待审批的修改申请，请先由审批人处理后再换版。')
    return lines


def convertible(old_line):
    """关联原 BOM 行、仍有未到货余量的采购明细（采购单未作废、未收完、未删除），加锁后按采购单和明细排序。"""
    return lock_convertible([old_line])


def convert_purchases(user, change, lines):
    """把旧版未到货余量转为新版；返回 [{purchase, code, quantity, pending}] 供提示和审计。"""
    from .supply import receiving_status

    result, touched = [], {}
    for line in lines:
        purchase = line.purchase
        remainder = unreceived(line)
        extra_audit = {}
        if purchase.status in {'draft', 'submitted'}:
            # 未批准：这一行直接改成新版，审批人批准的就是新版。
            line.item, line.bom_line = change.new_item, change.new_line
            line.revision, line.revision_role = change, 'converted'
            save(line, user)
            converted = line
        else:
            # 已批准：旧版余量取消（应付按累计舍入差冲减，与取消未收余量同一算法），同单新增新版明细，
            # 应付按新版明细金额增加（保持 Entry 净额与逐行有效金额合计一致）；待采购确认新图或取消。
            retained = line.quantity - line.cancelled_quantity
            credit = rounded(retained * line.unit_price) - rounded((retained - remainder) * line.unit_price)
            new_amount = rounded(remainder * line.unit_price)
            rounding_delta = new_amount - credit
            line.cancelled_quantity += remainder
            save(line, user)
            converted = save(
                PurchaseLine(
                    purchase=purchase,
                    item=change.new_item,
                    bom_line=change.new_line,
                    quantity=remainder,
                    unit_price=line.unit_price,
                    due_date=line.due_date,
                    revision=change,
                    revision_role='converted',
                    revision_pending=True,
                ),
                user,
            )
            entry = Entry.objects.select_for_update().filter(purchase=purchase).first()
            if entry:
                if entry.amount + new_amount < entry.credit_amount + credit:
                    raise Conflict('换版改单后应付金额小于已冲减金额，请先核对应付。')
                entry.amount += new_amount
                entry.credit_amount += credit
                save(entry, user)
            extra_audit = {'credit': str(credit)}
            if rounding_delta != ZERO:
                extra_audit['rounding_delta'] = str(rounding_delta)
            touched[purchase.pk] = purchase
        audit(
            user,
            'purchase.revision_convert',
            purchase,
            line=line.pk,
            converted_line=converted.pk,
            quantity=str(remainder),
            old_item=change.old_item.code,
            new_item=change.new_item.code,
            change=change.pk,
            reason=change.reason,
            pending=converted.revision_pending,
            **extra_audit,
        )
        result.append(
            {
                'purchase': purchase.pk,
                'code': purchase.code,
                'quantity': str(remainder),
                'pending': converted.revision_pending,
            }
        )
    for purchase in touched.values():
        purchase.status = receiving_status(purchase.lines.all())
        save(purchase, user)
    return result


def converted_minimum(project, old_line, item, converted):
    """旧版在途转为新版后，新版这一行至少要多少：新版已领用、在途加上转来的数量，扣除新版其他单元的需求。"""
    if not converted:
        return ZERO
    others = BOMLine.objects.filter(project=project, item=item).aggregate(total=Sum('quantity'))['total'] or ZERO
    used = issued_by_item(project, [item.pk])[item.pk] + incoming_by_item(project, [item.pk])[item.pk]
    return used + converted - others


def unreceived_by_line(line_ids):
    """{BOM 行: 关联采购的未到货余量}，换版时这些余量会按新图转为新版（与 convertible 同一口径，不加锁）。"""
    totals = {}
    for row in (
        PurchaseLine.objects.filter(bom_line_id__in=list(line_ids), purchase__is_deleted=False)
        .exclude(purchase__status__in=['cancelled', 'received'])
        .values('bom_line_id')
        .annotate(total=Sum(F('quantity') - F('received_quantity') - F('cancelled_quantity') - F('pending_quantity')))
    ):
        totals[row['bom_line_id']] = row['total'] or ZERO
    return totals


def conversion_problems(project, existing, updates, replacements):
    """导入预览：换版行的旧版在途转为新版后，新版各单元需求合计须覆盖新版已领、在途和转来的数量。

    existing 为当前 BOM 行，updates 为 [(原 BOM 行或 None, 物料, 新数量)]（含换版新增的新版行），
    replacements 为 [(原 BOM 行 ID, 新物料, 行号)]；返回 [{'row', 'message'}]。
    """
    converted = unreceived_by_line([pk for pk, _, _ in replacements])
    incoming, rows = {}, {}
    for pk, item_id, row in replacements:
        if converted.get(pk, ZERO) > ZERO:
            incoming[item_id] = incoming.get(item_id, ZERO) + converted[pk]
            rows.setdefault(item_id, row)
    if not incoming:
        return []
    totals = {}
    for line in existing:
        totals[line.item_id] = totals.get(line.item_id, ZERO) + line.quantity
    for current, item_id, qty in updates:
        totals[item_id] = totals.get(item_id, ZERO) + qty - (current.quantity if current else ZERO)
    ids = sorted(incoming)
    used, pending = issued_by_item(project, ids), incoming_by_item(project, ids)
    codes = dict(Item.objects.filter(pk__in=ids).values_list('pk', 'code'))
    problems = []
    for item_id in ids:
        minimum = used[item_id] + pending[item_id] + incoming[item_id]
        if totals.get(item_id, ZERO) < minimum:
            problems.append(
                {
                    'row': rows[item_id],
                    'message': f'旧版未到货 {incoming[item_id]} 将按新图转为 {codes[item_id]}；加上新版已领用和在途，'
                    f'新版各单元需求合计至少 {minimum}，当前为 {totals.get(item_id, ZERO)}。确需减少请先在采购单取消多余的旧版余量。',
                }
            )
    return problems


def change_revision(
    user, project, line, item, qty, note, details=None, *, operation='replace', pending_lines=None, items_locked=False
):
    """在调用方已锁定的项目里把 BOM 行 line（已加锁）换成物料 item，数量 qty；返回（换版记录，转换的采购）。

    旧版已领、已到货和在途都不再拦截：在途转新版，已领和到货多出的转「旧版待处理」。新物料须在用、
    与原物料不同，且原单元没有该物料（已有时请改那一行的数量并移除原行）。
    锁顺序严格遵循 Project → BOMLine → PurchaseOrder → PurchaseLine → Item → Entry。
    """
    details = details or {}
    if item.pk == line.item_id:
        raise ValidationError({'item': '请选择与原物料不同的新物料；只改数量请用「修改此行」。'})
    if pending_lines is None:
        pending_lines = convertible(line)
    if not items_locked:
        locked_items = lock_items({item.pk, line.item_id})
        item = locked_items[item.pk]
    if not item.is_active:
        raise ValidationError({'item': 'BOM 不能添加或修改为已停用物料。'})
    if BOMLine.objects.filter(project=project, item=item, assembly_unit=line.assembly_unit).exists():
        raise Conflict(
            f'单元「{line.assembly_unit or "未分单元"}」已有物料 {item.code}，请用「修改此行」调整该行数量后移除原行。'
        )
    converted_qty = sum((unreceived(row) for row in pending_lines), ZERO)
    minimum = converted_minimum(project, line, item, converted_qty)
    if qty < minimum:
        raise Conflict(
            f'旧版 {line.item.code} 还有 {converted_qty} 未到货，将按新图改为 {item.code}；加上新版已领用和在途，'
            f'这一行新版数量至少为 {minimum}。确需减少时，请先在采购单取消多余的旧版余量。'
        )
    replacement = BOMLine(
        project=project,
        item=item,
        quantity=qty,
        assembly_unit=line.assembly_unit,
        change_note=note,
        required_date=line.required_date,
        application_date=line.application_date,
        applicant=line.applicant,
    )
    for field in ('required_date', 'application_date'):
        if field in details:
            setattr(replacement, field, day(details, field, optional=True))
    if 'applicant' in details:
        replacement.applicant = text(details, 'applicant', default='', maximum=80)
    line.soft_delete(user)
    save(replacement, user)
    change = save(
        RevisionChange(
            project=project,
            old_item=line.item,
            new_item=item,
            old_line=line,
            new_line=replacement,
            assembly_unit=line.assembly_unit,
            old_quantity=line.quantity,
            new_quantity=qty,
            converted_quantity=converted_qty,
            reason=note,
        ),
        user,
    )
    converted = convert_purchases(user, change, pending_lines)
    detail = {
        'replaced_line': line.pk,
        'replaced_item': line.item.code,
        'replacement_item': item.code,
        'revision_change': change.pk,
        'revision_operation': operation,
        'converted': converted,
    }
    audit(
        user,
        'bom.remove',
        line,
        reason=note,
        quantity=str(line.quantity),
        assembly_unit=line.assembly_unit,
        replacement=replacement.pk,
        **detail,
    )
    audit(
        user,
        'bom.revise',
        replacement,
        before=None,
        after=str(qty),
        reason=note,
        before_unit='',
        after_unit=replacement.assembly_unit,
        **detail,
    )
    return change, converted


def live_target(change):
    """返修改制的目标 BOM 行：沿换版链（B 又换成 C）找到项目里仍在用的那一行，没有则返回 None。"""
    line, seen = change.new_line, set()
    while line.is_deleted and line.pk not in seen:
        seen.add(line.pk)
        following = (
            RevisionChange.objects.filter(project_id=change.project_id, old_line=line)
            .select_related('new_line__item')
            .order_by('-pk')
            .first()
        )
        if following is None:
            return None
        line = following.new_line
    return None if line.is_deleted else line


def leftovers(project, needed):
    """{旧物料: 数量明细}：按给定的现 BOM 需求算旧版余量与已处理、待处理数量。

    超出需求的已领用和到货未领（报废、送修出库已从到货里扣除）为旧版余量；在库的再扣除留作备件
    和尚未收货的在库返修，已领用的再扣除已登记报废和全部已装机返修（未作废的返修采购数量）。
    """
    ids = list(needed)
    if not ids:
        return {}
    used = issued_by_item(project, ids)
    stocked = received_unissued_by_item(project, ids)
    disposed = {
        (row['change__old_item_id'], row['source'], row['kind']): row['total']
        for row in RevisionDisposition.objects.filter(change__project=project, change__old_item_id__in=ids)
        .values('change__old_item_id', 'source', 'kind')
        .annotate(total=Sum('quantity'))
    }
    reworked = {
        (row['revision__old_item_id'], REWORK_ROLES[row['revision_role']]): (
            row['total'] or ZERO,
            row['received'] or ZERO,
        )
        for row in PurchaseLine.objects.filter(
            revision__project=project,
            revision__old_item_id__in=ids,
            revision_role__in=list(REWORK_ROLES),
            purchase__is_deleted=False,
        )
        .exclude(purchase__status='cancelled')
        .values('revision__old_item_id', 'revision_role')
        .annotate(total=Sum(F('quantity') - F('cancelled_quantity')), received=Sum('received_quantity'))
    }
    result = {}
    for item_id in ids:
        need = needed[item_id] or ZERO
        issued_qty = used[item_id]
        received = stocked.get(item_id, ZERO)
        excess_issued = max(ZERO, issued_qty - need)
        excess_stock = max(ZERO, received - max(ZERO, need - issued_qty))
        rework_issued, rework_issued_received = reworked.get((item_id, 'issued'), (ZERO, ZERO))
        rework_stock, rework_stock_received = reworked.get((item_id, 'stock'), (ZERO, ZERO))
        scrapped_issued = disposed.get((item_id, 'issued', 'scrap'), ZERO)
        kept = disposed.get((item_id, 'stock', 'keep'), ZERO)
        result[item_id] = {
            'need': need,
            'issued_total': issued_qty,
            'received_unissued': received,
            'issued': excess_issued,
            'stock': excess_stock,
            'scrapped_issued': scrapped_issued,
            'scrapped_stock': disposed.get((item_id, 'stock', 'scrap'), ZERO),
            'kept': kept,
            'rework_issued': rework_issued,
            'rework_issued_received': rework_issued_received,
            'rework_stock': rework_stock,
            'rework_stock_received': rework_stock_received,
            'pending_issued': max(ZERO, excess_issued - scrapped_issued - rework_issued),
            'pending_stock': max(ZERO, excess_stock - kept - (rework_stock - rework_stock_received)),
        }
    return result


def needed_by_item(project, ids):
    return {
        row['item_id']: row['total']
        for row in BOMLine.objects.filter(project=project, item_id__in=list(ids))
        .values('item_id')
        .annotate(total=Sum('quantity'))
    }


def obsolete(project, item_ids=None):
    """{旧物料: 旧版待处理明细}，按本项目每个换下来的旧物料最近一次换版汇总。"""
    changes = RevisionChange.objects.filter(project=project).select_related('old_item', 'new_item', 'new_line__item')
    if item_ids is not None:
        changes = changes.filter(old_item_id__in=list(item_ids))
    latest, history_ids = {}, {}
    for change in changes.order_by('pk'):
        latest[change.old_item_id] = change
        history_ids.setdefault(change.old_item_id, []).append(change.pk)
    if not latest:
        return {}
    ids = list(latest)
    needed = needed_by_item(project, ids)
    numbers = leftovers(project, {pk: needed.get(pk) or ZERO for pk in ids})
    on_hand = {
        row['item_id']: row['total']
        for row in Stock.objects.filter(item_id__in=ids).values('item_id').annotate(total=Sum('quantity'))
    }
    result = {}
    for item_id, change in latest.items():
        row = numbers[item_id]
        target = live_target(change)
        new_item = target.item if target else change.new_item
        result[item_id] = {
            'change': change.pk,
            'changes': history_ids[item_id],
            'old_item': item_id,
            'old_item_code': change.old_item.code,
            'old_item_name': change.old_item.name,
            'old_revision': change.old_item.drawing_revision,
            'unit': change.old_item.unit,
            'new_item': new_item.pk,
            'new_item_code': new_item.code,
            'new_item_name': new_item.name,
            'new_revision': new_item.drawing_revision,
            'new_line': target.pk if target else None,
            'assembly_unit': change.assembly_unit,
            'reason': change.reason,
            'created_at': change.created_at,
            'on_hand': on_hand.get(item_id) or ZERO,
            **{key: row[key] for key in row if key not in {'need', 'issued_total', 'received_unissued'}},
        }
    return result


def in_transit(line):
    """原 BOM 行关联的未到货采购（不加锁）：换版时会按新图转为新版的部分。"""
    from .purchase_changes import pending_requests

    lines = [
        row
        for row in PurchaseLine.objects.select_related('purchase')
        .filter(bom_line=line, purchase__is_deleted=False)
        .exclude(purchase__status__in=['cancelled', 'received'])
        .order_by('purchase_id', 'pk')
        if unreceived(row) > ZERO
    ]
    waiting = pending_requests([row.purchase for row in lines])
    return [
        {
            'purchase': row.purchase_id,
            'code': row.purchase.code,
            'status': row.purchase.status,
            'status_label': row.purchase.get_status_display(),
            'quantity': quantity(unreceived(row)),
            'pending': row.purchase.status not in {'draft', 'submitted'},
            'blocked': row.purchase_id in waiting,
        }
        for row in lines
    ]


def impact_rows(project, removed):
    """换版前的影响预估。removed 为 {旧物料: 换版后旧物料在本项目剩余的需求合计}。"""
    numbers = leftovers(project, removed)
    return {
        item_id: {
            'issued': quantity(row['issued_total']),
            'received_unissued': quantity(row['received_unissued']),
            'need_after': quantity(row['need']),
            'pending_issued': quantity(row['pending_issued']),
            'pending_stock': quantity(row['pending_stock']),
        }
        for item_id, row in numbers.items()
    }


def impact(actor, line):
    """升版、替换物料前展示：旧版在途怎么转、换版后旧版待处理大约多少（按移除这一行后的需求估算）。"""
    require_project(actor, line.project, BOM_WRITERS)
    needed = needed_by_item(line.project, [line.item_id]).get(line.item_id) or ZERO
    estimate = impact_rows(line.project, {line.item_id: max(ZERO, needed - line.quantity)})[line.item_id]
    return {'line': line.pk, 'item_code': line.item.code, 'in_transit': in_transit(line), **estimate}


def quantity(value):
    return str(value.quantize(Decimal('0.001')))


def format_parts(rows_by_item):
    rows = []
    for row in rows_by_item.values():
        pending = row['pending_issued'] + row['pending_stock']
        rows.append(
            {
                **{key: quantity(value) if isinstance(value, Decimal) else value for key, value in row.items()},
                'id': row['change'],
                'open': pending > ZERO,
            }
        )
    return sorted(rows, key=lambda row: (not row['open'], -row['change']))


def parts(project):
    """项目「旧版待处理」：每个换下来的旧物料一行，仍有待处理的排前面。"""
    return format_parts(obsolete(project))


def _live_target_cached(change, next_by_old_line):
    line, seen = change.new_line, set()
    while line.is_deleted and line.pk not in seen:
        seen.add(line.pk)
        following = next_by_old_line.get((change.project_id, line.pk))
        if following is None:
            return None
        line = following.new_line
    return None if line.is_deleted else line


def open_parts(projects):
    """[(项目, 仍有旧版待处理的行)]，工作台用；批量聚合所有有换版记录的项目，避免 N+1 查询。"""
    project_list = list(projects.filter(pk__in=RevisionChange.objects.values('project_id')).order_by('pk'))
    if not project_list:
        return []
    project_ids = [project.pk for project in project_list]
    latest, history_ids, next_by_old_line = {}, {}, {}
    for change in (
        RevisionChange.objects.filter(project_id__in=project_ids)
        .select_related('old_item', 'new_item', 'new_line__item')
        .order_by('project_id', 'pk')
    ):
        key = (change.project_id, change.old_item_id)
        latest[key] = change
        history_ids.setdefault(key, []).append(change.pk)
        next_by_old_line[(change.project_id, change.old_line_id)] = change
    if not latest:
        return []
    item_ids = sorted({item_id for _, item_id in latest})
    needed = {
        (row['project_id'], row['item_id']): row['total'] or ZERO
        for row in BOMLine.objects.filter(project_id__in=project_ids, item_id__in=item_ids)
        .values('project_id', 'item_id')
        .annotate(total=Sum('quantity'))
    }
    used = {
        (row['project_id'], row['stock__item_id']): -(row['total'] or ZERO)
        for row in StockMove.objects.filter(
            project_id__in=project_ids, stock__item_id__in=item_ids, kind__in=['issue', 'return']
        )
        .exclude(task__kind='service')
        .values('project_id', 'stock__item_id')
        .annotate(total=Sum('quantity'))
    }
    arrived = {
        (row['project_id'], row['stock__item_id']): row['total'] or ZERO
        for row in StockMove.objects.filter(
            project_id__in=project_ids, stock__item_id__in=item_ids, kind__in=ARRIVAL_KINDS
        )
        .values('project_id', 'stock__item_id')
        .annotate(total=Sum('quantity'))
    }
    disposed = {
        (row['change__project_id'], row['change__old_item_id'], row['source'], row['kind']): row['total'] or ZERO
        for row in RevisionDisposition.objects.filter(
            change__project_id__in=project_ids, change__old_item_id__in=item_ids
        )
        .values('change__project_id', 'change__old_item_id', 'source', 'kind')
        .annotate(total=Sum('quantity'))
    }
    reworked = {
        (row['revision__project_id'], row['revision__old_item_id'], REWORK_ROLES[row['revision_role']]): (
            row['total'] or ZERO,
            row['received'] or ZERO,
        )
        for row in PurchaseLine.objects.filter(
            revision__project_id__in=project_ids,
            revision__old_item_id__in=item_ids,
            revision_role__in=list(REWORK_ROLES),
            purchase__is_deleted=False,
        )
        .exclude(purchase__status='cancelled')
        .values('revision__project_id', 'revision__old_item_id', 'revision_role')
        .annotate(total=Sum(F('quantity') - F('cancelled_quantity')), received=Sum('received_quantity'))
    }
    on_hand = {
        row['item_id']: row['total'] or ZERO
        for row in Stock.objects.filter(item_id__in=item_ids).values('item_id').annotate(total=Sum('quantity'))
    }
    by_project = {}
    for (project_id, item_id), change in latest.items():
        need = needed.get((project_id, item_id), ZERO)
        issued_qty = used.get((project_id, item_id), ZERO)
        received = max(ZERO, arrived.get((project_id, item_id), ZERO) - issued_qty)
        excess_issued = max(ZERO, issued_qty - need)
        excess_stock = max(ZERO, received - max(ZERO, need - issued_qty))
        rework_issued, rework_issued_received = reworked.get((project_id, item_id, 'issued'), (ZERO, ZERO))
        rework_stock, rework_stock_received = reworked.get((project_id, item_id, 'stock'), (ZERO, ZERO))
        scrapped_issued = disposed.get((project_id, item_id, 'issued', 'scrap'), ZERO)
        kept = disposed.get((project_id, item_id, 'stock', 'keep'), ZERO)
        target = _live_target_cached(change, next_by_old_line)
        new_item = target.item if target else change.new_item
        by_project.setdefault(project_id, {})[item_id] = {
            'change': change.pk,
            'changes': history_ids[(project_id, item_id)],
            'old_item': item_id,
            'old_item_code': change.old_item.code,
            'old_item_name': change.old_item.name,
            'old_revision': change.old_item.drawing_revision,
            'unit': change.old_item.unit,
            'new_item': new_item.pk,
            'new_item_code': new_item.code,
            'new_item_name': new_item.name,
            'new_revision': new_item.drawing_revision,
            'new_line': target.pk if target else None,
            'assembly_unit': change.assembly_unit,
            'reason': change.reason,
            'created_at': change.created_at,
            'on_hand': on_hand.get(item_id, ZERO),
            'issued': excess_issued,
            'stock': excess_stock,
            'scrapped_issued': scrapped_issued,
            'scrapped_stock': disposed.get((project_id, item_id, 'stock', 'scrap'), ZERO),
            'kept': kept,
            'rework_issued': rework_issued,
            'rework_issued_received': rework_issued_received,
            'rework_stock': rework_stock,
            'rework_stock_received': rework_stock_received,
            'pending_issued': max(ZERO, excess_issued - scrapped_issued - rework_issued),
            'pending_stock': max(ZERO, excess_stock - kept - (rework_stock - rework_stock_received)),
        }
    result = []
    for project in project_list:
        rows = [row for row in format_parts(by_project.get(project.pk, {})) if row['open']]
        if rows:
            result.append((project, rows))
    return result


def change_action(actor, key, operation, change_id, data, roles, execute):
    change = get_object_or_404(RevisionChange.objects, pk=identity(change_id))

    def perform(user, project):
        current = RevisionChange.objects.select_related('old_item', 'new_item', 'new_line').get(pk=change.pk)
        return execute(user, project, current)

    return project_action(actor, key, operation, change.project_id, {'change': change.pk, 'data': data}, roles, perform)


def take_stock(user, project, item, qty, *, kind, reason, remark=''):
    """按库位顺序从旧版库存出库 qty（报废或送修），流水挂在项目上并计入材料成本；库存不足时拒绝。"""
    from .inventory import take_value

    stocks = list(Stock.objects.select_for_update().filter(item=item, quantity__gt=ZERO).order_by('pk'))
    available = sum((stock.quantity for stock in stocks), ZERO)
    if available < qty:
        raise Conflict(f'旧版 {item.code} {item.name} 在库只有 {available}，不足 {qty}；请先核对库存。')
    moves, left = [], qty
    for stock in stocks:
        if left <= ZERO:
            break
        amount = min(left, stock.quantity)
        value = take_value(stock, amount)
        stock.quantity -= amount
        stock.value -= value
        save(stock, user)
        moves.append(
            save(
                StockMove(
                    stock=stock,
                    project=project,
                    kind=kind,
                    quantity=-amount,
                    value=-value,
                    reason=reason,
                    remark=remark,
                ),
                user,
            )
        )
        left -= amount
    return moves


def pending_for(row, source):
    return row['pending_stock'] if source == 'stock' else row['pending_issued']


def dispose(actor, key, change_id, data):
    """登记旧版处理：在库的报废（出库）或留作公用备件由仓管登记；已装机的报废由仓管、工程师或项目经理登记。"""

    def execute(user, project, change):
        fields(data, {'source', 'kind', 'quantity', 'reason'})
        state(project, BOM_STATES | {'warranty'})
        source, kind = data.get('source'), data.get('kind')
        if source not in SOURCE_LABELS:
            raise ValidationError({'source': '请选择在库或已领用的旧版。'})
        if kind not in KIND_LABELS or (source == 'issued' and kind != 'scrap'):
            raise ValidationError({'kind': '在库旧版可报废或留作备件；已领用（已装机）的旧版只能登记报废。'})
        if source == 'stock' and not has_role(user, WAREHOUSE):
            raise PermissionDenied('在库旧版的报废和留作备件由仓管登记。')
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        reason = text(data, 'reason')
        lock_items({change.old_item_id})
        pending = pending_for(obsolete(project, [change.old_item_id])[change.old_item_id], source)
        if qty > pending:
            raise Conflict(f'{SOURCE_LABELS[source]}旧版待处理只有 {pending}，请刷新后重试。')
        if source == 'stock' and kind == 'scrap':
            moves = take_stock(user, project, change.old_item, qty, kind='scrap', reason=f'旧版报废：{reason}')
            records = [
                save(
                    RevisionDisposition(
                        change=change, source=source, kind=kind, quantity=-move.quantity, move=move, reason=reason
                    ),
                    user,
                )
                for move in moves
            ]
        else:
            records = [
                save(RevisionDisposition(change=change, source=source, kind=kind, quantity=qty, reason=reason), user)
            ]
        audit(
            user,
            'revision.dispose',
            change,
            source=source,
            kind=kind,
            quantity=str(qty),
            reason=reason,
            item=change.old_item.code,
            dispositions=[record.pk for record in records],
        )
        return {'id': records[0].pk, 'change': change.pk}

    return change_action(actor, key, 'revision.dispose', change_id, data, DISPOSERS, execute)


def rework(actor, key, change_id, data):
    """采购为旧版开返修采购单：新版物料、挂在用的新版 BOM 行，生成草稿后走正常提交、审批和收货。

    在库旧版返修：收到改好的新版时同数量旧版出库（送修改制）。已装机旧版返修：拆下送修，收货只入新版。
    """
    from .supply import create_purchase

    def execute(user, project, change):
        fields(data, {'source', 'quantity', 'supplier', 'unit_price', 'due_date', 'note'})
        source = data.get('source')
        if source not in SOURCE_LABELS:
            raise ValidationError({'source': '请选择返修在库的旧版还是已装机的旧版。'})
        qty = number(data.get('quantity'), 'quantity', 3, positive=True)
        note = text(data, 'note', default='')
        lock_items({change.old_item_id})
        pending = pending_for(obsolete(project, [change.old_item_id])[change.old_item_id], source)
        if qty > pending:
            raise Conflict(f'{SOURCE_LABELS[source]}旧版待处理只有 {pending}，请刷新后重试。')
        target = live_target(change)
        if target is None:
            raise Conflict('新版已不在本项目 BOM 中，不能返修改制；多出的旧版请报废或留作备件。')
        need = BOMLine.objects.filter(project=project, item=target.item).aggregate(total=Sum('quantity'))['total']
        room = (need or ZERO) - issued_by_item(project, [target.item_id])[target.item_id]
        room -= incoming_by_item(project, [target.item_id])[target.item_id]
        if qty > room:
            raise Conflict(
                f'新版 {target.item.code} 的剩余需求只有 {max(ZERO, room)}（其余已由采购或领用覆盖），返修数量不能超过它；'
                '多出的旧版请报废或留作备件。'
            )
        created = create_purchase(
            user,
            nested_key(key, 'rework-purchase'),
            {
                'project': project.pk,
                'supplier': data.get('supplier'),
                'due_date': data.get('due_date'),
                'note': f'返修改制：{change.old_item.code} → {target.item.code}' + (f'；{note}' if note else ''),
                'lines': [
                    {
                        'item': target.item_id,
                        'bom_line': target.pk,
                        'quantity': str(qty),
                        'unit_price': data.get('unit_price'),
                    }
                ],
            },
        )
        line = PurchaseLine.objects.select_for_update().get(purchase_id=created['id'])
        line.revision, line.revision_role = change, f'rework_{source}'
        save(line, user)
        audit(
            user,
            'revision.rework',
            change,
            purchase=created['id'],
            source=source,
            quantity=str(qty),
            item=change.old_item.code,
            target=target.item.code,
        )
        return {'id': created['id'], 'change': change.pk}

    return change_action(actor, key, 'revision.rework', change_id, data, PURCHASERS, execute)


def rework_items(lines):
    """本次收货中在库返修明细对应的旧物料，收货前与新版物料一起按主键加锁。"""
    return {line.revision.old_item_id for line in lines if line.revision_role == 'rework_stock'}


def receive_rework(user, project, line, qty, purchase):
    """返修采购收到新版时，在库旧版返修的同数量旧版出库（送修改制），流水计入项目材料成本。"""
    if line.revision_role != 'rework_stock' or qty <= ZERO:
        return []
    old = Item.objects.get(pk=line.revision.old_item_id)
    try:
        return take_stock(
            user, project, old, qty, kind='rework', reason=f'送修改制：{purchase.code} 改制为 {line.item.code}'
        )
    except Conflict as exc:
        raise Conflict(f'返修明细收货时要同时出库同数量旧版（送修改制）：{exc.detail}') from exc


def review(actor, key, purchase_id, data):
    """采购处理换版改单：按新图确认（调高单价须采购审批权限、独立审批与预算复核）或取消余量。"""
    from . import budgets
    from .supply import cancel_lines, purchase_action, purchase_applicants

    def execute(user, purchase):
        fields(data, {'line', 'decision', 'unit_price', 'reason', 'confirm_over_budget'})
        state(purchase, {'approved', 'partial'})
        decision = data.get('decision')
        if decision not in {'confirm', 'cancel'}:
            raise ValidationError({'decision': '请选择按新图改单或取消余量。'})
        confirm_over_budget = data.get('confirm_over_budget', False)
        if not isinstance(confirm_over_budget, bool):
            raise ValidationError({'confirm_over_budget': '必须为布尔值。'})
        reason = text(data, 'reason')
        lines = list(purchase.lines.select_for_update().order_by('item_id', 'pk'))
        line_id = identity(data.get('line'), 'line')
        line = next((row for row in lines if row.pk == line_id), None)
        if line is None or not line.revision_pending:
            raise Conflict('该明细没有待确认的换版改单，请刷新后重试。')
        remaining = line.quantity - line.received_quantity - line.cancelled_quantity
        if decision == 'cancel':
            if 'unit_price' in data:
                raise ValidationError({'unit_price': '取消余量不需要单价。'})
            if 'confirm_over_budget' in data:
                raise ValidationError({'confirm_over_budget': '取消余量不需要超预算确认。'})
            line.revision_pending = False
            save(line, user)
            if remaining > ZERO:
                cancel_lines(user, purchase, lines, {line.pk: remaining}, reason)
            return audit(
                user, 'purchase.revision_cancel', purchase, line=line.pk, quantity=str(remaining), reason=reason
            )
        before = line.unit_price
        price = number(data['unit_price'], 'unit_price') if 'unit_price' in data else before
        delta = ZERO
        audit_extra = {}
        if price != before:
            number(rounded(line.quantity * price), 'line_amount')
            # 换版明细确认前不能收货；已取消的部分按原价冲减过，调价只调整未取消的部分。
            retained = line.quantity - line.cancelled_quantity
            delta = rounded(retained * price) - rounded(retained * before)
            if price > before:
                try:
                    require_role(user, PURCHASE_APPROVERS)
                    require_project(user, purchase.project, PURCHASE_APPROVERS)
                except PermissionDenied as exc:
                    raise PermissionDenied(
                        '换版改单调高单价会增加已批准应付，请由采购经理、项目经理或管理员确认。'
                    ) from exc
                self_approval = independent_approval(user, purchase_applicants(purchase), reason)
                over_budget = False
                budget_adjuster_approval = False
                report = None
                if delta > ZERO:
                    report = budgets.analysis(purchase.project, delta)
                    if report['over_budget']:
                        if not has_role(user, {'admin'}) and user.pk == purchase.project.budget_changed_by_id:
                            raise PermissionDenied(
                                '预算调整人不能确认本项目超预算调价，请由其他经理审批；管理员例外必须填写原因。'
                            )
                        if not confirm_over_budget:
                            warnings = budgets.purchase_visibility(user, report, purchase.project)['warnings']
                            raise Conflict(
                                '；'.join(warnings) + '。调高单价会超出项目预算，请勾选「确认承担超预算调价」后提交。'
                            )
                        over_budget = True
                        budget_adjuster_approval = user.pk == purchase.project.budget_changed_by_id
                audit_extra.update(
                    self_approval=self_approval,
                    over_budget=over_budget,
                    budget_adjuster_approval=budget_adjuster_approval,
                )
                if report is not None:
                    audit_extra['budget_check'] = report
            entry = Entry.objects.select_for_update().filter(purchase=purchase).first()
            if entry:
                if entry.amount + delta < entry.credit_amount:
                    raise Conflict('调价后应付金额小于已冲减金额，请先核对应付。')
                entry.amount += delta
                save(entry, user)
            line.unit_price = price
            audit_extra['delta'] = str(delta)
        line.revision_pending = False
        save(line, user)
        audit(
            user,
            'purchase.revision_confirm',
            purchase,
            line=line.pk,
            item=line.item.code,
            before_price=str(before),
            after_price=str(price),
            reason=reason,
            **audit_extra,
        )
        # 已归档过签署合同的，提示与供应商确认新图和价格后归档新版本合同。
        archived = purchase.contract_versions.order_by('-version').values_list('version', flat=True).first()
        return {'id': purchase.pk, 'contract_version': archived}

    return purchase_action(actor, key, 'purchase.revision_review', purchase_id, data, PURCHASERS, execute)


def pending_reviews(queryset=None):
    """待采购确认的换版改单明细：采购单已批准、未删除，且仍有未收余量。"""
    queryset = PurchaseLine.objects.all() if queryset is None else queryset
    return queryset.filter(
        revision_pending=True, purchase__is_deleted=False, purchase__status__in=['approved', 'partial']
    ).filter(quantity__gt=F('received_quantity') + F('cancelled_quantity'))


def scope(actor, line):
    """升版时可一并换版的其他项目：同一物料仍在 BOM 中、可维护 BOM 的项目，标明当前用户能否修改。"""
    writable = set(
        projects_for(actor, Project.objects.filter(status__in=BOM_STATES), BOM_WRITERS).values_list('pk', flat=True)
    )
    result = {}
    rows = list(
        BOMLine.objects.filter(item_id=line.item_id, project__status__in=BOM_STATES)
        .exclude(project_id=line.project_id)
        .select_related('project')
        .order_by('project_id', 'pk')
    )
    # 勾选前看到对方项目的在途和已领：一次批量查询，避免按 BOM 行重复查库。
    transit = unreceived_by_line([row.pk for row in rows])
    project_ids = sorted({row.project_id for row in rows})
    issued_totals = (
        {
            row['project_id']: -(row['total'] or ZERO)
            for row in StockMove.objects.filter(
                project_id__in=project_ids, stock__item_id=line.item_id, kind__in=['issue', 'return']
            )
            .exclude(task__kind='service')
            .values('project_id')
            .annotate(total=Sum('quantity'))
        }
        if project_ids
        else {}
    )
    for row in rows:
        entry = result.get(row.project_id)
        if entry is None:
            entry = {
                'id': row.project_id,
                'code': row.project.code,
                'name': row.project.name,
                'quantity': ZERO,
                'in_transit': ZERO,
                'issued': issued_totals.get(row.project_id, ZERO),
                'units': [],
                'writable': row.project_id in writable,
            }
            result[row.project_id] = entry
        entry['quantity'] += row.quantity
        entry['in_transit'] += max(ZERO, transit.get(row.pk, ZERO))
        entry['units'].append(row.assembly_unit or '未分单元')
    return [
        {**row, **{key: quantity(row[key]) for key in ('quantity', 'in_transit', 'issued')}} for row in result.values()
    ]


def new_revision(user, key, old, data):
    """升版的新物料：同图号、新版本号的在用物料已存在时直接复用，否则复制原物料资料新建（编码按规则自动生成）。"""
    from . import masterdata

    revision = masterdata.normalized(text(data, 'drawing_revision', maximum=30))
    if masterdata.comparison_key(revision) == masterdata.comparison_key(old.drawing_revision):
        raise ValidationError({'drawing_revision': f'新版本号不能与原版本「{old.drawing_revision or "空"}」相同。'})
    for item in Item.objects.filter(is_active=True, drawing_number__iexact=old.drawing_number).order_by('pk'):
        if masterdata.comparison_key(item.drawing_revision) == masterdata.comparison_key(revision):
            return item, False
    payload = {
        'name': text(data, 'name', default=old.name, maximum=150),
        'specification': text(data, 'specification', default=old.specification, maximum=2000),
        'drawing_number': old.drawing_number,
        'drawing_revision': revision,
        'product_category': old.product_category,
        'brand': old.brand,
        'part_type': old.part_type,
        'unit': old.unit,
        # 新版与旧版名称、型号常常相同，只差图档版本；写明来源，查重时不当成未核对的重复建料。
        'duplicate_reason': f'升版：由 {old.code}（图号 {old.drawing_number} 版本 {old.drawing_revision or "空"}）'
        f'升为版本 {revision}',
    }
    created = masterdata.masterdata(user, nested_key(key, 'item'), Item, payload)
    return Item.objects.get(pk=created['id']), True


def upgrade(actor, key, line_id, data):
    """一步升版：复制原物料资料建新版（或复用已有新版）并在本单元换版；可勾选同物料的其他项目一并换版。

    按全局锁顺序（Project 升序 → BOMLine → PurchaseOrder → PurchaseLine → Item → Entry）一次锁齐全部目标项目，
    避免跨项目双向升版或与收货并发产生死锁。
    """
    require_role(actor, BOM_WRITERS)
    source = get_object_or_404(BOMLine.all_objects.select_related('project'), pk=identity(line_id))
    require_project(actor, source.project, BOM_WRITERS)
    allowed = {
        'drawing_revision',
        'name',
        'specification',
        'quantity',
        'change_note',
        'required_date',
        'application_date',
        'applicant',
        'projects',
    }
    fields(data, allowed)
    others = data.get('projects', [])
    if not isinstance(others, list) or any(not isinstance(pk, int) or isinstance(pk, bool) for pk in others):
        raise ValidationError({'projects': '请提交项目编号列表。'})
    if len(set(others)) != len(others) or source.project_id in others:
        raise ValidationError({'projects': '项目重复或包含本项目。'})
    sorted_others = sorted(others)
    project_ids = sorted({source.project_id, *sorted_others})
    context = {}

    def authorize(current_actor):
        require_role(current_actor, BOM_WRITERS)
        locked = {
            project.pk: project
            for project in Project.objects.select_for_update().filter(pk__in=project_ids).order_by('pk')
        }
        if source.project_id not in locked:
            raise Http404
        current_actor.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        require_role(current_actor, BOM_WRITERS)
        require_project(current_actor, locked[source.project_id], BOM_WRITERS)
        for other_id in sorted_others:
            other_project = locked.get(other_id)
            if other_project is None or other_project.status not in BOM_STATES:
                raise Conflict('所选项目已不再使用原物料或不能维护 BOM，请刷新后重新选择。')
            try:
                require_project(current_actor, other_project, BOM_WRITERS)
            except PermissionDenied as exc:
                raise PermissionDenied(
                    f'你不能维护项目 {other_project.code} 的 BOM，请由该项目的工程师或项目经理换版。'
                ) from exc
        context['projects'] = locked

    def execute(user):
        locked = context['projects']
        project = locked[source.project_id]
        state(project, BOM_STATES)
        line = get_object_or_404(
            BOMLine.all_objects.select_for_update(of=('self',)).select_related('item'), pk=source.pk, project=project
        )
        if line.is_deleted:
            raise Conflict('此 BOM 行已移除。')
        if not line.item.drawing_number:
            raise ValidationError('只有带图号的物料可以升版；换成其他型号请用「替换物料」。')
        qty = number(data.get('quantity', str(line.quantity)), 'quantity', 3, positive=True)
        note = text(data, 'change_note')
        old = line.item
        other_lines = {}
        for other_id in sorted_others:
            other_project = locked[other_id]
            if other_project.status not in BOM_STATES:
                raise Conflict('所选项目已不再使用原物料或不能维护 BOM，请刷新后重新选择。')
            found = list(
                BOMLine.objects.select_for_update(of=('self',))
                .select_related('item')
                .filter(project=other_project, item=old)
                .order_by('pk')
            )
            if not found:
                raise Conflict('所选项目已不再使用原物料或不能维护 BOM，请刷新后重新选择。')
            other_lines[other_id] = found
        item, created = new_revision(user, key, old, data)
        all_target_lines = [line, *(row for rows in other_lines.values() for row in rows)]
        all_pending = lock_convertible(all_target_lines)
        pending_by_line = {}
        for purchase_line in all_pending:
            pending_by_line.setdefault(purchase_line.bom_line_id, []).append(purchase_line)
        locked_items = lock_items({old.pk, item.pk})
        item = locked_items[item.pk]
        details = {field: data[field] for field in ('required_date', 'application_date', 'applicant') if field in data}
        change, converted = change_revision(
            user,
            project,
            line,
            item,
            qty,
            note,
            details,
            operation='upgrade',
            pending_lines=pending_by_line.get(line.pk, []),
            items_locked=True,
        )
        applied = []
        for other_id in sorted_others:
            other_project = locked[other_id]
            changes = []
            for other_line in other_lines[other_id]:
                other_change, other_converted = change_revision(
                    user,
                    other_project,
                    other_line,
                    item,
                    other_line.quantity,
                    note,
                    operation='upgrade',
                    pending_lines=pending_by_line.get(other_line.pk, []),
                    items_locked=True,
                )
                changes.append(
                    {'change': other_change.pk, 'assembly_unit': other_line.assembly_unit, 'converted': other_converted}
                )
            applied.append({'project': other_project.pk, 'code': other_project.code, 'changes': changes})
        return {
            'id': change.new_line_id,
            'change': change.pk,
            'item': item.pk,
            'item_code': item.code,
            'created_item': created,
            'converted': converted,
            'projects': applied,
        }

    return perform(
        actor=actor,
        key=key,
        operation='bom.upgrade',
        payload={'project': source.project_id, 'data': {'line': source.pk, 'data': data}},
        authorize=authorize,
        execute=execute,
    )


def history(project):
    """项目换版记录，最新在前。"""
    return [
        {
            'id': change.pk,
            'old_item_code': change.old_item.code,
            'old_item_name': change.old_item.name,
            'old_revision': change.old_item.drawing_revision,
            'new_item_code': change.new_item.code,
            'new_item_name': change.new_item.name,
            'new_revision': change.new_item.drawing_revision,
            'assembly_unit': change.assembly_unit,
            'old_quantity': str(change.old_quantity),
            'new_quantity': str(change.new_quantity),
            'converted_quantity': str(change.converted_quantity),
            'reason': change.reason,
            'created_at': change.created_at,
            'created_by': (change.created_by.display_name or change.created_by.username) if change.created_by else '',
        }
        for change in RevisionChange.objects.filter(project=project)
        .select_related('old_item', 'new_item', 'created_by')
        .order_by('-pk')
    ]
