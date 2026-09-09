import csv
import io
import re
import zipfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from rest_framework.exceptions import ValidationError

from ..models import BOMLine, Item
from .bom import incoming, issued, revision
from .common import number, state

MAX_BYTES = 5 * 1024 * 1024
HEADERS = ['物料编码', '数量', '变更说明']


def read_file(upload):
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
            result = read_xlsx(content)
        else:
            raise ValidationError({'file': '仅支持 UTF-8 CSV 或 XLSX。'})
    except (
        UnicodeDecodeError,
        csv.Error,
        zipfile.BadZipFile,
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
        EOFError,
    ) as exc:
        raise ValidationError({'file': '文件损坏、编码不正确或不是受支持的表格。'}) from exc
    if not result:
        raise ValidationError({'file': '表格不能为空。'})
    header = [str(value).strip() if value is not None else '' for value in result[0]]
    while header and not header[-1]:
        header.pop()
    if header != HEADERS:
        raise ValidationError({'file': '表头必须依次为：物料编码、数量、变更说明。'})
    if len(result) > 1001:
        raise ValidationError({'file': '一次最多导入 1000 行。'})
    return result[1:]


def read_xlsx(content):
    # Bound decompression and reject entity declarations before openpyxl sees XML.
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > 200 or sum(info.file_size for info in infos) > 20 * 1024 * 1024:
            raise ValidationError({'file': 'XLSX 解压后过大或包含过多部件。'})
        for info in infos:
            if info.filename.lower().endswith(('.xml', '.rels')):
                root = ElementTree.fromstring(
                    archive.read(info), forbid_dtd=True, forbid_entities=True, forbid_external=True
                )
                if info.filename.startswith('xl/worksheets/'):
                    for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                        if int(row.get('r', '0')) > 1001:
                            raise ValidationError({'file': '一次最多导入 1000 行，请移除表格末尾多余行。'})
                    for cell in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                        column = re.match(r'[A-Z]+', cell.get('r', ''))
                        if (
                            column
                            and column.group() not in {'A', 'B', 'C'}
                            and any(child.tag.rsplit('}', 1)[-1] in {'v', 'is', 'f'} for child in cell)
                        ):
                            raise ValidationError({'file': '表格只能包含三列。'})
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
    try:
        if len(workbook.worksheets) != 1:
            raise ValidationError({'file': '请保留一个工作表后再导入。'})
        sheet = workbook.worksheets[0]
        sheet.reset_dimensions()
        result = []
        for cells in sheet.iter_rows(max_row=1002, max_col=4):
            if any(cell.data_type == 'f' for cell in cells):
                raise ValidationError({'file': 'BOM 导入不接受公式，请粘贴为值后再导入。'})
            result.append([cell.value for cell in cells])
        while result and all(value in (None, '') for value in result[-1]):
            result.pop()
        return result
    finally:
        workbook.close()


def message(detail):
    if isinstance(detail, dict):
        return '；'.join(f'{key}：{message(value)}' for key, value in detail.items())
    if isinstance(detail, (list, tuple)):
        return '；'.join(message(value) for value in detail)
    return str(detail)


def preview(project, upload):
    state(project, {'draft', 'quoted', 'active', 'delivering'})
    expected_revision = revision(project)
    raw = read_file(upload)
    codes = {str(row[0]).strip() for row in raw if row and row[0] is not None}
    items = {item.code: item for item in Item.objects.filter(code__in=codes, is_active=True)}
    current = {line.item_id: line for line in BOMLine.objects.filter(project=project)}
    lines, errors, seen = [], [], set()
    for row_number, row in enumerate(raw, 2):
        if all(value in (None, '') for value in row):
            continue
        try:
            if len(row) > 3 and any(value not in (None, '') for value in row[3:]):
                raise ValidationError('表格只能包含三列。')
            values = list(row[:3]) + [''] * max(0, 3 - len(row))
            code = str(values[0] or '').strip()
            item = items.get(code)
            if item is None:
                raise ValidationError('物料编码不存在或已停用。')
            if code in seen:
                raise ValidationError('同一文件中的物料编码不能重复。')
            seen.add(code)
            qty = number(values[1], '数量', 3, positive=True)
            note = str(values[2] or '').strip()
            if len(note) > 500 or (item.pk in current and not note):
                raise ValidationError('修改已有 BOM 必须填写变更说明，且不超过 500 字符。')
            if qty < issued(project, item.pk) + incoming(project, item.pk):
                raise ValidationError('数量不能小于已领用和在途采购数量。')
            lines.append(
                {
                    'row': row_number,
                    'item': item.pk,
                    'item_code': code,
                    'item_name': item.name,
                    'quantity': str(qty),
                    'change_note': note,
                }
            )
        except ValidationError as exc:
            errors.append({'row': row_number, 'message': message(exc.detail)})
    if not lines and not errors:
        errors.append({'row': 2, 'message': '文件没有可导入的明细。'})
    return {
        'expected_revision': expected_revision,
        'lines': lines,
        'errors': errors,
        'can_import': bool(lines) and not errors,
    }
