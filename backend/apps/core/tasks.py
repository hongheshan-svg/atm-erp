"""
Celery tasks for core app.
"""
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_webhook_deliveries():
    """
    Process pending webhook deliveries.
    Runs every minute.
    """
    from .webhook import WebhookService
    WebhookService.process_pending_deliveries()
    return "Webhook deliveries processed"


@shared_task
def send_scheduled_report(report_type, recipients, params=None):
    """
    Send scheduled report via email.
    
    Args:
        report_type: Type of report to generate
        recipients: List of email addresses
        params: Optional report parameters
    """
    from .export_service import ExcelExportService
    import io
    
    params = params or {}
    
    try:
        # Generate report based on type
        if report_type == 'daily_summary':
            attachment = generate_daily_summary_report()
            subject = f'ERP日报 - {timezone.now().strftime("%Y-%m-%d")}'
        elif report_type == 'weekly_sales':
            attachment = generate_weekly_sales_report()
            subject = f'销售周报 - {timezone.now().strftime("%Y年第%W周")}'
        elif report_type == 'monthly_finance':
            attachment = generate_monthly_finance_report()
            subject = f'财务月报 - {timezone.now().strftime("%Y年%m月")}'
        elif report_type == 'inventory_status':
            attachment = generate_inventory_report()
            subject = f'库存报表 - {timezone.now().strftime("%Y-%m-%d")}'
        else:
            logger.error(f"Unknown report type: {report_type}")
            return f"Unknown report type: {report_type}"
        
        # Send email
        email = EmailMessage(
            subject=subject,
            body=f'请查收附件中的{subject}。\n\n此邮件由系统自动发送，请勿回复。',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )
        
        email.attach(
            f'{report_type}_{timezone.now().strftime("%Y%m%d")}.xlsx',
            attachment,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        email.send()
        
        return f"Report {report_type} sent to {len(recipients)} recipients"
        
    except Exception as e:
        logger.exception(f"Failed to send scheduled report: {e}")
        return f"Failed: {str(e)}"


def generate_daily_summary_report():
    """Generate daily summary report."""
    import pandas as pd
    from apps.sales.models import SalesOrder
    from apps.purchase.models import PurchaseOrder
    from apps.finance.models import AccountReceivable, AccountPayable
    from django.db.models import Sum, Count
    
    today = timezone.now().date()
    
    # Sales summary
    sales_data = SalesOrder.objects.filter(
        order_date=today,
        is_deleted=False
    ).aggregate(
        count=Count('id'),
        total=Sum('total_amount')
    )
    
    # Purchase summary
    purchase_data = PurchaseOrder.objects.filter(
        order_date=today,
        is_deleted=False
    ).aggregate(
        count=Count('id'),
        total=Sum('total_amount')
    )
    
    # Create Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Summary sheet
        summary_df = pd.DataFrame([
            {'指标': '今日销售订单数', '数值': sales_data['count'] or 0},
            {'指标': '今日销售金额', '数值': float(sales_data['total'] or 0)},
            {'指标': '今日采购订单数', '数值': purchase_data['count'] or 0},
            {'指标': '今日采购金额', '数值': float(purchase_data['total'] or 0)},
        ])
        summary_df.to_excel(writer, sheet_name='日报汇总', index=False)
    
    output.seek(0)
    return output.read()


def generate_weekly_sales_report():
    """Generate weekly sales report."""
    import pandas as pd
    from apps.sales.models import SalesOrder
    
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    
    orders = SalesOrder.objects.filter(
        order_date__gte=week_start,
        order_date__lte=today,
        is_deleted=False
    ).select_related('customer', 'project').values(
        'order_no', 'customer__name', 'project__name',
        'total_amount', 'status', 'order_date'
    )
    
    output = io.BytesIO()
    df = pd.DataFrame(list(orders))
    
    if not df.empty:
        df.columns = ['订单号', '客户', '项目', '金额', '状态', '日期']
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='销售订单', index=False)
    
    output.seek(0)
    return output.read()


def generate_monthly_finance_report():
    """Generate monthly finance report."""
    import pandas as pd
    from apps.finance.models import AccountReceivable, AccountPayable, Expense
    from django.db.models import Sum
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # AR summary
    ar_data = AccountReceivable.objects.filter(
        invoice_date__gte=month_start,
        is_deleted=False
    ).values('customer__name').annotate(
        total_due=Sum('amount_due'),
        total_paid=Sum('amount_paid')
    )
    
    # AP summary
    ap_data = AccountPayable.objects.filter(
        invoice_date__gte=month_start,
        is_deleted=False
    ).values('supplier__name').annotate(
        total_due=Sum('amount_due'),
        total_paid=Sum('amount_paid')
    )
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(list(ar_data)).to_excel(writer, sheet_name='应收账款', index=False)
        pd.DataFrame(list(ap_data)).to_excel(writer, sheet_name='应付账款', index=False)
    
    output.seek(0)
    return output.read()


def generate_inventory_report():
    """Generate inventory status report."""
    import pandas as pd
    from apps.inventory.models import Stock
    
    stocks = Stock.objects.select_related('warehouse', 'item').values(
        'warehouse__name', 'item__sku', 'item__name',
        'qty_on_hand', 'qty_reserved', 'weighted_avg_cost'
    )
    
    output = io.BytesIO()
    df = pd.DataFrame(list(stocks))
    
    if not df.empty:
        df.columns = ['仓库', 'SKU', '物料名称', '库存数量', '预留数量', '平均成本']
        df['库存价值'] = df['库存数量'] * df['平均成本']
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='库存状态', index=False)
    
    output.seek(0)
    return output.read()


@shared_task
def cleanup_old_logs(days=90):
    """
    Clean up old logs and records.
    Runs weekly.
    """
    from .security import LoginLog, SensitiveOperationLog
    from .webhook import WebhookDelivery
    from .models import AuditLog
    
    cutoff = timezone.now() - timedelta(days=days)
    
    # Clean login logs
    login_deleted = LoginLog.objects.filter(login_time__lt=cutoff).delete()[0]
    
    # Clean webhook deliveries
    webhook_deleted = WebhookDelivery.objects.filter(
        created_at__lt=cutoff,
        status__in=['SUCCESS', 'FAILED']
    ).delete()[0]
    
    # Clean audit logs (keep longer)
    audit_cutoff = timezone.now() - timedelta(days=days * 2)
    audit_deleted = AuditLog.objects.filter(timestamp__lt=audit_cutoff).delete()[0]
    
    return f"Cleaned: {login_deleted} login logs, {webhook_deleted} webhook deliveries, {audit_deleted} audit logs"


@shared_task
def check_password_expiry():
    """
    Check for users with expiring passwords and send reminders.
    Runs daily.
    """
    from apps.accounts.models import User
    from .security import PasswordPolicy
    from .models import SystemNotification
    
    warning_days = 7
    
    for user in User.objects.filter(is_active=True, is_deleted=False):
        is_expired, days_until = PasswordPolicy.check_password_expiry(user)
        
        if days_until is not None and 0 < days_until <= warning_days:
            # Send reminder
            SystemNotification.objects.create(
                user=user,
                type='WARNING',
                title='密码即将过期',
                message=f'您的密码将在{days_until}天后过期，请及时修改密码。'
            )
    
    return "Password expiry check completed"


@shared_task
def check_workflow_deadline_reminders():
    """
    Check for workflow tasks with upcoming or overdue deadlines.
    Runs daily at 10 AM.
    
    Sends reminders for:
    1. Overdue approval tasks
    2. Approval tasks with deadline within the next 24 hours
    """
    from .workflow.models import WorkflowTask
    from apps.accounts.models import User
    from .models import Notification
    from .notification_service import NotificationService
    
    now = timezone.now()
    warning_time = now + timedelta(hours=24)
    
    # Find overdue tasks
    overdue_tasks = WorkflowTask.objects.filter(
        deadline__lt=now,
        status='PENDING',
    ).select_related('instance', 'instance__workflow', 'assignee')
    
    # Find tasks with deadline within 24 hours
    upcoming_tasks = WorkflowTask.objects.filter(
        deadline__gte=now,
        deadline__lte=warning_time,
        status='PENDING',
    ).select_related('instance', 'instance__workflow', 'assignee')
    
    if not overdue_tasks.exists() and not upcoming_tasks.exists():
        return "No workflow deadline reminders needed"
    
    # Group by assignee
    assignee_tasks = {}
    
    for task in list(overdue_tasks) + list(upcoming_tasks):
        if task.assignee_id not in assignee_tasks:
            assignee_tasks[task.assignee_id] = {'overdue': [], 'upcoming': []}
        
        is_overdue = task.deadline < now
        task_info = {
            'business_no': task.instance.business_no,
            'business_type': task.instance.workflow.get_business_type_display() if task.instance.workflow else '未知',
            'amount': float(task.instance.amount or 0),
            'deadline': task.deadline.strftime('%Y-%m-%d %H:%M'),
            'hours': abs((task.deadline - now).total_seconds() / 3600)
        }
        
        if is_overdue:
            assignee_tasks[task.assignee_id]['overdue'].append(task_info)
        else:
            assignee_tasks[task.assignee_id]['upcoming'].append(task_info)
    
    # Create notifications for each assignee
    for assignee_id, tasks_data in assignee_tasks.items():
        message_lines = ["您有待处理的审批任务:\n"]
        
        if tasks_data['overdue']:
            message_lines.append("\n【已超时】")
            for t in tasks_data['overdue'][:5]:
                message_lines.append(
                    f"- {t['business_no']} | {t['business_type']} | "
                    f"¥{t['amount']:,.2f} | 已超时{t['hours']:.0f}小时"
                )
        
        if tasks_data['upcoming']:
            message_lines.append("\n【即将超时】")
            for t in tasks_data['upcoming'][:5]:
                message_lines.append(
                    f"- {t['business_no']} | {t['business_type']} | "
                    f"¥{t['amount']:,.2f} | {t['hours']:.0f}小时后超时"
                )
        
        message = "\n".join(message_lines)
        
        Notification.objects.create(
            user_id=assignee_id,
            title='审批任务截止提醒',
            content=message,
            notification_type='WARNING',
            link='/workflow/tasks'
        )
    
    # Send summary to DingTalk/WeChat Work
    try:
        total_overdue = sum(len(t['overdue']) for t in assignee_tasks.values())
        total_upcoming = sum(len(t['upcoming']) for t in assignee_tasks.values())
        
        if total_overdue > 0 or total_upcoming > 0:
            title = "⏰ 审批任务截止提醒"
            markdown_content = f"### {title}\n\n"
            
            if total_overdue > 0:
                markdown_content += f"**⚠️ 已超时**: {total_overdue} 个审批任务\n"
            
            if total_upcoming > 0:
                markdown_content += f"**📅 24小时内到期**: {total_upcoming} 个审批任务\n"
            
            markdown_content += "\n请相关人员及时处理！"
            
            NotificationService.send_custom_notification(title, markdown_content)
    except Exception:
        pass
    
    return f"Sent workflow deadline reminders: {overdue_tasks.count()} overdue, {upcoming_tasks.count()} upcoming"


import io
