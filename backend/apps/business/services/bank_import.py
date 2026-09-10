"""Bank-native imports: retain evidence, preview without writes, atomic deduplicated confirmation."""

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import xlrd
from django.core import signing
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core.actions import perform
from apps.core.permissions import FINANCE, require_role

from ..models import BankRecord
from . import banking
from .bom_import import MAX_BYTES, read_xlsx
from .common import audit, save

ICBC = [
    '凭证号',
    '对方账号',
    '交易时间',
    '借贷标志',
    '对方单位',
    '对方行号',
    '用途',
    '摘要',
    '附言',
    '回单个性化信息',
    '转入金额',
    '转出金额',
    '支付凭证种类',
    '余额',
]
HXB = [
    '序号',
    '交易日期',
    '交易时间',
    '支出金额',
    '收入金额',
    '余额',
    '对方账号',
    '对方户名',
    '对方行名',
    '核心流水号',
    '交易描述',
    '摘要',
    '凭证号码',
    '明细标注',
    '记账日期',
]
UNKNOWN = '原流水未提供户名（待核实）'


def string(value):
    return '' if value is None else str(value).strip()


def amount(value):
    raw = string(value).replace(',', '') or '0'
    try:
        result = Decimal(raw)
        if not result.is_finite() or abs(result) >= Decimal('1e16') or result != result.quantize(Decimal('.01')):
            raise ValueError
        return result.quantize(Decimal('.01'))
    except (ValueError, InvalidOperation) as exc:
        raise ValidationError('金额须为有效数字，最多两位小数。') from exc


def read(upload):
    if upload is None or not hasattr(upload, 'read'):
        raise ValidationError('请选择工行 XLSX 或华夏 XLS 原始流水。')
    content = upload.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise ValidationError('文件不能为空且不能超过 5 MB。')
    try:
        suffix = Path(upload.name).suffix.lower()
        if suffix == '.xlsx':
            rows = read_xlsx(content, 15)
        elif suffix == '.xls':
            book = xlrd.open_workbook(file_contents=content, on_demand=True)
            try:
                if book.nsheets != 1:
                    raise ValidationError('请保留一个工作表。')
                sheet = book.sheet_by_index(0)
                if sheet.nrows > 1000 or sheet.ncols > 15:
                    raise ValidationError('表格最多 1000 行、15 列。')
                rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            finally:
                book.release_resources()
        else:
            raise ValidationError('仅支持 XLSX / XLS 原始银行流水。')
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError('表格损坏、加密或格式不支持，请重新导出。') from exc
    rows = [(row + [''] * 15)[:15] for row in rows]
    return content, rows


def existing(record, *, lock=False):
    data = record['data']
    queryset = BankRecord.objects.select_for_update() if lock else BankRecord.objects.all()
    found = queryset.filter(import_fingerprint=record['fingerprint']).first()
    if not found:
        found = queryset.filter(
            account=data['account'], reference__in=[data['reference'], record['legacy_reference']], void_reason=''
        ).first()
    if found:
        # Do not silently skip a reference collision with different money or ownership.
        expected = ['account', 'amount', 'date']
        if any(str(getattr(found, field)) != data[field] for field in expected):
            raise ValidationError(f'第 {record["row"]} 行：已有相同标识但日期或金额不同，请核对原记录。')
        if not found.import_fingerprint and found.counterparty != data['counterparty']:
            raise ValidationError(f'第 {record["row"]} 行：已有记录户名不同，请先核实。')
        if found.import_fingerprint and found.import_fingerprint != record['fingerprint']:
            raise ValidationError(f'第 {record["row"]} 行：银行流水号重复但原始内容不同。')
    return found


def parse(upload):
    content, rows = read(upload)
    sha = hashlib.sha256(content).hexdigest()
    headers = [[string(v) for v in row] for row in rows]
    if len(rows) > 2 and headers[1][:14] == ICBC:
        bank, start = 'ICBC', 2
        accounts = {a for row in rows[start:] for a in re.findall(r'业务发生账号[:：]\s*(\d+)', string(row[9]))}
        if len(accounts) != 1:
            raise ValidationError('无法唯一识别工行本方账号，请使用含业务发生账号的完整原始流水。')
        account = accounts.pop()
    elif len(rows) > 8 and headers[7] == HXB:
        bank, start = 'HXB', 8
        account = string(rows[0][1])
        if not re.fullmatch(r'\d{6,40}', account) or rows[1][1] != '人民币':
            raise ValidationError('华夏账号或币种不支持；仅支持人民币。')
    else:
        raise ValidationError('未识别工行或华夏原始表头，请勿删除标题、汇总或调整列顺序。')
    records, errors, fingerprints = [], [], set()
    income = expense = Decimal('0.00')
    income_count = expense_count = 0
    for index, row in enumerate(rows[start:], start + 1):
        if not any(string(v) for v in row):
            continue
        try:
            incoming, outgoing = (
                (amount(row[10]), amount(row[11])) if bank == 'ICBC' else (amount(row[4]), amount(row[3]))
            )
            if min(incoming, outgoing) < 0 or bool(incoming) == bool(outgoing):
                raise ValidationError('收入和支出必须恰有一项为正数。')
            value = incoming - outgoing
            stamp = string(row[2]) if bank == 'ICBC' else f'{string(row[1])} {string(row[2])}'
            parsed_date = datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S')
            name = string(row[4] if bank == 'ICBC' else row[7])
            original = string(row[0] if bank == 'ICBC' else row[9])
            balance = amount(row[13] if bank == 'ICBC' else row[5])
            if not string(row[13] if bank == 'ICBC' else row[5]):
                raise ValidationError('缺少银行余额，无法可靠识别重复流水。')
            source = dict(
                bank=bank,
                file=Path(upload.name).name,
                file_sha256=sha,
                row=index,
                timestamp=stamp,
                original_reference=original,
                counterparty=name,
                counterparty_account=string(row[1] if bank == 'ICBC' else row[6]),
                balance=str(balance),
                raw=[string(v) for v in row],
            )
            identity = [bank, account, stamp, str(value), str(balance), source['counterparty_account'], original]
            fingerprint = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
            if fingerprint in fingerprints:
                raise ValidationError('文件内有完全重复的交易，请核实银行原文件后重试。')
            fingerprints.add(fingerprint)
            if bank == 'ICBC' and string(row[3]) != ('贷' if value > 0 else '借'):
                raise ValidationError('借贷标志与收入/支出金额不一致。')
            detail = '；'.join(string(row[i]) for i in ([6, 7, 8] if bank == 'ICBC' else [10, 11]))
            reference = (
                f'IMPORT-{bank}-{fingerprint[:40]}'
                if bank == 'ICBC' or not original
                else f'{parsed_date.date()}:{original}'
            )
            data = dict(
                account=account,
                amount=str(value),
                date=parsed_date.date().isoformat(),
                reference=reference,
                counterparty=name or UNKNOWN,
                reason=f'银行导入：{source["file"]}第{index}行；{detail}',
            )
            for field, limit in [('account', 100), ('reference', 100), ('counterparty', 150), ('reason', 500)]:
                if len(data[field]) > limit:
                    raise ValidationError(f'{field} 超过 {limit} 字符，请核实，系统不会截断原数据。')
            record = dict(
                row=index,
                data=data,
                source=source,
                fingerprint=fingerprint,
                needs_review=not name,
                legacy_reference=f'IMPORT-ICBC-{sha[:16]}-{index}' if bank == 'ICBC' else reference,
            )
            prior = existing(record)
            record['status'] = '已导入（跳过）' if prior else '待核实户名' if not name else '可导入'
            records.append(record)
            income += incoming
            expense += outgoing
            income_count += int(incoming > 0)
            expense_count += int(outgoing > 0)
        except (ValidationError, ValueError) as exc:
            errors.append({'row': index, 'message': str(getattr(exc, 'detail', exc))})
    if not records and not errors:
        errors.append({'row': 0, 'message': '没有交易明细。'})
    summary = dict(
        income=str(income),
        expense=str(expense),
        income_count=income_count,
        expense_count=expense_count,
        check='原文件无独立汇总，仅逐笔汇总；不代表银行余额勾稽已通过。',
    )
    if bank == 'HXB':
        try:
            if (amount(rows[5][1]), amount(rows[6][1]), int(rows[5][3]), int(rows[6][3])) != (
                income,
                expense,
                income_count,
                expense_count,
            ):
                raise ValueError
            summary['check'] = '收入、支出总额和笔数与银行表头汇总一致。'
        except (ValidationError, ValueError, TypeError):
            errors.append({'row': 6, 'message': '明细与银行表头汇总不一致，整批禁止导入。'})
    return records, errors, summary


def preview(actor, upload):
    require_role(actor, FINANCE)
    records, errors, summary = parse(upload)
    token = (
        signing.dumps({'actor': actor.pk, 'records': records, 'nonce': str(uuid4())}, salt='bank-import', compress=True)
        if not errors
        else None
    )
    columns = [
        {'key': key, 'label': label}
        for key, label in [
            ('date', '银行日期'),
            ('account', '账户'),
            ('reference', '流水号 / 导入标识'),
            ('counterparty', '对方户名'),
            ('amount', '收入 / 支出'),
            ('reason', '说明'),
        ]
    ]
    return dict(
        rows=records,
        columns=columns,
        row_count=len(records),
        count=len(records),
        errors=errors,
        summary=summary,
        can_import=not errors,
        token=token,
    )


def confirm(actor, token):
    require_role(actor, FINANCE)
    if not isinstance(token, str) or len(token) > 10 * 1024 * 1024:
        raise ValidationError('请重新预览文件。')
    try:
        batch = signing.loads(token, salt='bank-import', max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError('预览已过期或被修改，请重新上传。') from exc
    if batch['actor'] != actor.pk:
        raise ValidationError('预览不属于当前用户。')

    def execute(user):
        # Serialize imports across users/files; fingerprints also have a DB unique constraint.
        with transaction.get_connection().cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [731960911])
        created = skipped = 0
        for record in batch['records']:
            found = existing(record, lock=True)
            if found:
                if not found.import_fingerprint:
                    found.import_fingerprint = record['fingerprint']
                    found.source = record['source']
                    found.needs_review = record['needs_review']
                    save(found, user)
                    audit(user, 'bank.import-evidence', found)
                skipped += 1
                continue
            result = banking.create(user, 'bank-import:' + record['fingerprint'], record['data'])
            bank = BankRecord.objects.get(pk=result['id'])
            bank.import_fingerprint = record['fingerprint']
            bank.source = record['source']
            bank.needs_review = record['needs_review']
            save(bank, user)
            audit(user, 'bank.import-evidence', bank)
            created += 1
        return dict(count=created, skipped=skipped)

    return perform(
        actor=actor,
        key='bank-import-batch:' + batch['nonce'],
        operation='bank.import',
        payload=batch,
        authorize=lambda user: require_role(user, FINANCE),
        execute=execute,
    )
