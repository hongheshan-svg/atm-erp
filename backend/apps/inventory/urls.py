"""
URL configuration for inventory app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .batch_views import BatchMoveViewSet, BatchViewSet
from .cost_accounting import InventoryCostConfigViewSet, ItemCostRecordViewSet, PeriodCostSummaryViewSet
from .data_accuracy import (
    DataValidationResultViewSet,
    DataValidationRuleViewSet,
    InOutBalanceReportView,
    InventoryAccuracyReportView,
    ReconciliationSessionViewSet,
)
from .material_views import (
    MaterialRequisitionLineViewSet,
    MaterialRequisitionViewSet,
    MaterialReturnLineViewSet,
    MaterialReturnViewSet,
)
from .mrp import MRPLineViewSet, MRPPlanViewSet
from .spare_parts import (
    SparePartAlertViewSet,
    SparePartCategoryViewSet,
    SparePartConsumptionViewSet,
    SparePartEquipmentRelationViewSet,
    SparePartViewSet,
)
from .spare_parts_prediction import LifecyclePredictionView, PurchaseSuggestionView, SparePartCostAnalysisView
from .stock_alert import StockAlertRuleViewSet, StockAlertViewSet
from .views import StockAdjustmentLineViewSet, StockAdjustmentViewSet, StockMoveViewSet, StockViewSet

router = DefaultRouter()
router.register(r'stocks', StockViewSet, basename='stock')
router.register(r'moves', StockMoveViewSet, basename='move')
router.register(r'stock-moves', StockMoveViewSet, basename='stock-move')  # 别名
router.register(r'adjustments', StockAdjustmentViewSet, basename='adjustment')
router.register(r'stock-adjustments', StockAdjustmentViewSet, basename='stock-adjustment')  # 别名
router.register(r'adjustment-lines', StockAdjustmentLineViewSet, basename='adjustment-line')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'batch-moves', BatchMoveViewSet, basename='batch-move')

# 领料/退料管理
router.register(r'requisitions', MaterialRequisitionViewSet, basename='requisition')
router.register(r'requisition-lines', MaterialRequisitionLineViewSet, basename='requisition-line')
router.register(r'returns', MaterialReturnViewSet, basename='return')
router.register(r'return-lines', MaterialReturnLineViewSet, basename='return-line')

# 库存成本核算
router.register(r'cost-configs', InventoryCostConfigViewSet, basename='cost-config')
router.register(r'cost-records', ItemCostRecordViewSet, basename='cost-record')
router.register(r'period-summaries', PeriodCostSummaryViewSet, basename='period-summary')

# MRP物料需求计划
router.register(r'mrp-plans', MRPPlanViewSet, basename='mrp-plan')
router.register(r'mrp-lines', MRPLineViewSet, basename='mrp-line')

# 库存预警
router.register(r'stock-alert-rules', StockAlertRuleViewSet, basename='stock-alert-rule')
router.register(r'stock-alerts', StockAlertViewSet, basename='stock-alert')

# 备件管理增强
router.register(r'spare-part-categories', SparePartCategoryViewSet, basename='spare-part-category')
router.register(r'spare-parts', SparePartViewSet, basename='spare-part')
router.register(
    r'spare-part-equipment-relations', SparePartEquipmentRelationViewSet, basename='spare-part-equipment-relation'
)
router.register(r'spare-part-consumptions', SparePartConsumptionViewSet, basename='spare-part-consumption')
router.register(r'spare-part-alerts', SparePartAlertViewSet, basename='spare-part-alert')

# 数据准确性校验
router.register(r'validation-rules', DataValidationRuleViewSet, basename='validation-rule')
router.register(r'validation-results', DataValidationResultViewSet, basename='validation-result')
router.register(r'reconciliation-sessions', ReconciliationSessionViewSet, basename='reconciliation-session')

urlpatterns = [
    # NOTE: 这些具体路径必须在 router 之前，否则 router 的 spare-parts/<pk>/ 会先匹配，
    # 把 lifecycle-prediction 之类的当成 pk 处理导致 404。
    # 备件智能预测
    path('spare-parts/lifecycle-prediction/', LifecyclePredictionView.as_view(), name='lifecycle-prediction'),
    path('spare-parts/purchase-suggestions/', PurchaseSuggestionView.as_view(), name='purchase-suggestions'),
    path('spare-parts/cost-analysis/', SparePartCostAnalysisView.as_view(), name='spare-part-cost-analysis'),
    # 数据准确性报表
    path('reports/accuracy/', InventoryAccuracyReportView.as_view(), name='inventory-accuracy-report'),
    path('reports/in-out-balance/', InOutBalanceReportView.as_view(), name='in-out-balance-report'),
    path('', include(router.urls)),
]
