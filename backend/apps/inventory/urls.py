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

router = DefaultRouter()
router.register(r'stocks', StockViewSet, basename='stock')
router.register(r'moves', StockMoveViewSet, basename='move')
router.register(r'adjustments', StockAdjustmentViewSet, basename='adjustment')
router.register(r'adjustment-lines', StockAdjustmentLineViewSet, basename='adjustment-line')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'batch-moves', BatchMoveViewSet, basename='batch-move')

# 领料/退料管理
router.register(r'requisitions', MaterialRequisitionViewSet, basename='requisition')
router.register(r'requisition-lines', MaterialRequisitionLineViewSet, basename='requisition-line')
router.register(r'returns', MaterialReturnViewSet, basename='return')
router.register(r'return-lines', MaterialReturnLineViewSet, basename='return-line')

urlpatterns = [
    path('', include(router.urls)),
]

