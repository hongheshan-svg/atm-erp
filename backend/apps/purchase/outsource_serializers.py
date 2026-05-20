"""
外协加工管理序列化器
"""
from django.db import transaction
from rest_framework import serializers

from .outsource_models import (
    OutsourceMaterialIssue,
    OutsourceMaterialIssueLine,
    OutsourceOrder,
    OutsourceOrderLine,
    OutsourceReceipt,
    OutsourceReceiptLine,
)


class OutsourceOrderLineSerializer(serializers.ModelSerializer):
    """外协加工单明细序列化器"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    process_type_display = serializers.CharField(source='get_process_type_display', read_only=True)
    remaining_send_qty = serializers.SerializerMethodField()
    remaining_receive_qty = serializers.SerializerMethodField()

    class Meta:
        model = OutsourceOrderLine
        fields = [
            'id', 'outsource_order', 'item', 'item_name', 'item_sku',
            'process_type', 'process_type_display', 'process_content', 'drawing_no',
            'qty', 'unit_price', 'process_amount',
            'material_provided', 'material_weight',
            'sent_qty', 'received_qty', 'remaining_send_qty', 'remaining_receive_qty',
            'required_date', 'notes', 'is_deleted'
        ]
        read_only_fields = ['process_amount', 'sent_qty', 'received_qty']

    def get_remaining_send_qty(self, obj):
        return float(obj.qty - obj.sent_qty)

    def get_remaining_receive_qty(self, obj):
        return float(obj.sent_qty - obj.received_qty)


class OutsourceOrderSerializer(serializers.ModelSerializer):
    """外协加工单序列化器"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = OutsourceOrderLineSerializer(many=True, read_only=True)
    lines_count = serializers.SerializerMethodField()

    class Meta:
        model = OutsourceOrder
        fields = [
            'id', 'order_no', 'supplier', 'supplier_name', 'project', 'project_name',
            'order_date', 'required_date', 'total_amount', 'tax_rate', 'tax_amount', 'total_with_tax',
            'status', 'status_display', 'contact_person', 'contact_phone', 'delivery_address',
            'notes', 'lines', 'lines_count', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order_no', 'order_date', 'total_amount', 'tax_amount', 'total_with_tax', 'created_at', 'updated_at']

    def get_lines_count(self, obj):
        return obj.lines.filter(is_deleted=False).count()

    def create(self, validated_data):
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            order = OutsourceOrder.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    OutsourceOrderLine.objects.create(
                        outsource_order=order,
                        item_id=line_data['item'],
                        process_type=line_data.get('process_type', 'OTHER'),
                        process_content=line_data.get('process_content', ''),
                        drawing_no=line_data.get('drawing_no', ''),
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        material_provided=line_data.get('material_provided', True),
                        material_weight=line_data.get('material_weight', 0),
                        required_date=line_data.get('required_date'),
                        notes=line_data.get('notes', ''),
                        created_by=order.created_by
                    )

            order.update_totals()

        return order

    def update(self, instance, validated_data):
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # 重建明细
            instance.lines.all().delete()

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    OutsourceOrderLine.objects.create(
                        outsource_order=instance,
                        item_id=line_data['item'],
                        process_type=line_data.get('process_type', 'OTHER'),
                        process_content=line_data.get('process_content', ''),
                        drawing_no=line_data.get('drawing_no', ''),
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        material_provided=line_data.get('material_provided', True),
                        material_weight=line_data.get('material_weight', 0),
                        required_date=line_data.get('required_date'),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )

            instance.update_totals()

        return instance


class OutsourceMaterialIssueLineSerializer(serializers.ModelSerializer):
    """外协发料单明细序列化器"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)

    class Meta:
        model = OutsourceMaterialIssueLine
        fields = [
            'id', 'issue', 'outsource_line', 'item', 'item_name', 'item_sku',
            'qty', 'weight', 'notes', 'is_deleted'
        ]


class OutsourceMaterialIssueSerializer(serializers.ModelSerializer):
    """外协发料单序列化器"""
    outsource_order_no = serializers.CharField(source='outsource_order.order_no', read_only=True)
    supplier_name = serializers.CharField(source='outsource_order.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = OutsourceMaterialIssueLineSerializer(many=True, read_only=True)

    class Meta:
        model = OutsourceMaterialIssue
        fields = [
            'id', 'issue_no', 'outsource_order', 'outsource_order_no', 'supplier_name',
            'warehouse', 'warehouse_name', 'issue_date', 'status', 'status_display',
            'logistics_company', 'tracking_number', 'notes', 'lines',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['issue_no', 'created_at', 'updated_at']

    def create(self, validated_data):
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            issue = OutsourceMaterialIssue.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    OutsourceMaterialIssueLine.objects.create(
                        issue=issue,
                        outsource_line_id=line_data.get('outsource_line'),
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        weight=line_data.get('weight', 0),
                        notes=line_data.get('notes', ''),
                        created_by=issue.created_by
                    )

        return issue


class OutsourceReceiptLineSerializer(serializers.ModelSerializer):
    """外协收货单明细序列化器"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    quality_status_display = serializers.CharField(source='get_quality_status_display', read_only=True)

    class Meta:
        model = OutsourceReceiptLine
        fields = [
            'id', 'receipt', 'outsource_line', 'item', 'item_name', 'item_sku',
            'qty', 'qualified_qty', 'rejected_qty',
            'quality_status', 'quality_status_display', 'quality_notes', 'notes', 'is_deleted'
        ]


class OutsourceReceiptSerializer(serializers.ModelSerializer):
    """外协收货单序列化器"""
    outsource_order_no = serializers.CharField(source='outsource_order.order_no', read_only=True)
    supplier_name = serializers.CharField(source='outsource_order.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    quality_status_display = serializers.CharField(source='get_quality_status_display', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    lines = OutsourceReceiptLineSerializer(many=True, read_only=True)

    class Meta:
        model = OutsourceReceipt
        fields = [
            'id', 'receipt_no', 'outsource_order', 'outsource_order_no', 'supplier_name',
            'warehouse', 'warehouse_name', 'receipt_date', 'status', 'status_display',
            'quality_status', 'quality_status_display',
            'inspector', 'inspector_name', 'inspect_date', 'inspect_notes',
            'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['receipt_no', 'created_at', 'updated_at']

    def create(self, validated_data):
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            receipt = OutsourceReceipt.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    OutsourceReceiptLine.objects.create(
                        receipt=receipt,
                        outsource_line_id=line_data.get('outsource_line'),
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        qualified_qty=line_data.get('qualified_qty', 0),
                        rejected_qty=line_data.get('rejected_qty', 0),
                        quality_status=line_data.get('quality_status', 'PENDING'),
                        quality_notes=line_data.get('quality_notes', ''),
                        notes=line_data.get('notes', ''),
                        created_by=receipt.created_by
                    )

        return receipt

