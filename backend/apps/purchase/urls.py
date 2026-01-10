"""
URL configuration for purchase app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PurchaseRequestViewSet, PurchaseRequestLineViewSet,
    PurchaseOrderViewSet, PurchaseOrderLineViewSet,
    GoodsReceiptViewSet, GoodsReceiptLineViewSet,
    PurchaseContractViewSet
)
from .rfq_views import (
    RFQViewSet, RFQLineViewSet, RFQSupplierViewSet,
    SupplierQuotationViewSet, SupplierQuotationLineViewSet,
    QuotationComparisonViewSet, QuotationScoreViewSet, ItemPriceHistoryViewSet
)
from .outsource_views import (
    OutsourceOrderViewSet, OutsourceOrderLineViewSet,
    OutsourceMaterialIssueViewSet, OutsourceMaterialIssueLineViewSet,
    OutsourceReceiptViewSet, OutsourceReceiptLineViewSet
)
from .evaluation_views import (
    SupplierEvaluationTemplateViewSet, EvaluationCriteriaViewSet,
    SupplierEvaluationViewSet, EvaluationScoreItemViewSet,
    SupplierGradeHistoryViewSet, SupplierBlacklistViewSet
)
from .budget import PurchaseBudgetViewSet, BudgetLineViewSet
from .supplier_qualification import (
    QualificationTypeViewSet, SupplierQualificationViewSet, QualificationReminderViewSet
)
from .contract_execution import (
    ContractExecutionViewSet, DeliveryRecordViewSet, PaymentRecordViewSet, ContractIssueViewSet
)

router = DefaultRouter()
router.register(r'requests', PurchaseRequestViewSet, basename='request')
router.register(r'request-lines', PurchaseRequestLineViewSet, basename='request-line')
router.register(r'orders', PurchaseOrderViewSet, basename='order')
router.register(r'order-lines', PurchaseOrderLineViewSet, basename='order-line')
router.register(r'receipts', GoodsReceiptViewSet, basename='receipt')
router.register(r'receipt-lines', GoodsReceiptLineViewSet, basename='receipt-line')
router.register(r'contracts', PurchaseContractViewSet, basename='contract')
# RFQ endpoints
router.register(r'rfqs', RFQViewSet, basename='rfq')
router.register(r'rfq-lines', RFQLineViewSet, basename='rfq-line')
router.register(r'rfq-suppliers', RFQSupplierViewSet, basename='rfq-supplier')
router.register(r'supplier-quotations', SupplierQuotationViewSet, basename='supplier-quotation')
router.register(r'supplier-quotation-lines', SupplierQuotationLineViewSet, basename='supplier-quotation-line')
# Quotation comparison endpoints
router.register(r'comparisons', QuotationComparisonViewSet, basename='comparison')
router.register(r'comparison-scores', QuotationScoreViewSet, basename='comparison-score')
router.register(r'price-history', ItemPriceHistoryViewSet, basename='price-history')

# 外协加工
router.register(r'outsource-orders', OutsourceOrderViewSet, basename='outsource-order')
router.register(r'outsource-order-lines', OutsourceOrderLineViewSet, basename='outsource-order-line')
router.register(r'outsource-issues', OutsourceMaterialIssueViewSet, basename='outsource-issue')
router.register(r'outsource-issue-lines', OutsourceMaterialIssueLineViewSet, basename='outsource-issue-line')
router.register(r'outsource-receipts', OutsourceReceiptViewSet, basename='outsource-receipt')
router.register(r'outsource-receipt-lines', OutsourceReceiptLineViewSet, basename='outsource-receipt-line')

# 供应商评价管理
router.register(r'evaluation-templates', SupplierEvaluationTemplateViewSet, basename='evaluation-template')
router.register(r'evaluation-criteria', EvaluationCriteriaViewSet, basename='evaluation-criteria')
router.register(r'evaluations', SupplierEvaluationViewSet, basename='evaluation')
router.register(r'evaluation-scores', EvaluationScoreItemViewSet, basename='evaluation-score')
router.register(r'grade-history', SupplierGradeHistoryViewSet, basename='grade-history')
router.register(r'blacklist', SupplierBlacklistViewSet, basename='blacklist')

# 采购预算管理
router.register(r'budgets', PurchaseBudgetViewSet, basename='budget')
router.register(r'budget-lines', BudgetLineViewSet, basename='budget-line')

# 供应商资质管理
router.register(r'qualification-types', QualificationTypeViewSet, basename='qualification-type')
router.register(r'qualifications', SupplierQualificationViewSet, basename='qualification')
router.register(r'qualification-reminders', QualificationReminderViewSet, basename='qualification-reminder')

# 合同执行跟踪
router.register(r'contract-executions', ContractExecutionViewSet, basename='contract-execution')
router.register(r'delivery-records', DeliveryRecordViewSet, basename='delivery-record')
router.register(r'payment-records', PaymentRecordViewSet, basename='payment-record')
router.register(r'contract-issues', ContractIssueViewSet, basename='contract-issue')

urlpatterns = [
    path('', include(router.urls)),
]

