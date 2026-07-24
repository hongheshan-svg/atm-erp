import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('erp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    # Inventory alerts - Daily at 8 AM
    'check-low-stock-daily': {
        'task': 'apps.inventory.tasks.check_low_stock_levels',
        'schedule': crontab(hour=8, minute=0),
    },
    # Finance - Overdue checks at 9 AM
    'check-overdue-ar-daily': {
        'task': 'apps.finance.tasks.check_overdue_receivables',
        'schedule': crontab(hour=9, minute=0),
    },
    'check-overdue-ap-daily': {
        'task': 'apps.finance.tasks.check_overdue_payables',
        'schedule': crontab(hour=9, minute=5),
    },
    'check-upcoming-due-dates': {
        'task': 'apps.finance.tasks.check_upcoming_due_dates',
        'schedule': crontab(hour=9, minute=10),
    },
    # Payment schedule reminders at 9:15 AM
    'check-payment-schedule-reminders': {
        'task': 'apps.finance.tasks.check_payment_schedule_reminders',
        'schedule': crontab(hour=9, minute=15),
    },
    'check-purchase-payment-schedule-reminders': {
        'task': 'apps.finance.tasks.check_purchase_payment_schedule_reminders',
        'schedule': crontab(hour=9, minute=20),
    },
    # Sales/Purchase order delivery reminders at 9:30 AM
    'check-sales-delivery-reminders': {
        'task': 'apps.sales.tasks.check_delivery_reminders',
        'schedule': crontab(hour=9, minute=30),
    },
    'check-purchase-delivery-reminders': {
        'task': 'apps.purchase.tasks.check_delivery_reminders',
        'schedule': crontab(hour=9, minute=35),
    },
    # Workflow approval deadline reminders at 10 AM
    'check-workflow-deadline-reminders': {
        'task': 'apps.core.tasks.check_workflow_deadline_reminders',
        'schedule': crontab(hour=10, minute=0),
    },
    # Project deadline reminders at 10:30 AM
    'check-project-deadline-reminders': {
        'task': 'apps.projects.tasks.check_project_deadline_reminders',
        'schedule': crontab(hour=10, minute=30),
    },
    # Project task progress reminders at 10:45 AM
    'check-project-task-reminders': {
        'task': 'apps.projects.tasks.check_project_task_reminders',
        'schedule': crontab(hour=10, minute=45),
    },
    # After-sales order reminders at 11 AM
    'check-aftersales-reminders': {
        'task': 'apps.projects.tasks.check_aftersales_reminders',
        'schedule': crontab(hour=11, minute=0),
    },
    # Reset payment schedule reminders weekly on Monday
    'reset-payment-schedule-reminders': {
        'task': 'apps.finance.tasks.reset_payment_schedule_reminders',
        'schedule': crontab(hour=1, minute=0, day_of_week=1),
    },
    # Finance daily summary at 6 PM
    'daily-finance-summary': {
        'task': 'apps.finance.tasks.generate_daily_finance_summary',
        'schedule': crontab(hour=18, minute=0),
    },
    # 待付款项台账兜底回填(应对信号静默失败场景) - 每天凌晨 2:30
    'backfill-payables-safety-net-daily': {
        'task': 'apps.finance.tasks.backfill_payables_safety_net',
        'schedule': crontab(hour=2, minute=30),
    },
    # Project cost recalculation at 2 AM
    'recalculate-project-costs-nightly': {
        'task': 'apps.reports.tasks.calculate_all_project_costs',
        'schedule': crontab(hour=2, minute=0),
    },
    # Webhook delivery processing - Every minute
    'process-webhook-deliveries': {
        'task': 'apps.core.tasks.process_webhook_deliveries',
        'schedule': crontab(minute='*'),
    },
    # Password expiry check - Daily at 7 AM
    'check-password-expiry-daily': {
        'task': 'apps.core.tasks.check_password_expiry',
        'schedule': crontab(hour=7, minute=0),
    },
    # Log cleanup - Weekly on Sunday at 3 AM
    'cleanup-old-logs-weekly': {
        'task': 'apps.core.tasks.cleanup_old_logs',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
        'kwargs': {'days': 90},
    },
    # ============ 考勤设备同步任务 ============
    # 自动同步考勤设备数据 - 每10分钟
    'sync-attendance-devices': {
        'task': 'apps.oa.tasks.sync_all_attendance_devices',
        'schedule': crontab(minute='*/10'),
    },
    # 处理未处理的打卡记录 - 每5分钟
    'process-attendance-logs': {
        'task': 'apps.oa.tasks.process_unprocessed_attendance_logs',
        'schedule': crontab(minute='*/5'),
    },
    # 考勤设备健康检查 - 每30分钟
    'check-attendance-device-health': {
        'task': 'apps.oa.tasks.check_device_health',
        'schedule': crontab(minute='*/30'),
    },
    # 生成每日考勤报表 - 每天早上7点
    'generate-daily-attendance-report': {
        'task': 'apps.oa.tasks.generate_daily_attendance_report',
        'schedule': crontab(hour=7, minute=0),
    },
    # 清理旧的设备日志 - 每周日凌晨4点
    'cleanup-old-device-logs': {
        'task': 'apps.oa.tasks.cleanup_old_device_logs',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
        'kwargs': {'days': 90},
    },
    # ============ 企业微信考勤同步任务 ============
    # 自动同步企业微信考勤数据 - 每15分钟
    'sync-wechat-work-attendance': {
        'task': 'apps.oa.tasks.sync_wechat_work_attendance',
        'schedule': crontab(minute='*/15'),
    },
}
