"""apps.oa 模型的 post_save 信号处理器。

- VehicleRequest(用车申请)归还结算(RETURNED)且行程费合计 > 0 时自动登记统一待付款项
  台账(PayableItem),避免行程费(油费/过路/停车/其他)只停留在用车单据里、从不进入
  应付/核销流程。取消/驳回时作废对应台账项。

登记/作废失败均不冒泡(用 `_safe_sync_payable` 包裹),避免台账同步问题打断用车流程
本身;失败只记日志 + 通知财务管理员,真正的数据补齐留给人工核查或
`backfill_vehicle_request_payables` 管理命令兜底。

注意:本文件可能同时被其它并行改动(如资产/车辆维护相关信号)扩展,新增 receiver 时
请勿相互覆盖——每个 receiver 只关注自己的 sender,互不干扰。
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.oa.vehicle import VehicleRequest

logger = logging.getLogger(__name__)


@receiver(post_save, sender=VehicleRequest)
def register_vehicle_request_payable(sender, instance, **kwargs):
    """用车归还结算(RETURNED)且行程费合计 > 0 → 登记台账;取消/驳回,或结算金额被
    修正为 0 → 台账项作废。

    VehicleRequestViewSet.return_vehicle() 在同一次 save() 里把 status 置为 RETURNED
    并一并写入 fuel_cost/toll_cost/parking_cost/other_cost,本信号触发时四项费用已是
    归还时的最终值,VehicleRequestPayableSource.to_payable 取 total_cost(四项之和)
    作为 amount_due。纯公务用车未产生任何费用(total_cost == 0,如公司代付油卡、无
    过路停车费)不构成应付事实,不登记,避免核销工作台里出现一堆金额为 0 的噪音候选;
    若此前已登记但费用被人工修正为 0,则作废该台账项(cancel_payable 内部已守卫仅
    amount_paid==0 时才允许作废,不会误伤已核销项)。

    CANCELLED/REJECTED:审批流程当前只在 PENDING 阶段触发 REJECTED(早于归还登记
    时点,不会有已登记项需要作废);CANCELLED 目前也无直接入口,一并处理是防御性
    写法,以防将来接入"取消已归还申请"之类的操作。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'RETURNED':
        if instance.total_cost and instance.total_cost > 0:
            _safe_sync_payable(register_payable, instance, 'vehicle_request', action='登记')
        else:
            _safe_sync_payable(cancel_payable, instance, 'vehicle_request', action='作废')
    elif instance.status in ('CANCELLED', 'REJECTED'):
        _safe_sync_payable(cancel_payable, instance, 'vehicle_request', action='作废')


def _safe_sync_payable(func, instance, source_type, *, action):
    """执行 register_payable/cancel_payable,失败时记日志 + 发系统通知给财务管理员,不冒泡。

    与 apps.finance.signals / apps.purchase.signals 里的同名函数逻辑一致(未跨 app
    复用私有辅助函数,各自保留一份简单实现,避免引入不必要的 app 间耦合)。成功时
    返回底层函数结果,失败返回 None。
    """
    try:
        return func(instance, source_type)
    except Exception:
        logger.exception(
            '%s(id=%s, status=%s)台账%s失败,需人工核查',
            source_type, instance.pk, getattr(instance, 'status', ''), action,
        )
        _notify_finance_admins_of_payable_sync_failure(instance, source_type, action)


def _notify_finance_admins_of_payable_sync_failure(instance, source_type, action):
    """台账登记/作废失败的兜底告警:创建系统通知给财务管理员(超管兜底)。"""
    try:
        from apps.accounts.models import User
        from apps.core.models import SystemNotification

        recipients = User.objects.filter(is_active=True, is_deleted=False, is_superuser=True)
        source_no = getattr(instance, 'request_no', None) or getattr(instance, 'pk', '')
        title = '待付款项台账同步失败'
        message = (
            f'{source_type} 单据 {source_no} (id={instance.pk}) 的待付款项台账{action}失败,'
            f'请人工核查。'
        )
        SystemNotification.objects.bulk_create(
            [SystemNotification(user=user, type='ERROR', title=title, message=message) for user in recipients]
        )
    except Exception:
        logger.exception('发送待付款项台账同步失败告警通知时出错(source_type=%s, id=%s)', source_type, instance.pk)
