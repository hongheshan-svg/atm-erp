"""
Serializers for masterdata app.
"""
from rest_framework import serializers
from .models import ItemCategory, Item, Customer, Supplier, Warehouse, WarehouseLocation


class ItemCategorySerializer(serializers.ModelSerializer):
    """ItemCategory serializer."""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ItemCategory
        fields = [
            'id', 'code', 'name', 'parent', 'parent_name', 'description',
            'sort_order', 'item_count', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_item_count(self, obj):
        return obj.items.filter(is_deleted=False).count()


class ItemSerializer(serializers.ModelSerializer):
    """Item serializer."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    default_supplier_name = serializers.CharField(source='default_supplier.name', read_only=True)
    item_type_display = serializers.CharField(source='get_item_type_display', read_only=True)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)
    tax_rate_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Item
        fields = [
            'id', 'sku', 'name', 'specification', 
            # 品牌型号
            'brand', 'model', 'manufacturer', 'origin_country',
            'category', 'category_name', 'item_type', 'item_type_display', 
            'unit', 'unit_display',
            # 价格税率
            'standard_cost', 'purchase_price', 'sale_price', 'tax_rate', 'tax_rate_display',
            'default_supplier', 'default_supplier_name',
            # 库存
            'min_stock', 'max_stock', 'safety_stock', 'lead_time',
            # 其他
            'description', 'image', 'barcode', 'weight', 'volume', 'shelf_life',
            'is_active', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_tax_rate_display(self, obj):
        return f"{obj.tax_rate}%"


class CustomerSerializer(serializers.ModelSerializer):
    """Customer serializer."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Customer
        fields = [
            'id', 'code', 'name', 'short_name', 'contact_person', 'phone',
            'email', 'address', 'credit_limit', 'payment_terms',
            # 开票信息
            'invoice_title', 'tax_number', 'bank_name', 'bank_account',
            'registered_address', 'registered_phone',
            'status', 'status_display', 'notes', 'is_deleted',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SupplierSerializer(serializers.ModelSerializer):
    """Supplier serializer."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    code = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'code', 'name', 'short_name', 'contact_person', 'phone',
            'email', 'address', 'payment_terms',
            # 开票信息
            'invoice_title', 'tax_number', 'bank_name', 'bank_account',
            'registered_address', 'registered_phone',
            'status', 'status_display', 'notes', 'is_deleted',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class WarehouseSerializer(serializers.ModelSerializer):
    """Warehouse serializer."""
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    type_display = serializers.CharField(source='get_warehouse_type_display', read_only=True)
    location_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Warehouse
        fields = [
            'id', 'code', 'name', 'warehouse_type', 'type_display', 'address',
            'manager', 'manager_name', 'contact_phone', 'is_active', 'notes',
            'is_deleted', 'created_at', 'updated_at', 'location_count'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_location_count(self, obj):
        return obj.locations.filter(is_deleted=False).count()


class WarehouseLocationSerializer(serializers.ModelSerializer):
    """WarehouseLocation serializer."""
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    type_display = serializers.CharField(source='get_location_type_display', read_only=True)
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WarehouseLocation
        fields = [
            'id', 'warehouse', 'warehouse_name', 'warehouse_code',
            'parent', 'parent_name', 'code', 'name', 'full_path',
            'location_type', 'type_display', 'max_weight', 'max_volume',
            'is_active', 'is_pickable', 'is_storable', 'sort_order', 'notes',
            'is_deleted', 'created_at', 'updated_at', 'children_count'
        ]
        read_only_fields = ['full_path', 'created_at', 'updated_at']
    
    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class WarehouseLocationTreeSerializer(serializers.ModelSerializer):
    """WarehouseLocation serializer with children for tree view."""
    type_display = serializers.CharField(source='get_location_type_display', read_only=True)
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = WarehouseLocation
        fields = [
            'id', 'code', 'name', 'full_path', 'location_type', 'type_display',
            'is_active', 'children'
        ]
    
    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False).order_by('sort_order', 'code')
        return WarehouseLocationTreeSerializer(children, many=True).data

