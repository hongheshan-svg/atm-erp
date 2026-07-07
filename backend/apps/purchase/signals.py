"""
采购模块信号处理
Purchase Module Signals

处理采购订单确认、收货等事件时的BOM状态同步
"""

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from .contract_execution import PaymentRecord


@receiver(post_save, sender=PurchaseOrder)
def sync_bom_on_po_confirm(sender, instance, **kwargs):
    """
    采购订单确认时同步更新关联的BOM状态
    """
    # 只在状态变为CONFIRMED时触发
    if instance.status != 'CONFIRMED':
        return

    # 检查是否有BOM关联的行项
    bom_lines = instance.lines.filter(bom_item__isnull=False)
    if not bom_lines.exists():
        return

    with transaction.atomic():
        for line in bom_lines.select_related('bom_item'):
            bom = line.bom_item

            # 更新BOM的采购状态
            bom.ordered_qty = (bom.ordered_qty or 0) + line.qty
            bom.purchase_order = instance
            bom.supplier = instance.supplier
            bom.delivery_date = instance.delivery_date

            # 更新下单状态
            if bom.ordered_qty >= bom.planned_qty:
                bom.order_status = 'ORDERED'
            else:
                bom.order_status = 'PARTIAL'

            bom.save(
                update_fields=[
                    'ordered_qty',
                    'purchase_order',
                    'supplier',
                    'delivery_date',
                    'order_status',
                    'updated_at',
                ]
            )


@receiver(post_save, sender=GoodsReceipt)
def sync_bom_on_receipt(sender, instance, **kwargs):
    """
    收货单确认时同步更新关联的BOM状态
    """
    # 只处理已确认的收货单
    if instance.status != 'CONFIRMED':
        return

    with transaction.atomic():
        for line in instance.lines.select_related('po_line__bom_item'):
            po_line = line.po_line
            if not po_line or not po_line.bom_item:
                continue

            bom = po_line.bom_item

            # 更新已收货数量
            bom.received_qty = (bom.received_qty or 0) + line.received_qty

            # 更新实际到货日期
            bom.actual_delivery_date = instance.receipt_date

            # 更新实际成本(如果有)
            if line.po_line and line.po_line.unit_price:
                bom.actual_cost = line.po_line.unit_price
                bom.total_cost = bom.actual_cost * bom.actual_qty

            # 更新下单状态
            if bom.received_qty >= bom.planned_qty:
                bom.order_status = 'RECEIVED'
            elif bom.received_qty > 0:
                bom.order_status = 'IN_TRANSIT'

            bom.save(
                update_fields=[
                    'received_qty',
                    'actual_delivery_date',
                    'actual_cost',
                    'total_cost',
                    'order_status',
                    'updated_at',
                ]
            )


@receiver(pre_save, sender=PurchaseOrderLine)
def inherit_bom_properties(sender, instance, **kwargs):
    """
    创建采购订单行时从BOM继承属性
    """
    if instance.bom_item and not instance.pk:
        bom = instance.bom_item

        # 继承关键件/长周期件标识
        if not instance.is_critical:
            instance.is_critical = bom.is_critical
        if not instance.is_long_lead:
            instance.is_long_lead = bom.is_long_lead

        # 继承功能模块
        if not instance.function_module:
            instance.function_module = bom.function_module or ''

        # 继承图纸号
        if not instance.drawing_no:
            instance.drawing_no = bom.drawing_no or ''

        # 继承技术要求
        if not instance.technical_requirement:
            instance.technical_requirement = bom.technical_requirement or ''


@receiver(post_save, sender=PaymentRecord)
def register_contract_payment_payable(sender, instance, **kwargs):
    """合同付款审批通过 → 登记待付款项台账;取消/撤回 → 台账项作废;重新审批 → 复活。

    覆盖三条审批到达路径(直接 approve / submit 自动通过 / 工作流引擎完成),
    因它们最终都经 PaymentRecord.save() 落状态。register_payable/cancel_payable
    惰性 import,避免 app 加载期与 finance 的循环依赖。

    工作流"撤回"会把 PaymentRecord 从 APPROVED 打回 PENDING(见
    core/workflow/services.py _on_workflow_complete 的 PAYMENT_RECORD/WITHDRAWN 分支),
    而 PENDING 同时也是"新建未提交"的初始态。若不处理,撤回后已登记的台账项会
    继续留在核销候选池里,可能被误核销。这里对 PENDING 也调用 cancel_payable——
    它按 source_type+source_id 查找台账项,查无(新建场景,尚未登记)或已核销
    (amount_paid>0,不应被撤销)时都是 no-op,只有"已登记且未核销"才会被置
    CANCELLED,所以对新建流程和已核销流程都是安全的。

    若撤回后又重新审批通过(状态再次落到 APPROVED),register_payable 的
    update_or_create 的 defaults 不含 status(见 payable_adapters.py 顶部的不变量
    注释,故意不覆盖核销进度字段),不会自动把上面撤回时置为 CANCELLED 的台账项
    复活为待付。因此这里显式处理:register_payable 之后若发现台账项状态仍是
    CANCELLED 且尚未核销,说明是"撤回后重新审批通过"场景,手工置回 PENDING 再
    recalc_status() 校正(保持与其它状态推导路径一致)。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'APPROVED':
        item = register_payable(instance, 'contract_payment')
        if item.status == item.STATUS_CANCELLED and item.amount_paid == 0:
            item.status = item.STATUS_PENDING
            item.recalc_status()
            item.save(update_fields=['status', 'updated_at'])
    elif instance.status == 'CANCELLED':
        cancel_payable(instance, 'contract_payment')
    elif instance.status == 'PENDING':
        cancel_payable(instance, 'contract_payment')
