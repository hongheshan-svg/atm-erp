"""Batch creation through existing services, with rollback-only preview and signed confirmation."""

from datetime import date, datetime
from uuid import uuid4

from django.core import signing
from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import APIException, ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.permissions import ADMIN, ALL_ROLES, FINANCE, MANAGERS, PURCHASERS, SALES, WAREHOUSE, require_role

from ..models import Item, Partner, Project
from . import execution, finance, inventory, masterdata, projects, sales, supply
from .bom_import import message, read_file
from .tabular import document

# Label -> service field. Human-readable codes/usernames resolve at both preview and confirmation.
DETAIL = [
    ('名称', 'name'),
    ('客户编码', 'customer'),
    ('负责人账号', 'manager'),
    ('需求说明', 'requirements'),
    ('计划交期', 'due_date'),
    ('设备数量', 'equipment_quantity'),
    ('质保月数', 'warranty_months'),
]
LEGACY_SCHEMAS = {
    'items': (
        PURCHASERS,
        [
            ('物料编码', 'code'),
            ('名称', 'name'),
            ('规格', 'specification'),
            ('单位', 'unit'),
            ('品牌', 'brand'),
            ('物料类别', 'part_type'),
            ('独立建码原因', 'duplicate_reason'),
        ],
    ),
    'partners': (
        PURCHASERS | {'sales_manager'},
        [
            ('名称', 'name'),
            ('类型', 'kind'),
            ('联系人', 'contact'),
            ('电话', 'phone'),
            ('地址', 'address'),
            ('采购账期', 'payment_term'),
            ('自定义月结天数', 'payment_days'),
        ],
    ),
    'sales': (SALES, DETAIL),
    'projects': (MANAGERS, DETAIL + [('成员账号（分号分隔）', 'members')]),
    'purchases': (
        PURCHASERS,
        [
            ('分组号', 'group'),
            ('项目编号', 'project'),
            ('供应商编码', 'supplier'),
            ('交期', 'due_date'),
            ('说明', 'note'),
            ('物料编码', 'item'),
            ('数量', 'quantity'),
            ('含税单价', 'unit_price'),
            ('明细交期', 'line_due_date'),
            ('付款到期日', 'payment_due_date'),
            ('采购账期', 'payment_term'),
            ('自定义月结天数', 'payment_days'),
        ],
    ),
    'tasks': (
        MANAGERS,
        [
            ('项目编号', 'project'),
            ('阶段', 'kind'),
            ('任务名称', 'title'),
            ('说明', 'description'),
            ('执行人账号', 'assignee'),
            ('期限', 'due_date'),
        ],
    ),
    'stocks': (
        ADMIN,
        [
            ('物料编码', 'item'),
            ('库位', 'location'),
            ('数量', 'quantity'),
            ('单位成本', 'unit_cost'),
            ('原因', 'reason'),
        ],
    ),
    'entries': (FINANCE, [('项目编号', 'project'), ('费用名称', 'title'), ('金额', 'amount'), ('到期日', 'due_date')]),
    'payments': (
        FINANCE,
        [
            ('款项ID', 'entry'),
            ('金额', 'amount'),
            ('日期', 'date'),
            ('原因', 'reason'),
            ('结算方式（bank/cash/other）', 'method'),
            ('账户标识', 'account'),
            ('银行流水号', 'reference'),
            ('凭证ID', 'document'),
            ('对账单ID', 'reconciliation'),
        ],
    ),
    'time': (
        ALL_ROLES,
        [('任务ID', 'task'), ('人员账号', 'user'), ('日期', 'date'), ('工时', 'hours'), ('说明', 'reason')],
    ),
    'deliveries': (
        MANAGERS,
        [
            ('项目编号', 'project'),
            ('设备数量', 'quantity'),
            ('日期', 'date'),
            ('安装人账号', 'installer'),
            ('验收人账号', 'acceptor'),
            ('说明', 'note'),
        ],
    ),
    'moves': (
        WAREHOUSE,
        [('项目编号', 'project'), ('库存ID', 'stock'), ('任务ID', 'task'), ('数量', 'quantity'), ('原因', 'reason')],
    ),
}
# Keep old downloads readable by their original headers, never by the new column position.
LABEL_OVERRIDES = {
    'items': {'name': '物料名称'},
    'partners': {'name': '往来单位'},
    'sales': {'name': '销售名称'},
    'projects': {'name': '项目名称'},
    'stocks': {'quantity': '库存数量'},
    'entries': {'title': '款项', 'amount': '原金额', 'due_date': '最近待付期限'},
    'payments': {'reason': '说明', 'method': '结算方式'},
    'deliveries': {'date': '发货日'},
    'moves': {'reason': '说明'},
}
ORDERS = {
    'items': ['code', 'name', 'specification', 'brand', 'part_type', 'unit', 'duplicate_reason'],
    'partners': ['name', 'kind', 'contact', 'phone', 'payment_term', 'payment_days', 'address'],
    'projects': [
        'name',
        'customer',
        'manager',
        'due_date',
        'requirements',
        'equipment_quantity',
        'warranty_months',
        'members',
    ],
    'purchases': [
        'group',
        'project',
        'supplier',
        'payment_term',
        'payment_days',
        'due_date',
        'payment_due_date',
        'note',
        'item',
        'quantity',
        'unit_price',
        'line_due_date',
    ],
    'tasks': ['title', 'kind', 'assignee', 'due_date', 'project', 'description'],
    'moves': ['stock', 'quantity', 'reason', 'project', 'task'],
}
SCHEMAS = {}
for resource, (roles, old_columns) in LEGACY_SCHEMAS.items():
    labels = {key: LABEL_OVERRIDES.get(resource, {}).get(key, label) for label, key in old_columns}
    SCHEMAS[resource] = (roles, [(labels[key], key) for key in ORDERS.get(resource, list(labels))])

TABLE_KEYS = {
    'item': ['item_code', 'item_name'],
    'project': ['project_name'],
    'customer': ['customer_name'],
    'supplier': ['supplier_name'],
    'manager': ['manager_name'],
    'assignee': ['assignee_name'],
    'user': ['user_name'],
    'task': ['task_title'],
    'entry': ['entry_title'],
    'stock': ['item_name', 'location'],
}
FIELD_HINTS = {
    'item': '填写基础资料中的物料编码，名称等资料由编码关联。',
    'customer': '填写客户编码，不能填写客户名称或内部 ID。',
    'supplier': '填写供应商编码，不能填写供应商名称或内部 ID。',
    'project': '填写执行项目编号；文件中的编号决定归属，不自动使用当前筛选项目。',
    'manager': '填写登录账号，不能填写姓名。',
    'assignee': '填写登录账号，不能填写姓名。',
    'user': '填写登录账号，不能填写姓名。',
    'installer': '填写安装人员登录账号。',
    'acceptor': '填写验收人员登录账号。',
    'members': '填写登录账号，多个账号用英文分号分隔。',
    'entry': '从应收应付列表导出获取记录ID，页面显示对应款项名称。',
    'stock': '从共享库存列表导出获取记录ID，对应物料和库位。',
    'task': '从项目任务列表导出获取记录ID，页面显示对应任务名称。',
    'document': '填写已上传的同项目收付凭证记录ID，可留空。',
    'reconciliation': '采购付款填写已确认且仍有效的对账单ID；客户收款可留空。',
    'group': '仅用于将多行合并为一张采购草稿，不是采购编号；同组单据信息须一致。',
    'code': '可自定义，留空自动生成；不能覆盖已有编码。',
    'part_type': '填写标准件、非标件，或 standard/custom；可留空。',
    'payment_term': '填写指定日期、现付、月结30天、月结60天、月结90天、月结120天、自定义月结；也兼容原英文值。',
    'payment_days': '仅自定义月结填写 0～365；月结按收货当月月底加天数。',
    'duplicate_reason': '相同物料独立建码时填写原因；不显示在物料主列表，保留审计。',
    'method': '填写银行转账、现金、其他（兼容 bank/cash/other）。',
}
ENUMS = {
    'method': {'银行转账': 'bank', '现金': 'cash', '其他': 'other'},
    'part_type': {'标准件': 'standard', '非标件': 'custom'},
    'payment_term': {
        '指定日期': 'manual',
        '现付': 'cash',
        '月结30天': 'month30',
        '月结60天': 'month60',
        '月结90天': 'month90',
        '月结120天': 'month120',
        '自定义月结': 'custom',
    },
}
NOTES = {
    'items': '新增物料；编码留空自动生成，不覆盖现有物料。类别填写 standard（标准件）或 custom（非标件），可留空。',
    'partners': '新增往来单位；类型填写 customer（客户）、supplier（供应商）或 both（两者）。采购账期可填 manual/cash/month30/month60/month90/month120/custom；custom另填0到365天，纯客户只用manual。',
    'sales': '新增销售草稿，后续在销售页面报价和签约。',
    'projects': '新增执行项目；已签约销售请通过销售签约生成项目，避免重复。',
    'purchases': '同一分组号的行合并为一张采购草稿；项目、供应商、交期、账期及说明必须一致。采购账期留空沿用供应商，或填manual/cash/month30/month60/month90/month120/custom；custom另填天数。自动账期不能同时填付款到期日；月结按每批合格收货当月月底加天数。仍需提交审批。',
    'tasks': '新增任务；阶段填写 design（设计）、assembly（装配）或 test（调试）。',
    'stocks': '录入期初库存，仅允许尚无流水的物料与库位；已有库存使用盘点操作。',
    'entries': '录入项目费用；合同应收和采购应付继续由原单据生成。',
    'payments': '对现有款项登记正常收付款，金额为正数；采购付款必须填写已确认的对账单ID，客户收款可留空；退款和冲销仍使用原记录操作。',
    'time': '登记任务工时，仍校验任务、人员和项目权限。',
    'deliveries': '登记项目发货，仍校验生产阶段和剩余交付数量。',
    'moves': '登记项目领料，仍校验库存、任务与 BOM；退料和退货使用原流水操作。',
}


def schema(actor, resource):
    if resource not in SCHEMAS:
        raise ValidationError('此资源不支持批量新增。')
    roles, columns = SCHEMAS[resource]
    require_role(actor, roles)
    return columns


def layout(actor, resource):
    columns = []
    for label, key in schema(actor, resource):
        table_keys = TABLE_KEYS.get(key, [key])
        if resource == 'deliveries' and key == 'date':
            table_keys = ['shipped_date']
        hint = FIELD_HINTS.get(key, '按列名填写；仅新增，不覆盖原记录。')
        if key in {'date', 'due_date', 'line_due_date', 'payment_due_date'}:
            hint = (
                '日期格式 YYYY-MM-DD；明细交期留空沿用订单交期。' if key == 'line_due_date' else '日期格式 YYYY-MM-DD。'
            )
        if key == 'kind':
            hint = (
                '填写客户、供应商、客户及供应商（兼容 customer/supplier/both）。'
                if resource == 'partners'
                else '填写设计、装配、调试（兼容 design/assembly/test）。'
            )
        columns.append({'key': key, 'label': label, 'table_keys': table_keys, 'hint': hint})
    return {'columns': columns, 'note': NOTES[resource]}


def template(actor, resource, file_format):
    return document(resource + '-template', [label for label, _ in schema(actor, resource)], [], file_format)


def resolve(model, value, field='code'):
    obj = model.objects.filter(**{field: value}).first()
    if obj is None:
        raise ValidationError(f'找不到{model._meta.verbose_name}：{value}')
    return obj.pk


def payload(raw):
    data = {key: value for key, value in raw.items() if value != ''}
    for field in ['item', 'customer', 'supplier', 'project']:
        if field in data:
            data[field] = resolve(
                {'item': Item, 'customer': Partner, 'supplier': Partner, 'project': Project}[field], data[field]
            )
    for field in ['manager', 'assignee', 'user', 'installer', 'acceptor']:
        if field in data:
            data[field] = resolve(User, data[field], 'username')
    if 'members' in data:
        data['members'] = [
            resolve(User, value.strip(), 'username') for value in data['members'].split(';') if value.strip()
        ]
    return data


def execute_row(actor, resource, raw, key):
    data = payload(raw)
    if resource in {'items', 'partners'}:
        return masterdata.masterdata(actor, key, Item if resource == 'items' else Partner, data)
    simple = {
        'sales': sales.create,
        'projects': projects.create_project,
        'tasks': execution.create_task,
        'stocks': inventory.opening,
        'entries': finance.expense,
        'moves': inventory.issue,
    }
    if resource in simple:
        return simple[resource](actor, key, data)
    if resource == 'purchases':
        data.pop('group', None)
        data['lines'] = [payload(line) for line in raw['lines']]
        return supply.create_purchase(actor, key, data)
    target, service = {
        'payments': ('entry', finance.pay),
        'time': ('task', execution.log_time),
        'deliveries': ('project', execution.ship),
    }[resource]
    return service(actor, key, data.pop(target, None), data)


def parse(actor, resource, upload):
    columns = schema(actor, resource)
    records = []
    headers = [label for label, _ in columns]
    old_columns = LEGACY_SCHEMAS[resource][1]
    old_headers = [label for label, _ in old_columns]
    legacy = [old_headers] + (
        [old_headers[:4], old_headers[:8]]
        if resource == 'payments'
        else [old_headers[:4], old_headers[:6]]
        if resource == 'items'
        else [old_headers[:8], old_headers[:9], old_headers[:10]]
        if resource == 'purchases'
        else [old_headers[:5]]
        if resource == 'partners'
        else []
    )
    actual_headers, rows = read_file(upload, headers, legacy, return_headers=True)
    source_columns = columns if actual_headers == headers else old_columns[: len(actual_headers)]
    for index, row in enumerate(rows, 2):
        if not any(value not in (None, '') for value in row):
            continue
        if any(value not in (None, '') for value in row[len(columns) :]):
            raise ValidationError(f'第{index}行包含多余列。')
        values = []
        for value in row[: len(columns)]:
            if isinstance(value, datetime):
                value = value.date().isoformat()
            elif isinstance(value, date):
                value = value.isoformat()
            values.append('' if value is None else str(value).strip())
        raw = dict(zip([key for _, key in source_columns], values, strict=True))
        records.append({'row': index, 'data': {key: raw.get(key, '') for _, key in columns}})
    if not records:
        raise ValidationError('文件没有可导入明细。')
    return records


def executable_records(resource, records):
    # Preview keeps one row per file row; service payloads are separate from display data.
    records = [{'row': r['row'], 'data': dict(r['data'])} for r in records]
    for record in records:
        data = record['data']
        for key, translations in ENUMS.items():
            if key in data:
                data[key] = translations.get(data[key], data[key])
        kinds = (
            {'客户': 'customer', '供应商': 'supplier', '客户及供应商': 'both'}
            if resource == 'partners'
            else {'设计': 'design', '装配': 'assembly', '调试': 'test'}
        )
        if 'kind' in data:
            data['kind'] = kinds.get(data['kind'], data['kind'])
    if resource == 'purchases':
        grouped = {}
        for record in records:
            data = record['data']
            group = data['group']
            if not group:
                raise ValidationError(f'第{record["row"]}行必须填写分组号。')
            line = {key: data.pop(key) for key in ['item', 'quantity', 'unit_price']}
            line['due_date'] = data.pop('line_due_date', '') or data['due_date']
            if group not in grouped:
                grouped[group] = {'row': record['row'], 'data': {**data, 'lines': []}}
            target = grouped[group]['data']
            if any(target[key] != value for key, value in data.items()):
                raise ValidationError(f'分组号{group}的单据信息不一致。')
            target['lines'].append(line)
        records = list(grouped.values())
    return records


def run(actor, resource, records, *, preview=False):
    results, errors = [], []
    with transaction.atomic():
        for record in records:
            try:
                with transaction.atomic():
                    results.append(execute_row(actor, resource, record['data'], str(uuid4())))
            except (APIException, Http404) as exc:
                errors.append(
                    {'row': record['row'], 'message': message(getattr(exc, 'detail', '记录不存在或无权访问。'))}
                )
                if not preview:
                    raise ValidationError({'rows': errors}) from exc
        if preview:
            transaction.set_rollback(True)
    return results, errors


def preview(actor, resource, upload):
    display_records = parse(actor, resource, upload)
    records = executable_records(resource, display_records)
    _, errors = run(actor, resource, records, preview=True)
    token = (
        signing.dumps(
            {'actor': actor.pk, 'resource': resource, 'records': records, 'nonce': str(uuid4())},
            salt='business-import',
            compress=True,
        )
        if not errors
        else None
    )
    return {
        'count': len(records),
        'rows': display_records,
        'row_count': len(display_records),
        'columns': layout(actor, resource)['columns'],
        'errors': errors,
        'can_import': not errors,
        'token': token,
        'note': NOTES[resource],
    }


def confirm(actor, resource, token):
    schema(actor, resource)
    if not isinstance(token, str) or len(token) > 10 * 1024 * 1024:
        raise ValidationError('请重新预览文件。')
    try:
        batch = signing.loads(token, salt='business-import', max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError('预览已过期或被修改，请重新上传。') from exc
    if batch['actor'] != actor.pk or batch['resource'] != resource:
        raise ValidationError('预览不属于当前用户或模块。')

    def execute(user):
        results, _ = run(user, resource, batch['records'])
        return {'count': len(results), 'results': results}

    return perform(
        actor=actor,
        key='import:' + batch['nonce'],
        operation='import.' + resource,
        payload=batch,
        authorize=lambda user: schema(user, resource),
        execute=execute,
    )
