"""Spreadsheet output from authorized API representations; never query around permissions."""

import csv
import io
import json
import re
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from rest_framework.exceptions import ValidationError

MAX_EXPORT = 20000
LABELS = {
    'payment_due_date': '付款到期日',
    'payment_term': '采购账期',
    'payment_days': '月结天数',
    'payment_schedule': '未结到期明细',
    'due_amount': '当前到期金额',
    'received_date': '实际合格收货日期',
    'next_delivery_date': '最近待到货日',
    'material_requirements': '交付配套快照',
    'evidence': '关联凭证记录',
    'pending_quantity': '隔离待处理数量',
    'original_contract_amount': '原签约金额',
    'method': '结算方式',
    'account': '账户标识',
    'reference': '银行流水号',
    'document': '凭证ID',
    'brand': '品牌',
    'part_type': '物料类别',
    'product_category': '产品编码类别',
    'drawing_number': '图号',
    'drawing_revision': '图档版本',
    'required_date': '需求日期',
    'application_date': '申请日期',
    'applicant': '申请人',
    'assembly_unit': '单元',
    'id': '记录ID',
    'code': '编号',
    'name': '名称',
    'status': '状态',
    'kind': '类型',
    'project': '项目ID',
    'project_name': '项目名称',
    'project_code': '项目编号',
    'customer': '客户ID',
    'customer_name': '客户名称',
    'supplier': '供应商ID',
    'supplier_name': '供应商名称',
    'manager': '负责人',
    'manager_name': '负责人姓名',
    'item': '物料ID',
    'item_code': '物料编码',
    'item_name': '物料名称',
    'unit': '单位',
    'specification': '规格',
    'quantity': '数量',
    'location': '库位',
    'amount': '金额',
    'unit_price': '含税单价',
    'unit_cost': '单位成本',
    'value': '库存金额',
    'due_date': '到期日',
    'date': '日期',
    'title': '标题',
    'note': '说明',
    'reason': '原因',
    'is_active': '启用',
    'contact': '联系人',
    'phone': '电话',
    'address': '地址',
    'created_at': '创建时间',
    'updated_at': '更新时间',
    'requirements': '需求说明',
    'equipment_quantity': '设备数量',
    'warranty_months': '质保月数',
    'members': '成员ID',
    'quote_amount': '报价金额',
    'contract_amount': '合同金额',
    'contract_date': '签约日期',
    'contract_number': '合同编号',
    'actual_cost': '实际成本',
    'committed_cost': '在途采购',
    'budget': '预算',
    'occupied_cost': '实际与在途',
    'warnings': '提示',
    'receivable': '待收款',
    'payable': '待付款',
    'overdue_receivable': '逾期待收款',
    'overdue_payable': '逾期待付款',
    'refund_out': '待退客户款',
    'refund_in': '待收退款',
    'over_budget': '超预算',
    'overdue': '交付逾期',
    'unbudgeted': '未设置预算',
    'lines': '明细',
    'balance': '余额',
    'paid': '已付或已收',
    'credit_amount': '抵减金额',
    'task': '任务ID',
    'task_title': '任务',
    'user': '用户ID',
    'user_name': '用户姓名',
    'hours': '工时',
    'assignee': '执行人ID',
    'assignee_name': '执行人',
    'shipped_date': '发货日期',
    'accepted_date': '验收日期',
    'warranty_until': '质保截止',
    'line_id': '明细ID',
    'received_quantity': '已收数量',
    'cancelled_quantity': '已取消数量',
    'returned_quantity': '已退数量',
    'bom_line': 'BOM行ID',
    'record_type': '行类型',
}


# 纯数字（含负号）不是公式，不需要防注入前缀；其余以 = + - @ 开头的文本仍按公式风险转义。
NUMBER = re.compile(r'-?\d{1,18}(\.\d{1,6})?')
# xlsx 里按数值写入的金额和数量列。编码、账号、流水号即使全是数字也保持文本，避免丢前导零或变成科学计数。
NUMERIC_KEYS = {
    'amount',
    'approved_amount',
    'actual_cost',
    'balance',
    'budget',
    'cancelled_quantity',
    'cash_amount',
    'committed_cost',
    'contract_amount',
    'cost',
    'counterparty_balance',
    'credit_amount',
    'difference',
    'due_amount',
    'equipment_quantity',
    'fee',
    'hourly_cost',
    'hours',
    'occupied_cost',
    'original_contract_amount',
    'overdue_payable',
    'overdue_receivable',
    'paid',
    'paid_amount',
    'payable',
    'pending_quantity',
    'quantity',
    'quote_amount',
    'receivable',
    'received_quantity',
    'refund_in',
    'refund_out',
    'remaining_amount',
    'returned_quantity',
    'size',
    'supplier_credit',
    'unit_cost',
    'unit_price',
    'value',
    'warranty_months',
}


def cell(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    elif isinstance(value, bool):
        value = '是' if value else '否'
    else:
        value = str(value)
    if NUMBER.fullmatch(value):
        return value
    # Prevent spreadsheet formula execution, including leading whitespace/control characters.
    if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        value = "'" + value
    return value


def spreadsheet_number(value):
    """金额、数量列写成数值便于求和；Excel 只有 15 位有效数字，超出的仍存文本，不损失精度。"""
    if not NUMBER.fullmatch(value) or len(value.lstrip('-').replace('.', '').lstrip('0')) > 15:
        return value
    return Decimal(value)


def document(name, headers, rows, file_format='csv', numeric=()):
    if file_format not in {'csv', 'xlsx'}:
        raise ValidationError({'file_format': '请选择 csv 或 xlsx。'})
    if len(rows) > MAX_EXPORT:
        raise ValidationError(f'一次最多导出 {MAX_EXPORT} 条，请缩小筛选范围。')
    if file_format == 'csv':
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows([[cell(v) for v in row] for row in rows])
        content = ('\ufeff' + output.getvalue()).encode('utf-8')
        content_type = 'text/csv; charset=utf-8'
    else:
        book = Workbook(write_only=True)
        sheet = book.create_sheet('数据')
        sheet.append(headers)
        for row in rows:
            values = [cell(v) for v in row]
            sheet.append(
                [spreadsheet_number(value) if index in numeric else value for index, value in enumerate(values)]
            )
        output = io.BytesIO()
        book.save(output)
        content = output.getvalue()
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{name}.{file_format}"'
    response['Cache-Control'] = 'no-store'
    return response


def export_rows(name, rows, file_format='csv', fields=None):
    flattened = []
    for row in rows:
        if isinstance(row.get('lines'), list):
            parent = {key: value for key, value in row.items() if key != 'lines'}
            flattened.extend(
                {**parent, **{('line_id' if key == 'id' else key): value for key, value in line.items()}}
                for line in row['lines'] or [{}]
            )
        else:
            flattened.append(row)
    rows = flattened
    keys = list(dict.fromkeys(key for row in rows for key in row)) if rows else list(fields or [])
    return document(
        name,
        [LABELS.get(key, key) for key in keys],
        [[row.get(key) for key in keys] for row in rows],
        file_format,
        numeric={index for index, key in enumerate(keys) if key in NUMERIC_KEYS},
    )
