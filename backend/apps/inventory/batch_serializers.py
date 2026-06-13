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
    # 初始入库数量（仅创建时写入）：直接设置 qty_on_hand 并生成 IN 流水，补全追溯链。
    initial_qty = serializers.DecimalField(
        max_digits=12, decimal_places=3, write_only=True, required=False, default=0
    )

    class Meta:
        model = Batch
        fields = [
            'id',
            'batch_no',
            'item',
            'item_sku',
            'item_name',
            'warehouse',
            'warehouse_name',
            'manufacture_date',
            'expiry_date',
            'qty_on_hand',
            'initial_qty',
            'unit_cost',
            'supplier_batch_no',
            'quality_status',
            'quality_status_display',
            'is_expired',
            'days_to_expiry',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'qty_on_hand']

    def create(self, validated_data):
        from django.db import transaction

        from .batch_models import BatchMove

        initial_qty = validated_data.pop('initial_qty', 0) or 0
        with transaction.atomic():
            validated_data['qty_on_hand'] = initial_qty
            batch = super().create(validated_data)
            if initial_qty and initial_qty > 0:
                BatchMove.objects.create(
                    batch=batch,
                    move_type='IN',
                    qty=initial_qty,
                    reference_type='BATCH_INIT',
                    reference_id=batch.id,
                    notes='批次初始入库',
                    created_by=validated_data.get('created_by'),
                )
        return batch


class BatchMoveSerializer(serializers.ModelSerializer):
    """Batch move serializer"""

    batch_no = serializers.CharField(source='batch.batch_no', read_only=True)
    move_type_display = serializers.CharField(source='get_move_type_display', read_only=True)

    class Meta:
        model = BatchMove
        fields = [
            'id',
            'batch',
            'batch_no',
            'move_type',
            'move_type_display',
            'qty',
            'reference_type',
            'reference_id',
            'move_date',
            'notes',
        ]
        read_only_fields = ['move_date']
