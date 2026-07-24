"""
采购三单匹配 (Three-Way Match) 服务：PO — 收货 — 发票/应付。

审计缺口整改：AP 在订单确认时按 PO 全额挂账，缺少"已收货物才可结算/付款"的
三单匹配校验，存在超付风险。本模块提供：

- three_way_match(po): 逐行比对 订购数量 vs 已收数量，并在单据级比对已挂账
  金额(应付) vs 已收货物价值，输出每行 status(matched/over_received) 与单据级
  over_invoiced 标记及 ok 布尔。
- assert_can_pay(po, amount): 付款/挂账门禁——拟结算金额超过已收货物可结算价值
  时抛 ValidationError，用于阻断超付。

发票→PO 关联说明：
- 系统内采购发票以两种方式关联 PO：finance.AccountPayable.po(应付挂账，含税
  金额)、finance.Invoice(reference_type='PURCHASE_ORDER', reference_id=po.id，
  进项发票登记)。二者均为"单据/金额级"关联，未维护到 po_line 的逐行开票数量，
  故发票腿按"单据级金额"匹配(over_invoiced)，而非逐行开票数量。
- 已收货物价值以 po_line 维护的净已收数量(received_qty，收货确认加、退货减)
  × 单价计算，税额按 PO 税率折算，以与应付/发票的含税口径一致。
"""

from decimal import Decimal

from rest_framework.exceptions import ValidationError

# 金额比较容差(分)
AMOUNT_EPS = Decimal('0.01')
QTY_EPS = Decimal('0.000001')


def _d(value):
    """安全转 Decimal。"""
    if value is None or value == '':
        return Decimal('0')
    return Decimal(str(value))


def _invoiced_amount_for_po(po):
    """该 PO 已挂账/已开票金额(含税)。

    取 finance.AccountPayable(未删除、未取消)的 amount_due 汇总作为权威"已挂账"额；
    读取 finance 仅用于聚合，不改动其数据。
    """
    try:
        from apps.finance.models import AccountPayable
    except Exception:
        return Decimal('0')

    total = Decimal('0')
    qs = AccountPayable.objects.filter(po=po, is_deleted=False).exclude(status='CANCELLED')
    for ap in qs.only('amount_due'):
        total += _d(ap.amount_due)
    return total


def three_way_match(po):
    """对单个采购订单执行三单匹配，返回结构化报告(dict)。

    返回字段：
    - po_id / po_no / tax_rate
    - ordered_amount / received_amount(均不含税)
    - received_amount_with_tax(已收货物含税可结算价值)
    - invoiced_amount(已挂账/开票含税金额)
    - over_invoiced(bool)：已挂账 > 已收含税价值
    - ok(bool)：无行超收 且 未超额挂账
    - lines: [{po_line_id, item_id, item_sku, ordered_qty, received_qty,
               unit_price, line_ordered_amount, line_received_amount, status}]
      其中 status ∈ {'matched', 'over_received'}。
    """
    tax_rate = _d(getattr(po, 'tax_rate', 0))

    ordered_amount = Decimal('0')
    received_amount = Decimal('0')
    line_reports = []
    any_over_received = False

    for line in po.lines.filter(is_deleted=False):
        ordered_qty = _d(line.qty)
        received_qty = _d(line.received_qty)
        unit_price = _d(line.unit_price)

        line_ordered_amount = ordered_qty * unit_price
        line_received_amount = received_qty * unit_price
        ordered_amount += line_ordered_amount
        received_amount += line_received_amount

        if received_qty > ordered_qty + QTY_EPS:
            line_status = 'over_received'
            any_over_received = True
        else:
            line_status = 'matched'

        line_reports.append(
            {
                'po_line_id': line.id,
                'item_id': line.item_id,
                'item_sku': getattr(line.item, 'sku', ''),
                'ordered_qty': ordered_qty,
                'received_qty': received_qty,
                'unit_price': unit_price,
                'line_ordered_amount': line_ordered_amount,
                'line_received_amount': line_received_amount,
                'status': line_status,
            }
        )

    received_amount_with_tax = received_amount * (Decimal('1') + tax_rate / Decimal('100'))
    invoiced_amount = _invoiced_amount_for_po(po)
    over_invoiced = invoiced_amount > received_amount_with_tax + AMOUNT_EPS

    ok = (not any_over_received) and (not over_invoiced)

    return {
        'po_id': po.id,
        'po_no': po.order_no,
        'tax_rate': tax_rate,
        'ordered_amount': ordered_amount,
        'received_amount': received_amount,
        'received_amount_with_tax': received_amount_with_tax,
        'invoiced_amount': invoiced_amount,
        'over_invoiced': over_invoiced,
        'ok': ok,
        'lines': line_reports,
    }


def assert_can_pay(po, amount, tax_inclusive=True):
    """付款/挂账门禁：拟结算金额 amount 不得超过已收货物可结算价值。

    参数：
    - amount: 拟对该 PO 累计挂账/付款金额。
    - tax_inclusive: amount 是否含税(应付 amount_due 含税，默认 True)。

    超过已收价值(matched value)时抛 rest_framework ValidationError，用于在
    AP/付款路径上阻断超付。返回三单匹配报告以便调用方复用。
    """
    amount = _d(amount)
    report = three_way_match(po)
    ceiling = report['received_amount_with_tax'] if tax_inclusive else report['received_amount']

    if amount > ceiling + AMOUNT_EPS:
        raise ValidationError(
            f'超付拦截：采购订单 {report["po_no"]} 本次拟挂账/付款 {amount} '
            f'超过已收货物可结算金额 {ceiling}（三单匹配未通过）。请先完成收货或调整金额。'
        )
    return report
