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
from .import_feedback import feedback
from .import_guides import BOM_COLUMNS

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
HEADERS = [label for label, _ in BOM_COLUMNS]
SALT = 'lean-bom-material-import-v1'
BRAND_BACKFILLED = '沿用已有物料，补填品牌'


def row_data(row):
    from .transfers import ENUMS

    data = {field: str(value or '').strip() for field, value in zip(MATERIAL_FIELDS, row[7:], strict=True)}
    for field in ('product_category', 'part_type'):
        data[field] = ENUMS[field].get(data[field], data[field])
    return data


def lock_existing(records):
    """按主键顺序先锁住这批文件可能沿用或补填品牌的现有物料。

    逐行补填品牌会按文件行序加锁，随后保存 BOM 又按主键顺序锁物料；
    与其他按主键加锁的单据交错时会形成死锁，所以在逐行处理前一次锁齐。
    """
    codes, ids = set(), set()
    for row in records:
        if not any(row):
            continue
        code = row[0].strip()
        if code:
            codes.add(code)
            continue
        data = row_data(row)
        ids.update(item.pk for item in masterdata.duplicates(data))
        if data['brand']:
            ids.update(item.pk for item in masterdata.duplicates({**data, 'brand': ''}))
    ids.update(Item.objects.filter(code__in=codes).values_list('pk', flat=True))
    list(Item.objects.select_for_update().filter(pk__in=ids).order_by('pk').only('pk'))


def material(actor, row):
    data = row_data(row)
    code = row[0].strip()
    if code:
        item = Item.objects.filter(code=code, is_active=True).first()
        if item:
            backfill = {}
            for field, value in data.items():
                current = masterdata.normalized(getattr(item, field))
                if not value or current.casefold() == masterdata.normalized(value).casefold():
                    continue
                # 品牌原来为空时按文件补填（导出可回导模板、补品牌列再导回）；已有品牌和其他资料仍不覆盖。
                if field == 'brand' and not current:
                    backfill[field] = value
                    continue
                raise ValidationError(
                    '所填物料资料与编码对应的现有物料不一致，请核对编码；导入不会覆盖物料主数据，'
                    '只会补填原来为空的品牌。'
                )
            if backfill:
                masterdata.masterdata(actor, str(uuid.uuid4()), Item, backfill, item.pk)
                return Item.objects.get(pk=item.pk), BRAND_BACKFILLED
            return item, '使用已有编码'
        if Item.all_objects.filter(code=code).exists():
            raise ValidationError('填写的物料编码已停用或已删除，请先核对主数据，不能重复占用该编码。')
    required = ('name', 'specification', 'unit') + (() if code else ('product_category',))
    errors = {field: '新增物料时必填。' for field in required if not data[field]}
    if data['product_category'] and data['product_category'] not in Item.ProductCategory.values:
        errors['product_category'] = '请按填写说明选择，例如“无图·标准件”（21）、“有图·机加”（11）、“有图·钣金”（12）。'
    if data['product_category'].startswith('1') and not data['drawing_number']:
        errors['drawing_number'] = '有图产品必须填写图号。'
    if data['part_type'] not in ('', *Item.PartType.values):
        errors['part_type'] = '请填写标准件或非标件，未分类可留空；机加、钣金属于产品编码类别。'
    if errors:
        raise ValidationError(errors)
    if code:
        result = masterdata.masterdata(actor, str(uuid.uuid4()), Item, {**data, 'code': code})
        return Item.objects.get(pk=result['id']), '按填写编码新建物料'
    matches = masterdata.duplicates(data)
    if len(matches) > 1:
        raise ValidationError('存在多个相同物料，请明确填写要复用的物料编码。')
    if matches:
        if not matches[0].is_active:
            raise ValidationError('相同物料已停用，请先核对主数据，不能自动重复建码。')
        return matches[0], '复用相同物料'
    if data['brand']:
        # 原始 BOM 表补上品牌、编码仍留空再导入：除品牌外完全相同、原来没有品牌的物料就是同一物料，
        # 补填品牌后复用，不另建一批重复物料（否则 BOM 会多出新行，需求量翻倍）。
        unbranded = masterdata.duplicates({**data, 'brand': ''})
        if len(unbranded) > 1:
            raise ValidationError('存在多个除品牌外相同、且没有品牌的物料，请填写要补品牌的物料编码。')
        if unbranded:
            if not unbranded[0].is_active:
                raise ValidationError('相同物料已停用，请先核对主数据，不能自动重复建码。')
            masterdata.masterdata(actor, str(uuid.uuid4()), Item, {'brand': data['brand']}, unbranded[0].pk)
            return Item.objects.get(pk=unbranded[0].pk), BRAND_BACKFILLED
    result = masterdata.masterdata(actor, str(uuid.uuid4()), Item, data)
    return Item.objects.get(pk=result['id']), '自动新建物料'


def resolve(actor, project, records, expected, *, collect_errors=False):
    if bom.revision(project) != expected:
        raise Conflict('BOM 已变化，请重新上传预览。')
    CodeRule.objects.select_for_update().get(key='item')
    lock_existing(records)
    output, actions, errors = [], [], []
    new_ids = set()
    for index, row in enumerate(records, 2):
        if not any(row):
            output.append(row[:7])
            continue
        try:
            with transaction.atomic():
                item, action = material(actor, row)
        except ValidationError as exc:
            errors.append({'row': index, 'message': bom_import.message(exc.detail)})
            # Preserve source row numbers when validating the remaining BOM lines.
            output.append([''] * 7)
            continue
        if action in {'自动新建物料', '按填写编码新建物料'}:
            new_ids.add(item.pk)
        output.append([item.code, *row[1:7]])
        actions.append((index, action, item.pk in new_ids))
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(bom_import.HEADERS)
    writer.writerows(output)
    result = bom_import.preview(project, SimpleUploadedFile('bom.csv', stream.getvalue().encode()))
    if errors and not actions:
        result['errors'] = []  # Material errors already explain why there are no valid lines.
    if errors or any(action == BRAND_BACKFILLED for _, action, _ in actions):
        # 有物料问题时，「其余行与当前 BOM 一致」不是失败原因，不再另行提示；
        # 只补填品牌、BOM 用量不变时，这次导入照样有内容要保存。
        result['errors'] = [error for error in result['errors'] if not error.get('unchanged')]
    result['errors'] = sorted([*errors, *result['errors']], key=lambda error: error.get('row', 0))
    result['can_import'] = bool(result['lines']) and not result['errors']
    if not result['can_import'] and not collect_errors:
        raise ValidationError([f'第{error["row"]}行：{error["message"]}' for error in result['errors']])
    by_row = {index: (action, new) for index, action, new in actions}
    for line in result['lines']:
        line['material_action'], line['new_material'] = by_row[line['row']]
    if collect_errors:
        resolved = {line['row']: line for line in result['lines']}
        issues = {error['row']: error['message'] for error in result['errors'] if 'row' in error}
        result['lines'] = [
            {
                **dict(zip((key for _, key in BOM_COLUMNS), row, strict=True)),
                'row': index,
                'item_code': row[0],
                'item_name': row[7],
                'material_action': '需修改',
                **resolved.get(index, {}),
                'validation_error': issues.get(index, ''),
            }
            for index, row in enumerate(records, 2)
            if any(row)
        ]
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
        result = bom_import.preview(project, upload)
        keys = (
            ['item_code', 'assembly_unit', 'quantity', 'change_note', 'required_date', 'application_date', 'applicant']
            if headers in (bom_import.HEADERS, bom_import.PREVIOUS_HEADERS)
            else ['item_code', 'quantity', 'change_note', 'assembly_unit']
        )
        columns = list(zip(headers, keys[: len(headers)], strict=True))
        resolved = {line['row']: line for line in result['lines']}
        result['lines'] = [
            {**dict(zip(keys[: len(row)], row, strict=True)), 'row': index, **resolved.get(index, {})}
            for index, row in enumerate(records, 2)
            if any(value not in (None, '') for value in row)
        ]
        return feedback(result, headers, records, columns, 'BOM')
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
                lambda user, locked: resolve(user, locked, records, expected, collect_errors=True),
            )
            transaction.set_rollback(True)
    except ValidationError as exc:
        return {
            'can_import': False,
            'lines': [],
            'errors': [{'message': bom_import.message(exc.detail)}],
            'expected_revision': expected,
        }
    result['note'] = (
        '预览不占用编号；自编编号原样保留，留空才在确认时自动生成。型号不会自动补全或改写。物料与BOM整批保存，完全相同物料可复用；任一行失败全部撤销。'
    )
    for line in result['lines']:
        if line.get('new_material'):
            line['item_code'] = records[line['row'] - 2][0] or '确认时自动生成'
            line.pop('item', None)
    if result['can_import']:
        result['token'] = signing.dumps(
            {'actor': actor.pk, 'project': project.pk, 'revision': expected, 'records': records},
            salt=SALT,
            compress=True,
        )
    return feedback(
        result,
        headers,
        records,
        [(label, {'code': 'item_code', 'name': 'item_name'}.get(key, key)) for label, key in BOM_COLUMNS],
        'BOM',
    )


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
        # 与当前 BOM 完全一致的行不提交，不要求变更说明，也不写修订记录。
        changed = [
            {field: row.get(field) for field in fields}
            for row in result['lines']
            if row.get('bom_action') != 'unchanged'
        ]
        if not changed:
            # 只补填了品牌：物料主数据已在 resolve 里保存，BOM 本身没有修订。
            return {'id': locked.pk, 'revision': bom.revision(locked), 'lines': result['lines']}
        saved = bom.revise_bom(
            user,
            str(uuid.uuid4()),
            locked.pk,
            {'expected_revision': payload['revision'], 'lines': changed},
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
