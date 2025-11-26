"""
URL configuration for purchase app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PurchaseRequestViewSet, PurchaseRequestLineViewSet,
    PurchaseOrderViewSet, PurchaseOrderLineViewSet,
    GoodsReceiptViewSet, GoodsReceiptLineViewSet
)
from .rfq_views import (
    RFQViewSet, RFQLineViewSet, RFQSupplierViewSet,
    SupplierQuotationViewSet, SupplierQuotationLineViewSet
)

router = DefaultRouter()
router.register(r'requests', PurchaseRequestViewSet, basename='request')
router.register(r'request-lines', PurchaseRequestLineViewSet, basename='request-line')
router.register(r'orders', PurchaseOrderViewSet, basename='order')
router.register(r'order-lines', PurchaseOrderLineViewSet, basename='order-line')
router.register(r'receipts', GoodsReceiptViewSet, basename='receipt')
router.register(r'receipt-lines', GoodsReceiptLineViewSet, basename='receipt-line')
# RFQ endpoints
router.register(r'rfqs', RFQViewSet, basename='rfq')
router.register(r'rfq-lines', RFQLineViewSet, basename='rfq-line')
router.register(r'rfq-suppliers', RFQSupplierViewSet, basename='rfq-supplier')
router.register(r'supplier-quotations', SupplierQuotationViewSet, basename='supplier-quotation')
router.register(r'supplier-quotation-lines', SupplierQuotationLineViewSet, basename='supplier-quotation-line')

urlpatterns = [
    path('', include(router.urls)),
]

