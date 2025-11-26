"""
Serializers for sales app.
"""
from rest_framework import serializers
from .models import (
    SalesQuotation, SalesQuotationLine,
    SalesOrder, SalesOrderLine,
    DeliveryOrder, DeliveryOrderLine
)


class SalesQuotationLineSerializer(serializers.ModelSerializer):
    """SalesQuotationLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    
    class Meta:
        model = SalesQuotationLine
        fields = [
            'id', 'quotation', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'unit_price', 'line_amount', 'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount']


class SalesQuotationSerializer(serializers.ModelSerializer):
    """SalesQuotation serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = SalesQuotationLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = SalesQuotation
        fields = [
            'id', 'quote_no', 'customer', 'customer_name', 'project', 'project_name',
            'quote_date', 'valid_until', 'status', 'status_display', 'version',
            'total_amount', 'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['quote_no', 'quote_date', 'created_at', 'updated_at']


class SalesOrderLineSerializer(serializers.ModelSerializer):
    """SalesOrderLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    remaining_qty = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesOrderLine
        fields = [
            'id', 'so', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'unit_price', 'line_amount', 'delivered_qty', 'remaining_qty',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount', 'delivered_qty']
    
    def get_remaining_qty(self, obj):
        return float(obj.qty - obj.delivered_qty)


class SalesOrderSerializer(serializers.ModelSerializer):
    """SalesOrder serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = SalesOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_no', 'customer', 'customer_name', 'project', 'project_name',
            'order_date', 'delivery_date', 'status', 'status_display', 'total_amount',
            'payment_terms', 'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order_no', 'order_date', 'created_at', 'updated_at']


class DeliveryOrderLineSerializer(serializers.ModelSerializer):
    """DeliveryOrderLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    
    class Meta:
        model = DeliveryOrderLine
        fields = [
            'id', 'delivery', 'so_line', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'notes', 'is_deleted'
        ]


class DeliveryOrderSerializer(serializers.ModelSerializer):
    """DeliveryOrder serializer."""
    so_no = serializers.CharField(source='so.order_no', read_only=True)
    customer_name = serializers.CharField(source='so.customer.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = DeliveryOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = DeliveryOrder
        fields = [
            'id', 'delivery_no', 'so', 'so_no', 'customer_name', 'warehouse', 'warehouse_name',
            'delivery_date', 'status', 'status_display', 'notes', 'lines',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['delivery_no', 'created_at', 'updated_at']

