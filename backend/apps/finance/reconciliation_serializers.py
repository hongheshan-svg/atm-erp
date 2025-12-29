"""
对账单序列化器
"""
from rest_framework import serializers
from .reconciliation_models import (
    PurchaseReconciliation, PurchaseReconciliationLine,
    SalesReconciliation, SalesReconciliationLine,
    InvoiceReconciliation, InvoiceReconciliationLine
)


class PurchaseReconciliationLineSerializer(serializers.ModelSerializer):
    """采购对账单明细序列化器"""
    line_type_display = serializers.CharField(source='get_line_type_display', read_only=True)
    receipt_status_display = serializers.CharField(source='get_receipt_status_display', read_only=True)
    po_order_no = serializers.CharField(source='po.order_no', read_only=True)
    
    class Meta:
        model = PurchaseReconciliationLine
        fields = [
            'id', 'line_type', 'line_type_display', 'po', 'po_order_no',
            'reference_no', 'reference_date',
            'debit_amount', 'credit_amount', 'balance',
            'order_qty', 'received_qty', 'receipt_status', 'receipt_status_display',
            'receipt_confirmed', 'receipt_confirmed_at',
            'payable_amount', 'paid_amount', 'payment_progress',
            'is_matched', 'notes'
        ]


class PurchaseReconciliationSerializer(serializers.ModelSerializer):
    """采购对账单序列化器"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.username', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True)
    lines = PurchaseReconciliationLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseReconciliation
        fields = [
            'id', 'reconciliation_no', 'supplier', 'supplier_name',
            'period_start', 'period_end',
            'total_order_amount', 'total_received_amount',
            'total_invoice_amount', 'total_paid_amount', 'balance_amount',
            'opening_balance', 'closing_balance',
            'status', 'status_display',
            'reconciled_by', 'reconciled_by_name', 'reconciled_at',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'notes', 'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'reconciliation_no', 'total_order_amount', 'total_received_amount',
            'total_invoice_amount', 'total_paid_amount', 'balance_amount',
            'closing_balance', 'reconciled_at', 'confirmed_at', 'created_at', 'updated_at'
        ]


class PurchaseReconciliationListSerializer(serializers.ModelSerializer):
    """采购对账单列表序列化器"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseReconciliation
        fields = [
            'id', 'reconciliation_no', 'supplier', 'supplier_name',
            'period_start', 'period_end',
            'total_order_amount', 'total_received_amount',
            'total_invoice_amount', 'total_paid_amount', 'balance_amount',
            'status', 'status_display', 'line_count', 'created_at'
        ]
    
    def get_line_count(self, obj):
        return obj.lines.count()


class SalesReconciliationLineSerializer(serializers.ModelSerializer):
    """销售对账单明细序列化器"""
    line_type_display = serializers.CharField(source='get_line_type_display', read_only=True)
    delivery_status_display = serializers.CharField(source='get_delivery_status_display', read_only=True)
    so_order_no = serializers.CharField(source='so.order_no', read_only=True)
    
    class Meta:
        model = SalesReconciliationLine
        fields = [
            'id', 'line_type', 'line_type_display', 'so', 'so_order_no',
            'reference_no', 'reference_date',
            'debit_amount', 'credit_amount', 'balance',
            'order_qty', 'delivered_qty', 'delivery_status', 'delivery_status_display',
            'delivery_confirmed', 'delivery_confirmed_at',
            'receivable_amount', 'received_amount', 'collection_progress',
            'is_matched', 'notes'
        ]


class SalesReconciliationSerializer(serializers.ModelSerializer):
    """销售对账单序列化器"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.username', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True)
    lines = SalesReconciliationLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = SalesReconciliation
        fields = [
            'id', 'reconciliation_no', 'customer', 'customer_name',
            'period_start', 'period_end',
            'total_order_amount', 'total_delivered_amount',
            'total_invoice_amount', 'total_received_amount', 'balance_amount',
            'opening_balance', 'closing_balance',
            'status', 'status_display',
            'reconciled_by', 'reconciled_by_name', 'reconciled_at',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'notes', 'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'reconciliation_no', 'total_order_amount', 'total_delivered_amount',
            'total_invoice_amount', 'total_received_amount', 'balance_amount',
            'closing_balance', 'reconciled_at', 'confirmed_at', 'created_at', 'updated_at'
        ]


class SalesReconciliationListSerializer(serializers.ModelSerializer):
    """销售对账单列表序列化器"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesReconciliation
        fields = [
            'id', 'reconciliation_no', 'customer', 'customer_name',
            'period_start', 'period_end',
            'total_order_amount', 'total_delivered_amount',
            'total_invoice_amount', 'total_received_amount', 'balance_amount',
            'status', 'status_display', 'line_count', 'created_at'
        ]
    
    def get_line_count(self, obj):
        return obj.lines.count()


class InvoiceReconciliationLineSerializer(serializers.ModelSerializer):
    """发票对账单明细序列化器"""
    match_status_display = serializers.CharField(source='get_match_status_display', read_only=True)
    
    class Meta:
        model = InvoiceReconciliationLine
        fields = [
            'id', 'invoice_no', 'invoice_date', 'party_name', 'tax_number',
            'amount_before_tax', 'tax_amount', 'total_amount',
            'matched_order_no', 'matched_order_amount', 'difference_amount',
            'match_status', 'match_status_display', 'notes'
        ]


class InvoiceReconciliationSerializer(serializers.ModelSerializer):
    """发票对账单序列化器"""
    invoice_type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.username', read_only=True)
    lines = InvoiceReconciliationLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = InvoiceReconciliation
        fields = [
            'id', 'reconciliation_no', 'invoice_type', 'invoice_type_display',
            'period_start', 'period_end',
            'total_invoice_count', 'total_invoice_amount', 'total_tax_amount',
            'matched_count', 'matched_amount',
            'unmatched_count', 'unmatched_amount',
            'status', 'status_display',
            'reconciled_by', 'reconciled_by_name', 'reconciled_at',
            'notes', 'lines', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'reconciliation_no', 'total_invoice_count', 'total_invoice_amount',
            'total_tax_amount', 'matched_count', 'matched_amount',
            'unmatched_count', 'unmatched_amount',
            'reconciled_at', 'created_at', 'updated_at'
        ]


class InvoiceReconciliationListSerializer(serializers.ModelSerializer):
    """发票对账单列表序列化器"""
    invoice_type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = InvoiceReconciliation
        fields = [
            'id', 'reconciliation_no', 'invoice_type', 'invoice_type_display',
            'period_start', 'period_end',
            'total_invoice_count', 'total_invoice_amount',
            'matched_count', 'unmatched_count',
            'status', 'status_display', 'created_at'
        ]

