"""
Serializers for inventory app.
"""
from rest_framework import serializers
from .models import Stock, StockMove, StockAdjustment, StockAdjustmentLine


class StockSerializer(serializers.ModelSerializer):
    """Stock serializer."""
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    qty_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Stock
        fields = [
            'id', 'warehouse', 'warehouse_name', 'item', 'item_sku', 'item_name',
            'item_unit', 'qty_on_hand', 'qty_reserved', 'qty_available',
            'weighted_avg_cost', 'last_updated'
        ]
        read_only_fields = ['qty_on_hand', 'weighted_avg_cost', 'last_updated']
    
    def get_qty_available(self, obj):
        return float(obj.qty_available)


class StockMoveSerializer(serializers.ModelSerializer):
    """StockMove serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    warehouse_from_name = serializers.CharField(source='warehouse_from.name', read_only=True)
    warehouse_to_name = serializers.CharField(source='warehouse_to.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    move_type_display = serializers.CharField(source='get_move_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = StockMove
        fields = [
            'id', 'move_no', 'item', 'item_sku', 'item_name',
            'warehouse_from', 'warehouse_from_name', 'warehouse_to', 'warehouse_to_name',
            'qty', 'unit_cost', 'move_type', 'move_type_display', 'reference_type',
            'reference_id', 'project', 'project_name', 'move_date', 'status',
            'status_display', 'notes', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['move_no', 'created_at', 'updated_at']


class StockAdjustmentLineSerializer(serializers.ModelSerializer):
    """StockAdjustmentLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    
    class Meta:
        model = StockAdjustmentLine
        fields = [
            'id', 'adjustment', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty_system', 'qty_actual', 'qty_diff', 'cost_impact', 'notes',
            'is_deleted'
        ]
        read_only_fields = ['qty_diff']


class StockAdjustmentSerializer(serializers.ModelSerializer):
    """StockAdjustment serializer."""
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'adjustment_no', 'warehouse', 'warehouse_name', 'adjustment_date',
            'reason', 'status', 'status_display', 'notes', 'lines',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['adjustment_no', 'created_at', 'updated_at']

