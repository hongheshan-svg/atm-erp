"""
Celery tasks for sales app - delivery reminders.
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def check_delivery_reminders():
    """
    Check for sales orders with upcoming or overdue delivery dates.
    Runs daily at 9:30 AM.
    
    Sends reminders for:
    1. Overdue deliveries (past expected delivery date, not yet delivered)
    2. Deliveries due within the next 3 days
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import SalesOrder

    today = timezone.now().date()
    warning_date = today + timedelta(days=3)

    # Find orders with overdue delivery
    overdue_orders = SalesOrder.objects.filter(
        expected_delivery_date__lt=today,
        status__in=['CONFIRMED', 'IN_PRODUCTION'],
        is_deleted=False
    ).select_related('customer', 'project')

    # Find orders due within 3 days
    upcoming_orders = SalesOrder.objects.filter(
        expected_delivery_date__gte=today,
        expected_delivery_date__lte=warning_date,
        status__in=['CONFIRMED', 'IN_PRODUCTION'],
        is_deleted=False
    ).select_related('customer', 'project')

    if not overdue_orders.exists() and not upcoming_orders.exists():
        return "No delivery reminders needed"

    # Build message
    message_lines = ["销售订单交货提醒:\n"]
    overdue_items = []
    upcoming_items = []

    if overdue_orders.exists():
        message_lines.append("\n【已逾期】")
        for order in overdue_orders[:10]:
            days_overdue = (today - order.expected_delivery_date).days
            message_lines.append(
                f"- {order.order_no} | {order.customer.name} | "
                f"¥{order.total_amount:,.2f} | 逾期{days_overdue}天"
            )
            overdue_items.append({
                'order_no': order.order_no,
                'customer': order.customer.name,
                'amount': float(order.total_amount),
                'days_overdue': days_overdue
            })

    if upcoming_orders.exists():
        message_lines.append("\n【即将到期】")
        for order in upcoming_orders[:10]:
            days_until = (order.expected_delivery_date - today).days
            message_lines.append(
                f"- {order.order_no} | {order.customer.name} | "
                f"¥{order.total_amount:,.2f} | {days_until}天后到期"
            )
            upcoming_items.append({
                'order_no': order.order_no,
                'customer': order.customer.name,
                'amount': float(order.total_amount),
                'days_until': days_until
            })

    message = "\n".join(message_lines)

    # Get sales staff
    recipients = User.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        role__code__in=['SALES', 'WAREHOUSE', 'ADMIN']
    ).values_list('id', flat=True)

    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id,
            title='销售订单交货提醒',
            content=message,
            notification_type='WARNING',
            link='/sales/orders'
        )

    # Send to DingTalk/WeChat Work
    try:
        title = "🚚 销售订单交货提醒"

        # 群发安全内容（不含具体客户和金额）
        safe_content = f"### {title}\n\n"
        if overdue_items:
            safe_content += f"⚠️ **{len(overdue_items)}** 笔订单已逾期交货\n"
        if upcoming_items:
            safe_content += f"📅 **{len(upcoming_items)}** 笔订单即将到期\n"
        safe_content += "\n请登录ERP系统查看详情并及时安排发货！"

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f"Sent delivery reminders: {overdue_orders.count()} overdue, {upcoming_orders.count()} upcoming"

