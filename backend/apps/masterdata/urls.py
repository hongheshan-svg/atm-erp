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
from .customer_follow import (
    CustomerFollowUpViewSet, CustomerReminderViewSet, CustomerContactViewSet
)
from .credit_management import (
    CreditLevelViewSet, CustomerCreditViewSet, CreditAdjustmentViewSet
)

router = DefaultRouter()
router.register(r'categories', ItemCategoryViewSet, basename='category')
router.register(r'items', ItemViewSet, basename='item')
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'locations', WarehouseLocationViewSet, basename='location')

# 客户跟进管理
router.register(r'customer-followups', CustomerFollowUpViewSet, basename='customer-followup')
router.register(r'customer-reminders', CustomerReminderViewSet, basename='customer-reminder')
router.register(r'customer-contacts', CustomerContactViewSet, basename='customer-contact')

# 客户信用管理
router.register(r'credit-levels', CreditLevelViewSet, basename='credit-level')
router.register(r'customer-credits', CustomerCreditViewSet, basename='customer-credit')
router.register(r'credit-adjustments', CreditAdjustmentViewSet, basename='credit-adjustment')

urlpatterns = [
    path('', include(router.urls)),
]

