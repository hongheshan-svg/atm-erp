import csv
import io
import lzma
import re
import struct
import zipfile
import zlib
from datetime import date, datetime
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework.exceptions import ValidationError

from apps.core.error_messages import chinese_error

from ..models import BOMLine, Item
from .bom import (
    BOM_STATES,
    blank_unit_message,
    by_item,
    linked_incoming_by_line,
    revision,
    total_shortfalls,
    unit_conflict,
)
from .common import ZERO, day, number, state
from .import_guides import BOM_COLUMNS, GUIDE_MARKER, GUIDE_SHEET

MAX_BYTES = 5 * 1024 * 1024
LEGACY_HEADERS = ['物料编码', '数量', '变更说明', '单元']
PREVIOUS_HEADERS = ['物料编码', '单元', '需求数量', '变更说明']
HEADERS = PREVIOUS_HEADERS + ['需求日期', '申请日期', '申请人']
# 物料导入解析后交给预览的格式：多一列「替换原编码」，表示本行在原单元把该物料换版为本行物料。
REVISION_HEADERS = HEADERS + ['替换原编码']


def read_file(upload, headers=None, legacy_headers=None, *, return_headers=False):
    if headers is None:
        legacy_headers = [REVISION_HEADERS, PREVIOUS_HEADERS, LEGACY_HEADERS, LEGACY_HEADERS[:3]]
    headers = HEADERS if headers is None else headers
    if upload is None or not hasattr(upload, 'read'):
        raise ValidationError({'file': '请选择 CSV 或 XLSX 文件。'})
    content = upload.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise ValidationError({'file': '文件不能为空且不能超过 5 MB。'})
    extension = Path(upload.name).suffix.lower()
    try:
        if extension == '.csv':
            result = []
            for index, row in enumerate(csv.reader(io.StringIO(content.decode('utf-8-sig')), strict=True)):
                if index > 1000:
                    raise ValidationError({'file': '一次最多导入 1000 行。'})
                result.append(row)
        elif extension == '.xlsx':
            result = read_xlsx(content, max(len(headers), len(BOM_COLUMNS)))
        else:
            raise ValidationError({'file': '仅支持 UTF-8 CSV 或 XLSX。'})
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValidationError({'file': '文件损坏、编码不正确或不是受支持的表格。'}) from exc
    except (
        # XLSX 是 ZIP 包：部件压缩数据损坏、截断或加密时，解包会抛出这些底层异常。
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
        lzma.LZMAError,
        struct.error,
        EOFError,
        KeyError,
        ValueError,
        DefusedXmlException,
        ParseError,
        InvalidFileException,
        IndexError,
        TypeError,
        RuntimeError,
        NotImplementedError,
        OSError,
    ) as exc:
        raise ValidationError(
            {'file': '表格损坏、加密或格式不支持，请用 Excel 重新另存为 XLSX（不设密码）或下载模板后重新导入。'}
        ) from exc
    if not result:
        raise ValidationError({'file': '表格不能为空。'})
    header = [str(value).strip() if value is not None else '' for value in result[0]]
    while header and not header[-1]:
        header.pop()
    if (
        header != headers
        and header != legacy_headers
        and not (legacy_headers and isinstance(legacy_headers[0], list) and header in legacy_headers)
    ):
        from .import_feedback import template_hint

        hint = template_hint(header)
        if hint:
            raise ValidationError(
                {
                    'file': f'这是{hint["title"]}模板，请到{hint["title"]}导入入口。{hint["entry"]}。切换后请重新选择文件。',
                    'template_hint': hint,
                }
            )
        raise ValidationError(
            {
                'file': '这个文件的表头与当前导入入口不一致。请先确认要导入的是项目、项目任务还是BOM等资料；'
                '在对应入口重新下载模板，只把业务数据按列粘贴为值，保留新模板表头。表头必须依次为：'
                + '、'.join(headers)
                + '。'
            }
        )
    if len(result) > 1001:
        raise ValidationError({'file': '一次最多导入 1000 行。'})
    normalized = []
    for row in result[1:]:
        if any(value not in (None, '') for value in row[len(header) :]):
            raise ValidationError({'file': '数据列数不能超过表头。'})
        normalized.append(list(row[: len(header)]) + [''] * max(0, len(header) - len(row)))
    return (header, normalized) if return_headers else normalized


MAX_XLSX_EXPANDED = 20 * 1024 * 1024


def _read_zip_member_bounded(archive, info, remaining, *, keep=True):
    """按实际解压字节上限读取 ZIP 成员，防止伪造 ZipInfo.file_size 绕过解压大小限制。"""
    chunks, read_bytes = [], 0
    with archive.open(info) as stream:
        while True:
            cap = remaining - read_bytes
            chunk = stream.read(min(65536, cap + 1))
            if not chunk:
                break
            read_bytes += len(chunk)
            if read_bytes > remaining:
                raise ValidationError({'file': 'XLSX 解压后过大或包含过多部件。'})
            if keep:
                chunks.append(chunk)
    return (b''.join(chunks) if keep else b''), read_bytes


def read_xlsx(content, columns=3):
    # Bound actual decompression bytes and reject entity declarations before openpyxl sees XML.
    allowed = {get_column_letter(i) for i in range(1, columns + 1)}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > 200 or sum(info.file_size for info in infos) > MAX_XLSX_EXPANDED:
            raise ValidationError({'file': 'XLSX 解压后过大或包含过多部件。'})
        remaining = MAX_XLSX_EXPANDED
        for info in infos:
            is_xml = info.filename.lower().endswith(('.xml', '.rels'))
            raw, used = _read_zip_member_bounded(archive, info, remaining, keep=is_xml)
            remaining -= used
            if is_xml:
                root = ElementTree.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                if info.filename.startswith('xl/worksheets/'):
                    for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                        if int(row.get('r', '0')) > 1001:
                            raise ValidationError({'file': '一次最多导入 1000 行，请移除表格末尾多余行。'})
                    for cell in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                        column = re.match(r'[A-Z]+', cell.get('r', ''))
                        if (
                            column
                            and column.group() not in allowed
                            and any(child.tag.rsplit('}', 1)[-1] in {'v', 'is', 'f'} for child in cell)
                        ):
                            raise ValidationError({'file': f'表格只能包含{columns}列。'})
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
    try:
        if len(workbook.worksheets) == 1:
            sheet = workbook.worksheets[0]
        elif set(workbook.sheetnames) == {'数据', GUIDE_SHEET} and workbook[GUIDE_SHEET]['A1'].value == GUIDE_MARKER:
            sheet = workbook['数据']
        else:
            raise ValidationError({'file': '请只保留一个数据工作表；可附带系统模板自带的“填写说明”页。'})
        sheet.reset_dimensions()
        result = []
        for cells in sheet.iter_rows(max_row=1002, max_col=columns + 1):
            if any(cell.data_type == 'f' for cell in cells):
                raise ValidationError({'file': '导入不接受公式，请粘贴为值后再导入。'})
            result.append([cell.value for cell in cells])
        while result and all(value in (None, '') for value in result[-1]):
            result.pop()
        return result
    finally:
        workbook.close()


def message(detail, labels=None):
    labels = {key: label for label, key in BOM_COLUMNS} | (labels or {})
    if isinstance(detail, dict):
        return '；'.join(
            f'{labels.get(key, key)}：{message(value, labels)}'
            if key in labels or re.search(r'[\u4e00-\u9fff]', key)
            else message(value, labels)
            for key, value in detail.items()
        )
    if isinstance(detail, (list, tuple)):
        return '；'.join(message(value, labels) for value in detail)
    return str(chinese_error(detail))


def annotate_revisions(project, existing, effective):
    """预览提示：仍用旧版的行标出「该图已有新版」；换版行给出旧版在途怎么转、换版后旧版待处理大约多少。"""
    from .revision_chain import label, newer
    from .revisions import impact_rows, in_transit

    latest = newer([line['item'] for line in effective if line['bom_action'] in {'create', 'update'}])
    for line in effective:
        hint = latest.get(line['item'])
        if hint is None or line['bom_action'] not in {'create', 'update'}:
            continue
        line['newer_revision'] = hint
        line['revision_hint'] = (
            f'该图已有新版 {label(hint)}。确认仍用旧版可直接导入；要用新版请把物料编码改为 {hint["code"]}。'
            if line['bom_action'] == 'create'
            else f'该图已有新版 {label(hint)}，本行仍是旧版。要换成新版：「替换原编码」填本行编码，物料编码填 {hint["code"]}。'
        )
    replaced = {line.pk: line for line in existing}
    rows = [line for line in effective if line['bom_action'] == 'replace' and line['replaces_line'] in replaced]
    if not rows:
        return
    final = {(line.item_id, line.assembly_unit): line.quantity for line in existing}
    for line in effective:
        if line['bom_action'] in {'create', 'update', 'replace'}:
            final[(line['item'], line['assembly_unit'])] = number(line['quantity'], 'quantity', 3)
    for line in rows:
        old = replaced[line['replaces_line']]
        final.pop((old.item_id, old.assembly_unit), None)
    olds = {replaced[line['replaces_line']].item_id for line in rows}
    estimates = impact_rows(
        project, {pk: sum((qty for (item, _), qty in final.items() if item == pk), ZERO) for pk in olds}
    )
    for line in rows:
        old = replaced[line['replaces_line']]
        line['replace_impact'] = {'in_transit': in_transit(old), **estimates[old.item_id]}


def preview(project, upload):
    state(project, BOM_STATES)
    expected_revision = revision(project)
    headers, raw = read_file(upload, return_headers=True)
    if headers in (REVISION_HEADERS, HEADERS, PREVIOUS_HEADERS):
        raw = [[row[0], row[2], row[3], row[1], *row[4:]] for row in raw]
    codes = {str(row[0]).strip() for row in raw if row and row[0] is not None}
    items = {item.code: item for item in Item.objects.filter(code__in=codes, is_active=True)}
    existing = list(BOMLine.objects.filter(project=project).select_related('item'))
    grouped = by_item(existing)
    current = {(line.item_id, line.assembly_unit): line for line in existing}
    known = {line.assembly_unit for line in existing}
    # 换版的原物料可能已停用，按编码在项目现有 BOM 里找；{原 BOM 行: 换版所在行号}。
    old_items = {line.item.code: line.item for line in existing}
    replacing = {}
    lines, errors, primary = [], [], {}
    linked = None  # 各 BOM 行关联的未取消在途，首次修改已有行时一次读取。
    for row_number, row in enumerate(raw, 2):
        if all(value in (None, '') for value in row):
            continue
        try:
            values = list(row[:3]) + [''] * max(0, 3 - len(row))
            code = str(values[0] or '').strip()
            item = items.get(code)
            if item is None:
                raise ValidationError('物料编码不存在或已停用。')
            note = str(values[2] or '').strip()
            matching = grouped.get(item.pk, [])
            assembly_unit = (
                str(row[3] or '').strip() if len(row) > 3 else next((line.assembly_unit for line in matching), '')
            )
            if len(row) < 4 and len(matching) > 1:
                raise ValidationError('此物料分属多个单元，请使用含单元列的新模板。')
            if not assembly_unit and matching and all(line.assembly_unit for line in matching):
                # 留空单元会新增一条「未分单元」行，需求量虚增；已有用料的物料必须写明改哪个单元。
                raise ValidationError(blank_unit_message(matching))
            problem = unit_conflict(assembly_unit, known)
            if problem:
                raise ValidationError(problem)
            qty = number(values[1], '数量', 3, positive=True)
            details = {}
            if headers in (HEADERS, REVISION_HEADERS):
                for field, value in zip(('required_date', 'application_date'), row[4:6], strict=True):
                    if isinstance(value, datetime):
                        value = value.date().isoformat()
                    elif isinstance(value, date):
                        value = value.isoformat()
                    details[field] = day({field: value}, field, optional=True)
                    if details[field]:
                        details[field] = details[field].isoformat()
                details['applicant'] = str(row[6] or '').strip()
                if len(details['applicant']) > 80:
                    raise ValidationError('申请人不能超过80字符。')
            if len(assembly_unit) > 100:
                raise ValidationError('单元不能超过100字符。')
            if len(note) > 500:
                raise ValidationError('变更说明不能超过 500 字符。')
            replaced = None
            replaces = str(row[7] or '').strip() if headers == REVISION_HEADERS and len(row) > 7 else ''
            first = primary.get((item.pk, assembly_unit))
            if replaces:
                old = old_items.get(replaces)
                if old is None:
                    raise ValidationError(f'替换原编码 {replaces} 不在本项目 BOM 中，请从项目 BOM 复制原物料编码。')
                if old.pk == item.pk:
                    raise ValidationError('替换原编码与物料编码相同；只改数量请清空替换原编码。')
                replaced = current.get((old.pk, assembly_unit))
                if replaced is None:
                    raise ValidationError(
                        f'单元「{assembly_unit or "未分单元"}」没有原物料 {replaces}，无法换版；请核对单元和替换原编码。'
                    )
                if not note:
                    raise ValidationError('换版必须填写变更说明（如设计变更单号和原因）。')
            if first is not None and first.get('replaces_line') != (replaced.pk if replaced else None):
                raise ValidationError('同一单元同一物料的多行，替换原编码必须一致；请合并为一行。')
            if replaced is not None and first is None:
                if replaced.pk in replacing:
                    raise ValidationError(f'原物料 {replaces} 在本单元已由第 {replacing[replaced.pk]} 行换版。')
                if (item.pk, assembly_unit) in current:
                    raise ValidationError(
                        f'单元「{assembly_unit or "未分单元"}」已有物料 {code}，不能再换成它；请修改那一行的数量，并另行移除原物料。'
                    )
                replacing[replaced.pk] = row_number
            known.add(assembly_unit)
            line = {
                **details,
                'row': row_number,
                'item': item.pk,
                'item_code': code,
                'item_name': item.name,
                'brand': item.brand,
                'specification': item.specification,
                'drawing_number': item.drawing_number,
                'drawing_revision': item.drawing_revision,
                'product_category': item.product_category,
                'unit': item.unit,
                'part_type': item.part_type,
                'quantity': str(qty),
                'change_note': note,
                'assembly_unit': assembly_unit,
            }
            if replaced is not None:
                line |= {
                    'replaces': replaced.item.code,
                    'replaces_line': replaced.pk,
                    'replaces_name': replaced.item.name,
                    'replaces_revision': replaced.item.drawing_revision,
                }
            if first is None:
                primary[(item.pk, assembly_unit)] = line
            else:
                # 非标设备的设计 BOM 常按工位、气路逐处列料，同一物料在同一单元出现多次：数量并入首次出现的那行，
                # 预览逐行标明并入哪一行，由人核对是独立用量还是重复粘贴；申请信息与变更说明以先填写的为准。
                first['quantity'] = str(number(first['quantity'], '数量', 3) + qty)
                first.setdefault('merged_rows', []).append(row_number)
                for field in ('change_note', *details):
                    first[field] = first[field] or line[field]
                line |= {'bom_action': 'merged', 'merged_into': first['row'], 'before_quantity': None}
            lines.append(line)
        except ValidationError as exc:
            errors.append({'row': row_number, 'message': message(exc.detail)})
    # 合并完成后再按合计数量判断新增、修改或不变，校验变更说明与在途采购。
    replaced_keys = {
        (line.item_id, line.assembly_unit): replacing[line.pk] for line in existing if line.pk in replacing
    }
    for row_key, line in primary.items():
        existing_line = current.get(row_key)
        qty = number(line['quantity'], '数量', 3)
        action = 'create'
        if row_key in replaced_keys:
            # 原物料这一单元已由另一行换版，同时再修改它会互相覆盖。
            rows = [line['row'], *line.get('merged_rows', [])]
            errors.append(
                {
                    'row': line['row'],
                    'message': f'这一行的物料在本单元已由第 {replaced_keys[row_key]} 行换版，不能同时修改；请删除这一行。',
                }
            )
            lines = [entry for entry in lines if entry['row'] not in rows]
            continue
        if line.get('replaces_line'):
            line['bom_action'] = 'replace'
            line['before_quantity'] = str(next(old.quantity for old in existing if old.pk == line['replaces_line']))
            continue
        if existing_line is not None:
            same = qty == existing_line.quantity and all(
                str(getattr(existing_line, field) or '') == str(line.get(field) or '')
                for field in ('required_date', 'application_date', 'applicant')
                if field in line
            )
            # 从系统导出再回导时，没改的行原样跳过，不要求变更说明，也不写修订记录。
            action = 'unchanged' if same and line['change_note'] in ('', existing_line.change_note) else 'update'
        line['bom_action'] = action
        line['before_quantity'] = str(existing_line.quantity) if existing_line is not None else None
        problem = None
        if action == 'update' and not line['change_note']:
            problem = '修改已有 BOM 必须填写变更说明，且不超过 500 字符。'
        elif action == 'update':
            if linked is None:
                linked = linked_incoming_by_line([line.pk for line in existing])
            if qty < linked[existing_line.pk]:
                problem = '单元用量不能小于该行在途采购数量。'
        if problem:
            rows = [line['row'], *line.get('merged_rows', [])]
            errors.append({'row': line['row'], 'message': problem})
            lines = [entry for entry in lines if entry['row'] not in rows]
    errors.sort(key=lambda error: error['row'])
    effective = [line for line in lines if line['bom_action'] != 'merged']
    if not lines and not errors:
        errors.append({'row': 2, 'message': '文件没有可导入的明细。'})
    elif lines and not errors and all(line['bom_action'] == 'unchanged' for line in effective):
        errors.append({'message': '文件中的明细与当前 BOM 完全一致，没有需要导入的变化。', 'unchanged': True})
    updates = [
        (current.get((line['item'], line['assembly_unit'])), line['item'], number(line['quantity'], 'quantity', 3))
        for line in effective
        if line['bom_action'] != 'unchanged'
    ]
    first_row = {}
    for line in lines:
        first_row.setdefault(line['item'], line['row'])
    for problem in total_shortfalls(project, existing, updates):
        errors.append({'row': first_row[problem['item']], 'message': problem['message']})
    from .revisions import conversion_problems

    # 换版行：旧版在途按新图转为新版，新版各单元需求合计须覆盖新版已领、在途和转来的数量。
    replacements = [
        (line['replaces_line'], line['item'], line['row']) for line in effective if line['bom_action'] == 'replace'
    ]
    problems = conversion_problems(project, existing, updates, replacements)
    if problems:
        errors = sorted([*errors, *problems], key=lambda error: error.get('row', 0))
    annotate_revisions(project, existing, effective)
    listed = {(line['item'], line['assembly_unit']) for line in lines} | set(replaced_keys)
    # 导入只新增和修改，不会移除文件里没有的行；列出来，免得人以为上传整表就等于整批替换。
    untouched = [
        {
            'item_code': line.item.code,
            'item_name': line.item.name,
            'assembly_unit': line.assembly_unit,
            'quantity': str(line.quantity),
        }
        for line in sorted(existing, key=lambda line: (line.assembly_unit, line.item.code))
        if (line.item_id, line.assembly_unit) not in listed
    ]
    return {
        'expected_revision': expected_revision,
        'lines': lines,
        'errors': errors,
        'can_import': bool(lines) and not errors,
        'summary': {
            **{
                key: sum(line['bom_action'] == key for line in lines)
                for key in ('create', 'update', 'unchanged', 'merged', 'replace')
            },
            'untouched': len(untouched),
        },
        'untouched': untouched,
    }
