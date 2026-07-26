import calendar
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.analytics.services import CashFlowForecastService
from apps.finance.models import AccountPayable, AccountReceivable, Expense
from apps.masterdata.models import Customer, Supplier


class CashFlowForecastServiceTest(TestCase):
    def setUp(self):
        from apps.finance.accounting import FiscalPeriod
        from apps.finance.posting import seed_standard_accounts

        self.today = timezone.localdate()
        seed_standard_accounts()
        FiscalPeriod.objects.create(
            year=self.today.year,
            period=self.today.month,
            start_date=date(self.today.year, self.today.month, 1),
            end_date=date(
                self.today.year,
                self.today.month,
                calendar.monthrange(self.today.year, self.today.month)[1],
            ),
            status='OPEN',
        )
        self.customer = Customer.objects.create(code='CASH-CUSTOMER', name='现金流客户')
        self.supplier = Supplier.objects.create(code='CASH-SUPPLIER', name='现金流供应商')
        self.user = get_user_model().objects.create_user(username='cash-flow-user')

        AccountReceivable.objects.create(
            ar_no='AR-CASH-1',
            customer=self.customer,
            invoice_date=self.today,
            due_date=self.today + timedelta(days=10),
            amount_due=Decimal('1000.00'),
            amount_paid=Decimal('100.00'),
        )
        AccountReceivable.objects.create(
            ar_no='AR-CASH-2',
            customer=self.customer,
            invoice_date=self.today,
            due_date=self.today + timedelta(days=45),
            amount_due=Decimal('500.00'),
        )
        AccountPayable.objects.create(
            ap_no='AP-CASH-1',
            supplier=self.supplier,
            invoice_date=self.today,
            due_date=self.today + timedelta(days=20),
            amount_due=Decimal('600.00'),
            amount_paid=Decimal('100.00'),
        )
        expense = Expense.objects.create(
            expense_no='EXP-CASH-1',
            user=self.user,
            expense_date=self.today - timedelta(days=30),
            category='OTHER',
            amount=Decimal('900.00'),
            description='现金流预测历史费用',
            status='DRAFT',
        )
        Expense.objects.filter(pk=expense.pk).update(status='APPROVED')

    @patch('apps.finance.financial_statements.cash_flow')
    def test_uses_posted_cash_and_prorates_historical_expenses(self, cash_flow_mock):
        cash_flow_mock.return_value = {'closing_cash': Decimal('2500.00')}

        forecast = CashFlowForecastService.forecast_next_30_days(days=30)

        self.assertEqual(forecast['current_balance'], 2500.0)
        self.assertEqual(forecast['expected_inflows'], 900.0)
        self.assertEqual(forecast['breakdown']['payables'], 500.0)
        self.assertEqual(forecast['breakdown']['expenses'], 300.0)
        self.assertEqual(forecast['expected_outflows'], 800.0)
        self.assertEqual(forecast['net_cash_flow'], 100.0)

    @patch('apps.finance.financial_statements.cash_flow')
    def test_requested_horizon_changes_due_items_and_expense_projection(self, cash_flow_mock):
        cash_flow_mock.return_value = {'closing_cash': Decimal('0.00')}

        forecast = CashFlowForecastService.forecast_next_30_days(days=60)

        self.assertEqual(forecast['expected_inflows'], 1400.0)
        self.assertEqual(forecast['breakdown']['expenses'], 600.0)
        self.assertEqual(forecast['period']['end'], (self.today + timedelta(days=60)).isoformat())
