"""Batch creation through existing services, with rollback-only preview and signed confirmation."""

import re
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from django.core import signing
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.error_messages import validation_detail
from apps.core.permissions import (
    ADMIN,
    ALL_ROLES,
    FINANCE,
    ITEM_WRITERS,
    MANAGERS,
    PRODUCTION_MANAGERS,
    PURCHASERS,
    SALES,
    WAREHOUSE,
    can_manage_task,
    has_role,
    require_project,
    require_role,
    task_management_roles,
)

from ..models import Document, Entry, Item, Partner, Project, Reconciliation, Stock, Task
from . import execution, finance, inventory, masterdata, projects, sales, supply
from .bom_import import message, read_file
from .common import identity
from .import_dedup import DUPLICATE_MESSAGE, content_digest, imported, normalized_record, receipt_payload
from .import_feedback import feedback, locate
from .import_guides import RESOURCES, guide, template_document
from .import_locks import lock_batch, lock_content

# Label -> service field. Human-readable references resolve at preview and confirmation.
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
        ITEM_WRITERS,
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
        PRODUCTION_MANAGERS,
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
    'items': [
        'code',
        'name',
        'specification',
        'drawing_number',
        'drawing_revision',
        'product_category',
        'brand',
        'part_type',
        'unit',
        'duplicate_reason',
    ],
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
PERSON_LABELS = {
    'manager': '负责人姓名或账号',
    'members': '成员姓名或账号（分号分隔）',
    'assignee': '执行人姓名或账号',
    'user': '人员姓名或账号',
    'installer': '安装人姓名或账号',
    'acceptor': '验收人姓名或账号',
}
SCHEMAS = {}
PREVIOUS_SCHEMAS = {}
PREVIOUS_ITEM_COLUMNS = [
    ('物料编码', 'code'),
    ('物料名称', 'name'),
    ('规格', 'specification'),
    ('品牌', 'brand'),
    ('物料类别', 'part_type'),
    ('单位', 'unit'),
    ('独立建码原因', 'duplicate_reason'),
]
for resource, (roles, old_columns) in LEGACY_SCHEMAS.items():
    labels = {key: LABEL_OVERRIDES.get(resource, {}).get(key, label) for label, key in old_columns}
    if resource == 'items':
        labels.update(drawing_number='图号', drawing_revision='图档版本', product_category='产品编码类别')
    previous = [(labels[key], key) for key in ORDERS.get(resource, list(labels))]
    PREVIOUS_SCHEMAS[resource] = previous
    SCHEMAS[resource] = (roles, [(PERSON_LABELS.get(key, label), key) for label, key in previous])

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
ENUMS = {
    'product_category': {
        **{label: value for value, label in Item.ProductCategory.choices},
        '机加': '11',
        '机加件': '11',
        '钣金': '12',
        '特殊工艺': '13',
        '标准件': '21',
        '耗材辅料': '22',
        '办公用品': '23',
    },
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
NOTES = {resource: metadata[2] for resource, metadata in RESOURCES.items()}


def schema(actor, resource):
    if resource not in SCHEMAS:
        raise ValidationError('此资源不支持批量新增。')
    roles, columns = SCHEMAS[resource]
    require_role(actor, roles)
    return columns


def layout(actor, resource):
    result = guide(resource, schema(actor, resource))
    if resource == 'tasks' and not has_role(actor, MANAGERS):
        result['quick_start']['prepare'] = '生产经理仅可导入本人参与项目的装配、调试任务；执行人员须已加入该项目。'
        result['quick_start']['example'] = (
            '例如装配任务：名称填机械装配，阶段选装配，执行人填真实姓名，项目编号从参与项目复制。'
        )
        for column in result['columns']:
            if column['key'] == 'kind':
                column.update(
                    options=['装配', '调试'],
                    example='装配',
                    hint='生产经理仅可选择装配、调试（兼容assembly/test）；不能导入设计任务。',
                    source='Excel下拉选择装配或调试。',
                )
    for column in result['columns']:
        key = column['key']
        column['table_keys'] = (
            ['shipped_date'] if resource == 'deliveries' and key == 'date' else TABLE_KEYS.get(key, [key])
        )
    return result


def template(actor, resource, file_format):
    return template_document(resource + '-template', layout(actor, resource), file_format)


def resolve_person(value):
    value = str(value).strip()
    explicit = re.fullmatch(r'(.+?)[（(]([^（）()]+)[）)]', value)
    if explicit:
        name, username = (part.strip() for part in explicit.groups())
        obj = User.objects.filter(username=username).first()
        candidates = [obj] if obj and (obj.display_name or obj.username) == name else []
    else:
        # Include inactive users and name/account collisions: never choose an arbitrary person.
        candidates = list(User.objects.filter(Q(username=value) | Q(display_name=value)).order_by('pk')[:2])
    if not candidates:
        raise ValidationError(f'未找到人员“{value}”。请核对人员姓名或登录账号；也可填写姓名（用户名）。')
    if len(candidates) > 1:
        raise ValidationError(
            f'“{value}”对应多名人员，请填写姓名（用户名）或可唯一匹配的登录账号，不能仅填写重名姓名。'
        )
    obj = candidates[0]
    if not obj.is_active:
        raise ValidationError(f'人员“{obj.display_name or obj.username}（{obj.username}）”已停用，请选择已启用的人员。')
    return obj.pk


def resolve(model, value, field='code'):
    if model is User:
        return resolve_person(value)
    obj = model.objects.filter(**{field: value}).first()
    if obj is None:
        label = {Item: '物料', Partner: '往来单位', Project: '项目'}[model]
        raise ValidationError(f'找不到{label}：{value}，请核对系统中的编号。')
    return obj.pk


def payload(raw, people=None):
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
        data['members'] = [resolve_person(value) for value in re.split('[;；]', data['members']) if value.strip()]
    if people is not None:
        resolved = {key: data[key] for key in PERSON_LABELS if key in data}
        if people and people != resolved:
            raise ValidationError('人员对应关系已变化，请重新预览文件并核对人员后再确认。')
        people.update(resolved)
    return data


UNREACHABLE = '记录不存在或不在你的权限范围内。'


def check_references(actor, resource, data):
    """Locate ID columns before the business service, using the service's own lookup filters.

    Check project access before resolving secondary references. Missing and out-of-range
    records share one wording to avoid revealing which reference exists.
    """

    def need(key, model, **filters):
        if data.get(key) in (None, ''):
            return None
        found = model.objects.filter(pk=identity(data[key], key), **filters).first()
        if found is None:
            raise ValidationError({key: UNREACHABLE})
        if model in {Entry, Task}:
            try:
                require_project(actor, found.project, SCHEMAS[resource][0])
            except PermissionDenied as exc:
                raise ValidationError({key: UNREACHABLE}) from exc
        return found

    if resource == 'payments':
        entry = need('entry', Entry)
        if entry is not None:
            need('document', Document, project=entry.project, category='receipt')
            need('reconciliation', Reconciliation, entry=entry)
    elif resource == 'moves':
        need('stock', Stock)
        if data.get('project'):
            need('task', Task, project_id=data['project'], status='open')
    elif resource == 'time':
        need('task', Task)


def execute_row(actor, resource, raw, key, people=None):
    data = payload(raw, people)
    if resource == 'tasks' and not has_role(actor, task_management_roles(data.get('kind'))):
        raise ValidationError({'kind': '生产经理只能导入装配、调试任务；设计任务须由项目经理或管理员导入。'})
    check_references(actor, resource, data)
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


def accepted_schemas(resource):
    old = LEGACY_SCHEMAS[resource][1]
    sizes = {'payments': [4, 8], 'items': [4, 6], 'purchases': [8, 9, 10], 'partners': [5]}
    return [
        SCHEMAS[resource][1],
        PREVIOUS_SCHEMAS[resource],
        old,
        *[old[:size] for size in sizes.get(resource, [])],
        *([PREVIOUS_ITEM_COLUMNS] if resource == 'items' else []),
    ]


def parse(actor, resource, upload, *, with_source=False):
    columns = schema(actor, resource)
    records = []
    variants = accepted_schemas(resource)
    headers = [label for label, _ in columns]
    actual_headers, rows = read_file(
        upload, headers, [[label for label, _ in variant] for variant in variants], return_headers=True
    )
    source_columns = next(variant for variant in variants if [label for label, _ in variant] == actual_headers)
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
        raise ValidationError('文件没有可导入明细。请在“数据”页第2行起填写真实业务数据；“填写说明”页和示例不参与导入。')
    return (records, actual_headers, rows, source_columns) if with_source else records


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
        lock_batch(actor, resource, records)
        for record in records:
            try:
                with transaction.atomic():
                    # Bind previewed identities in the signed token, then reject silent reassignment on confirmation.
                    people = record.setdefault('people', {}) if preview else record.get('people')
                    results.append(execute_row(actor, resource, record['data'], str(uuid4()), people))
                    current = normalized_record(actor, resource, record['data'], people)
                    if not preview and record.get('normalized') != current:
                        raise ValidationError('引用资料或默认值已变化，请重新上传预览后确认。')
                    record['normalized'] = current
            except (APIException, ModelValidationError, Http404) as exc:
                detail = (
                    validation_detail(exc)
                    if isinstance(exc, ModelValidationError)
                    else getattr(exc, 'detail', '记录不存在或无权访问。')
                )
                labels = {key: label for label, key in schema(actor, resource)}
                fields = [key for key in detail if key in labels] if isinstance(detail, dict) else []
                errors.append({'row': record['row'], 'message': message(detail, labels), 'fields': fields})
                if not preview:
                    locate(errors, schema(actor, resource))
                    raise ValidationError({'rows': errors}) from exc
        if preview:
            transaction.set_rollback(True)
    return results, errors


def expand_errors(resource, errors, display_records):
    if resource != 'purchases':
        return errors
    groups = {record['row']: record['data']['group'] for record in display_records}
    return [
        {**error, 'row': record['row']}
        for error in errors
        for record in display_records
        if groups[record['row']] == groups[error['row']]
    ]


def preview(actor, resource, upload):
    display_records, headers, source_rows, source_columns = parse(actor, resource, upload, with_source=True)
    records = executable_records(resource, display_records)
    _, errors = run(actor, resource, records, preview=True)
    errors = expand_errors(resource, errors, display_records)
    invalid_rows = {error['row'] for error in errors}
    people_by_row = {record['row']: record.get('people', {}) for record in records if record['row'] not in invalid_rows}
    person_ids = {
        pk
        for people in people_by_row.values()
        for value in people.values()
        for pk in (value if isinstance(value, list) else [value])
    }
    names = {
        person.pk: f'{person.display_name or person.username}（{person.username}）'
        for person in User.objects.filter(pk__in=person_ids)
    }
    for record in display_records:
        if record['row'] in invalid_rows:
            continue
        record['matches'] = {
            field: '；'.join(names[pk] for pk in (value if isinstance(value, list) else [value]) if pk in names)
            for field, value in people_by_row.get(record['row'], {}).items()
        }
    digest = content_digest(resource, records) if not errors else None
    duplicate = imported(resource, digest) if digest else False
    token = (
        signing.dumps(
            {
                'actor': actor.pk,
                'resource': resource,
                'records': records,
                'nonce': str(uuid4()),
                'source': {
                    'headers': headers,
                    'rows': [
                        [value.isoformat()[:10] if isinstance(value, date) else value for value in row]
                        for row in source_rows
                    ],
                    'columns': source_columns,
                    'records': display_records,
                },
            },
            salt='business-import',
            compress=True,
        )
        if not errors
        else None
    )
    return feedback(
        {
            'count': len(records),
            'rows': display_records,
            'row_count': len(display_records),
            'columns': layout(actor, resource)['columns'],
            'errors': errors,
            'can_import': not errors,
            'token': token,
            'note': NOTES[resource],
            'duplicate_import': {'message': DUPLICATE_MESSAGE} if duplicate else None,
        },
        headers,
        source_rows,
        source_columns,
        RESOURCES[resource][0],
    )


def confirm(actor, resource, token, *, allow_duplicate=False, key=None):
    schema(actor, resource)
    if not isinstance(allow_duplicate, bool):
        raise ValidationError({'allow_duplicate': '必须明确选择是否再次导入。'})
    if not isinstance(token, str) or len(token) > 10 * 1024 * 1024:
        raise ValidationError('请重新预览文件。')
    try:
        batch = signing.loads(token, salt='business-import', max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError('预览已过期或被修改，请重新上传。') from exc
    if batch['actor'] != actor.pk or batch['resource'] != resource:
        raise ValidationError('预览不属于当前用户或模块。')
    if any('normalized' not in record for record in batch['records']):
        raise ValidationError('导入校验已更新，请重新上传预览。')
    digest = content_digest(resource, batch['records'])

    def authorize(user):
        schema(user, resource)
        projects_by_id = {project.pk: project for project in lock_batch(user, resource, batch['records'])}
        user.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        schema(user, resource)
        for project in projects_by_id.values():
            require_project(user, project, SCHEMAS[resource][0])
        for record in batch['records']:
            data = record['normalized']
            if resource == 'tasks':
                project = projects_by_id.get(data['project'])
                if project is None:
                    raise ValidationError({'project': UNREACHABLE})
                require_project(user, project, task_management_roles(data['kind']))
            if resource == 'sales' and not has_role(user, MANAGERS) and data.get('manager') != user.pk:
                raise PermissionDenied('仅能操作自己负责的销售单。')
            if resource == 'time':
                task = Task.objects.filter(pk=int(Decimal(data['task']))).first()
                if task is None:
                    raise ValidationError({'task': UNREACHABLE})
                if not can_manage_task(user, task) and (data['user'] != user.pk or task.assignee_id != user.pk):
                    raise PermissionDenied('只能为自己的任务登记本人工时，或登记管理范围内的生产与售后工时。')

    def execute(user):
        lock_content(digest)
        if imported(resource, digest) and not allow_duplicate:
            raise Conflict({'duplicate_import': {'message': DUPLICATE_MESSAGE}})
        try:
            results, _ = run(user, resource, batch['records'])
        except ValidationError as exc:
            if not isinstance(exc.detail, dict) or 'rows' not in exc.detail:
                raise
            errors = [{**error, 'row': int(error['row'])} for error in exc.detail['rows']]
            source = batch['source']
            result = feedback(
                {'errors': expand_errors(resource, errors, source['records'])},
                source['headers'],
                source['rows'],
                source['columns'],
                RESOURCES[resource][0],
            )
            raise ValidationError({'rows': result['errors'], 'error_file': result['error_file']}) from exc
        if resource == 'deliveries':
            results = [
                {**result, 'project': record['normalized']['project']}
                for result, record in zip(results, batch['records'], strict=True)
            ]
        return {'count': len(results), 'results': results, 'resource': 'moves' if resource == 'stocks' else resource}

    def confirm_token(user):
        return perform(
            actor=user,
            key='import:' + batch['nonce'],
            operation='import.' + resource,
            payload=receipt_payload(digest),
            authorize=authorize,
            execute=execute,
        )

    if key is None:
        return confirm_token(actor)
    return perform(
        actor=actor,
        key=key,
        operation='import.request.' + resource,
        payload=receipt_payload(digest),
        authorize=authorize,
        execute=confirm_token,
    )
