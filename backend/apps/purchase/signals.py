"""
采购模块信号处理
Purchase Module Signals

处理采购订单确认、收货等事件时的BOM状态同步
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderLine
from .contract_execution import PaymentRecord

logger = logging.getLogger(__name__)


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
    """合同付款审批通过 → 登记待付款项台账;取消/撤回(PENDING)→ 台账项作废;撤回后重新审批 → 复活。

    覆盖三条审批到达路径(直接 approve / submit 自动通过 / 工作流引擎完成),
    因它们最终都经 PaymentRecord.save() 落状态。register_payable/cancel_payable
    惰性 import,避免 app 加载期与 finance 的循环依赖。

    这两次调用都包一层 try/except:当审批经工作流引擎完成时,
    apps.core.workflow.services._on_workflow_complete 的外层 try/except 会把
    这里抛出的异常吞掉、仅 logger.error,导致 PaymentRecord 已 APPROVED 但台账项
    静默缺失、且无人知晓。这里捕获异常后只做"记录 + 告知财务管理员",绝不
    re-raise——否则会把 PaymentRecord.save() 事务一并回滚,让已批准的付款单
    连状态都保存不了,比台账缺失更糟。真正的数据补齐由每日 backfill 定时任务兜底
    (见 apps.finance.tasks.backfill_payables_safety_net)。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'APPROVED':
        item = _safe_sync_payable(register_payable, instance, 'contract_payment', action='登记')
        # 撤回后重新审批通过:register_payable 的 update_or_create 不含 status,不会把撤回时
        # 置为 CANCELLED 的台账项复活,这里显式置回 PENDING(与 item5 撤回回收配套)。
        if item is not None and item.status == item.STATUS_CANCELLED and item.amount_paid == 0:
            item.status = item.STATUS_PENDING
            item.recalc_status()
            item.save(update_fields=['status', 'updated_at'])
    elif instance.status == 'CANCELLED':
        _safe_sync_payable(cancel_payable, instance, 'contract_payment', action='作废')
    elif instance.status == 'PENDING':
        # 工作流"撤回"把 PaymentRecord 打回 PENDING:回收已登记且未核销的台账项,避免误核销。
        # cancel_payable 对"新建未登记"与"已核销"场景均为安全 no-op。
        _safe_sync_payable(cancel_payable, instance, 'contract_payment', action='撤回作废')


def _safe_sync_payable(func, instance, source_type, *, action):
    """执行 register_payable/cancel_payable,失败时记日志 + 发系统通知给财务管理员,不冒泡。

    成功时返回底层函数结果(register_payable 返回 PayableItem,供撤回后复活判断);失败返回 None。"""
    try:
        return func(instance, source_type)
    except Exception:
        logger.exception(
            '合同付款 %s 台账%s失败(payment_id=%s, status=%s),需人工核查或等待定时兜底任务',
            getattr(instance, 'payment_no', instance.pk),
            action,
            instance.pk,
            instance.status,
        )
        _notify_finance_admins_of_payable_sync_failure(instance, source_type, action)


def _notify_finance_admins_of_payable_sync_failure(instance, source_type, action):
    """台账登记/作废失败的兜底告警:创建系统通知给财务管理员(超管兜底)。"""
    try:
        from apps.accounts.models import User
        from apps.core.models import SystemNotification

        recipients = User.objects.filter(is_active=True, is_deleted=False, is_superuser=True)
        title = '合同付款台账同步失败'
        message = (
            f'合同付款单 {getattr(instance, "payment_no", instance.pk)} (id={instance.pk}, '
            f'status={instance.status}) 的待付款项台账{action}失败,请人工核查并按需执行 '
            f'backfill_contract_payables 命令补齐。'
        )
        SystemNotification.objects.bulk_create(
            [SystemNotification(user=user, type='ERROR', title=title, message=message) for user in recipients]
        )
    except Exception:
        # 告警通道本身失败也不能影响主流程,只记日志。
        logger.exception('发送合同付款台账同步失败告警通知时出错(payment_id=%s)', instance.pk)
