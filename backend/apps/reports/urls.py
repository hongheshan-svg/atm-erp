"""
URL configuration for reports app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('profitability/', views.project_profitability, name='project-profitability'),
    path('cost-detail/', views.project_cost_detail, name='project-cost-detail'),
    path('refresh-cache/', views.refresh_project_cache, name='refresh-cache'),
    path('dashboard/', views.dashboard_summary, name='dashboard-summary'),
    path('inventory-turnover/', views.inventory_turnover_report, name='inventory-turnover'),
    path('purchase-price-trend/', views.purchase_price_trend_report, name='purchase-price-trend'),
    path('aging/', views.aging_report, name='aging-report'),
]

