"""
URL configuration for finance app.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.purchase.budget import BudgetLineViewSet, PurchaseBudgetViewSet

from .accounting import (
    AccountBalanceViewSet,
    AccountCategoryViewSet,
    ChartOfAccountViewSet,
    FiscalPeriodViewSet,
    JournalVoucherViewSet,
)
from .asset import (
    AssetCategoryViewSet,
    AssetDepreciationViewSet,
    AssetDisposalViewSet,
    AssetTransferViewSet,
    FixedAssetViewSet,
)
from .bank_statement_views import BankStatementImportLogViewSet, BankStatementViewSet
from .collection_views import (
    CollectionMilestoneViewSet,
    CollectionPlanViewSet,
    CollectionRecordViewSet,
    CollectionReminderViewSet,
)
from .reconciliation_views import (
    InvoiceReconciliationViewSet,
    PurchaseReconciliationViewSet,
    SalesReconciliationViewSet,
)
from .tax_management import TaxDeclarationViewSet, TaxInvoiceViewSet, TaxPeriodViewSet, TaxRateViewSet, TaxTypeViewSet
from .views import (
    AccountPayableViewSet,
    AccountReceivableViewSet,
    CurrencyViewSet,
    ExpenseViewSet,
    InvoiceViewSet,
    PaymentRequestViewSet,
    PaymentScheduleViewSet,
    PaymentViewSet,
    PurchasePaymentScheduleViewSet,
    SharedExpenseAllocationViewSet,
    SharedExpenseViewSet,
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
router.register(r'purchase-payment-schedules', PurchasePaymentScheduleViewSet, basename='purchase-payment-schedule')

# 付款申请
router.register(r'payment-requests', PaymentRequestViewSet, basename='payment-request')

# 回款计划
router.register(r'collection-plans', CollectionPlanViewSet, basename='collection-plan')
router.register(r'collection-milestones', CollectionMilestoneViewSet, basename='collection-milestone')
router.register(r'collection-records', CollectionRecordViewSet, basename='collection-record')
router.register(r'collection-reminders', CollectionReminderViewSet, basename='collection-reminder')

# 固定资产管理
router.register(r'asset-categories', AssetCategoryViewSet, basename='asset-category')
router.register(r'fixed-assets', FixedAssetViewSet, basename='fixed-asset')
router.register(r'asset-transfers', AssetTransferViewSet, basename='asset-transfer')
router.register(r'asset-disposals', AssetDisposalViewSet, basename='asset-disposal')
router.register(r'asset-depreciations', AssetDepreciationViewSet, basename='asset-depreciation')

# 总账管理
router.register(r'account-categories', AccountCategoryViewSet, basename='account-category')
router.register(r'chart-of-accounts', ChartOfAccountViewSet, basename='chart-of-account')
router.register(r'fiscal-periods', FiscalPeriodViewSet, basename='fiscal-period')
router.register(r'journal-vouchers', JournalVoucherViewSet, basename='journal-voucher')
router.register(r'account-balances', AccountBalanceViewSet, basename='account-balance')

# 税务管理
router.register(r'tax-types', TaxTypeViewSet, basename='tax-type')
router.register(r'tax-rates', TaxRateViewSet, basename='tax-rate')
router.register(r'tax-periods', TaxPeriodViewSet, basename='tax-period')
router.register(r'tax-declarations', TaxDeclarationViewSet, basename='tax-declaration')
router.register(r'tax-invoices', TaxInvoiceViewSet, basename='tax-invoice')

# 预算管理
router.register(r'budgets', PurchaseBudgetViewSet, basename='budget')
router.register(r'budget-lines', BudgetLineViewSet, basename='budget-line')

urlpatterns = [
    path('', include(router.urls)),
]
