"""
Celery tasks for finance app - AR/AP overdue reminders.
"""

from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.core.management import call_command
from django.utils import timezone


@shared_task
def check_overdue_receivables():
    """
    Check for overdue accounts receivable and send alerts.
    Runs daily at 9 AM.
    Also updates status to OVERDUE if past due date.
    """
    from apps.accounts.models import User
    from apps.core.models import SystemNotification
    from apps.core.notification_service import NotificationService

    from .models import AccountReceivable

    today = timezone.now().date()

    # Find overdue receivables
    overdue_ar = AccountReceivable.objects.filter(
        due_date__lt=today, status__in=['PENDING', 'PARTIAL'], is_deleted=False
    ).select_related('customer', 'project')

    if not overdue_ar.exists():
        return 'No overdue receivables'

    # Update status to OVERDUE
    overdue_ar.update(status='OVERDUE')

    # Build alert message
    message_lines = ['以下应收账款已逾期:\n']
    total_overdue = Decimal('0')
    overdue_items = []

    for ar in overdue_ar:
        remaining = ar.amount_due - ar.amount_paid
        days_overdue = (today - ar.due_date).days
        total_overdue += remaining

        message_lines.append(
            f'- {ar.ar_no} | 客户: {ar.customer.name} | ' f'应收: ¥{remaining:,.2f} | 逾期: {days_overdue}天'
        )
        overdue_items.append(
            {'ar_no': ar.ar_no, 'customer': ar.customer.name, 'amount': float(remaining), 'days_overdue': days_overdue}
        )

    message_lines.append(f'\n逾期总额: ¥{total_overdue:,.2f}')
    message = '\n'.join(message_lines)

    # Get finance staff and admins
    recipients = (
        User.objects.filter(is_active=True, is_deleted=False)
        .filter(role__code__in=['FINANCE', 'ADMIN'])
        .values_list('id', flat=True)
    )

    # Create in-app notifications
    for user_id in recipients:
        SystemNotification.objects.create(user_id=user_id, title='应收账款逾期提醒', message=message, type='WARNING')

    # Send email to admins
    admin_emails = list(
        User.objects.filter(is_staff=True, is_active=True).exclude(email='').values_list('email', flat=True)
    )

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
        title = '💰 应收账款逾期提醒'

        # 群发安全内容（不含具体财务数据）
        safe_content = f'### {title}\n\n'
        safe_content += f'您有 **{len(overdue_items)}** 笔应收账款已逾期，请登录ERP系统查看详情并及时跟进催收。\n\n'
        safe_content += '👉 [点击查看详情](应收账款管理)'

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f'Sent overdue AR alert for {overdue_ar.count()} items, total: ¥{total_overdue:,.2f}'


@shared_task
def check_overdue_payables():
    """
    Check for overdue accounts payable and send alerts.
    Runs daily at 9 AM.
    Also updates status to OVERDUE if past due date.
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import AccountPayable

    today = timezone.now().date()

    # Find overdue payables
    overdue_ap = AccountPayable.objects.filter(
        due_date__lt=today, status__in=['PENDING', 'PARTIAL'], is_deleted=False
    ).select_related('supplier')

    if not overdue_ap.exists():
        return 'No overdue payables'

    # Update status to OVERDUE
    overdue_ap.update(status='OVERDUE')

    # Build alert message
    message_lines = ['以下应付账款已逾期:\n']
    total_overdue = Decimal('0')
    overdue_items = []

    for ap in overdue_ap:
        remaining = ap.amount_due - ap.amount_paid
        days_overdue = (today - ap.due_date).days
        total_overdue += remaining

        message_lines.append(
            f'- {ap.ap_no} | 供应商: {ap.supplier.name} | ' f'应付: ¥{remaining:,.2f} | 逾期: {days_overdue}天'
        )
        overdue_items.append(
            {'ap_no': ap.ap_no, 'supplier': ap.supplier.name, 'amount': float(remaining), 'days_overdue': days_overdue}
        )

    message_lines.append(f'\n逾期总额: ¥{total_overdue:,.2f}')
    message = '\n'.join(message_lines)

    # Get finance staff and admins
    recipients = (
        User.objects.filter(is_active=True, is_deleted=False)
        .filter(role__code__in=['FINANCE', 'ADMIN'])
        .values_list('id', flat=True)
    )

    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id, title='应付账款逾期提醒', content=message, notification_type='WARNING', link='/finance/ap'
        )

    # Send email to admins
    admin_emails = list(
        User.objects.filter(is_staff=True, is_active=True).exclude(email='').values_list('email', flat=True)
    )

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

    # Send to DingTalk/WeChat Work
    try:
        title = '💸 应付账款逾期提醒'

        # 群发安全内容（不含具体财务数据）
        safe_content = f'### {title}\n\n'
        safe_content += f'您有 **{len(overdue_items)}** 笔应付账款已逾期，请登录ERP系统查看详情并及时安排付款。\n\n'
        safe_content += '👉 [点击查看详情](应付账款管理)'

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f'Sent overdue AP alert for {overdue_ap.count()} items, total: ¥{total_overdue:,.2f}'


@shared_task
def check_upcoming_due_dates():
    """
    Check for AR/AP due in the next 7 days and send early warnings.
    Runs daily at 9 AM.
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import AccountPayable, AccountReceivable

    today = timezone.now().date()
    warning_date = today + timedelta(days=7)

    # Find AR due in 7 days
    upcoming_ar = AccountReceivable.objects.filter(
        due_date__gte=today, due_date__lte=warning_date, status__in=['PENDING', 'PARTIAL'], is_deleted=False
    ).select_related('customer')

    # Find AP due in 7 days
    upcoming_ap = AccountPayable.objects.filter(
        due_date__gte=today, due_date__lte=warning_date, status__in=['PENDING', 'PARTIAL'], is_deleted=False
    ).select_related('supplier')

    if not upcoming_ar.exists() and not upcoming_ap.exists():
        return 'No upcoming due dates'

    message_lines = ['以下账款即将到期 (7天内):\n']
    ar_items = []
    ap_items = []
    ar_total = Decimal('0')
    ap_total = Decimal('0')

    if upcoming_ar.exists():
        message_lines.append('\n【应收账款】')
        for ar in upcoming_ar:
            remaining = ar.amount_due - ar.amount_paid
            days_to_due = (ar.due_date - today).days
            ar_total += remaining
            message_lines.append(f'- {ar.ar_no} | {ar.customer.name} | ' f'¥{remaining:,.2f} | {days_to_due}天后到期')
            ar_items.append(
                {'ar_no': ar.ar_no, 'customer': ar.customer.name, 'amount': float(remaining), 'days': days_to_due}
            )
        message_lines.append(f'应收小计: ¥{ar_total:,.2f}')

    if upcoming_ap.exists():
        message_lines.append('\n【应付账款】')
        for ap in upcoming_ap:
            remaining = ap.amount_due - ap.amount_paid
            days_to_due = (ap.due_date - today).days
            ap_total += remaining
            message_lines.append(f'- {ap.ap_no} | {ap.supplier.name} | ' f'¥{remaining:,.2f} | {days_to_due}天后到期')
            ap_items.append(
                {'ap_no': ap.ap_no, 'supplier': ap.supplier.name, 'amount': float(remaining), 'days': days_to_due}
            )
        message_lines.append(f'应付小计: ¥{ap_total:,.2f}')

    message = '\n'.join(message_lines)

    # Get finance staff
    recipients = (
        User.objects.filter(is_active=True, is_deleted=False)
        .filter(role__code__in=['FINANCE', 'ADMIN'])
        .values_list('id', flat=True)
    )

    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id, title='账款到期预警', content=message, notification_type='INFO', link='/finance/ar'
        )

    # Send to DingTalk/WeChat Work
    try:
        title = '📅 账款到期预警'

        # 群发安全内容（不含具体财务数据）
        safe_content = f'### {title}\n\n'
        if ar_items:
            safe_content += f'- 📥 **{len(ar_items)}** 笔应收账款即将到期\n'
        if ap_items:
            safe_content += f'- 📤 **{len(ap_items)}** 笔应付账款即将到期\n'
        safe_content += '\n请登录ERP系统查看详情，提前做好资金准备！'

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f'Sent due date warnings: {upcoming_ar.count()} AR, {upcoming_ap.count()} AP'


@shared_task
def generate_daily_finance_summary():
    """
    Generate daily finance summary report.
    Runs daily at 6 PM.
    """
    from django.db.models import Count, Q, Sum

    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import AccountPayable, AccountReceivable, Expense

    today = timezone.now().date()

    # AR Summary
    ar_stats = AccountReceivable.objects.filter(is_deleted=False).aggregate(
        total_pending=Sum('amount_due', filter=Q(status='PENDING')),
        total_partial=Sum('amount_due', filter=Q(status='PARTIAL')) - Sum('amount_paid', filter=Q(status='PARTIAL')),
        total_overdue=Sum('amount_due', filter=Q(status='OVERDUE')) - Sum('amount_paid', filter=Q(status='OVERDUE')),
        count_pending=Count('id', filter=Q(status='PENDING')),
        count_overdue=Count('id', filter=Q(status='OVERDUE')),
    )

    # AP Summary
    ap_stats = AccountPayable.objects.filter(is_deleted=False).aggregate(
        total_pending=Sum('amount_due', filter=Q(status='PENDING')),
        total_partial=Sum('amount_due', filter=Q(status='PARTIAL')) - Sum('amount_paid', filter=Q(status='PARTIAL')),
        total_overdue=Sum('amount_due', filter=Q(status='OVERDUE')) - Sum('amount_paid', filter=Q(status='OVERDUE')),
        count_pending=Count('id', filter=Q(status='PENDING')),
        count_overdue=Count('id', filter=Q(status='OVERDUE')),
    )

    # Expense Summary (pending approval)
    expense_pending = Expense.objects.filter(status='SUBMITTED', is_deleted=False).aggregate(
        total=Sum('amount'), count=Count('id')
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
    admin_users = User.objects.filter(is_staff=True, is_active=True, is_deleted=False).values_list('id', flat=True)

    # Create notifications
    for user_id in admin_users:
        Notification.objects.create(
            user_id=user_id, title=f'财务日报 - {today}', content=message, notification_type='INFO'
        )

    # Send to DingTalk/WeChat Work
    try:
        title = f'📊 财务日报 - {today}'

        # 群发安全内容（只发笔数，不发金额）
        safe_content = f"""### {title}

#### 今日待办
- 📥 待收款 **{ar_stats['count_pending'] or 0}** 笔
- ⚠️ 应收逾期 **{ar_stats['count_overdue'] or 0}** 笔
- 📤 待付款 **{ap_stats['count_pending'] or 0}** 笔
- ⚠️ 应付逾期 **{ap_stats['count_overdue'] or 0}** 笔
- 📝 费用待审批 **{expense_pending['count'] or 0}** 笔

请登录ERP系统查看详情。
"""
        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return 'Daily finance summary generated'


@shared_task
def check_payment_schedule_reminders():
    """
    Check for payment schedules that need reminders.
    Runs daily at 9 AM.

    Sends reminders for:
    1. Overdue payments
    2. Payments due within the reminder window (default 7 days)
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import PaymentSchedule

    today = timezone.now().date()

    # Find schedules needing reminders
    # 1. Overdue and not yet reminded today
    # 2. Due within reminder window and not yet reminded
    schedules_to_remind = []

    pending_schedules = (
        PaymentSchedule.objects.filter(status__in=['PENDING', 'PARTIAL'], reminder_status='PENDING', is_deleted=False)
        .select_related('sales_order', 'sales_order__customer', 'project')
        .order_by('due_date')
    )

    for schedule in pending_schedules:
        remind_date = schedule.due_date - timedelta(days=schedule.reminder_days_before)

        # Check if it's time to remind (today >= remind_date)
        if today >= remind_date:
            schedules_to_remind.append(schedule)

    if not schedules_to_remind:
        return 'No payment schedule reminders needed'

    # Update overdue status
    for schedule in schedules_to_remind:
        if schedule.due_date < today and schedule.status != 'OVERDUE':
            schedule.status = 'OVERDUE'
            schedule.save()

    # Create in-app notifications for finance and sales staff
    message_lines = ['以下付款计划需要跟进收款：\n']

    overdue_schedules = [s for s in schedules_to_remind if s.is_overdue]
    upcoming_schedules = [s for s in schedules_to_remind if not s.is_overdue]

    if overdue_schedules:
        message_lines.append('\n【已逾期】')
        for s in overdue_schedules[:5]:
            remaining = s.amount_due - s.amount_paid
            message_lines.append(
                f'- {s.sales_order.order_no} | {s.milestone_name} | '
                f'{s.sales_order.customer.name} | ¥{remaining:,.2f} | 逾期{abs(s.days_until_due)}天'
            )
        if len(overdue_schedules) > 5:
            message_lines.append(f'  ... 还有 {len(overdue_schedules) - 5} 笔')

    if upcoming_schedules:
        message_lines.append('\n【即将到期】')
        for s in upcoming_schedules[:5]:
            remaining = s.amount_due - s.amount_paid
            message_lines.append(
                f'- {s.sales_order.order_no} | {s.milestone_name} | '
                f'{s.sales_order.customer.name} | ¥{remaining:,.2f} | {s.days_until_due}天后到期'
            )
        if len(upcoming_schedules) > 5:
            message_lines.append(f'  ... 还有 {len(upcoming_schedules) - 5} 笔')

    total_remaining = sum(s.amount_due - s.amount_paid for s in schedules_to_remind)
    message_lines.append(f'\n待收款总额: ¥{total_remaining:,.2f}')

    message = '\n'.join(message_lines)

    # Get finance and sales staff
    recipients = (
        User.objects.filter(is_active=True, is_deleted=False)
        .filter(role__code__in=['FINANCE', 'SALES', 'ADMIN'])
        .values_list('id', flat=True)
    )

    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id,
            title='付款计划收款提醒',
            content=message,
            notification_type='WARNING',
            link='/finance/payment-schedules',
        )

    # Mark as reminded
    for schedule in schedules_to_remind:
        schedule.reminder_status = 'REMINDED'
        schedule.last_reminded_at = timezone.now()
        schedule.save()

    # Send to DingTalk/WeChat Work
    try:
        NotificationService.send_payment_reminder(schedules_to_remind)
    except Exception:
        pass

    return f'Sent payment schedule reminders for {len(schedules_to_remind)} items, total: ¥{total_remaining:,.2f}'


@shared_task
def reset_payment_schedule_reminders():
    """
    Reset reminder status for schedules that were reminded but still not paid.
    Runs weekly to allow for repeated reminders.
    """
    from .models import PaymentSchedule, PurchasePaymentSchedule

    # Reset reminded schedules that are still pending (销售)
    ar_updated = PaymentSchedule.objects.filter(
        status__in=['PENDING', 'PARTIAL', 'OVERDUE'], reminder_status='REMINDED', is_deleted=False
    ).update(reminder_status='PENDING')

    # Reset reminded schedules that are still pending (采购)
    ap_updated = PurchasePaymentSchedule.objects.filter(
        status__in=['PENDING', 'PARTIAL', 'OVERDUE'], reminder_status='REMINDED', is_deleted=False
    ).update(reminder_status='PENDING')

    return f'Reset {ar_updated} AR and {ap_updated} AP payment schedule reminders'


@shared_task
def check_purchase_payment_schedule_reminders():
    """
    Check for purchase payment schedules that need reminders.
    Runs daily at 9 AM.

    Sends reminders for:
    1. Overdue payments
    2. Payments due within the reminder window (default 3 days for purchases)
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import PurchasePaymentSchedule

    today = timezone.now().date()

    # Find schedules needing reminders
    schedules_to_remind = []

    pending_schedules = (
        PurchasePaymentSchedule.objects.filter(
            status__in=['PENDING', 'PARTIAL'], reminder_status='PENDING', is_deleted=False
        )
        .select_related('purchase_order', 'purchase_order__supplier', 'project')
        .order_by('due_date')
    )

    for schedule in pending_schedules:
        remind_date = schedule.due_date - timedelta(days=schedule.reminder_days_before)

        # Check if it's time to remind (today >= remind_date)
        if today >= remind_date:
            schedules_to_remind.append(schedule)

    if not schedules_to_remind:
        return 'No purchase payment schedule reminders needed'

    # Update overdue status
    for schedule in schedules_to_remind:
        if schedule.due_date < today and schedule.status != 'OVERDUE':
            schedule.status = 'OVERDUE'
            schedule.save()

    # Create in-app notifications for finance and purchase staff
    message_lines = ['以下采购付款计划需要跟进付款：\n']

    overdue_schedules = [s for s in schedules_to_remind if s.is_overdue]
    upcoming_schedules = [s for s in schedules_to_remind if not s.is_overdue]

    if overdue_schedules:
        message_lines.append('\n【已逾期】')
        for s in overdue_schedules[:5]:
            remaining = s.amount_due - s.amount_paid
            message_lines.append(
                f'- {s.purchase_order.order_no} | {s.milestone_name} | '
                f'{s.purchase_order.supplier.name} | ¥{remaining:,.2f} | 逾期{abs(s.days_until_due)}天'
            )
        if len(overdue_schedules) > 5:
            message_lines.append(f'  ... 还有 {len(overdue_schedules) - 5} 笔')

    if upcoming_schedules:
        message_lines.append('\n【即将到期】')
        for s in upcoming_schedules[:5]:
            remaining = s.amount_due - s.amount_paid
            message_lines.append(
                f'- {s.purchase_order.order_no} | {s.milestone_name} | '
                f'{s.purchase_order.supplier.name} | ¥{remaining:,.2f} | {s.days_until_due}天后到期'
            )
        if len(upcoming_schedules) > 5:
            message_lines.append(f'  ... 还有 {len(upcoming_schedules) - 5} 笔')

    total_remaining = sum(s.amount_due - s.amount_paid for s in schedules_to_remind)
    message_lines.append(f'\n待付款总额: ¥{total_remaining:,.2f}')

    message = '\n'.join(message_lines)

    # Get finance and purchase staff
    recipients = (
        User.objects.filter(is_active=True, is_deleted=False)
        .filter(role__code__in=['FINANCE', 'PURCHASE', 'ADMIN'])
        .values_list('id', flat=True)
    )

    # Create in-app notifications
    for user_id in recipients:
        Notification.objects.create(
            user_id=user_id,
            title='采购付款计划提醒',
            content=message,
            notification_type='WARNING',
            link='/finance/purchase-payment-schedules',
        )

    # Mark as reminded
    for schedule in schedules_to_remind:
        schedule.reminder_status = 'REMINDED'
        schedule.last_reminded_at = timezone.now()
        schedule.save()

    # Send to DingTalk/WeChat Work
    try:
        title = '💸 采购付款提醒'

        # 群发安全内容（不含具体财务数据）
        safe_content = f'### {title}\n\n'
        if overdue_schedules:
            safe_content += f'⚠️ **{len(overdue_schedules)}** 笔付款已逾期\n'
        if upcoming_schedules:
            safe_content += f'📅 **{len(upcoming_schedules)}** 笔付款即将到期\n'
        safe_content += '\n请登录ERP系统查看详情并及时安排付款！'

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return (
        f'Sent purchase payment schedule reminders for {len(schedules_to_remind)} items, total: ¥{total_remaining:,.2f}'
    )


@shared_task
def backfill_payables_safety_net():
    """
    每日定时兜底:重跑 backfill_payables / backfill_contract_payables。

    背景(问题 I-2):合同付款审批经工作流引擎完成时,apps.core.workflow.services
    ._on_workflow_complete 外层 try/except 会吞掉 register_payable 抛出的异常、
    仅 logger.error,可能导致 PaymentRecord 已 APPROVED 但待付款项台账静默缺失。
    apps.purchase.signals 已加了失败告警通知,但告警只是"知道出了问题",本任务
    才是真正的数据补齐兜底——两条 backfill 命令均为幂等(register_payable 走
    update_or_create),重复执行不会产生重复台账项或覆盖已核销进度。
    """
    call_command('backfill_payables')
    call_command('backfill_contract_payables')

    return 'Ran backfill_payables and backfill_contract_payables safety net'
