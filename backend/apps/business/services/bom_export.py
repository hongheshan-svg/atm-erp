"""Human-readable BOM files, using only the view's authorized and visible rows."""

from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict

from . import tabular
from .common import fields, identity
from .import_guides import BOM_COLUMNS

HEADERS = [
    '项目编号',
    '项目名称',
    '物料编码',
    '物料名称',
    '规格',
    '图号',
    '图档版本',
    '产品编码类别',
    '品牌',
    '物料类别',
    '单元',
    '单位',
    '需求数量',
    '需求日期',
    '申请日期',
    '申请人',
    '变更说明',
]
# 采购缺料视图导出：在「需求数量」后追加与页面同一口径的占用和缺口，拿去询价或汇报不必再手工对数。
DEMAND_COLUMNS = [
    ('已领', 'issued'),
    ('在途', 'incoming'),
    ('其中待批采购', 'unapproved'),
    ('可用库存', 'available'),
    ('缺料', 'shortage'),
    ('其他项目待领', 'other_demand'),
]
LAYOUTS = ('standard', 'purchase', 'import')


def selected_rows(queryset, data):
    fields(data, {'project', 'ids', 'file_format', 'layout'})
    if data.get('file_format', 'xlsx') not in ('csv', 'xlsx'):
        raise ValidationError('请选择Excel或CSV导出格式。')
    if data.get('layout', 'standard') not in LAYOUTS:
        raise ValidationError('请选择BOM明细、缺料清单或可回导模板。')
    project = identity(data.get('project'), 'project')
    ids = data.get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > tabular.MAX_EXPORT:
        raise ValidationError(f'请选择1至{tabular.MAX_EXPORT}条BOM明细后导出。')
    ids = [identity(value, 'ids') for value in ids]
    if len(set(ids)) != len(ids):
        raise ValidationError('导出明细不能重复，请刷新后重新选择。')
    found = {line.pk: line for line in queryset.filter(project_id=project, pk__in=ids)}
    if len(found) != len(ids):
        raise Conflict('所选BOM明细已变化或不在当前项目可见范围，请刷新后重新选择。')
    return [found[pk] for pk in ids]


def document(lines, file_format, layout='standard'):
    if layout == 'import':
        return template(lines, file_format)
    rows = []
    demand = {}
    if layout == 'purchase' and lines:
        from .bom import demand as project_demand

        demand = {row['bom_line']: row for row in project_demand(lines[0].project)}
    for line in lines:
        item = line.item
        extra = [demand.get(line.pk, {}).get(key, '') for _, key in DEMAND_COLUMNS] if layout == 'purchase' else []
        rows.append(
            [
                line.project.code,
                line.project.name,
                item.code,
                item.name,
                item.specification,
                item.drawing_number,
                item.drawing_revision,
                item.get_product_category_display() or '未分类',
                item.brand,
                item.get_part_type_display() or '未分类',
                line.assembly_unit,
                item.unit,
                line.quantity,
                *extra,
                line.required_date,
                line.application_date,
                line.applicant,
                line.change_note,
            ]
        )
    headers = list(HEADERS)
    numeric = {12}
    if layout == 'purchase':
        headers[13:13] = [label for label, _ in DEMAND_COLUMNS]
        numeric |= set(range(13, 13 + len(DEMAND_COLUMNS)))
    return tabular.document('bom', headers, rows, file_format, numeric=numeric)


def template(lines, file_format):
    """按导入模板的列顺序导出，改完数量和说明可直接回导；变更说明留空，只给改过的行填写。"""
    rows = []
    for line in lines:
        item = line.item
        values = {
            'code': item.code,
            'assembly_unit': line.assembly_unit,
            'quantity': line.quantity,
            'change_note': '',
            'required_date': line.required_date,
            'application_date': line.application_date,
            'applicant': line.applicant,
            'name': item.name,
            'specification': item.specification,
            'drawing_number': item.drawing_number,
            'drawing_revision': item.drawing_revision,
            # 留空表示沿用物料主数据；写「未分类」回导时会被当成不一致的类别。
            'product_category': item.get_product_category_display() if item.product_category else '',
            'brand': item.brand,
            'part_type': item.get_part_type_display() if item.part_type else '',
            'unit': item.unit,
        }
        rows.append([values[key] for _, key in BOM_COLUMNS])
    return tabular.document('bom-template', [label for label, _ in BOM_COLUMNS], rows, file_format, numeric={2})
