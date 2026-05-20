"""
Celery tasks for projects app - deadline reminders and progress alerts.
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def check_project_task_reminders():
    """
    Check for project tasks with upcoming or overdue end dates.
    Runs daily at 10:30 AM.
    
    Sends reminders for:
    1. Overdue tasks (past end date, not yet completed)
    2. Tasks ending within the next 3 days
    3. Tasks with progress behind schedule
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import ProjectTask

    today = timezone.now().date()
    warning_date = today + timedelta(days=3)

    # Find overdue tasks
    overdue_tasks = ProjectTask.objects.filter(
        end_date__lt=today,
        status__in=['TODO', 'IN_PROGRESS'],
        is_deleted=False
    ).select_related('project', 'assignee')

    # Find tasks ending within 3 days
    upcoming_tasks = ProjectTask.objects.filter(
        end_date__gte=today,
        end_date__lte=warning_date,
        status__in=['TODO', 'IN_PROGRESS'],
        is_deleted=False
    ).select_related('project', 'assignee')

    # Find tasks with progress behind schedule (less than 50% progress with more than 50% time elapsed)
    behind_schedule_tasks = []
    in_progress_tasks = ProjectTask.objects.filter(
        status='IN_PROGRESS',
        start_date__isnull=False,
        end_date__isnull=False,
        is_deleted=False
    ).select_related('project', 'assignee')

    for task in in_progress_tasks:
        if task.start_date and task.end_date and task.start_date < today < task.end_date:
            total_days = (task.end_date - task.start_date).days
            elapsed_days = (today - task.start_date).days
            if total_days > 0:
                expected_progress = (elapsed_days / total_days) * 100
                # If actual progress is 20% or more behind expected
                if task.progress_percent < expected_progress - 20:
                    behind_schedule_tasks.append({
                        'task': task,
                        'expected': expected_progress,
                        'actual': task.progress_percent,
                        'gap': expected_progress - task.progress_percent
                    })

    if not overdue_tasks.exists() and not upcoming_tasks.exists() and not behind_schedule_tasks:
        return "No project task reminders needed"

    # Group by assignee
    assignee_reminders = {}

    def add_to_assignee(assignee_id, category, item):
        if assignee_id not in assignee_reminders:
            assignee_reminders[assignee_id] = {'overdue': [], 'upcoming': [], 'behind': []}
        assignee_reminders[assignee_id][category].append(item)

    # Collect overdue tasks
    overdue_items = []
    for task in overdue_tasks:
        days_overdue = (today - task.end_date).days
        item = {
            'project_code': task.project.code,
            'task_name': task.name,
            'days_overdue': days_overdue,
            'progress': task.progress_percent,
            'assignee_name': task.assignee.get_full_name() if task.assignee else '未指定'
        }
        overdue_items.append(item)
        if task.assignee:
            add_to_assignee(task.assignee_id, 'overdue', item)

    # Collect upcoming tasks
    upcoming_items = []
    for task in upcoming_tasks:
        days_until = (task.end_date - today).days
        item = {
            'project_code': task.project.code,
            'task_name': task.name,
            'days_until': days_until,
            'progress': task.progress_percent,
            'assignee_name': task.assignee.get_full_name() if task.assignee else '未指定'
        }
        upcoming_items.append(item)
        if task.assignee:
            add_to_assignee(task.assignee_id, 'upcoming', item)

    # Collect behind schedule tasks
    behind_items = []
    for item_data in behind_schedule_tasks:
        task = item_data['task']
        item = {
            'project_code': task.project.code,
            'task_name': task.name,
            'expected_progress': round(item_data['expected'], 1),
            'actual_progress': task.progress_percent,
            'gap': round(item_data['gap'], 1),
            'assignee_name': task.assignee.get_full_name() if task.assignee else '未指定'
        }
        behind_items.append(item)
        if task.assignee:
            add_to_assignee(task.assignee_id, 'behind', item)

    # Create notifications for each assignee
    for assignee_id, data in assignee_reminders.items():
        message_lines = ["您负责的项目任务提醒:\n"]

        if data['overdue']:
            message_lines.append("\n【已逾期】")
            for item in data['overdue'][:5]:
                message_lines.append(
                    f"- [{item['project_code']}] {item['task_name']} | "
                    f"逾期{item['days_overdue']}天 | 进度{item['progress']}%"
                )

        if data['upcoming']:
            message_lines.append("\n【即将到期】")
            for item in data['upcoming'][:5]:
                message_lines.append(
                    f"- [{item['project_code']}] {item['task_name']} | "
                    f"{item['days_until']}天后到期 | 进度{item['progress']}%"
                )

        if data['behind']:
            message_lines.append("\n【进度落后】")
            for item in data['behind'][:5]:
                message_lines.append(
                    f"- [{item['project_code']}] {item['task_name']} | "
                    f"应完成{item['expected_progress']}% 实际{item['actual_progress']}%"
                )

        message = "\n".join(message_lines)

        Notification.objects.create(
            user_id=assignee_id,
            title='项目任务进度提醒',
            content=message,
            notification_type='WARNING',
            link='/projects/tasks'
        )

    # Also notify project managers
    pm_recipients = User.objects.filter(
        is_active=True,
        is_deleted=False,
        role__code__in=['PROJECT_MANAGER', 'ADMIN']
    ).values_list('id', flat=True)

    summary_message = f"""项目任务进度提醒汇总:

【已逾期任务】{len(overdue_items)} 个
【即将到期任务】{len(upcoming_items)} 个
【进度落后任务】{len(behind_items)} 个
"""

    for user_id in pm_recipients:
        if user_id not in assignee_reminders:  # Don't duplicate notifications
            Notification.objects.create(
                user_id=user_id,
                title='项目任务进度汇总',
                content=summary_message,
                notification_type='INFO',
                link='/projects/tasks'
            )

    # Send to DingTalk/WeChat Work
    try:
        title = "📋 项目任务进度提醒"

        # 群发安全内容（不含具体项目和人员信息）
        safe_content = f"### {title}\n\n"
        if overdue_items:
            safe_content += f"⚠️ **{len(overdue_items)}** 个任务已逾期\n"
        if upcoming_items:
            safe_content += f"📅 **{len(upcoming_items)}** 个任务即将到期\n"
        if behind_items:
            safe_content += f"🔴 **{len(behind_items)}** 个任务进度落后\n"
        safe_content += "\n请登录ERP系统查看详情并及时跟进！"

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f"Sent task reminders: {len(overdue_items)} overdue, {len(upcoming_items)} upcoming, {len(behind_items)} behind"


@shared_task
def check_project_deadline_reminders():
    """
    Check for projects with upcoming or overdue end dates.
    Runs daily at 10:30 AM.
    
    Sends reminders for:
    1. Overdue projects (past end date, not yet completed)
    2. Projects ending within the next 7 days
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import Project

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

        # 群发安全内容（不含具体项目信息）
        safe_content = f"### {title}\n\n"
        if overdue_items:
            safe_content += f"⚠️ **{len(overdue_items)}** 个项目已逾期\n"
        if upcoming_items:
            safe_content += f"📅 **{len(upcoming_items)}** 个项目即将到期\n"
        safe_content += "\n请登录ERP系统查看详情并及时跟进！"

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f"Sent project deadline reminders: {overdue_projects.count()} overdue, {upcoming_projects.count()} upcoming"


@shared_task
def check_aftersales_reminders():
    """
    Check for after-sales orders that need attention.
    Runs daily at 11 AM.
    
    Sends reminders for:
    1. Overdue after-sales orders (past expected date, not resolved)
    2. After-sales orders expected to be completed within 2 days
    3. High priority unassigned orders
    """
    from apps.accounts.models import User
    from apps.core.models import Notification
    from apps.core.notification_service import NotificationService

    from .models import AfterSalesOrder

    today = timezone.now().date()
    warning_date = today + timedelta(days=2)

    # Find overdue after-sales orders
    overdue_orders = AfterSalesOrder.objects.filter(
        expected_date__lt=today,
        status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS', 'ON_SITE', 'WAITING_PARTS'],
        is_deleted=False
    ).select_related('project', 'customer', 'assigned_to')

    # Find orders due within 2 days
    upcoming_orders = AfterSalesOrder.objects.filter(
        expected_date__gte=today,
        expected_date__lte=warning_date,
        status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS', 'ON_SITE', 'WAITING_PARTS'],
        is_deleted=False
    ).select_related('project', 'customer', 'assigned_to')

    # Find high priority unassigned orders
    unassigned_urgent = AfterSalesOrder.objects.filter(
        assigned_to__isnull=True,
        priority__in=['HIGH', 'URGENT'],
        status='PENDING',
        is_deleted=False
    ).select_related('project', 'customer')

    if not overdue_orders.exists() and not upcoming_orders.exists() and not unassigned_urgent.exists():
        return "No after-sales reminders needed"

    # Build items lists
    overdue_items = []
    for order in overdue_orders:
        days_overdue = (today - order.expected_date).days
        overdue_items.append({
            'order_no': order.order_no,
            'title': order.title,
            'customer': order.customer.name,
            'priority': order.get_priority_display(),
            'days_overdue': days_overdue,
            'assignee': order.assigned_to.get_full_name() if order.assigned_to else '未指派'
        })

    upcoming_items = []
    for order in upcoming_orders:
        days_until = (order.expected_date - today).days
        upcoming_items.append({
            'order_no': order.order_no,
            'title': order.title,
            'customer': order.customer.name,
            'priority': order.get_priority_display(),
            'days_until': days_until,
            'assignee': order.assigned_to.get_full_name() if order.assigned_to else '未指派'
        })

    unassigned_items = []
    for order in unassigned_urgent:
        unassigned_items.append({
            'order_no': order.order_no,
            'title': order.title,
            'customer': order.customer.name,
            'priority': order.get_priority_display(),
            'reported_at': order.reported_at.strftime('%Y-%m-%d %H:%M')
        })

    # Build message
    message_lines = ["售后工单提醒:\n"]

    if overdue_items:
        message_lines.append("\n【已逾期】")
        for item in overdue_items[:5]:
            message_lines.append(
                f"- {item['order_no']} | {item['customer']} | "
                f"{item['priority']} | 逾期{item['days_overdue']}天"
            )

    if upcoming_items:
        message_lines.append("\n【即将到期】")
        for item in upcoming_items[:5]:
            message_lines.append(
                f"- {item['order_no']} | {item['customer']} | "
                f"{item['priority']} | {item['days_until']}天后到期"
            )

    if unassigned_items:
        message_lines.append("\n【紧急待指派】")
        for item in unassigned_items[:5]:
            message_lines.append(
                f"- {item['order_no']} | {item['customer']} | {item['priority']}"
            )

    message = "\n".join(message_lines)

    # Get after-sales and admin staff
    recipients = User.objects.filter(
        is_active=True,
        is_deleted=False,
        role__code__in=['AFTER_SALES', 'SERVICE', 'ADMIN']
    ).values_list('id', flat=True)

    # Also notify assigned technicians
    assignee_ids = list(overdue_orders.exclude(assigned_to__isnull=True).values_list('assigned_to_id', flat=True))
    assignee_ids += list(upcoming_orders.exclude(assigned_to__isnull=True).values_list('assigned_to_id', flat=True))
    all_recipients = set(list(recipients) + assignee_ids)

    for user_id in all_recipients:
        Notification.objects.create(
            user_id=user_id,
            title='售后工单提醒',
            content=message,
            notification_type='WARNING',
            link='/projects/aftersales'
        )

    # Send to DingTalk/WeChat Work
    try:
        title = "🔧 售后工单提醒"

        # 群发安全内容（不含具体客户信息）
        safe_content = f"### {title}\n\n"
        if overdue_items:
            safe_content += f"⚠️ **{len(overdue_items)}** 个工单已逾期\n"
        if upcoming_items:
            safe_content += f"📅 **{len(upcoming_items)}** 个工单即将到期\n"
        if unassigned_items:
            safe_content += f"🔴 **{len(unassigned_items)}** 个紧急工单待指派\n"
        safe_content += "\n请登录ERP系统查看详情并及时处理！"

        NotificationService.send_custom_notification(title, safe_content, group_safe_content=safe_content)
    except Exception:
        pass

    return f"Sent after-sales reminders: {len(overdue_items)} overdue, {len(upcoming_items)} upcoming, {len(unassigned_items)} unassigned"

