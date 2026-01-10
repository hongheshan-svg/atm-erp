"""
设备维保提醒服务
Equipment Maintenance Reminder Service
"""
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from celery import shared_task

from apps.core.models import Notification
from apps.core.notification_service import NotificationService


@shared_task
def check_equipment_maintenance():
    """
    检查设备维保到期提醒
    每天运行一次
    """
    from apps.projects.equipment_models import Equipment, MaintenanceSchedule
    from apps.accounts.models import User
    
    today = timezone.now().date()
    
    # 提前7天提醒
    reminder_days = [7, 3, 1, 0]
    
    results = {
        'warranty_expiring': [],
        'maintenance_due': [],
        'calibration_due': []
    }
    
    # 1. 检查保修到期
    for days in reminder_days:
        check_date = today + timedelta(days=days)
        expiring_equipment = Equipment.objects.filter(
            warranty_end_date=check_date,
            is_deleted=False
        )
        
        for eq in expiring_equipment:
            results['warranty_expiring'].append({
                'equipment': eq.name,
                'code': eq.equipment_no,
                'days_remaining': days
            })
            
            # 发送通知给相关人员
            notify_users = _get_equipment_notify_users(eq)
            for user in notify_users:
                Notification.objects.create(
                    user=user,
                    title=f'设备保修即将到期',
                    message=f'设备 [{eq.equipment_no}] {eq.name} 的保修期将于 {days} 天后到期，请及时处理。',
                    notification_type='WARNING',
                    related_model='Equipment',
                    related_id=eq.id
                )
    
    # 2. 检查维保计划到期
    for days in reminder_days:
        check_date = today + timedelta(days=days)
        due_schedules = MaintenanceSchedule.objects.filter(
            next_maintenance_date=check_date,
            status='PENDING',
            is_deleted=False
        ).select_related('equipment')
        
        for schedule in due_schedules:
            results['maintenance_due'].append({
                'equipment': schedule.equipment.name,
                'code': schedule.equipment.equipment_no,
                'maintenance_type': schedule.maintenance_type,
                'days_remaining': days
            })
            
            # 发送通知
            if schedule.responsible_person:
                Notification.objects.create(
                    user=schedule.responsible_person,
                    title=f'设备维保到期提醒',
                    message=f'设备 [{schedule.equipment.equipment_no}] {schedule.equipment.name} 的{schedule.get_maintenance_type_display()}维保将于 {days} 天后到期。',
                    notification_type='WARNING',
                    related_model='MaintenanceSchedule',
                    related_id=schedule.id
                )
    
    # 3. 检查工装夹具校准到期
    from apps.projects.fixture_models import Fixture
    
    for days in reminder_days:
        check_date = today + timedelta(days=days)
        calibration_due = Fixture.objects.filter(
            next_calibration_date=check_date,
            is_deleted=False
        )
        
        for fixture in calibration_due:
            results['calibration_due'].append({
                'fixture': fixture.name,
                'code': fixture.fixture_no,
                'days_remaining': days
            })
            
            # 发送通知给负责人
            if fixture.responsible_person:
                Notification.objects.create(
                    user=fixture.responsible_person,
                    title=f'工装夹具校准到期提醒',
                    message=f'工装夹具 [{fixture.fixture_no}] {fixture.name} 的校准将于 {days} 天后到期，请安排校准。',
                    notification_type='WARNING',
                    related_model='Fixture',
                    related_id=fixture.id
                )
    
    # 发送汇总通知给管理员
    if any(results.values()):
        _send_summary_notification(results)
    
    return results


def _get_equipment_notify_users(equipment):
    """获取设备相关通知用户"""
    from apps.accounts.models import User
    
    users = []
    
    # 项目相关人员
    if equipment.project:
        if equipment.project.manager:
            users.append(equipment.project.manager)
    
    # 设备管理员（按角色查找）
    equipment_managers = User.objects.filter(
        groups__name__in=['equipment_manager', 'admin'],
        is_active=True
    )
    users.extend(list(equipment_managers))
    
    return list(set(users))


def _send_summary_notification(results):
    """发送汇总通知"""
    from apps.accounts.models import User
    
    summary = []
    
    if results['warranty_expiring']:
        summary.append(f"- {len(results['warranty_expiring'])} 台设备保修即将到期")
    
    if results['maintenance_due']:
        summary.append(f"- {len(results['maintenance_due'])} 项维保计划即将到期")
    
    if results['calibration_due']:
        summary.append(f"- {len(results['calibration_due'])} 个工装夹具需要校准")
    
    if summary:
        message = "设备维保提醒汇总：\n" + "\n".join(summary)
        
        # 通知管理员
        admins = User.objects.filter(
            groups__name__in=['admin', 'equipment_manager'],
            is_active=True
        )
        
        for admin in admins:
            Notification.objects.create(
                user=admin,
                title='设备维保日报',
                message=message,
                notification_type='INFO'
            )


@shared_task
def generate_maintenance_report():
    """
    生成维保状态月报
    每月1号运行
    """
    from apps.projects.equipment_models import Equipment, MaintenanceSchedule
    from apps.projects.fixture_models import Fixture
    
    today = timezone.now().date()
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = today.replace(day=1) - timedelta(days=1)
    
    # 统计上月完成的维保
    completed_maintenance = MaintenanceSchedule.objects.filter(
        status='COMPLETED',
        actual_date__gte=last_month_start,
        actual_date__lte=last_month_end
    ).count()
    
    # 统计超期未完成的维保
    overdue_maintenance = MaintenanceSchedule.objects.filter(
        status='PENDING',
        next_maintenance_date__lt=today
    ).count()
    
    # 统计设备状态
    equipment_stats = Equipment.objects.filter(is_deleted=False).values('status').annotate(
        count=models.Count('id')
    )
    
    # 统计保修状态
    in_warranty = Equipment.objects.filter(
        warranty_end_date__gte=today,
        is_deleted=False
    ).count()
    
    out_of_warranty = Equipment.objects.filter(
        warranty_end_date__lt=today,
        is_deleted=False
    ).count()
    
    report = {
        'period': f'{last_month_start} - {last_month_end}',
        'completed_maintenance': completed_maintenance,
        'overdue_maintenance': overdue_maintenance,
        'equipment_stats': list(equipment_stats),
        'in_warranty': in_warranty,
        'out_of_warranty': out_of_warranty,
        'generated_at': timezone.now().isoformat()
    }
    
    return report
