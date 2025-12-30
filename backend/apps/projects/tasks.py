"""
Celery tasks for projects app - deadline reminders.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def check_project_deadline_reminders():
    """
    Check for projects with upcoming or overdue end dates.
    Runs daily at 10:30 AM.
    
    Sends reminders for:
    1. Overdue projects (past end date, not yet completed)
    2. Projects ending within the next 7 days
    """
    from .models import Project
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService
    
    today = timezone.now().date()
    warning_date = today + timedelta(days=7)
    
    # Find overdue projects
    overdue_projects = Project.objects.filter(
        end_date__lt=today,
        status__in=['ACTIVE', 'PLANNING'],
        is_deleted=False
    ).select_related('customer', 'manager')
    
    # Find projects ending within 7 days
    upcoming_projects = Project.objects.filter(
        end_date__gte=today,
        end_date__lte=warning_date,
        status__in=['ACTIVE', 'PLANNING'],
        is_deleted=False
    ).select_related('customer', 'manager')
    
    if not overdue_projects.exists() and not upcoming_projects.exists():
        return "No project deadline reminders needed"
    
    # Build message
    message_lines = ["项目截止日期提醒:\n"]
    overdue_items = []
    upcoming_items = []
    
    if overdue_projects.exists():
        message_lines.append("\n【已逾期】")
        for project in overdue_projects[:10]:
            days_overdue = (today - project.end_date).days
            manager_name = project.manager.get_full_name() if project.manager else '未指定'
            message_lines.append(
                f"- {project.code} | {project.name} | "
                f"负责人: {manager_name} | 逾期{days_overdue}天"
            )
            overdue_items.append({
                'code': project.code,
                'name': project.name,
                'manager': manager_name,
                'days_overdue': days_overdue
            })
    
    if upcoming_projects.exists():
        message_lines.append("\n【即将到期】")
        for project in upcoming_projects[:10]:
            days_until = (project.end_date - today).days
            manager_name = project.manager.get_full_name() if project.manager else '未指定'
            message_lines.append(
                f"- {project.code} | {project.name} | "
                f"负责人: {manager_name} | {days_until}天后到期"
            )
            upcoming_items.append({
                'code': project.code,
                'name': project.name,
                'manager': manager_name,
                'days_until': days_until
            })
    
    message = "\n".join(message_lines)
    
    # Get project managers and admins
    recipients = User.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        role__code__in=['PROJECT_MANAGER', 'ADMIN']
    ).values_list('id', flat=True)
    
    # Also notify specific project managers
    manager_ids = list(overdue_projects.exclude(manager__isnull=True).values_list('manager_id', flat=True))
    manager_ids += list(upcoming_projects.exclude(manager__isnull=True).values_list('manager_id', flat=True))
    all_recipients = set(list(recipients) + manager_ids)
    
    # Create in-app notifications
    for user_id in all_recipients:
        Notification.objects.create(
            user_id=user_id,
            title='项目截止日期提醒',
            content=message,
            notification_type='WARNING',
            link='/projects'
        )
    
    # Send to DingTalk/WeChat Work
    try:
        title = "📋 项目截止日期提醒"
        markdown_content = f"### {title}\n\n"
        
        if overdue_items:
            markdown_content += f"#### ⚠️ 已逾期 ({len(overdue_items)}个)\n"
            for item in overdue_items[:5]:
                markdown_content += f"- **{item['code']}** {item['name']}\n  - 负责人: {item['manager']} | 逾期{item['days_overdue']}天\n"
            if len(overdue_items) > 5:
                markdown_content += f"  ... 还有 {len(overdue_items) - 5} 个\n"
        
        if upcoming_items:
            markdown_content += f"\n#### 📅 即将到期 ({len(upcoming_items)}个)\n"
            for item in upcoming_items[:5]:
                markdown_content += f"- **{item['code']}** {item['name']}\n  - 负责人: {item['manager']} | {item['days_until']}天后\n"
            if len(upcoming_items) > 5:
                markdown_content += f"  ... 还有 {len(upcoming_items) - 5} 个\n"
        
        markdown_content += "\n请及时跟进项目进度！"
        
        NotificationService.send_custom_notification(title, markdown_content)
    except Exception:
        pass
    
    return f"Sent project deadline reminders: {overdue_projects.count()} overdue, {upcoming_projects.count()} upcoming"

