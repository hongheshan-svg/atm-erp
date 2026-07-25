from django.test import TestCase

from apps.core.tasks import check_workflow_deadline_reminders
from apps.finance.tasks import check_payment_schedule_reminders, check_purchase_payment_schedule_reminders
from apps.projects.tasks import (
    check_aftersales_reminders,
    check_project_deadline_reminders,
    check_project_task_reminders,
)
from apps.purchase.tasks import check_delivery_reminders as check_purchase_delivery_reminders
from apps.sales.tasks import check_delivery_reminders as check_sales_delivery_reminders


class ScheduledTaskSmokeTest(TestCase):
    def test_reminder_tasks_run_with_an_empty_database(self):
        tasks = [
            check_workflow_deadline_reminders,
            check_payment_schedule_reminders,
            check_purchase_payment_schedule_reminders,
            check_project_deadline_reminders,
            check_project_task_reminders,
            check_aftersales_reminders,
            check_purchase_delivery_reminders,
            check_sales_delivery_reminders,
        ]

        for task in tasks:
            with self.subTest(task=task.name):
                task.run()
