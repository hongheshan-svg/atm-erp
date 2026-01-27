"""
URL configuration for inventory app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StockViewSet,
    StockMoveViewSet,
    StockAdjustmentViewSet,
    StockAdjustmentLineViewSet
)
from .batch_views import BatchViewSet, BatchMoveViewSet
from .material_views import (
    MaterialRequisitionViewSet,
    MaterialRequisitionLineViewSet,
    MaterialReturnViewSet,
    MaterialReturnLineViewSet
)
from .cost_accounting import (
    InventoryCostConfigViewSet, ItemCostRecordViewSet, PeriodCostSummaryViewSet
)
from .mrp import MRPPlanViewSet, MRPLineViewSet
from .stock_alert import StockAlertRuleViewSet, StockAlertViewSet
from .spare_parts import (
    SparePartCategoryViewSet, SparePartViewSet, SparePartEquipmentRelationViewSet,
    SparePartConsumptionViewSet, SparePartAlertViewSet
)
from .data_accuracy import (
    DataValidationRuleViewSet, DataValidationResultViewSet,
    ReconciliationSessionViewSet, InventoryAccuracyReportView, InOutBalanceReportView
)

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
router.register(r'spare-part-equipment-relations', SparePartEquipmentRelationViewSet, basename='spare-part-equipment-relation')
router.register(r'spare-part-consumptions', SparePartConsumptionViewSet, basename='spare-part-consumption')
router.register(r'spare-part-alerts', SparePartAlertViewSet, basename='spare-part-alert')

# 数据准确性校验
router.register(r'validation-rules', DataValidationRuleViewSet, basename='validation-rule')
router.register(r'validation-results', DataValidationResultViewSet, basename='validation-result')
router.register(r'reconciliation-sessions', ReconciliationSessionViewSet, basename='reconciliation-session')

urlpatterns = [
    path('', include(router.urls)),
    
    # 数据准确性报表
    path('reports/accuracy/', InventoryAccuracyReportView.as_view(), name='inventory-accuracy-report'),
    path('reports/in-out-balance/', InOutBalanceReportView.as_view(), name='in-out-balance-report'),
]

