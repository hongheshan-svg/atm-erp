from django.contrib import admin
from .models import (
    SalesQuotation, SalesQuotationLine,
    SalesOrder, SalesOrderLine,
    DeliveryOrder, DeliveryOrderLine
)


class SalesQuotationLineInline(admin.TabularInline):
    model = SalesQuotationLine
    extra = 1


@admin.register(SalesQuotation)
class SalesQuotationAdmin(admin.ModelAdmin):
    list_display = ['quote_no', 'customer', 'project', 'quote_date', 'valid_until', 'status', 'version', 'total_amount']
    list_filter = ['status', 'created_at']
    search_fields = ['quote_no']
    inlines = [SalesQuotationLineInline]
    ordering = ['-created_at']


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ['order_no', 'customer', 'project', 'order_date', 'status', 'total_amount']
    list_filter = ['status', 'created_at']
    search_fields = ['order_no']
    inlines = [SalesOrderLineInline]
    ordering = ['-created_at']


class DeliveryOrderLineInline(admin.TabularInline):
    model = DeliveryOrderLine
    extra = 1


@admin.register(DeliveryOrder)
class DeliveryOrderAdmin(admin.ModelAdmin):
    list_display = ['delivery_no', 'so', 'warehouse', 'delivery_date', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['delivery_no']
    inlines = [DeliveryOrderLineInline]
    ordering = ['-created_at']

