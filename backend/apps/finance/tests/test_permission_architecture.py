from django.test import SimpleTestCase

from apps.finance.views import PaymentScheduleViewSet


class FinancePermissionArchitectureTests(SimpleTestCase):
    def test_payment_schedule_declares_permission_resource(self):
        self.assertEqual(PaymentScheduleViewSet.permission_module, 'finance')
        self.assertEqual(PaymentScheduleViewSet.permission_resource, 'payment_schedule')
