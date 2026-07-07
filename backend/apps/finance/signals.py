"""apps.finance 模型的 post_save 信号处理器。

目前只有一个:AccountPayable(AP)创建/变更后自动登记/作废统一待付款项台账
(PayableItem),避免每次都要人工重跑 backfill_payables 管理命令才能让新
产生的 AP 出现在核销工作台候选里。
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.finance.models import AccountPayable


@receiver(post_save, sender=AccountPayable)
def register_ap_payable(sender, instance, **kwargs):
    """AP 处于开放状态(待付/部分/逾期)即登记台账;取消则作废对应台账项。

    - 过滤口径与 `backfill_payables` 管理命令一致(status in PENDING/PARTIAL/OVERDUE);
      已结清(PAID)的 AP 不登记——同合同付款"已付无需核销"的口径,避免污染核销候选。
    - `register_payable` 走 `update_or_create` 且 defaults 不含 amount_paid/status(见
      `payable_adapters.register_payable` 顶部注释的不变量),因此本信号可安全地在
      AccountPayable 的每次 save()(含 `APPayableSource.write_back` 触发的重入 save)
      上重复触发,只会刷新供应商/金额/日期等静态字段,不会覆盖已由核销/反核销正确
      维护的 amount_paid/status。
    - `cancel_payable` 内部已守卫:仅当台账项 `amount_paid==0` 时才允许置为 CANCELLED,
      已核销过的台账项不会被这里误伤。
    - 惰性 import `payable_adapters`,避免与本模块顶层 import 之间出现意外的加载期耦合
      (虽然当前无循环依赖,保持与 apps.purchase.signals 里同类信号一致的写法)。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status in ('PENDING', 'PARTIAL', 'OVERDUE'):
        register_payable(instance, 'ap')
    elif instance.status == 'CANCELLED':
        cancel_payable(instance, 'ap')
