"""apps.projects 模型的 post_save 信号处理器。

- 现场服务费报销(ServiceExpense)审批通过(APPROVED)后自动登记统一待付款项台账;
  拒绝(REJECTED)则作废对应台账项——避免每次都要人工重跑
  backfill_service_expense_payables 管理命令才能让新审批通过的费用出现在核销
  工作台候选里。旧逻辑里 approve() 只把已批准费用汇总进 ServiceOrder.actual_cost
  (成本口径统计),从未创建 AccountPayable,是完全游离于 finance 之外的费用来源
  (见 apps.finance.payable_adapters.ServiceExpensePayableSource 顶部注释)。

登记/作废失败均不冒泡(用 `_safe_sync_payable` 包裹),避免台账同步问题打断审批
事务;失败只记日志 + 通知财务管理员,真正的数据补齐留给人工核查或
backfill_service_expense_payables 命令兜底。
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.projects.field_service import ServiceExpense

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ServiceExpense)
def register_service_expense_payable(sender, instance, **kwargs):
    """服务费审批通过(APPROVED)→ 登记台账;拒绝(REJECTED)→ 台账项作废;
    拒绝后重新审批通过 → 复活。

    覆盖 ServiceExpenseViewSet.approve()/reject() 两条路径(均经 ServiceExpense.save()
    落状态,该 ViewSet 未接入 WorkflowEnforcementMixin,没有工作流引擎分支)。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'APPROVED':
        item = _safe_sync_payable(register_payable, instance, 'service_expense', action='登记')
        # 拒绝后重新审批通过:register_payable 的 update_or_create 不含 status,不会把
        # 拒绝时置为 CANCELLED 的台账项复活,这里显式置回 PENDING(与合同付款
        # 撤回复活的处理原则一致,见 apps.purchase.signals.register_contract_payment_payable)。
        if item is not None and item.status == item.STATUS_CANCELLED and item.amount_paid == 0:
            item.status = item.STATUS_PENDING
            item.recalc_status()
            item.save(update_fields=['status', 'updated_at'])
    elif instance.status == 'REJECTED':
        _safe_sync_payable(cancel_payable, instance, 'service_expense', action='作废')


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
        title = '待付款项台账同步失败'
        message = (
            f'{source_type} 单据 id={instance.pk} 的待付款项台账{action}失败,'
            f'请人工核查并按需执行 backfill_service_expense_payables 命令补齐。'
        )
        SystemNotification.objects.bulk_create(
            [SystemNotification(user=user, type='ERROR', title=title, message=message) for user in recipients]
        )
    except Exception:
        logger.exception('发送待付款项台账同步失败告警通知时出错(source_type=%s, id=%s)', source_type, instance.pk)
