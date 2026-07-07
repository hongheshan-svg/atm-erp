"""apps.finance 模型的 post_save 信号处理器。

- AccountPayable(AP)创建/变更后自动登记/作废统一待付款项台账(PayableItem),
  避免每次都要人工重跑 backfill_payables 管理命令才能让新产生的 AP 出现在核销
  工作台候选里。
- 二期来源(公共费用分摊/税务申报/独立付款申请)审批到达各自"确认应付"状态时
  同样自动登记;取消/撤回时作废对应台账项。通用规则:一个来源若已经通过创建/
  引用 AccountPayable 间接进了台账(经 register_ap_payable 登记为 source_type=
  'ap'),就不再挂独立信号,避免同一笔应付被双记——据此,委外加工(outsource,
  OutsourceOrder.confirm() 里内联创建 AccountPayable)整体跳过;付款申请
  (PaymentRequest)仅当 `ap` 为空(不挂靠任何已有 AP 的独立申请,如预付款)时才
  登记为 source_type='payment_request'。
- 员工费用报销(Expense)审批通过(APPROVED)登记台账;驳回(REJECTED)或工作流撤回
  退回草稿(DRAFT)时作废对应台账项(withdraw_workflow 会把 EXPENSE 退回 DRAFT,
  见 apps.core.workflow.services._on_workflow_complete)。Expense 无供应商、
  不创建 AccountPayable,不存在双记风险,可直接登记。reimburse() 目前仍直接把
  Expense 置 PAID(绕过核销台账),是否收口为「只能由银行流水核销触发 PAID」留待
  后续设计决策,本信号只负责让 APPROVED 的报销单进入台账、可被核销。

登记/作废失败均不冒泡(用 `_safe_sync_payable` 包裹),避免台账同步问题打断审批
事务;失败只记日志 + 通知财务管理员,真正的数据补齐留给人工核查或未来的
backfill 命令兜底。
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.finance.models import AccountPayable, Expense, PaymentRequest, SharedExpense
from apps.finance.tax_management import TaxDeclaration

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=SharedExpense)
def register_shared_expense_payable(sender, instance, **kwargs):
    """公共费用完成分摊(ALLOCATED)→ 登记台账;撤销分摊退回 PENDING 或取消 → 台账项作废。

    SharedExpenseViewSet.allocate() 把 status 置为 ALLOCATED 时才产生"确认应付"事实
    (分摊前的 DRAFT/PENDING 只是费用登记草稿,金额可能还会调整);
    cancel_allocation() 会把 ALLOCATED 退回 PENDING,此时应回收已登记且未核销的台账项,
    避免误核销(同合同付款撤回场景的处理方式)。CANCELLED 目前代码里无入口触发,
    与 cancel_payable 一样一并处理以防将来接入。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'ALLOCATED':
        _safe_sync_payable(register_payable, instance, 'shared_expense', action='登记')
    elif instance.status in ('PENDING', 'CANCELLED'):
        _safe_sync_payable(cancel_payable, instance, 'shared_expense', action='作废')


@receiver(post_save, sender=Expense)
def register_expense_payable(sender, instance, **kwargs):
    """费用报销审批通过(APPROVED)→ 登记台账;驳回(REJECTED)或撤回退回草稿(DRAFT)
    → 台账项作废。

    ExpenseViewSet.submit()(未配置审批流的直接批准)与工作流引擎
    `_on_workflow_complete` business_type='EXPENSE' 分支都会把状态落到 APPROVED,
    两者都经 Expense.save() 触发本信号。REJECTED 由 approve/reject 直接操作或工作流
    拒绝产生;DRAFT 由 `withdraw_workflow` 把已提交的报销单撤回产生——两者发生时
    若之前已登记过台账项(理论上只有 APPROVED 之后才会登记,REJECTED/DRAFT 本身不会
    触发登记),`cancel_payable` 会回收未核销的台账项,避免误核销;`cancel_payable`
    内部已守卫仅当台账项 `amount_paid==0` 时才允许作废,已核销的不会被误伤。

    Expense 无供应商、不创建 AccountPayable,不存在与 AP 双记的问题,可直接登记。
    reimburse() 目前仍直接把 Expense 置为 PAID(绕过核销台账),是否收口为「只能由
    银行流水核销触发 PAID」是需要产品/用户拍板的行为变更,本信号先只保证 APPROVED
    的报销单能进入台账、可被核销工作台核销。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'APPROVED':
        _safe_sync_payable(register_payable, instance, 'expense', action='登记')
    elif instance.status in ('REJECTED', 'DRAFT'):
        _safe_sync_payable(cancel_payable, instance, 'expense', action='作废')


@receiver(post_save, sender=TaxDeclaration)
def register_tax_payable(sender, instance, **kwargs):
    """税务申报确认申报(DECLARED)→ 登记台账;CANCELLED → 台账项作废。

    DRAFT/SUBMITTED/APPROVED 都还在申报流程内,应缴税额(payable_amount)在此之前
    可能因抵扣调整而变化,不适合提前登记;declare() 落 DECLARED 后才是"已申报待缴"
    的确认应付事实,与 `TaxPayableSource.write_back` 反核销时退回的状态一致
    (见 payable_adapters.py:223)。REJECTED 只发生在 SUBMITTED 阶段(早于登记时点),
    无需处理。

    `TaxDeclaration.STATUS_CHOICES` 目前没有 CANCELLED 取值,
    `TaxDeclarationViewSet` 也没有 DECLARED 之后的撤回/作废操作入口——即下面的
    elif 分支在当前代码里是死代码。之所以仍然加上,是为了和其它来源信号
    (register_ap_payable/register_shared_expense_payable/
    register_payment_request_payable 均有对应的 CANCELLED/撤回分支)保持一致,
    并为未来一旦接入"撤回申报"之类的操作预留钩子,避免重蹈申报 DECLARED 之后
    被撤销、AP/台账却无人处理导致"幽灵应付"的覆辙。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.status == 'DECLARED':
        _safe_sync_payable(register_payable, instance, 'tax', action='登记')
    elif instance.status == 'CANCELLED':
        _safe_sync_payable(cancel_payable, instance, 'tax', action='作废')


@receiver(post_save, sender=PaymentRequest)
def register_payment_request_payable(sender, instance, **kwargs):
    """付款申请审批通过(APPROVED)→ 登记台账;取消(CANCELLED)→ 台账项作废。

    覆盖两条到达 APPROVED 的路径(PaymentRequestViewSet.submit() 未配置审批流时的
    直接批准、以及工作流引擎 `_on_workflow_complete` business_type='PAYMENT' 分支),
    两者都经 PaymentRequest.save() 落状态。REJECTED/WITHDRAWN 都退回 DRAFT,早于登记
    时点,无需处理;PAID 由 `PaymentRequestPayableSource.write_back` 或 pay() 视图直接
    置位,不需要这里额外处理。

    只登记 `ap` 为空的独立付款申请(如 PREPAY 预付款,尚无对应发票/AP)。若申请挂了
    `ap` FK(申请支付某张已存在的 AccountPayable),该 AP 只要处于开放状态就已经由
    `register_ap_payable` 登记为 source_type='ap';这里若再登记 source_type=
    'payment_request' 会对同一笔应付双记,故显式跳过(与 outsource 的处理原则一致)。
    """
    from apps.finance.payable_adapters import cancel_payable, register_payable

    if instance.ap_id is not None:
        return

    if instance.status == 'APPROVED':
        _safe_sync_payable(register_payable, instance, 'payment_request', action='登记')
    elif instance.status == 'CANCELLED':
        _safe_sync_payable(cancel_payable, instance, 'payment_request', action='作废')


def _safe_sync_payable(func, instance, source_type, *, action):
    """执行 register_payable/cancel_payable,失败时记日志 + 发系统通知给财务管理员,不冒泡。

    与 apps.purchase.signals 里的同名函数逻辑一致(未跨 app 复用私有辅助函数,各自
    保留一份简单实现,避免引入不必要的 app 间耦合)。成功时返回底层函数结果,失败
    返回 None。
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
        source_no = getattr(instance, 'source_no', None) or getattr(instance, 'pk', '')
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
