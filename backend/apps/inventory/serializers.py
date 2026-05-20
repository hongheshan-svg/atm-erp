"""
Serializers for inventory app.
"""

from django.db import transaction
from rest_framework import serializers

from .models import Stock, StockAdjustment, StockAdjustmentLine, StockMove


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
            'id',
            'warehouse',
            'warehouse_name',
            'item',
            'item_sku',
            'item_name',
            'item_unit',
            'qty_on_hand',
            'qty_reserved',
            'qty_available',
            'weighted_avg_cost',
            'last_updated',
        ]
        read_only_fields = ['qty_on_hand', 'weighted_avg_cost', 'last_updated']

    def get_qty_available(self, obj):
        return float(obj.qty_available)


class StockMoveSerializer(serializers.ModelSerializer):
    """StockMove serializer."""

    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_code = serializers.CharField(source='item.sku', read_only=True)  # 前端兼容字段
    warehouse_from_name = serializers.CharField(source='warehouse_from.name', read_only=True)
    warehouse_to_name = serializers.CharField(source='warehouse_to.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    move_type_display = serializers.CharField(source='get_move_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    reference_no = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''

    def get_reference_no(self, obj):
        """根据reference_type和reference_id获取关联单号"""
        if not obj.reference_type or not obj.reference_id:
            return ''
        try:
            if obj.reference_type == 'PO':
                from apps.purchase.models import PurchaseOrder

                po = PurchaseOrder.objects.filter(id=obj.reference_id).first()
                return po.order_no if po else ''
            elif obj.reference_type == 'SO':
                from apps.sales.models import SalesOrder

                so = SalesOrder.objects.filter(id=obj.reference_id).first()
                return so.order_no if so else ''
            elif obj.reference_type == 'DO':
                from apps.sales.models import DeliveryOrder

                do = DeliveryOrder.objects.filter(id=obj.reference_id).first()
                return do.delivery_no if do else ''
            elif obj.reference_type == 'ADJ':
                from apps.inventory.models import StockAdjustment

                adj = StockAdjustment.objects.filter(id=obj.reference_id).first()
                return adj.adjustment_no if adj else ''
        except Exception:
            pass
        return f'{obj.reference_type}-{obj.reference_id}'

    class Meta:
        model = StockMove
        fields = [
            'id',
            'move_no',
            'item',
            'item_sku',
            'item_code',
            'item_name',
            'warehouse_from',
            'warehouse_from_name',
            'warehouse_to',
            'warehouse_to_name',
            'qty',
            'unit_cost',
            'move_type',
            'move_type_display',
            'reference_type',
            'reference_id',
            'reference_no',
            'project',
            'project_name',
            'move_date',
            'status',
            'status_display',
            'notes',
            'is_deleted',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
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
            'id',
            'adjustment',
            'item',
            'item_sku',
            'item_name',
            'item_unit',
            'qty_system',
            'qty_actual',
            'qty_diff',
            'cost_impact',
            'notes',
            'is_deleted',
        ]
        read_only_fields = ['qty_diff']


class StockAdjustmentSerializer(serializers.ModelSerializer):
    """StockAdjustment serializer."""

    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)
    cost_impact = serializers.SerializerMethodField()

    class Meta:
        model = StockAdjustment
        fields = [
            'id',
            'adjustment_no',
            'warehouse',
            'warehouse_name',
            'adjustment_date',
            'reason',
            'status',
            'status_display',
            'notes',
            'lines',
            'cost_impact',
            'created_by_name',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['adjustment_no', 'created_at', 'updated_at']

    def get_cost_impact(self, obj):
        return sum(line.cost_impact or 0 for line in obj.lines.all())

    def create(self, validated_data):
        """Create adjustment with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            adjustment = StockAdjustment.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item'):
                    qty_system = float(line_data.get('qty_system', 0))
                    qty_actual = float(line_data.get('qty_actual', 0))
                    qty_diff = qty_actual - qty_system

                    StockAdjustmentLine.objects.create(
                        adjustment=adjustment,
                        item_id=line_data['item'],
                        qty_system=qty_system,
                        qty_actual=qty_actual,
                        qty_diff=qty_diff,
                        notes=line_data.get('notes', ''),
                        created_by=adjustment.created_by,
                    )

        return adjustment

    def update(self, instance, validated_data):
        """Update adjustment with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            # Update adjustment fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Delete old lines and create new ones
            instance.lines.all().delete()

            for line_data in lines_data:
                if line_data.get('item'):
                    qty_system = float(line_data.get('qty_system', 0))
                    qty_actual = float(line_data.get('qty_actual', 0))
                    qty_diff = qty_actual - qty_system

                    StockAdjustmentLine.objects.create(
                        adjustment=instance,
                        item_id=line_data['item'],
                        qty_system=qty_system,
                        qty_actual=qty_actual,
                        qty_diff=qty_diff,
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by,
                    )

        return instance
