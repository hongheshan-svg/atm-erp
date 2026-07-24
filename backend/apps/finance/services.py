"""财务模块事件驱动服务：发货 → 开票 → 应收 勾稽链路。

审计缺口修复：
- 发货完成不再是"只改单据状态"的死链，而是触发开票草稿的生成（结构化勾稽到 SO + 发货单）。
- '发货款' 付款节点由纯日期偏移改为事件驱动激活（发票开出/确认时把节点置为当天到期）。
- Invoice 与 SalesOrder / DeliveryOrder 建立外键勾稽，可双向反查、天然幂等。

设计约束（对齐仓库既有约定）：
- 金额一律 Decimal；发票号走 CodeRule 锁定计数行生成（``_generate_dated_sequence_no``）。
- 与 ``apps.sales.services.create_sales_order_receivables`` 协作：应收在 SO 确认时可能已建，
  这里只补建/回填，绝不重复创建。
- 幂等：同一发货单只生成一张开票草稿；重复调用直接返回既有发票。
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.finance.models import AccountReceivable, Invoice, InvoiceItem, PaymentSchedule


def _q2(value):
    """统一量化到 2 位小数（金额），输入保证为 Decimal。"""
    return (value or Decimal('0')).quantize(Decimal('0.01'))


def create_invoice_from_delivery(delivery, user):
    """发货单完成时，从其已发明细生成销项发票草稿并勾稽 SO + 发货单。

    幂等：若该发货单已存在未删除的发票，直接返回既有发票，不重复生成。

    金额口径与 SO 一致：明细金额 = 发货数量 × SO 明细单价（不含税），
    税额按 SO.tax_rate 计提，价税合计 = 不含税 + 税额，全程 Decimal。

    Returns: 生成或既有的 Invoice；无有效明细时返回 None。
    """
    from apps.finance.models import _generate_dated_sequence_no

    with transaction.atomic():
        # 幂等守卫：一张发货单只对应一张开票草稿
        existing = Invoice.objects.filter(delivery_order=delivery, is_deleted=False).first()
        if existing:
            return existing

        so = delivery.so
        tax_rate = Decimal(str(so.tax_rate or 0))

        lines = list(delivery.lines.filter(is_deleted=False).select_related('so_line', 'item'))
        if not lines:
            return None

        # 先汇总金额，再落库（total_amount 在 Invoice.save 里由不含税+税额兜底计算）
        amount_before_tax = Decimal('0')
        item_rows = []
        for idx, line in enumerate(lines, 1):
            unit_price = Decimal(str(line.so_line.unit_price or 0))
            qty = Decimal(str(line.qty or 0))
            line_amount = _q2(qty * unit_price)
            line_tax = _q2(line_amount * tax_rate / Decimal('100'))
            amount_before_tax += line_amount

            # 明细展示信息：优先物料主数据，非标产品回退 SO 明细的手填信息
            if line.item:
                item_name = line.item.name
                specification = line.item.specification or ''
                unit = line.item.get_unit_display()
            else:
                item_name = line.so_line.display_name
                specification = line.so_line.display_spec
                unit = line.so_line.custom_unit or ''

            item_rows.append({
                'line_no': idx,
                'item_name': item_name,
                'specification': specification,
                'unit': unit,
                'quantity': qty,
                'unit_price': unit_price,
                'amount': line_amount,
                'tax_rate': tax_rate,
                'tax_amount': line_tax,
            })

        amount_before_tax = _q2(amount_before_tax)
        tax_amount = _q2(amount_before_tax * tax_rate / Decimal('100'))
        total_amount = _q2(amount_before_tax + tax_amount)

        invoice = Invoice.objects.create(
            invoice_type='OUTPUT',  # 销项发票
            invoice_no=_generate_dated_sequence_no('INV', 'SALES_INVOICE', '销售发票号'),
            invoice_date=timezone.now(),
            party_name=so.customer.name,
            buyer_name=so.customer.name,
            buyer_tax_no=getattr(so.customer, 'tax_number', '') or '',
            amount_before_tax=amount_before_tax,
            tax_amount=tax_amount,
            total_amount=total_amount,
            reference_type='SALES_ORDER',
            reference_id=so.id,
            project=so.project,
            sales_order=so,
            delivery_order=delivery,
            status='REGISTERED',  # 既有初始状态（模型无 DRAFT 选项）
            notes=f'由发货单 {delivery.delivery_no} 自动生成',
            created_by=user,
        )

        for row in item_rows:
            InvoiceItem.objects.create(invoice=invoice, created_by=user, **row)

        return invoice


def ensure_ar_and_activate_milestone(invoice_or_delivery, user):
    """发票开出/确认时：确保 SO 应收账款反映本次开票，并事件驱动激活 '发货款' 节点。

    - 接受 Invoice 或 DeliveryOrder，二者都能解析出 SalesOrder。
    - 应收账款：若 SO 确认时 ``create_sales_order_receivables`` 已建，则回填发票号/发票日期，
      不重复创建；否则按发票金额补建一张（金额取 SO 含税总额，与既有口径一致）。
    - '发货款'（milestone_type='ON_DELIVERY'）节点：把 due_date 置为当天并挂接应收，
      以事件驱动激活替代纯日期偏移。防御式：无匹配节点则静默跳过。

    Returns: 关联/更新的 AccountReceivable（无法解析 SO 时返回 None）。
    """
    # 解析 SO 与可选的发票
    invoice = invoice_or_delivery if isinstance(invoice_or_delivery, Invoice) else None
    if invoice is not None:
        so = invoice.sales_order
    else:
        so = getattr(invoice_or_delivery, 'so', None)

    if so is None:
        return None

    today = timezone.now().date()

    with transaction.atomic():
        ar = AccountReceivable.objects.filter(so=so, is_deleted=False).select_for_update().first()
        if ar is None:
            # SO 确认路径未建应收时补建（金额优先取发票，否则 SO 含税总额）
            amount_due = None
            if invoice is not None and invoice.total_amount:
                amount_due = invoice.total_amount
            amount_due = amount_due or so.total_with_tax or so.total_amount
            ar = AccountReceivable.objects.create(
                customer=so.customer,
                so=so,
                project=so.project,
                invoice_no=invoice.invoice_no if invoice is not None else None,
                invoice_date=invoice.invoice_date.date() if invoice is not None else so.order_date,
                amount_due=amount_due,
                due_date=so.delivery_date,
                created_by=user,
            )
        elif invoice is not None and not ar.invoice_no:
            # 已存在应收：回填发票号（不动金额，避免与 SO 确认口径冲突）
            ar.invoice_no = invoice.invoice_no
            ar.save(update_fields=['invoice_no', 'updated_at'])

        # 事件驱动激活 '发货款' 节点（防御式：无则跳过）
        milestone = PaymentSchedule.objects.filter(
            sales_order=so, milestone_type='ON_DELIVERY', is_deleted=False,
        ).exclude(status__in=['PAID', 'CANCELLED']).order_by('milestone_order').first()
        if milestone is not None:
            update_fields = []
            if milestone.due_date != today:
                milestone.due_date = today
                update_fields.append('due_date')
            if milestone.account_receivable_id != ar.id:
                milestone.account_receivable = ar
                update_fields.append('account_receivable')
            if update_fields:
                update_fields.append('updated_at')
                milestone.save(update_fields=update_fields)

        return ar
