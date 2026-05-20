"""
Batch tracking serializers
"""
from rest_framework import serializers

from .batch_models import Batch, BatchMove


class BatchSerializer(serializers.ModelSerializer):
    """Batch serializer"""
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    quality_status_display = serializers.CharField(source='get_quality_status_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model = Batch
        fields = [
            'id', 'batch_no', 'item', 'item_sku', 'item_name',
            'warehouse', 'warehouse_name', 'manufacture_date', 'expiry_date',
            'qty_on_hand', 'unit_cost', 'supplier_batch_no',
            'quality_status', 'quality_status_display', 'is_expired',
            'days_to_expiry', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'qty_on_hand']


class BatchMoveSerializer(serializers.ModelSerializer):
    """Batch move serializer"""
    batch_no = serializers.CharField(source='batch.batch_no', read_only=True)
    move_type_display = serializers.CharField(source='get_move_type_display', read_only=True)

    class Meta:
        model = BatchMove
        fields = [
            'id', 'batch', 'batch_no', 'move_type', 'move_type_display',
            'qty', 'reference_type', 'reference_id', 'move_date', 'notes'
        ]
        read_only_fields = ['move_date']

