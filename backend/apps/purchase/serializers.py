"""
Serializers for purchase app.
"""
from rest_framework import serializers
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine
)
from .services import BudgetValidationService


class PurchaseRequestLineSerializer(serializers.ModelSerializer):
    """PurchaseRequestLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = PurchaseRequestLine
        fields = [
            'id', 'pr', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'estimated_price', 'line_amount', 'project', 'project_name',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount']


class PurchaseRequestSerializer(serializers.ModelSerializer):
    """PurchaseRequest serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    requestor_name = serializers.CharField(source='requestor.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = PurchaseRequestLineSerializer(many=True, read_only=True)
    budget_info = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'request_no', 'project', 'project_name', 'requestor', 'requestor_name',
            'request_date', 'required_date', 'status', 'status_display', 'total_amount',
            'notes', 'lines', 'is_deleted', 'created_at', 'updated_at', 'budget_info'
        ]
        read_only_fields = ['request_no', 'request_date', 'created_at', 'updated_at']
    
    def get_budget_info(self, obj):
        """Get budget validation info for this request."""
        if not obj.project:
            return None
        return BudgetValidationService.validate_purchase_request(
            obj.project, 
            obj.total_amount,
            exclude_pr_id=obj.id if obj.status in ['APPROVED', 'CONVERTED'] else None
        )


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    """PurchaseOrderLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    remaining_qty = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseOrderLine
        fields = [
            'id', 'po', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'unit_price', 'line_amount', 'received_qty', 'remaining_qty',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount', 'received_qty']
    
    def get_remaining_qty(self, obj):
        return float(obj.qty - obj.received_qty)


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """PurchaseOrder serializer."""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_no', 'supplier', 'supplier_name', 'project', 'project_name',
            'order_date', 'delivery_date', 'status', 'status_display', 'total_amount',
            'payment_terms', 'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order_no', 'order_date', 'created_at', 'updated_at']


class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    """GoodsReceiptLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    quality_status_display = serializers.CharField(source='get_quality_status_display', read_only=True)
    
    class Meta:
        model = GoodsReceiptLine
        fields = [
            'id', 'receipt', 'po_line', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'quality_status', 'quality_status_display', 'notes', 'is_deleted'
        ]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    """GoodsReceipt serializer."""
    po_no = serializers.CharField(source='po.order_no', read_only=True)
    supplier_name = serializers.CharField(source='po.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'receipt_no', 'po', 'po_no', 'supplier_name', 'warehouse', 'warehouse_name',
            'receipt_date', 'status', 'status_display', 'notes', 'lines',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['receipt_no', 'created_at', 'updated_at']

