"""物料跟踪：跨项目按「项目×物料」一行列出需求、采购、到货、领料和缺料，口径与项目 BOM 页一致。

- 一行合并同一项目同一物料的全部 BOM 行（各单元合计），单元、申请人、变更说明并列；项目后来另外采购或领用、
  不在当前 BOM 里的物料（零星采购、改版移除）也各占一行，标「不在 BOM」，没有需求和缺料；
- 缺料与 BOM 页、工作台「缺料待采购项目」同一分摊口径（bom.allocations，共享库存不预留）；
- 已下单、待批采购、在途、已收取本项目未作废采购（已收扣除采购退货）；已领为项目领料减退料（售后任务领料不计，
  与 BOM 已领一致）；最近入库只算未被反审冲回的收货；
- 采购单号、供应商、采购员和送货单号只给能看采购单的岗位，单价、金额只给能看采购价的岗位（与采购明细相同）；
  需求、数量、交期、领料人等所有能看 BOM 的人都能看。
"""

from decimal import Decimal

from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.permissions import MONEY_READERS, PURCHASE_READERS, PURCHASERS, has_role, projects_for

from ..models import BOMLine, Item, Project, PurchaseLine, PurchaseOrder, StockMove
from . import tabular
from .bom import UNAPPROVED, allocations, shortage
from .common import ZERO, identity, live_receipts

OPEN_PROJECTS = ('draft', 'quoted', 'active', 'delivering')
STATUSES = {
    'shortage': '缺料',
    'incoming': '在途',
    'unapproved': '待批采购',
    'ready': '待领料',
    'issued': '已领完',
}
PURCHASE_STATUS = dict(PurchaseOrder.Status.choices)
# 收货、领料不填说明时系统按动作名记录，这些不是送货单号或领料说明，不列出。
DEFAULT_RECEIPT_REASONS = {'采购收货', '隔离品合格入库'}
DEFAULT_ISSUE_REASONS = {'项目领料', '售后领料'}
QUANTUM = Decimal('0.001')


def visibility(user):
    """(能看采购单号和供应商, 能看单价金额)。"""
    return has_role(user, PURCHASE_READERS), has_role(user, MONEY_READERS | PURCHASERS)


def quantity_text(value):
    return str(Decimal(value).quantize(QUANTUM))


def joined(values, sep='、'):
    return sep.join(dict.fromkeys(value for value in values if value))


def scoped_projects(user, params):
    """可见项目范围：指定项目时只看该项目，否则默认只看在推进的项目（需求中到交付中），可选包括已验收、已结项。"""
    projects = projects_for(user, Project.objects.all())
    project = params.get('project')
    if project not in (None, '', 'all'):
        return projects.filter(pk=identity(project, 'project'))
    if params.get('all_projects') != 'true':
        return projects.filter(status__in=OPEN_PROJECTS)
    return projects


def matching(params, item, project):
    """物料类别与搜索词（物料编码、名称、型号、图号、品牌、项目编号与名称）；BOM 行、采购明细、领料流水各传自己的关联路径。"""
    condition = Q()
    part_type = params.get('part_type') or ''
    if part_type:
        if part_type not in dict(Item.PartType.choices):
            raise ValidationError({'part_type': '请选择标准件或非标件。'})
        condition &= Q(**{f'{item}__part_type': part_type})
    for word in str(params.get('search') or '').split()[:5]:
        words = Q()
        for field in ('code', 'name', 'specification', 'drawing_number', 'brand'):
            words |= Q(**{f'{item}__{field}__icontains': word})
        for field in ('code', 'name'):
            words |= Q(**{f'{project}__{field}__icontains': word})
        condition &= words
    return condition


def candidate_keys(projects, params):
    """跟踪行的「项目×物料」：项目 BOM 里的物料，加上项目后来另外采购（未作废）或领用过的物料——
    零星采购、BOM 改版移除但已买或已领的物料都列出，标为「不在 BOM」。"""
    lines = list(
        BOMLine.objects.filter(project__in=projects).filter(matching(params, 'item', 'project')).order_by('pk')
    )
    keys = {(line.project_id, line.item_id) for line in lines}
    keys.update(
        PurchaseLine.objects.filter(
            purchase__project__in=projects, purchase__is_deleted=False, quantity__gt=F('cancelled_quantity')
        )
        .exclude(purchase__status='cancelled')
        .filter(matching(params, 'item', 'purchase__project'))
        .values_list('purchase__project_id', 'item_id')
        .distinct()
    )
    keys.update(
        StockMove.objects.filter(project__in=projects, kind='issue')
        .exclude(task__kind='service')
        .filter(matching(params, 'stock__item', 'project'))
        .values_list('project_id', 'stock__item_id')
        .distinct()
    )
    return keys, lines


def status_of(row):
    if not row['lines']:
        # 不在 BOM：没有需求数量，按采购与领料进度给状态。
        if row['incoming_value'] > ZERO:
            return 'incoming'
        if row['unapproved_value'] > ZERO:
            return 'unapproved'
        return 'ready' if row['received_value'] > row['issued_value'] else 'issued'
    if row['issued_value'] >= row['need']:
        return 'issued'
    if row['shortage_value'] > ZERO:
        return 'shortage'
    if row['incoming_value'] > ZERO:
        return 'incoming'
    if row['unapproved_value'] > ZERO:
        return 'unapproved'
    return 'ready'


def tracked(user, params):
    """筛选后的全部跟踪行（项目编号倒序、物料编码顺序）；数量合计按分组一次读取，查询数与行数无关。"""
    from ..serializers import ambiguous_people, person_name

    status = params.get('status') or ''
    if status and status not in STATUSES:
        raise ValidationError({'status': '请选择缺料、在途、待批采购、待领料或已领完。'})
    supplier = params.get('supplier')
    supplier = identity(supplier, 'supplier') if supplier not in (None, '') else None
    keys, lines = candidate_keys(scoped_projects(user, params), params)
    if not keys:
        return []
    project_ids = {project_id for project_id, _ in keys}
    item_ids = {item_id for _, item_id in keys}
    projects = Project.objects.in_bulk(project_ids)
    items = Item.objects.in_bulk(item_ids)
    rows = {
        key: {
            'project': projects[key[0]],
            'item': items[key[1]],
            'lines': [],
            'need': ZERO,
            'shortage_value': ZERO,
            'ordered_value': ZERO,
            'unapproved_value': ZERO,
            'incoming_value': ZERO,
            'received_value': ZERO,
            'issued_value': ZERO,
            'amount_value': ZERO,
            'purchases': {},
            'supplier_ids': set(),
            'suppliers': [],
            'buyers': [],
            'prices': [],
            'due_dates': [],
            'receipt_dates': [],
            'delivery_notes': [],
            'issue_dates': [],
            'slips': [],
            'recipients': [],
            'issue_notes': [],
        }
        for key in keys
    }
    for line in lines:
        row = rows[(line.project_id, line.item_id)]
        row['lines'].append(line)
        row['need'] += line.quantity
    # 缺料：与 BOM 页同一分摊口径，逐行算后按物料合计。
    for bom_lines, plan in allocations(project_ids).values():
        for line in bom_lines:
            row = rows.get((line.project_id, line.item_id))
            if row is not None and row['lines']:
                row['shortage_value'] += shortage(line, plan[line.pk])
    ambiguous = ambiguous_people()
    for purchase_line in (
        PurchaseLine.objects.filter(
            purchase__project_id__in=project_ids, item_id__in=item_ids, purchase__is_deleted=False
        )
        .exclude(purchase__status='cancelled')
        .select_related('purchase__supplier', 'purchase__created_by')
        .order_by('purchase__code', 'pk')
    ):
        purchase = purchase_line.purchase
        row = rows.get((purchase.project_id, purchase_line.item_id))
        if row is None:
            continue
        net = purchase_line.quantity - purchase_line.cancelled_quantity
        if net <= ZERO:
            continue
        if purchase.status in UNAPPROVED:
            row['unapproved_value'] += net
        else:
            row['ordered_value'] += net
            row['incoming_value'] += max(
                ZERO, purchase_line.quantity - purchase_line.received_quantity - purchase_line.cancelled_quantity
            )
        row['received_value'] += purchase_line.received_quantity - purchase_line.returned_quantity
        row['amount_value'] += net * purchase_line.unit_price
        row['purchases'][purchase.code] = (purchase.pk, PURCHASE_STATUS.get(purchase.status, purchase.status))
        row['supplier_ids'].add(purchase.supplier_id)
        row['suppliers'].append(purchase.supplier.name)
        row['buyers'].append(person_name(purchase.created_by, ambiguous) if purchase.created_by_id else '')
        row['prices'].append(f'{purchase_line.unit_price:.2f}')
        row['due_dates'].append((purchase_line.due_date or purchase.due_date).isoformat())
    for project_id, item_id, received_date, created_at, reason in live_receipts(
        StockMove.objects.filter(project_id__in=project_ids, stock__item_id__in=item_ids)
    ).values_list('project_id', 'stock__item_id', 'received_date', 'created_at', 'reason'):
        row = rows.get((project_id, item_id))
        if row is None:
            continue
        row['receipt_dates'].append(received_date or timezone.localdate(created_at))
        if reason not in DEFAULT_RECEIPT_REASONS:
            row['delivery_notes'].append(reason)
    for project_id, item_id, kind, quantity, created_at, slip_id, slip_code, recipient, slip_reason in (
        StockMove.objects.filter(project_id__in=project_ids, stock__item_id__in=item_ids, kind__in=['issue', 'return'])
        .exclude(task__kind='service')
        .order_by('pk')
        .values_list(
            'project_id',
            'stock__item_id',
            'kind',
            'quantity',
            'created_at',
            'slip_id',
            'slip__code',
            'slip__recipient',
            'slip__reason',
        )
    ):
        row = rows.get((project_id, item_id))
        if row is None:
            continue
        row['issued_value'] -= quantity
        if kind != 'issue':
            continue
        row['issue_dates'].append(timezone.localdate(created_at))
        if slip_id:
            row['slips'].append((slip_id, slip_code))
        row['recipients'].append(recipient or '')
        if slip_reason and slip_reason not in DEFAULT_ISSUE_REASONS:
            row['issue_notes'].append(slip_reason)
    result = []
    outside = params.get('outside_bom') == 'true'
    for row in rows.values():
        state = status_of(row)
        if (status and state != status) or (outside and row['lines']):
            continue
        if supplier is not None and supplier not in row['supplier_ids']:
            continue
        result.append(output(row, state))
    result.sort(key=lambda row: (row['item_code'], row['item']))
    result.sort(key=lambda row: (row['project_code'], row['project']), reverse=True)
    return result


def output(row, state):
    lines, project, item = row['lines'], row['project'], row['item']
    required = [line.required_date for line in lines if line.required_date]
    applied = [line.application_date for line in lines if line.application_date]
    return {
        'id': f'{project.pk}-{item.pk}',
        'project': project.pk,
        'project_code': project.code,
        'project_name': project.name,
        'project_status': project.status,
        'item': item.pk,
        'item_code': item.code,
        'item_name': item.name,
        'specification': item.specification,
        'drawing_number': item.drawing_number,
        'drawing_revision': item.drawing_revision,
        'brand': item.brand,
        'unit': item.unit,
        'product_category': item.product_category,
        'part_type': item.part_type,
        'purchase_url': item.purchase_url,
        'in_bom': bool(lines),
        'assembly_units': joined(line.assembly_unit for line in lines),
        'quantity': quantity_text(row['need']) if lines else None,
        'required_date': min(required).isoformat() if required else None,
        'application_date': min(applied).isoformat() if applied else None,
        'applicants': joined(line.applicant for line in lines),
        'notes': joined((line.change_note for line in lines), '；'),
        'status': state,
        'status_label': STATUSES[state],
        'shortage': quantity_text(row['shortage_value']),
        'ordered': quantity_text(row['ordered_value']),
        'unapproved': quantity_text(row['unapproved_value']),
        'incoming': quantity_text(row['incoming_value']),
        'received': quantity_text(row['received_value']),
        'last_received_date': max(row['receipt_dates']).isoformat() if row['receipt_dates'] else None,
        'issued': quantity_text(row['issued_value']),
        'last_issued_date': max(row['issue_dates']).isoformat() if row['issue_dates'] else None,
        'issue_slips': joined(code for _, code in row['slips']),
        'slip_refs': [{'id': pk, 'code': code} for pk, code in dict(row['slips']).items()],
        'recipients': joined(row['recipients']),
        'issue_notes': joined(row['issue_notes'], '；'),
        'due_dates': joined(sorted(set(row['due_dates']))),
        'purchase_codes': joined(f'{code} {label}' for code, (_, label) in row['purchases'].items()),
        'purchase_refs': [
            {'id': pk, 'code': code, 'status_label': label} for code, (pk, label) in row['purchases'].items()
        ],
        'suppliers': joined(row['suppliers']),
        'buyers': joined(row['buyers']),
        'delivery_notes': joined(row['delivery_notes'], '；'),
        'unit_prices': joined(row['prices']),
        'amount': f'{row["amount_value"].quantize(Decimal("0.01"))}' if row['purchases'] else '',
    }


PURCHASE_FIELDS = ('purchase_codes', 'purchase_refs', 'suppliers', 'buyers', 'delivery_notes')
PRICE_FIELDS = ('unit_prices', 'amount')


def visible(user, rows):
    """按岗位去掉看不到的字段：采购单号与供应商等只给采购相关岗位，单价金额只给能看采购价的岗位。"""
    purchases, prices = visibility(user)
    hidden = (() if purchases else PURCHASE_FIELDS) + (() if prices else PRICE_FIELDS)
    if not hidden:
        return rows
    return [{key: value for key, value in row.items() if key not in hidden} for row in rows]


# 导出列：与跟踪表同序，接近现场常用的物料跟踪 Excel。
EXPORT_COLUMNS = [
    ('项目号', 'project_code', None),
    ('项目名称', 'project_name', None),
    ('物料编码', 'item_code', None),
    ('物料名称', 'item_name', None),
    ('图号', 'drawing_number', None),
    ('型号/规格', 'specification', None),
    ('版本', 'drawing_revision', None),
    ('品牌', 'brand', None),
    ('单位', 'unit', None),
    ('物料类别', 'part_type', None),
    ('单元', 'assembly_units', None),
    ('需求数量', 'quantity', 'number'),
    ('备注', 'notes', None),
    ('需求日期', 'required_date', None),
    ('申请日期', 'application_date', None),
    ('申请人', 'applicants', None),
    ('状态', 'status_label', None),
    ('是否在 BOM', 'in_bom', None),
    ('缺料', 'shortage', 'number'),
    ('已下单', 'ordered', 'number'),
    ('待批采购', 'unapproved', 'number'),
    ('在途', 'incoming', 'number'),
    ('采购单号', 'purchase_codes', 'purchase'),
    ('供应商', 'suppliers', 'purchase'),
    ('采购员', 'buyers', 'purchase'),
    ('单价', 'unit_prices', 'price'),
    ('金额', 'amount', 'price'),
    ('采购交期', 'due_dates', None),
    ('已收货', 'received', 'number'),
    ('最近入库日期', 'last_received_date', None),
    ('送货单号 / 收货说明', 'delivery_notes', 'purchase'),
    ('已领料', 'issued', 'number'),
    ('最近领料日期', 'last_issued_date', None),
    ('领料人', 'recipients', None),
    ('领料单号', 'issue_slips', None),
    ('领料说明', 'issue_notes', None),
]


def export(user, params, file_format):
    rows = tracked(user, params)
    tabular.check_export_size(len(rows))
    purchases, prices = visibility(user)
    columns = [
        column
        for column in EXPORT_COLUMNS
        if (column[2] != 'purchase' or purchases) and (column[2] != 'price' or prices)
    ]
    part_types = dict(Item.PartType.choices)
    shown = {
        'part_type': lambda value: part_types.get(value, ''),
        'in_bom': lambda value: '是' if value else '不在 BOM',
    }
    body = [[shown[key](row[key]) if key in shown else row[key] for _, key, _ in columns] for row in rows]
    numeric = {index for index, column in enumerate(columns) if column[2] == 'number' or column[1] == 'amount'}
    return tabular.document('material-tracking', [label for label, _, _ in columns], body, file_format, numeric=numeric)
