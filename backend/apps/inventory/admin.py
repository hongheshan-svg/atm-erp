from django.contrib import admin

from .models import Stock, StockAdjustment, StockAdjustmentLine, StockMove


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['warehouse', 'item', 'qty_on_hand', 'qty_reserved', 'weighted_avg_cost', 'last_updated']
    list_filter = ['warehouse', 'last_updated']
    search_fields = ['item__sku', 'item__name']
    ordering = ['warehouse', 'item']


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ['move_no', 'item', 'warehouse_from', 'warehouse_to', 'qty', 'move_type', 'project', 'status', 'move_date']
    list_filter = ['move_type', 'status', 'move_date']
    search_fields = ['move_no', 'item__sku']
    ordering = ['-move_date', '-created_at']


class StockAdjustmentLineInline(admin.TabularInline):
    model = StockAdjustmentLine
    extra = 1


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['adjustment_no', 'warehouse', 'adjustment_date', 'status']
    list_filter = ['status', 'adjustment_date']
    search_fields = ['adjustment_no']
    inlines = [StockAdjustmentLineInline]
    ordering = ['-created_at']

