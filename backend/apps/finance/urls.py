"""
URL configuration for finance app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CurrencyViewSet,
    PaymentViewSet,
    ExpenseViewSet,
    AccountReceivableViewSet,
    AccountPayableViewSet,
    InvoiceViewSet,
    SharedExpenseViewSet,
    SharedExpenseAllocationViewSet,
    PaymentScheduleViewSet
)
from .reconciliation_views import (
    PurchaseReconciliationViewSet,
    SalesReconciliationViewSet,
    InvoiceReconciliationViewSet
)
from .bank_statement_views import (
    BankStatementViewSet,
    BankStatementImportLogViewSet
)

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'receivables', AccountReceivableViewSet, basename='receivable')
router.register(r'payables', AccountPayableViewSet, basename='payable')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'shared-expenses', SharedExpenseViewSet, basename='shared-expense')
router.register(r'allocations', SharedExpenseAllocationViewSet, basename='allocation')

# 对账管理
router.register(r'purchase-reconciliations', PurchaseReconciliationViewSet, basename='purchase-reconciliation')
router.register(r'sales-reconciliations', SalesReconciliationViewSet, basename='sales-reconciliation')
router.register(r'invoice-reconciliations', InvoiceReconciliationViewSet, basename='invoice-reconciliation')

# 银行流水
router.register(r'bank-statements', BankStatementViewSet, basename='bank-statement')
router.register(r'bank-statement-logs', BankStatementImportLogViewSet, basename='bank-statement-log')

# 付款计划
router.register(r'payment-schedules', PaymentScheduleViewSet, basename='payment-schedule')

urlpatterns = [
    path('', include(router.urls)),
]

