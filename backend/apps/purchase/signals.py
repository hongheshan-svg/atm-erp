"""
采购模块信号处理
Purchase Module Signals

处理采购订单确认、收货等事件时的BOM状态同步
"""
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine


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

            bom.save(update_fields=[
                'ordered_qty', 'purchase_order', 'supplier',
                'delivery_date', 'order_status', 'updated_at'
            ])


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

            bom.save(update_fields=[
                'received_qty', 'actual_delivery_date',
                'actual_cost', 'total_cost', 'order_status', 'updated_at'
            ])


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
