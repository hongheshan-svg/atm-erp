"""
RFQ serializers
"""
from rest_framework import serializers
from .rfq_models import RFQ, RFQLine, RFQSupplier, SupplierQuotation, SupplierQuotationLine


class RFQLineSerializer(serializers.ModelSerializer):
    """RFQ line serializer"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    
    class Meta:
        model = RFQLine
        fields = [
            'id', 'rfq', 'item', 'item_name', 'item_sku', 'qty',
            'required_date', 'specifications', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RFQSupplierSerializer(serializers.ModelSerializer):
    """RFQ supplier serializer"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
    class Meta:
        model = RFQSupplier
        fields = [
            'id', 'rfq', 'supplier', 'supplier_name', 'sent_date',
            'is_responded', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'sent_date']


class RFQSerializer(serializers.ModelSerializer):
    """RFQ serializer"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = RFQLineSerializer(many=True, read_only=True)
    supplier_rfqs = RFQSupplierSerializer(many=True, read_only=True)
    
    class Meta:
        model = RFQ
        fields = [
            'id', 'rfq_no', 'project', 'project_name', 'request_date',
            'response_deadline', 'status', 'status_display', 'notes',
            'lines', 'supplier_rfqs', 'created_at', 'updated_at'
        ]
        read_only_fields = ['rfq_no', 'request_date', 'created_at', 'updated_at']


class SupplierQuotationLineSerializer(serializers.ModelSerializer):
    """Supplier quotation line serializer"""
    item_name = serializers.CharField(source='rfq_line.item.name', read_only=True)
    item_sku = serializers.CharField(source='rfq_line.item.sku', read_only=True)
    
    class Meta:
        model = SupplierQuotationLine
        fields = [
            'id', 'quotation', 'rfq_line', 'item_name', 'item_sku',
            'unit_price', 'qty', 'lead_time_days', 'line_amount', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['line_amount', 'created_at', 'updated_at']


class SupplierQuotationSerializer(serializers.ModelSerializer):
    """Supplier quotation serializer"""
    supplier_name = serializers.CharField(source='rfq_supplier.supplier.name', read_only=True)
    rfq_no = serializers.CharField(source='rfq_supplier.rfq.rfq_no', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = SupplierQuotationLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = SupplierQuotation
        fields = [
            'id', 'quotation_no', 'rfq_supplier', 'supplier_name', 'rfq_no',
            'quotation_date', 'valid_until', 'payment_terms', 'delivery_terms',
            'total_amount', 'status', 'status_display', 'notes',
            'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = ['quotation_no', 'quotation_date', 'created_at', 'updated_at']

