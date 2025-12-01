"""
Celery tasks for finance app - AR/AP overdue reminders.
"""
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import F
from datetime import timedelta
from decimal import Decimal


@shared_task
def check_overdue_receivables():
    """
    Check for overdue accounts receivable and send alerts.
    Runs daily at 9 AM.
    Also updates status to OVERDUE if past due date.
    """
    from .models import AccountReceivable
    from apps.accounts.models import User
    from apps.core.models import SystemNotification
    from apps.core.notification_service import NotificationService
    
    today = timezone.now().date()
    
    # Find overdue receivables
    overdue_ar = AccountReceivable.objects.filter(
        due_date__lt=today,
        status__in=['PENDING', 'PARTIAL'],
        is_deleted=False
    ).select_related('customer', 'project')
    
    if not overdue_ar.exists():
        return "No overdue receivables"
    
    # Update status to OVERDUE
    overdue_ar.update(status='OVERDUE')
    
    # Build alert message
    message_lines = ["以下应收账款已逾期:\n"]
    total_overdue = Decimal('0')
    overdue_items = []
    
    for ar in overdue_ar:
        remaining = ar.amount_due - ar.amount_paid
        days_overdue = (today - ar.due_date).days
        total_overdue += remaining
        
        message_lines.append(
            f"- {ar.ar_no} | 客户: {ar.customer.name} | "
            f"应收: ¥{remaining:,.2f} | 逾期: {days_overdue}天"
        )
        overdue_items.append({
            'ar_no': ar.ar_no,
            'customer': ar.customer.name,
            'amount': float(remaining),
            'days_overdue': days_overdue
        })
    
    message_lines.append(f"\n逾期总额: ¥{total_overdue:,.2f}")
    message = "\n".join(message_lines)
    
    # Get finance staff and admins
    recipients = User.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        role__code__in=['FINANCE', 'ADMIN']
    ).values_list('id', flat=True)
    
    # Create in-app notifications
    for user_id in recipients:
        SystemNotification.objects.create(
            user_id=user_id,
            title='应收账款逾期提醒',
            message=message,
            type='WARNING'
        )
    
    # Send email to admins
    admin_emails = list(User.objects.filter(
        is_staff=True, 
        is_active=True
    ).exclude(email='').values_list('email', flat=True))
    
    if admin_emails:
        try:
            send_mail(
                subject='ERP系统 - 应收账款逾期提醒',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except Exception:
            pass
    
    # Send to DingTalk/WeChat Work
    try:
        title = "💰 应收账款逾期提醒"
        markdown_content = f"### {title}\n\n"
        markdown_content += f"共 **{len(overdue_items)}** 笔应收账款已逾期，总额 **¥{total_overdue:,.2f}**\n\n"
        for item in overdue_items[:5]:
            markdown_content += f"- {item['ar_no']} | {item['customer']} | ¥{item['amount']:,.2f} | 逾期{item['days_overdue']}天\n"
        if len(overdue_items) > 5:
            markdown_content += f"\n... 还有 {len(overdue_items) - 5} 笔\n"
        
        NotificationService.send_custom_notification(title, markdown_content)
    except Exception:
        pass
    
    return f"Sent overdue AR alert for {overdue_ar.count()} items, total: ¥{total_overdue:,.2f}"


@shared_task
def check_overdue_payables():
    """
    Check for overdue accounts payable and send alerts.
    Runs daily at 9 AM.
    Also updates status to OVERDUE if past due date.
    """
    from .models import AccountPayable
    from apps.accounts.models import User
    from apps.core.models import Notification
    
    today = timezone.now().date()
    
    # Find overdue payables
    overdue_ap = AccountPayable.objects.filter(
        due_date__lt=today,
        status__in=['PENDING', 'PARTIAL'],
        is_deleted=False
    ).select_related('supplier')
    
    if not overdue_ap.exists():
        return "No overdue payables"
    
    # Update status to OVERDUE
    overdue_ap.update(status='OVERDUE')
    
    # Build alert message
    message_lines = ["以下应付账款已逾期:\n"]
    total_overdue = Decimal('0')
    
    for ap in overdue_ap:
        remaining = ap.amount_due - ap.amount_paid
        days_overdue = (today - ap.due_date).days
        total_overdue += remaining
        
        message_lines.append(
            f"- {ap.ap_no} | 供应商: {ap.supplier.name} | "
            f"应付: ¥{remaining:,.2f} | 逾期: {days_overdue}天"
        )
    
    message_lines.append(f"\n逾期总额: ¥{total_overdue:,.2f}")
    message = "\n".join(message_lines)
    
    # Get finance staff and admins
    recipients = User.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        role__code__in=['FINANCE', 'ADMIN']
    ).values_list('id', flat=True)
    
    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id,
            title='应付账款逾期提醒',
            content=message,
            notification_type='WARNING',
            link='/finance/ap'
        )
    
    # Send email to admins
    admin_emails = list(User.objects.filter(
        is_staff=True, 
        is_active=True
    ).exclude(email='').values_list('email', flat=True))
    
    if admin_emails:
        try:
            send_mail(
                subject='ERP系统 - 应付账款逾期提醒',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except Exception:
            pass
    
    return f"Sent overdue AP alert for {overdue_ap.count()} items, total: ¥{total_overdue:,.2f}"


@shared_task
def check_upcoming_due_dates():
    """
    Check for AR/AP due in the next 7 days and send early warnings.
    Runs daily at 9 AM.
    """
    from .models import AccountReceivable, AccountPayable
    from apps.accounts.models import User
    from apps.core.models import Notification
    
    today = timezone.now().date()
    warning_date = today + timedelta(days=7)
    
    # Find AR due in 7 days
    upcoming_ar = AccountReceivable.objects.filter(
        due_date__gte=today,
        due_date__lte=warning_date,
        status__in=['PENDING', 'PARTIAL'],
        is_deleted=False
    ).select_related('customer')
    
    # Find AP due in 7 days
    upcoming_ap = AccountPayable.objects.filter(
        due_date__gte=today,
        due_date__lte=warning_date,
        status__in=['PENDING', 'PARTIAL'],
        is_deleted=False
    ).select_related('supplier')
    
    if not upcoming_ar.exists() and not upcoming_ap.exists():
        return "No upcoming due dates"
    
    message_lines = ["以下账款即将到期 (7天内):\n"]
    
    if upcoming_ar.exists():
        message_lines.append("\n【应收账款】")
        ar_total = Decimal('0')
        for ar in upcoming_ar:
            remaining = ar.amount_due - ar.amount_paid
            days_to_due = (ar.due_date - today).days
            ar_total += remaining
            message_lines.append(
                f"- {ar.ar_no} | {ar.customer.name} | "
                f"¥{remaining:,.2f} | {days_to_due}天后到期"
            )
        message_lines.append(f"应收小计: ¥{ar_total:,.2f}")
    
    if upcoming_ap.exists():
        message_lines.append("\n【应付账款】")
        ap_total = Decimal('0')
        for ap in upcoming_ap:
            remaining = ap.amount_due - ap.amount_paid
            days_to_due = (ap.due_date - today).days
            ap_total += remaining
            message_lines.append(
                f"- {ap.ap_no} | {ap.supplier.name} | "
                f"¥{remaining:,.2f} | {days_to_due}天后到期"
            )
        message_lines.append(f"应付小计: ¥{ap_total:,.2f}")
    
    message = "\n".join(message_lines)
    
    # Get finance staff
    recipients = User.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        role__code__in=['FINANCE', 'ADMIN']
    ).values_list('id', flat=True)
    
    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id,
            title='账款到期预警',
            content=message,
            notification_type='INFO',
            link='/finance/ar'
        )
    
    return f"Sent due date warnings: {upcoming_ar.count()} AR, {upcoming_ap.count()} AP"


@shared_task
def generate_daily_finance_summary():
    """
    Generate daily finance summary report.
    Runs daily at 6 PM.
    """
    from .models import AccountReceivable, AccountPayable, Expense
    from apps.accounts.models import User
    from apps.core.models import Notification
    from django.db.models import Sum, Count, Q
    
    today = timezone.now().date()
    
    # AR Summary
    ar_stats = AccountReceivable.objects.filter(is_deleted=False).aggregate(
        total_pending=Sum('amount_due', filter=Q(status='PENDING')),
        total_partial=Sum('amount_due', filter=Q(status='PARTIAL')) - Sum('amount_paid', filter=Q(status='PARTIAL')),
        total_overdue=Sum('amount_due', filter=Q(status='OVERDUE')) - Sum('amount_paid', filter=Q(status='OVERDUE')),
        count_pending=Count('id', filter=Q(status='PENDING')),
        count_overdue=Count('id', filter=Q(status='OVERDUE'))
    )
    
    # AP Summary
    ap_stats = AccountPayable.objects.filter(is_deleted=False).aggregate(
        total_pending=Sum('amount_due', filter=Q(status='PENDING')),
        total_partial=Sum('amount_due', filter=Q(status='PARTIAL')) - Sum('amount_paid', filter=Q(status='PARTIAL')),
        total_overdue=Sum('amount_due', filter=Q(status='OVERDUE')) - Sum('amount_paid', filter=Q(status='OVERDUE')),
        count_pending=Count('id', filter=Q(status='PENDING')),
        count_overdue=Count('id', filter=Q(status='OVERDUE'))
    )
    
    # Expense Summary (pending approval)
    expense_pending = Expense.objects.filter(
        status='SUBMITTED',
        is_deleted=False
    ).aggregate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Build message
    message = f"""ERP财务日报 - {today}

【应收账款】
待收款: ¥{(ar_stats['total_pending'] or 0):,.2f} ({ar_stats['count_pending'] or 0}笔)
逾期款: ¥{(ar_stats['total_overdue'] or 0):,.2f} ({ar_stats['count_overdue'] or 0}笔)

【应付账款】
待付款: ¥{(ap_stats['total_pending'] or 0):,.2f} ({ap_stats['count_pending'] or 0}笔)
逾期款: ¥{(ap_stats['total_overdue'] or 0):,.2f} ({ap_stats['count_overdue'] or 0}笔)

【费用报销】
待审批: ¥{(expense_pending['total'] or 0):,.2f} ({expense_pending['count'] or 0}笔)
"""
    
    # Get admin users
    admin_users = User.objects.filter(
        is_staff=True,
        is_active=True,
        is_deleted=False
    ).values_list('id', flat=True)
    
    # Create notifications
    for user_id in admin_users:
        Notification.objects.create(
            user_id=user_id,
            title=f'财务日报 - {today}',
            content=message,
            notification_type='INFO'
        )
    
    return "Daily finance summary generated"
