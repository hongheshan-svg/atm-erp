"""
URL configuration for finance app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CurrencyViewSet,
    PaymentViewSet,
    ExpenseViewSet,
    AccountReceivableViewSet,
    AccountPayableViewSet,
    InvoiceViewSet,
    SharedExpenseViewSet,
    SharedExpenseAllocationViewSet
)

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'receivables', AccountReceivableViewSet, basename='receivable')
router.register(r'payables', AccountPayableViewSet, basename='payable')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'shared-expenses', SharedExpenseViewSet, basename='shared-expense')
router.register(r'allocations', SharedExpenseAllocationViewSet, basename='allocation')

urlpatterns = [
    path('', include(router.urls)),
]

