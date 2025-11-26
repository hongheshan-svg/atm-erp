"""
URL configuration for masterdata app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ItemCategoryViewSet,
    ItemViewSet,
    CustomerViewSet,
    SupplierViewSet,
    WarehouseViewSet,
    WarehouseLocationViewSet
)

router = DefaultRouter()
router.register(r'categories', ItemCategoryViewSet, basename='category')
router.register(r'items', ItemViewSet, basename='item')
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'locations', WarehouseLocationViewSet, basename='location')

urlpatterns = [
    path('', include(router.urls)),
]

