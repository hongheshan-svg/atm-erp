"""Human-readable BOM files, using only the view's authorized and visible rows."""

from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict

from . import tabular
from .common import fields, identity

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


def selected_rows(queryset, data):
    fields(data, {'project', 'ids', 'file_format'})
    if data.get('file_format', 'xlsx') not in ('csv', 'xlsx'):
        raise ValidationError('请选择Excel或CSV导出格式。')
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


def document(lines, file_format):
    rows = []
    for line in lines:
        item = line.item
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
                line.required_date,
                line.application_date,
                line.applicant,
                line.change_note,
            ]
        )
    return tabular.document('bom', HEADERS, rows, file_format, numeric={12})
