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
    order_items = serializers.SerializerMethodField()
    
    # 前端打印模板需要的字段映射
    description = serializers.SerializerMethodField()
    specification = serializers.SerializerMethodField()
    drawing_no = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    order_amount = serializers.DecimalField(source='debit_amount', max_digits=12, decimal_places=2, read_only=True)
    received_amount = serializers.SerializerMethodField()
    invoice_amount = serializers.SerializerMethodField()
    
    # 发票和付款相关字段
    tax_amount = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    is_deducted = serializers.BooleanField(default=False, read_only=True)
    
    class Meta:
        model = PurchaseReconciliationLine
        fields = [
            'id', 'line_type', 'line_type_display', 'po', 'po_order_no',
            'reference_no', 'reference_date',
            'debit_amount', 'credit_amount', 'balance',
            'order_qty', 'received_qty', 'receipt_status', 'receipt_status_display',
            'receipt_confirmed', 'receipt_confirmed_at',
            'payable_amount', 'paid_amount', 'payment_progress',
            'is_matched', 'notes',
            # 打印模板字段
            'order_items', 'description', 'specification', 'drawing_no',
            'unit_price', 'unit', 'quantity', 'order_amount', 'received_amount', 'invoice_amount',
            # 发票和付款字段
            'tax_amount', 'payment_method', 'is_deducted'
        ]
    
    def get_tax_amount(self, obj):
        """获取税额"""
        if obj.line_type == 'INVOICE':
            # 假设税率为13%
            return float(obj.debit_amount or 0) * 0.13 / 1.13
        return 0
    
    def get_payment_method(self, obj):
        """获取付款方式"""
        if obj.line_type == 'PAYMENT':
            return obj.notes or '银行转账'
        return ''
    
    def get_order_items(self, obj):
        """获取订单行明细"""
        if obj.line_type != 'ORDER' or not obj.po:
            return []
        items = []
        for line in obj.po.lines.filter(is_deleted=False):
            items.append({
                'material_name': line.material.name if hasattr(line, 'material') and line.material else (line.description or ''),
                'specification': getattr(line.material, 'specification', '') if hasattr(line, 'material') and line.material else '',
                'drawing_no': getattr(line.material, 'drawing_no', '') if hasattr(line, 'material') and line.material else '',
                'unit': line.unit or (line.material.unit if hasattr(line, 'material') and line.material else ''),
                'quantity': float(line.qty or 0),
                'unit_price': float(line.unit_price or 0),
                'amount': float(line.amount or 0),
            })
        return items
    
    def get_description(self, obj):
        """获取物料描述"""
        if obj.line_type != 'ORDER' or not obj.po:
            return obj.notes or ''
        first_line = obj.po.lines.filter(is_deleted=False).first()
        if first_line:
            if hasattr(first_line, 'material') and first_line.material:
                return first_line.material.name
            return first_line.description or ''
        return ''
    
    def get_specification(self, obj):
        """获取规格"""
        if obj.line_type != 'ORDER' or not obj.po:
            return ''
        first_line = obj.po.lines.filter(is_deleted=False).first()
        if first_line and hasattr(first_line, 'material') and first_line.material:
            return getattr(first_line.material, 'specification', '') or getattr(first_line.material, 'model', '')
        return ''
    
    def get_drawing_no(self, obj):
        """获取图号"""
        if obj.line_type != 'ORDER' or not obj.po:
            return ''
        first_line = obj.po.lines.filter(is_deleted=False).first()
        if first_line and hasattr(first_line, 'material') and first_line.material:
            return getattr(first_line.material, 'drawing_no', '') or ''
        return ''
    
    def get_unit_price(self, obj):
        """获取单价"""
        if obj.line_type != 'ORDER' or not obj.po:
            return 0
        first_line = obj.po.lines.filter(is_deleted=False).first()
        if first_line:
            return float(first_line.unit_price or 0)
        return 0
    
    def get_unit(self, obj):
        """获取单位"""
        if obj.line_type != 'ORDER' or not obj.po:
            return ''
        first_line = obj.po.lines.filter(is_deleted=False).first()
        if first_line:
            return first_line.unit or ''
        return ''
    
    def get_quantity(self, obj):
        """获取数量"""
        if obj.line_type != 'ORDER' or not obj.po:
            return 0
        total_qty = sum(line.qty for line in obj.po.lines.filter(is_deleted=False))
        return float(total_qty)
    
    def get_received_amount(self, obj):
        """计算已收货金额"""
        if obj.line_type != 'ORDER' or not obj.po:
            return 0
        total = 0
        for receipt in obj.po.receipts.filter(status__in=['CONFIRMED', 'COMPLETED'], is_deleted=False):
            for line in receipt.lines.filter(is_deleted=False):
                if hasattr(line, 'po_line') and line.po_line:
                    total += float(line.qty * line.po_line.unit_price)
        return total
    
    def get_invoice_amount(self, obj):
        """获取已开票金额"""
        if obj.line_type != 'ORDER' or not obj.po:
            return 0
        from apps.finance.models import AccountPayable
        from django.db.models import Sum
        total = AccountPayable.objects.filter(po=obj.po, is_deleted=False).aggregate(
            total=Sum('amount_due')
        )['total'] or 0
        return float(total)


class PurchaseReconciliationSerializer(serializers.ModelSerializer):
    """采购对账单序列化器"""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_contact = serializers.CharField(source='supplier.contact_person', read_only=True, allow_null=True)
    supplier_phone = serializers.CharField(source='supplier.phone', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.username', read_only=True, allow_null=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    lines = PurchaseReconciliationLineSerializer(many=True, read_only=True)
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''
    
    class Meta:
        model = PurchaseReconciliation
        fields = [
            'id', 'reconciliation_no', 'supplier', 'supplier_name',
            'supplier_contact', 'supplier_phone',
            'period_start', 'period_end',
            'total_order_amount', 'total_received_amount',
            'total_invoice_amount', 'total_paid_amount', 'balance_amount',
            'opening_balance', 'closing_balance',
            'status', 'status_display',
            'reconciled_by', 'reconciled_by_name', 'reconciled_at',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'created_by', 'created_by_name',
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
    order_items = serializers.SerializerMethodField()
    
    # 前端打印模板需要的字段映射
    description = serializers.SerializerMethodField()
    specification = serializers.SerializerMethodField()
    drawing_no = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    order_amount = serializers.DecimalField(source='debit_amount', max_digits=12, decimal_places=2, read_only=True)
    delivered_amount = serializers.SerializerMethodField()
    invoice_amount = serializers.SerializerMethodField()
    
    # 发票和收款相关字段
    tax_amount = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesReconciliationLine
        fields = [
            'id', 'line_type', 'line_type_display', 'so', 'so_order_no',
            'reference_no', 'reference_date',
            'debit_amount', 'credit_amount', 'balance',
            'order_qty', 'delivered_qty', 'delivery_status', 'delivery_status_display',
            'delivery_confirmed', 'delivery_confirmed_at',
            'receivable_amount', 'received_amount', 'collection_progress',
            'is_matched', 'notes',
            # 打印模板字段
            'order_items', 'description', 'specification', 'drawing_no',
            'unit_price', 'unit', 'quantity', 'order_amount', 'delivered_amount', 'invoice_amount',
            # 发票和收款字段
            'tax_amount', 'payment_method'
        ]
    
    def get_tax_amount(self, obj):
        """获取税额"""
        if obj.line_type == 'INVOICE':
            # 假设税率为13%
            return float(obj.debit_amount or 0) * 0.13 / 1.13
        return 0
    
    def get_payment_method(self, obj):
        """获取收款方式"""
        if obj.line_type == 'RECEIPT':
            return obj.notes or '银行转账'
        return ''
    
    def get_order_items(self, obj):
        """获取订单行明细"""
        if obj.line_type != 'ORDER' or not obj.so:
            return []
        items = []
        for line in obj.so.lines.filter(is_deleted=False):
            items.append({
                'material_name': line.material.name if hasattr(line, 'material') and line.material else (line.description or ''),
                'specification': getattr(line.material, 'specification', '') if hasattr(line, 'material') and line.material else '',
                'drawing_no': getattr(line.material, 'drawing_no', '') if hasattr(line, 'material') and line.material else '',
                'unit': line.unit or (line.material.unit if hasattr(line, 'material') and line.material else ''),
                'quantity': float(line.qty or 0),
                'unit_price': float(line.unit_price or 0),
                'amount': float(line.amount or 0),
            })
        return items
    
    def get_description(self, obj):
        """获取物料描述"""
        if obj.line_type != 'ORDER' or not obj.so:
            return obj.notes or ''
        first_line = obj.so.lines.filter(is_deleted=False).first()
        if first_line:
            if hasattr(first_line, 'material') and first_line.material:
                return first_line.material.name
            return first_line.description or ''
        return ''
    
    def get_specification(self, obj):
        """获取规格"""
        if obj.line_type != 'ORDER' or not obj.so:
            return ''
        first_line = obj.so.lines.filter(is_deleted=False).first()
        if first_line and hasattr(first_line, 'material') and first_line.material:
            return getattr(first_line.material, 'specification', '') or getattr(first_line.material, 'model', '')
        return ''
    
    def get_drawing_no(self, obj):
        """获取图号"""
        if obj.line_type != 'ORDER' or not obj.so:
            return ''
        first_line = obj.so.lines.filter(is_deleted=False).first()
        if first_line and hasattr(first_line, 'material') and first_line.material:
            return getattr(first_line.material, 'drawing_no', '') or ''
        return ''
    
    def get_unit_price(self, obj):
        """获取单价"""
        if obj.line_type != 'ORDER' or not obj.so:
            return 0
        first_line = obj.so.lines.filter(is_deleted=False).first()
        if first_line:
            return float(first_line.unit_price or 0)
        return 0
    
    def get_unit(self, obj):
        """获取单位"""
        if obj.line_type != 'ORDER' or not obj.so:
            return ''
        first_line = obj.so.lines.filter(is_deleted=False).first()
        if first_line:
            return first_line.unit or ''
        return ''
    
    def get_quantity(self, obj):
        """获取数量"""
        if obj.line_type != 'ORDER' or not obj.so:
            return 0
        total_qty = sum(line.qty for line in obj.so.lines.filter(is_deleted=False))
        return float(total_qty)
    
    def get_delivered_amount(self, obj):
        """计算已发货金额"""
        if obj.line_type != 'ORDER' or not obj.so:
            return 0
        total = 0
        for delivery in obj.so.deliveries.filter(status__in=['CONFIRMED', 'COMPLETED'], is_deleted=False):
            for line in delivery.lines.filter(is_deleted=False):
                if hasattr(line, 'so_line') and line.so_line:
                    total += float(line.qty * line.so_line.unit_price)
        return total
    
    def get_invoice_amount(self, obj):
        """获取已开票金额"""
        if obj.line_type != 'ORDER' or not obj.so:
            return 0
        from apps.finance.models import AccountReceivable
        from django.db.models import Sum
        total = AccountReceivable.objects.filter(so=obj.so, is_deleted=False).aggregate(
            total=Sum('amount_due')
        )['total'] or 0
        return float(total)


class SalesReconciliationSerializer(serializers.ModelSerializer):
    """销售对账单序列化器"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_contact = serializers.CharField(source='customer.contact_person', read_only=True, allow_null=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.username', read_only=True, allow_null=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.username', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    lines = SalesReconciliationLineSerializer(many=True, read_only=True)
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''
    
    class Meta:
        model = SalesReconciliation
        fields = [
            'id', 'reconciliation_no', 'customer', 'customer_name',
            'customer_contact', 'customer_phone',
            'period_start', 'period_end',
            'total_order_amount', 'total_delivered_amount',
            'total_invoice_amount', 'total_received_amount', 'balance_amount',
            'opening_balance', 'closing_balance',
            'status', 'status_display',
            'reconciled_by', 'reconciled_by_name', 'reconciled_at',
            'confirmed_by', 'confirmed_by_name', 'confirmed_at',
            'created_by', 'created_by_name',
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

