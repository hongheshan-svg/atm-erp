"""
URL configuration for sales app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SalesQuotationViewSet, SalesQuotationLineViewSet,
    SalesOrderViewSet, SalesOrderLineViewSet,
    DeliveryOrderViewSet, DeliveryOrderLineViewSet
)

router = DefaultRouter()
router.register(r'quotations', SalesQuotationViewSet, basename='quotation')
router.register(r'quotation-lines', SalesQuotationLineViewSet, basename='quotation-line')
router.register(r'orders', SalesOrderViewSet, basename='order')
router.register(r'order-lines', SalesOrderLineViewSet, basename='order-line')
router.register(r'deliveries', DeliveryOrderViewSet, basename='delivery')
router.register(r'delivery-lines', DeliveryOrderLineViewSet, basename='delivery-line')

urlpatterns = [
    path('', include(router.urls)),
]

