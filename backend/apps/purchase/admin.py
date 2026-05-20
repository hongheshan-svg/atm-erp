from django.contrib import admin

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
)


class PurchaseRequestLineInline(admin.TabularInline):
    model = PurchaseRequestLine
    extra = 1


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ['request_no', 'project', 'requestor', 'request_date', 'status', 'total_amount']
    list_filter = ['status', 'created_at']
    search_fields = ['request_no']
    inlines = [PurchaseRequestLineInline]
    ordering = ['-created_at']


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['order_no', 'supplier', 'project', 'order_date', 'status', 'total_amount']
    list_filter = ['status', 'created_at']
    search_fields = ['order_no']
    inlines = [PurchaseOrderLineInline]
    ordering = ['-created_at']


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 1


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_no', 'po', 'warehouse', 'receipt_date', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['receipt_no']
    inlines = [GoodsReceiptLineInline]
    ordering = ['-created_at']

