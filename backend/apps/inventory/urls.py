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

router = DefaultRouter()
router.register(r'stocks', StockViewSet, basename='stock')
router.register(r'moves', StockMoveViewSet, basename='move')
router.register(r'adjustments', StockAdjustmentViewSet, basename='adjustment')
router.register(r'adjustment-lines', StockAdjustmentLineViewSet, basename='adjustment-line')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'batch-moves', BatchMoveViewSet, basename='batch-move')

urlpatterns = [
    path('', include(router.urls)),
]

