"""apps.oa 模型的 post_save 信号处理器。

- AssetMaintenance(资产维修/保养):status 是处理进度机(PENDING/IN_PROGRESS/
  COMPLETED/CANCELLED,AssetMaintenanceViewSet.assign()/complete() 依赖它推进
  维修流程)。COMPLETED 且费用(cost)>0 才是"维修完成、费用确定"的确认应付事实,
  此时自动登记统一待付款项台账;COMPLETED 但 cost==0(保养/自行处理无实际支出)
  不登记空台账项,与 AssetMaintenancePayableSource(source_type='asset_maintenance')
  的取数口径一致。CANCELLED 作废对应台账项(cancel_payable 内部已守卫仅当
  amount_paid==0 时才允许作废,已核销过的台账项不会被误伤)。

- VehicleMaintenance(车辆维护记录):该模型无 status 字段、也无审批/撤销入口,
  维护记录一旦录入(cost>0)即是已发生费用的既成事实,创建/保存时即登记台账;
  没有可回收的"取消"状态,故无 cancel 分支。

登记/作废失败均不冒泡(用 `_safe_sync_payable` 包裹),避免台账同步问题打断
资产/车辆维护的保存事务;失败只记日志 + 通知财务管理员，真正的数据补齐留给
人工核查或 `backfill_oa_maintenance_payables` 管理命令兜底。
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.oa.asset import AssetMaintenance
from apps.oa.vehicle import VehicleMaintenance, VehicleRequest

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AssetMaintenance)
def register_asset_maintenance_payable(sender, instance, **kwargs):
    """维修完成(COMPLETED)且费用>0 → 登记台账;取消(CANCELLED)→ 台账项作废。"""
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'COMPLETED' and instance.cost and instance.cost > 0:
        _safe_sync_payable(register_payable, instance, 'asset_maintenance', action='登记')
    elif instance.status == 'CANCELLED':
        _safe_sync_payable(cancel_payable, instance, 'asset_maintenance', action='作废')


@receiver(post_save, sender=VehicleMaintenance)
def register_vehicle_maintenance_payable(sender, instance, **kwargs):
    """车辆维护记录一录入(cost>0)即视为已发生费用的确认应付,自动登记台账。

    该模型无 status 字段、无撤销/取消入口，因此无 cancel 分支——与
    VehicleMaintenancePayableSource(write_back no-op)的说明一致。
    """
    from apps.finance.payable_adapters import register_payable

    if instance.cost and instance.cost > 0:
        _safe_sync_payable(register_payable, instance, 'vehicle_maintenance', action='登记')


@receiver(post_save, sender=VehicleRequest)
def register_vehicle_request_payable(sender, instance, **kwargs):
    """用车归还结算(RETURNED)且行程费合计 > 0 → 登记台账;取消/驳回,或结算金额被
    修正为 0 → 台账项作废。

    VehicleRequestViewSet.return_vehicle() 在同一次 save() 里把 status 置为 RETURNED
    并一并写入 fuel_cost/toll_cost/parking_cost/other_cost,本信号触发时四项费用已是
    归还时的最终值,VehicleRequestPayableSource.to_payable 取 total_cost(四项之和)
    作为 amount_due。纯公务用车未产生任何费用(total_cost == 0)不构成应付事实,不
    登记,避免核销工作台里出现一堆金额为 0 的噪音候选;若此前已登记但费用被人工修正
    为 0,则作废该台账项。CANCELLED/REJECTED 一并作废(防御性,应对将来"取消已归还
    申请"之类入口)。
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
    复用私有辅助函数,各自保留一份简单实现,避免引入不必要的 app 间耦合)。
    成功时返回底层函数结果,失败返回 None。
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
        source_no = getattr(instance, 'maintenance_no', None) or getattr(instance, 'pk', '')
        title = 'OA维护台账同步失败'
        message = (
            f'{source_type} 单据 {source_no} (id={instance.pk}) 的待付款项台账{action}失败,'
            f'请人工核查。'
        )
        SystemNotification.objects.bulk_create(
            [SystemNotification(user=user, type='ERROR', title=title, message=message) for user in recipients]
        )
    except Exception:
        logger.exception('发送OA维护台账同步失败告警通知时出错(source_type=%s, id=%s)', source_type, instance.pk)
