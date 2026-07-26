from django.core.management import call_command
from django.test import TestCase

from apps.finance.accounting import ChartOfAccount, FiscalPeriod
from apps.finance.models import Currency


class InitFinanceCommandTest(TestCase):
    def test_initialization_is_complete_and_idempotent(self):
        call_command('init_finance', verbosity=0)
        first_counts = (
            ChartOfAccount.objects.filter(is_deleted=False).count(),
            Currency.objects.filter(code='CNY', is_base_currency=True, is_deleted=False).count(),
            FiscalPeriod.objects.filter(status='OPEN', is_deleted=False).count(),
        )

        call_command('init_finance', verbosity=0)

        self.assertEqual(first_counts, (8, 1, 1))
        self.assertEqual(
            (
                ChartOfAccount.objects.filter(is_deleted=False).count(),
                Currency.objects.filter(code='CNY', is_base_currency=True, is_deleted=False).count(),
                FiscalPeriod.objects.filter(status='OPEN', is_deleted=False).count(),
            ),
            first_counts,
        )
