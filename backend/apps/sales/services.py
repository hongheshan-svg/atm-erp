"""销售模块共用业务逻辑。

抽出供 ViewSet 直接确认与工作流审批回写共用，避免两条确认路径行为漂移。
"""


def create_sales_order_receivables(so, user, due_date=None):
    """销售订单确认时幂等创建应收账款与付款计划。

    供 SalesOrderViewSet._do_confirm（直接确认）与 WorkflowService 的
    SALES_ORDER 审批通过回写共用，确保两条路径都生成应收/付款计划。

    Returns: 新生成的付款计划列表（已存在则返回空列表）。
    """
    from apps.finance.models import AccountReceivable, PaymentSchedule

    if not AccountReceivable.objects.filter(so=so, is_deleted=False).exists():
        AccountReceivable.objects.create(
            customer=so.customer,
            so=so,
            project=so.project,
            invoice_date=so.order_date,
            amount_due=so.total_with_tax or so.total_amount,
            due_date=due_date or so.delivery_date,
            created_by=user,
        )

    if PaymentSchedule.objects.filter(sales_order=so, is_deleted=False).exists():
        return []
    return PaymentSchedule.generate_from_sales_order(so)
