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
    
    # Finance daily summary at 6 PM
    'daily-finance-summary': {
        'task': 'apps.finance.tasks.generate_daily_finance_summary',
        'schedule': crontab(hour=18, minute=0),
    },
    
    # Project cost recalculation at 2 AM
    'recalculate-project-costs-nightly': {
        'task': 'apps.reports.tasks.calculate_all_project_costs',
        'schedule': crontab(hour=2, minute=0),
    },
}
