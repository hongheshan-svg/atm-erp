import hashlib
import re
import unicodedata
from decimal import Decimal

from django.db.models import F, Q, Sum
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.permissions import BOM_WRITERS, require_project

from ..models import BOMLine, Item, PurchaseLine, Stock, StockMove
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

UNAPPROVED = ('draft', 'submitted')
PURCHASE_STATUS = {'draft': '草稿', 'submitted': '待批准', 'approved': '待收货', 'partial': '部分收货'}


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


def open_purchases(queryset):
    """未收完的采购单号和状态，拼进拦截提示：工程师要知道是哪张单、该找采购处理什么。"""
    found = (
        queryset.filter(purchase__is_deleted=False, quantity__gt=F('received_quantity') + F('cancelled_quantity'))
        .exclude(purchase__status='cancelled')
        .values_list('purchase__code', 'purchase__status')
        .distinct()
        .order_by('purchase__code')
    )
    return '、'.join(f'{code} {PURCHASE_STATUS.get(status, status)}' for code, status in found)


def unit_key(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value or '')).casefold()


def unit_conflict(unit, known):
    """单元名只差空格、全半角或大小写时是同一单元的两种写法；按新单元静默新增一行会让需求虚增。"""
    if not unit or unit in known:
        return None
    match = next((value for value in sorted(known) if value and unit_key(value) == unit_key(unit)), None)
    if match is None:
        return None
    return (
        f'单元「{unit}」与现有单元「{match}」只差空格、全半角或大小写，请统一使用现有写法；'
        '确需新单元请换一个能区分的名称。'
    )


def blank_unit_message(matching):
    units = sorted({line.assembly_unit or '未分单元' for line in matching})
    names = '、'.join(units[:5]) + (' 等' if len(units) > 5 else '')
    item = matching[0].item
    return (
        f'物料 {item.code} {item.name} 已在 {len(units)} 个单元有用料（{names}），单元不能留空：'
        '填写现有单元名即修改该行，填写新单元名才会新增一行。'
    )


def target_unit(row, matching):
    """修订行的目标单元：写明的按原文；按行号修改的沿用该行；物料只有一行时沿用；多单元物料必须写明。

    以前多单元物料留空单元会按「未分单元」静默新增一行，总需求虚增后采购会多买。预览和保存共用这条规则。
    """
    if 'assembly_unit' in row:
        return text(row, 'assembly_unit', default='', maximum=100)
    if row.get('id') is not None:
        row_id = identity(row['id'], 'id')
        by_id = next((line for line in matching if line.pk == row_id), None)
        if by_id is not None:
            return by_id.assembly_unit
    if len(matching) == 1:
        return matching[0].assembly_unit
    if matching and all(line.assembly_unit for line in matching):
        raise ValidationError({'assembly_unit': blank_unit_message(matching)})
    return ''


def check_line_limit(bom_line, quantity, *, exclude_line=None):
    """多单元同物料时，采购必须落到实际需要它的那一行，不能借用其他单元的用量。

    该行已占用 = 关联未收在途 + 关联已收（扣除已退货、仍计入本项目已领或库存的部分），与缺料表同一口径。
    """
    _, plan = allocation(bom_line.project_id, item_id=bom_line.item_id, exclude_line=exclude_line)
    entry = plan.get(bom_line.pk, {'linked': ZERO, 'received': ZERO})
    pending, received = entry['linked'], entry['received']
    remaining = bom_line.quantity - pending - received
    if quantity > remaining:
        raise Conflict(
            f'采购数量超过该 BOM 行（{bom_line.assembly_unit or "未分单元"}）的剩余需求：用量 {bom_line.quantity}，'
            f'已收 {received}、在途 {pending}，最多还可采购 {max(ZERO, remaining)}；'
            '其他单元的用量请分别挂到对应 BOM 行。'
        )


def issued(project, item_id):
    return -(
        StockMove.objects.filter(project=project, stock__item_id=item_id, kind__in=['issue', 'return'])
        .exclude(task__kind='service')
        .aggregate(total=Sum('quantity'))['total']
        or ZERO
    )


def total_shortfalls(project, existing, updates):
    """本次实际改动数量的物料，各单元合计不得低于已领用与在途；BOM 修订、修订预览和导入预览共用。

    existing 为当前 BOM 行，updates 为 [(原 BOM 行或 None, 物料, 新数量)]。只核对数量有变化或新增的物料，
    其他物料即使历史上已超量也不连带拒绝；返回 [{'item', 'message'}]。
    """
    totals = {}
    for line in existing:
        totals[line.item_id] = totals.get(line.item_id, ZERO) + line.quantity
    changed = set()
    for current, item_id, qty in updates:
        totals[item_id] = totals.get(item_id, ZERO) + qty - (current.quantity if current else ZERO)
        if current is None or qty != current.quantity:
            changed.add(item_id)
    shortfalls = []
    for item_id in sorted(changed):
        used, pending = issued(project, item_id) + ZERO, incoming(project, item_id) + ZERO
        if totals[item_id] < used + pending:
            shortfalls.append((item_id, used, pending))
    names = Item.objects.in_bulk([item_id for item_id, _, _ in shortfalls]) if shortfalls else {}
    result = []
    for item_id, used, pending in shortfalls:
        orders = open_purchases(PurchaseLine.objects.filter(purchase__project=project, item_id=item_id))
        result.append(
            {
                'item': item_id,
                'minimum': used + pending,
                'message': f'物料 {names[item_id].code} {names[item_id].name} 的各单元需求数量合计 {totals[item_id]} '
                f'小于已领用 {used} 与在途采购 {pending}{f"（{orders}）" if orders else ""} 之和，'
                f'最低可改为 {used + pending}；请联系采购员取消未收余量、联系仓管退回未用材料后再减少。',
            }
        )
    return result


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


def allocation(project, *, item_id=None, exclude_line=None):
    """把本项目已领、在途和共享库存分摊到 BOM 行，只用于展示缺口和单行采购上限，不是第二本账。

    每种物料先按原规则算出已领、共享在途和库存可计入的总量，再分到各行：关联本行的未收采购计入本行在途
    （超出行用量的转为共享），关联本行的已收采购（扣除已退货）先归属本行，其余按行顺序分摊。
    """
    lines = BOMLine.objects.filter(project=project).select_related('item').order_by('item_id', 'pk')
    if item_id is not None:
        lines = lines.filter(item_id=item_id)
    lines = list(lines)
    item_ids = {line.item_id for line in lines}
    line_ids = {line.pk for line in lines}
    used_pool = {pk: ZERO for pk in item_ids}
    stock_pool = {pk: ZERO for pk in item_ids}
    shared_pool = {pk: ZERO for pk in item_ids}
    line_incoming, line_received = {}, {}
    for row in (
        StockMove.objects.filter(project=project, stock__item_id__in=item_ids, kind__in=['issue', 'return'])
        .exclude(task__kind='service')
        .values('stock__item_id')
        .annotate(total=Sum('quantity'))
    ):
        used_pool[row['stock__item_id']] = -row['total']
    for row in Stock.objects.filter(item_id__in=item_ids).values('item_id').annotate(total=Sum('quantity')):
        stock_pool[row['item_id']] = row['total']
    shared_unapproved = {pk: ZERO for pk in item_ids}
    line_unapproved = {}
    purchases = PurchaseLine.objects.filter(purchase__project=project, purchase__is_deleted=False, item_id__in=item_ids)
    if exclude_line is not None:
        purchases = purchases.exclude(pk=exclude_line)
    remaining = F('quantity') - F('received_quantity') - F('cancelled_quantity')
    for row in purchases.values('item_id', 'bom_line_id').annotate(
        pending=Sum(remaining, filter=~Q(purchase__status='cancelled')),
        unapproved=Sum(remaining, filter=Q(purchase__status__in=UNAPPROVED)),
        received=Sum(F('received_quantity') - F('returned_quantity')),
    ):
        pending, unapproved = row['pending'] or ZERO, row['unapproved'] or ZERO
        if row['bom_line_id'] in line_ids:
            line_incoming[row['bom_line_id']] = pending
            line_unapproved[row['bom_line_id']] = unapproved
            line_received[row['bom_line_id']] = row['received'] or ZERO
        else:
            shared_pool[row['item_id']] += pending
            shared_unapproved[row['item_id']] += unapproved
    plan, rooms = {}, {pk: ZERO for pk in item_ids}
    for line in lines:
        # 按行校验之前的历史采购可能在某一行上挂超；多出的在途仍是同一物料，交给其他单元共享。
        linked = line_incoming.get(line.pk, ZERO)
        assigned = min(line.quantity, linked)
        # 草稿和待批采购同样占用缺口（防止重复下单），只是单独拆出来给人看；已批准的先计入本行。
        linked_unapproved = line_unapproved.get(line.pk, ZERO)
        assigned_unapproved = max(ZERO, assigned - (linked - linked_unapproved))
        shared_pool[line.item_id] += max(ZERO, linked - assigned)
        shared_unapproved[line.item_id] += linked_unapproved - assigned_unapproved
        rooms[line.item_id] += line.quantity - assigned
        plan[line.pk] = {
            'linked': linked,
            'assigned': assigned,
            'assigned_unapproved': assigned_unapproved,
            'used': ZERO,
            'shared': ZERO,
            'shared_unapproved': ZERO,
            'available': ZERO,
            'received': ZERO,
        }
    budgets = {}
    for pk in item_ids:
        used = min(max(ZERO, used_pool[pk]), rooms[pk])
        shared = min(max(ZERO, shared_pool[pk]), rooms[pk] - used)
        approved = min(shared, max(ZERO, shared_pool[pk] - shared_unapproved[pk]))
        budgets[pk] = {
            'used': used,
            'shared': approved,
            'shared_unapproved': shared - approved,
            'available': min(stock_pool[pk], rooms[pk] - used - shared),
        }

    def take(line, keys, want):
        entry, budget = plan[line.pk], budgets[line.item_id]
        taken = ZERO
        for key in keys:
            amount = min(want - taken, budget[key])
            budget[key] -= amount
            entry[key] += amount
            taken += amount
        return taken

    for line in lines:
        # 关联本行的到货先归属本行：已领走的计入已领，仍在库的计入库存；到货被挪用后不再计入。
        want = min(line.quantity - plan[line.pk]['assigned'], max(ZERO, line_received.get(line.pk, ZERO)))
        plan[line.pk]['received'] = take(line, ('used', 'available'), want)
    for line in lines:
        entry = plan[line.pk]
        left = line.quantity - entry['assigned'] - entry['used'] - entry['available']
        take(line, ('used', 'shared', 'shared_unapproved', 'available'), left)
    return lines, plan


def shortage(line, entry):
    """BOM 行缺料量：用量扣除已领、在途（含草稿与待批）和可计入的共享库存，缺料表与按缺料采购同一口径。"""
    ordered = entry['assigned'] + entry['shared'] + entry['shared_unapproved']
    return max(ZERO, max(ZERO, line.quantity - entry['used']) - ordered - entry['available'])


def line_shortage(bom_line, *, exclude_line=None):
    """单个 BOM 行的当前缺料量；修改采购草稿时 exclude_line 扣除本行原数量，只核对改后的数量。"""
    _, plan = allocation(bom_line.project_id, item_id=bom_line.item_id, exclude_line=exclude_line)
    return shortage(bom_line, plan[bom_line.pk])


def demand(project):
    result = []
    lines, plan = allocation(project)
    competing = competing_demand(project, {line.item_id for line in lines})
    for line in lines:
        entry = plan[line.pk]
        used, available = entry['used'], entry['available']
        ordered = entry['assigned'] + entry['shared'] + entry['shared_unapproved']
        unapproved = entry['assigned_unapproved'] + entry['shared_unapproved']
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
                # 在途里仍是草稿或待批准的部分：缺料照常扣除，界面单独标出，免得草稿被遗忘后没人再提醒。
                'unapproved': str(unapproved),
                'available': str(available),
                'other_demand': str(competing.get(line.item_id, {}).get('quantity', ZERO)),
                'other_projects': competing.get(line.item_id, {}).get('projects', 0),
                'shortage': str(shortage(line, entry)),
            }
        )
    return result


def received_unissued(project, item_id):
    """本项目采购已到货（扣除退货）但还没领走的数量，即减量后可能多出来、留在共享库存的料。"""
    received = (
        StockMove.objects.filter(
            project=project, stock__item_id=item_id, kind__in=['receipt', 'purchase_return']
        ).aggregate(total=Sum('quantity'))['total']
        or ZERO
    )
    return max(ZERO, received - issued(project, item_id))


def preview_revision(actor, project, data):
    import uuid

    from django.db import transaction
    from rest_framework.exceptions import APIException

    require_project(actor, project, BOM_WRITERS)
    fields(data, {'expected_revision', 'lines'})
    before = impact(project)
    existing = list(project.bom_lines.select_related('item'))
    totals = {row['item']: Decimal(row['quantity']) for row in before['items']}
    submitted = []
    for index, row in enumerate(rows(data)):
        item = identity(row.get('item'), 'item')
        try:
            qty = number(row.get('quantity'), 'quantity', 3, positive=True)
        except ValidationError as exc:
            raise ValidationError({'lines': {index: exc.detail}}) from exc
        matching = [line for line in existing if line.item_id == item]
        try:
            unit = target_unit(row, matching)
        except ValidationError:
            continue  # 单元没写明时不臆测目标行，保存校验会在下方说明原因。
        current = None
        if row.get('id') is not None:
            current = next((line for line in matching if line.pk == identity(row['id'], 'id')), None)
        if current is None:
            current = next((line for line in matching if line.assembly_unit == unit), None)
        totals[item] = totals.get(item, ZERO) + qty - (current.quantity if current else ZERO)
        submitted.append((item, unit, qty, current, matching))
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
    items = {row['item']: row for row in before['items']}
    added = Item.objects.in_bulk([item for item in totals if item not in items])
    for item_id, item in added.items():
        used, pending = issued(project, item_id), incoming(project, item_id)
        items[item_id] = {
            'item': item_id,
            'item_code': item.code,
            'item_name': item.name,
            'quantity': str(ZERO.quantize(Decimal('0.001'))),
            'issued': str(used),
            'incoming': str(pending),
            'minimum': str(used + pending),
        }
    # 只列本次真正改动数量或仍有未处理占用的物料，改动的那一行不会被几百行「差异 0」淹没。
    shown, warnings = [], []
    for row in items.values():
        target = totals.get(row['item'], ZERO)
        difference = target - Decimal(row['quantity'])
        unresolved = max(ZERO, Decimal(row['minimum']) - target)
        if not difference and not unresolved:
            continue
        stocked = received_unissued(project, row['item'])
        used, pending = Decimal(row['issued']), Decimal(row['incoming'])
        surplus = max(ZERO, stocked + pending - max(ZERO, target - used))
        shown.append(
            {
                **row,
                'after': str(target),
                'difference': str(difference),
                'unresolved_quantity': str(unresolved),
                'received_in_stock': str(stocked),
                'surplus': str(surplus),
            }
        )
        if difference < 0 and surplus > 0 and not unresolved:
            warnings.append(
                f'{row["item_code"]} {row["item_name"]} 已到货未领 {stocked}、在途 {pending}，变更后多出 {surplus}，'
                '多出的料会留在共享库存；在途部分可联系采购取消余量。'
            )
    shown.sort(key=lambda row: -abs(Decimal(row['difference'])))
    changes = []
    for item_id, unit, qty, current, matching in submitted:
        if item_id not in items:
            continue  # 物料不存在：保存校验已给出原因。
        code, name = items[item_id]['item_code'], items[item_id]['item_name']
        changes.append(
            {
                'item': item_id,
                'item_code': code,
                'item_name': name,
                'assembly_unit': unit,
                'action': 'update' if current else 'create',
                'line': current.pk if current else None,
                'before_unit': current.assembly_unit if current else None,
                'before': str(current.quantity) if current else None,
                'after': str(qty),
            }
        )
        if current is None and matching:
            warnings.insert(
                0,
                f'{code} {name} 已在 {len(matching)} 个单元有用料，本行将新增到「{unit or "未分单元"}」，'
                f'总需求 {sum((line.quantity for line in matching), ZERO)} → {totals[item_id]}。'
                '要修改现有行请在列表行尾用「修改此行」，或在单元里填写现有单元名。',
            )
    involved = [row['item'] for row in shown] or [change['item'] for change in changes]
    purchases = list(
        project.purchases.exclude(status__in=['received', 'cancelled'])
        .filter(lines__item_id__in=involved)
        .values('id', 'code', 'status')
        .distinct()
        .order_by('code')
    )
    return {
        **before,
        'items': shown,
        'unchanged_items': len({row['item'] for row in before['items']} - {row['item'] for row in shown}),
        'changes': changes,
        'warnings': warnings,
        'purchases': purchases,
        'project': project.pk,
        'can_apply': not blockers,
        'blockers': blockers,
    }


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
                'unapproved': ZERO,
            },
        )
        item['quantity'] += number(line['quantity'], 'quantity', 3)
        item['issued'] += number(line['issued'], 'issued', 3)
        item['incoming'] += number(line['incoming'], 'incoming', 3)
        item['unapproved'] += number(line['unapproved'], 'unapproved', 3)
    return {
        'revision': revision(project),
        'items': [
            {
                **row,
                'quantity': str(row['quantity']),
                'issued': str(row['issued']),
                'incoming': str(row['incoming']),
                'unapproved': str(row['unapproved']),
                'minimum': str(row['issued'] + row['incoming']),
            }
            for row in items.values()
        ],
        'purchases': list(
            project.purchases.exclude(status__in=['received', 'cancelled']).values('id', 'code', 'status')
        ),
        'note': '减少总量前先取消采购余量、处理隔离到货和退回未用材料；替换型号请新增物料行。已交付所需材料不能退回。单元的已领、在途和库存优先计入关联该行的采购（已收扣除退货），其余按行顺序分摊显示，不代表单元专属库存。',
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
        existing = list(BOMLine.objects.filter(project=project).select_related('item'))
        known = {line.assembly_unit for line in existing}
        for index, row in enumerate(rows(data)):
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
            try:
                unit = target_unit(row, matching)
                problem = unit_conflict(unit, known)
                if problem:
                    raise ValidationError({'assembly_unit': problem})
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
            known.add(unit)
            line_key = (item_id, unit)
            if line_key in planned:
                raise ValidationError('同一物料在同一单元只能出现一次。')
            planned[line_key] = row
        items = lock_items({item_id for item_id, unit in planned})
        prepared = []
        seen_ids = set()
        for index, ((item_id, unit), row) in enumerate(planned.items()):
            if not items[item_id].is_active:
                stopped = items[item_id]
                raise ValidationError(
                    f'物料 {stopped.code} {stopped.name} 已停用，BOM 不能新增或修改该物料；'
                    '请在行尾「操作」用「替换物料」换成在用物料，或移除该行。'
                )
            try:
                qty = number(row.get('quantity'), 'quantity', 3, positive=True)
            except ValidationError as exc:
                raise ValidationError({'lines': {index: exc.detail}}) from exc
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
                pending = linked_incoming(current)
                if qty < pending:
                    orders = open_purchases(PurchaseLine.objects.filter(bom_line=current))
                    raise Conflict(
                        f'{items[item_id].code} {items[item_id].name}（{unit or "未分单元"}）关联在途采购 {pending}'
                        f'{f"（{orders}）" if orders else ""}，最低可改为 {pending}；'
                        '请联系采购员取消未收余量后再减少。'
                    )
            prepared.append((item_id, unit, qty, note, current))
        problems = total_shortfalls(
            project, existing, [(current, item_id, qty) for item_id, _, qty, _, current in prepared]
        )
        if problems:
            raise Conflict('；'.join(problem['message'] for problem in problems))
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


CHANGE_OPERATIONS = ('bom.revise', 'bom.remove')
REQUEST_LABELS = {'required_date': '需求日期', 'application_date': '申请日期', 'applicant': '申请人'}


def change_log(project, params):
    """本项目 BOM 的新增、修改、替换与移除记录（含已移除行），取自修订时写下的审计，只读、不另记一本账。"""
    from apps.core.models import AuditLog

    lines = BOMLine.all_objects.filter(project=project).select_related('item')
    search = str(params.get('search') or '').strip()[:100]
    if search:
        lines = lines.filter(
            Q(item__code__icontains=search) | Q(item__name__icontains=search) | Q(assembly_unit__icontains=search)
        )
    found = {f'bomline:{line.pk}': line for line in lines}
    logs = (
        AuditLog.objects.filter(resource__in=list(found), operation__in=CHANGE_OPERATIONS)
        .select_related('actor')
        .order_by('-id')
    )
    for key, lookup in (('start', 'created_at__date__gte'), ('end', 'created_at__date__lte')):
        if params.get(key):
            logs = logs.filter(**{lookup: day(params, key)})
    return logs, found


def change_row(log, line):
    detail = log.detail if isinstance(log.detail, dict) else {}
    removed = log.operation == 'bom.remove'
    before = detail.get('quantity', str(line.quantity)) if removed else detail.get('before')
    notes = [
        f'{label} {detail["before_request"].get(field) or "空"} → {detail["after_request"].get(field) or "空"}'
        for field, label in REQUEST_LABELS.items()
        if isinstance(detail.get('before_request'), dict)
        and isinstance(detail.get('after_request'), dict)
        and detail['before_request'].get(field) != detail['after_request'].get(field)
    ]
    if not removed and before is not None and detail.get('before_unit') != detail.get('after_unit'):
        notes.insert(0, f'单元 {detail.get("before_unit") or "未分单元"} → {detail.get("after_unit") or "未分单元"}')
    if detail.get('replaced_item'):
        notes.insert(0, f'替换物料 {detail["replaced_item"]} → {detail.get("replacement_item", "")}')
    return {
        'id': log.pk,
        'created_at': log.created_at,
        'actor': log.actor.display_name or log.actor.username,
        'action': 'remove' if removed else 'create' if before is None else 'update',
        'item_code': line.item.code,
        'item_name': line.item.name,
        'assembly_unit': detail.get('assembly_unit', line.assembly_unit) if removed else detail.get('after_unit', ''),
        'before': before,
        'after': None if removed else detail.get('after'),
        'reason': detail.get('reason') or '',
        'details': notes,
    }
