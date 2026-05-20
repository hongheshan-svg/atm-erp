from django.contrib import admin

from .models import Customer, Item, ItemCategory, Supplier, Warehouse


@admin.register(ItemCategory)
class ItemCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'sort_order', 'is_deleted']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['code', 'name']
    ordering = ['sort_order', 'code']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'item_type', 'unit', 'standard_cost', 'is_active', 'is_deleted']
    list_filter = ['item_type', 'category', 'is_active', 'is_deleted', 'created_at']
    search_fields = ['sku', 'name', 'specification', 'barcode']
    ordering = ['-created_at']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'contact_person', 'phone', 'status', 'is_deleted']
    list_filter = ['status', 'is_deleted', 'created_at']
    search_fields = ['code', 'name', 'contact_person', 'phone']
    ordering = ['-created_at']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'contact_person', 'phone', 'status', 'is_deleted']
    list_filter = ['status', 'is_deleted', 'created_at']
    search_fields = ['code', 'name', 'contact_person', 'phone']
    ordering = ['-created_at']


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'warehouse_type', 'manager', 'is_active', 'is_deleted']
    list_filter = ['warehouse_type', 'is_active', 'is_deleted', 'created_at']
    search_fields = ['code', 'name', 'location']
    ordering = ['code']

