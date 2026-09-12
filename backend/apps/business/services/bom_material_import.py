"""Atomic BOM import with server-resolved material identities and deferred numbering."""

import csv
import hashlib
import io
import uuid
from datetime import date, datetime

from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import BOM_WRITERS, require_project

from ..models import Item
from . import bom, bom_import, masterdata
from .common import project_action

MATERIAL_FIELDS = (
    'name',
    'specification',
    'drawing_number',
    'drawing_revision',
    'product_category',
    'brand',
    'part_type',
    'unit',
)
HEADERS = bom_import.HEADERS + ['物料名称', '规格', '图号', '图档版本', '产品编码类别', '品牌', '物料类别', '单位']
SALT = 'lean-bom-material-import-v1'


def material(actor, row):
    from .transfers import ENUMS

    data = {
        field: masterdata.normalized(str(value or '')) for field, value in zip(MATERIAL_FIELDS, row[7:], strict=True)
    }
    for field in ('product_category', 'part_type'):
        data[field] = ENUMS[field].get(data[field], data[field])
    code = row[0].strip()
    if code:
        item = Item.objects.filter(code=code, is_active=True).first()
        if item is None:
            raise ValidationError('填写的物料编码不存在或已停用；新增物料请留空编码并填写物料资料。')
        if any(
            value and masterdata.normalized(getattr(item, field)).casefold() != value.casefold()
            for field, value in data.items()
        ):
            raise ValidationError('所填物料资料与编码对应的现有物料不一致，请核对编码；导入不会覆盖物料主数据。')
        return item, '使用已有编码'
    for field in ('name', 'specification', 'product_category', 'unit'):
        if not data[field]:
            raise ValidationError('编码留空时必须填写物料名称、规格、产品编码类别和单位。')
    if data['product_category'] not in Item.ProductCategory.values:
        raise ValidationError('请选择明确的有图/无图产品编码类别。')
    if data['product_category'].startswith('1') and not data['drawing_number']:
        raise ValidationError('有图产品必须填写图号。')
    matches = masterdata.duplicates(data)
    if len(matches) > 1:
        raise ValidationError('存在多个相同物料，请明确填写要复用的物料编码。')
    if matches:
        if not matches[0].is_active:
            raise ValidationError('相同物料已停用，请先核对主数据，不能自动重复建码。')
        return matches[0], '复用相同物料'
    result = masterdata.masterdata(actor, str(uuid.uuid4()), Item, data)
    return Item.objects.get(pk=result['id']), '自动新建物料'


def resolve(actor, project, records, expected):
    if bom.revision(project) != expected:
        raise Conflict('BOM 已变化，请重新上传预览。')
    CodeRule.objects.select_for_update().get(key='item')
    output, actions = [], []
    new_ids = set()
    for index, row in enumerate(records, 2):
        if not any(row):
            output.append(row[:7])
            continue
        try:
            item, action = material(actor, row)
        except ValidationError as exc:
            raise ValidationError(f'第{index}行：{bom_import.message(exc.detail)}') from exc
        if action == '自动新建物料':
            new_ids.add(item.pk)
        output.append([item.code, *row[1:7]])
        actions.append((index, action, item.pk in new_ids))
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(bom_import.HEADERS)
    writer.writerows(output)
    result = bom_import.preview(project, SimpleUploadedFile('bom.csv', stream.getvalue().encode()))
    if not result['can_import']:
        raise ValidationError([f'第{error["row"]}行：{error["message"]}' for error in result['errors']])
    by_row = {index: (action, new) for index, action, new in actions}
    for line in result['lines']:
        line['material_action'], line['new_material'] = by_row[line['row']]
    return result


def preview(actor, project, upload):
    require_project(actor, project, BOM_WRITERS)
    headers, records = bom_import.read_file(
        upload,
        HEADERS,
        [bom_import.HEADERS, bom_import.PREVIOUS_HEADERS, bom_import.LEGACY_HEADERS, bom_import.LEGACY_HEADERS[:3]],
        return_headers=True,
    )
    if headers != HEADERS:
        upload.seek(0)
        return bom_import.preview(project, upload)
    records = [
        [
            value.date().isoformat()
            if isinstance(value, datetime)
            else value.isoformat()
            if isinstance(value, date)
            else str(value).strip()
            if value is not None
            else ''
            for value in row
        ]
        for row in records
    ]
    expected = bom.revision(project)
    try:
        with transaction.atomic():
            result = project_action(
                actor,
                str(uuid.uuid4()),
                'bom.import.preview',
                project.pk,
                {},
                BOM_WRITERS,
                lambda user, locked: resolve(user, locked, records, expected),
            )
            transaction.set_rollback(True)
    except ValidationError as exc:
        return {
            'can_import': False,
            'lines': [],
            'errors': [{'message': bom_import.message(exc.detail)}],
            'expected_revision': expected,
        }
    result['token'] = signing.dumps(
        {'actor': actor.pk, 'project': project.pk, 'revision': expected, 'records': records}, salt=SALT, compress=True
    )
    result['note'] = (
        '预览不占用编号；新物料编号在确认时生成。物料与BOM整批保存，已有相同物料自动复用；任一行失败全部撤销。'
    )
    for line in result['lines']:
        if line['new_material']:
            line['item_code'] = '确认时自动生成'
            line.pop('item', None)
    return result


def confirm(actor, project, data):
    if not isinstance(data, dict) or set(data) != {'token'} or not isinstance(data['token'], str):
        raise ValidationError('请提交预览确认凭据。')
    try:
        payload = signing.loads(data['token'], salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError('预览已过期或无效，请重新上传。') from exc
    if payload['actor'] != actor.pk or payload['project'] != project.pk:
        raise ValidationError('此预览不属于当前用户或项目。')

    def execute(user, locked):
        result = resolve(user, locked, payload['records'], payload['revision'])
        fields = ('item', 'quantity', 'assembly_unit', 'change_note', 'required_date', 'application_date', 'applicant')
        saved = bom.revise_bom(
            user,
            str(uuid.uuid4()),
            locked.pk,
            {
                'expected_revision': payload['revision'],
                'lines': [{field: row.get(field) for field in fields} for row in result['lines']],
            },
        )
        return {**saved, 'lines': result['lines']}

    return project_action(
        actor,
        'bom-import-' + hashlib.sha256(data['token'].encode()).hexdigest(),
        'bom.import.confirm',
        project.pk,
        data,
        BOM_WRITERS,
        execute,
    )
