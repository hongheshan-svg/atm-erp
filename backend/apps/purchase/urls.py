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
    QuotationComparisonViewSet, QuotationScoreViewSet, ItemPriceHistoryViewSet,
    RFQTemplateViewSet, SupplierCapabilityViewSet, SupplierCapabilityMappingViewSet,
    RFQAttachmentViewSet
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
from .outsource_tracking import (
    OutsourceCapabilityViewSet, OutsourceProgressViewSet,
    OutsourceInspectionViewSet, OutsourceClaimViewSet
)
from .supply_chain_collaboration import (
    SupplierPortalUserViewSet, RFQCollaborationViewSet,
    DeliveryCollaborationViewSet, QualityCollaborationViewSet,
    ReconciliationCollaborationViewSet, SupplierNotificationViewSet
)
from .supplier_portal import (
    SupplierAccountViewSet, SupplierOrderViewViewSet, SupplierQualityRecordViewSet,
    SupplierPortalLoginView, SupplierPortalOrdersView, SupplierPortalOrderDetailView,
    SupplierPortalQualityView, SupplierPortalMessagesView, SupplierDashboardView
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
# 询价增强（非标自动化）
router.register(r'rfq-templates', RFQTemplateViewSet, basename='rfq-template')
router.register(r'rfq-attachments', RFQAttachmentViewSet, basename='rfq-attachment')
router.register(r'supplier-capabilities', SupplierCapabilityViewSet, basename='supplier-capability')
router.register(r'supplier-capability-mappings', SupplierCapabilityMappingViewSet, basename='supplier-capability-mapping')

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

# 外协加工跟踪增强
router.register(r'outsource-capabilities', OutsourceCapabilityViewSet, basename='outsource-capability')
router.register(r'outsource-progress', OutsourceProgressViewSet, basename='outsource-progress')
router.register(r'outsource-inspections', OutsourceInspectionViewSet, basename='outsource-inspection')
router.register(r'outsource-claims', OutsourceClaimViewSet, basename='outsource-claim')

# 供应链协同平台
router.register(r'portal-users', SupplierPortalUserViewSet, basename='portal-user')
router.register(r'rfq-collaborations', RFQCollaborationViewSet, basename='rfq-collaboration')
router.register(r'delivery-collaborations', DeliveryCollaborationViewSet, basename='delivery-collaboration')
router.register(r'quality-collaborations', QualityCollaborationViewSet, basename='quality-collaboration')
router.register(r'reconciliations', ReconciliationCollaborationViewSet, basename='reconciliation')
router.register(r'supplier-notifications', SupplierNotificationViewSet, basename='supplier-notification')

# 供应商协同门户增强
router.register(r'supplier-accounts', SupplierAccountViewSet, basename='supplier-account')
router.register(r'supplier-order-views', SupplierOrderViewViewSet, basename='supplier-order-view')
router.register(r'supplier-quality-records', SupplierQualityRecordViewSet, basename='supplier-quality-record')

urlpatterns = [
    path('', include(router.urls)),
    
    # 供应商门户API
    path('supplier-portal/login/', SupplierPortalLoginView.as_view(), name='supplier-portal-login'),
    path('supplier-portal/<int:supplier_id>/orders/', SupplierPortalOrdersView.as_view(), name='supplier-portal-orders'),
    path('supplier-portal/<int:supplier_id>/orders/<int:order_view_id>/', SupplierPortalOrderDetailView.as_view(), name='supplier-portal-order-detail'),
    path('supplier-portal/<int:supplier_id>/quality/', SupplierPortalQualityView.as_view(), name='supplier-portal-quality'),
    path('supplier-portal/<int:supplier_id>/messages/', SupplierPortalMessagesView.as_view(), name='supplier-portal-messages'),
    path('supplier-portal/dashboard/', SupplierDashboardView.as_view(), name='supplier-portal-dashboard'),
]

