"""
Serializers for finance app.
"""
from rest_framework import serializers
from .models import (
    Currency, ExchangeRateHistory, Expense, Invoice, InvoiceItem,
    AccountReceivable, AccountPayable, Payment, PaymentSchedule, PurchasePaymentSchedule,
    SharedExpense, SharedExpenseAllocation
)


class CurrencySerializer(serializers.ModelSerializer):
    """Currency serializer."""
    
    class Meta:
        model = Currency
        fields = [
            'id', 'code', 'name', 'symbol', 'exchange_rate',
            'is_base_currency', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ExchangeRateHistorySerializer(serializers.ModelSerializer):
    """Exchange rate history serializer."""
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    
    class Meta:
        model = ExchangeRateHistory
        fields = ['id', 'currency', 'currency_code', 'exchange_rate', 'effective_date', 'created_at']
        read_only_fields = ['created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    """Expense serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    
    class Meta:
        model = Expense
        fields = [
            'id', 'expense_no', 'project', 'project_name', 'department', 'department_name',
            'user', 'user_name', 'expense_date', 'category', 'category_display',
            'currency', 'currency_code', 'amount', 'exchange_rate', 'base_amount',
            'description', 'status', 'status_display', 'reimbursement_date',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['expense_no', 'base_amount', 'created_at', 'updated_at']


class AccountReceivableSerializer(serializers.ModelSerializer):
    """AccountReceivable serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    so_no = serializers.SerializerMethodField()
    sales_order_no = serializers.SerializerMethodField()  # 前端兼容字段
    project_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    def get_so_no(self, obj):
        return obj.so.order_no if obj.so else None
    
    def get_sales_order_no(self, obj):
        return obj.so.order_no if obj.so else None
    
    def get_project_name(self, obj):
        return obj.project.name if obj.project else '未关联项目'
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    amount_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = AccountReceivable
        fields = [
            'id', 'ar_no', 'customer', 'customer_name', 'so', 'so_no', 'sales_order_no',
            'project', 'project_name', 'invoice_no', 'invoice_date', 'currency', 'currency_code', 
            'amount_due', 'amount_paid', 'amount_remaining', 'exchange_rate', 'due_date', 
            'status', 'status_display', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['ar_no', 'amount_paid', 'created_at', 'updated_at']
    
    def get_amount_remaining(self, obj):
        return float(obj.amount_remaining)


class AccountPayableSerializer(serializers.ModelSerializer):
    """AccountPayable serializer."""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    po_no = serializers.CharField(source='po.order_no', read_only=True)
    purchase_order_no = serializers.CharField(source='po.order_no', read_only=True)  # 前端兼容字段
    project_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    amount_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = AccountPayable
        fields = [
            'id', 'ap_no', 'supplier', 'supplier_name', 'po', 'po_no', 'purchase_order_no',
            'project_name', 'invoice_no', 'invoice_date', 'currency', 'currency_code', 
            'amount_due', 'amount_paid', 'amount_remaining', 'exchange_rate', 'due_date', 
            'status', 'status_display', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['ap_no', 'amount_paid', 'created_at', 'updated_at']
    
    def get_project_name(self, obj):
        if obj.po and obj.po.project:
            return obj.po.project.name
        return None
    
    def get_amount_remaining(self, obj):
        return float(obj.amount_remaining)


class PaymentSerializer(serializers.ModelSerializer):
    """Payment serializer."""
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_no', 'payment_type', 'payment_type_display',
            'ar', 'ap', 'payment_date', 'payment_method', 'payment_method_display',
            'currency', 'currency_code', 'amount', 'exchange_rate', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['payment_no', 'created_at', 'updated_at']


class InvoiceItemSerializer(serializers.ModelSerializer):
    """Invoice line item serializer."""
    
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'invoice', 'line_no', 'tax_category_code', 'business_type',
            'item_name', 'specification', 'unit', 'quantity', 'unit_price',
            'amount', 'tax_rate', 'tax_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class InvoiceSerializer(serializers.ModelSerializer):
    """Invoice serializer."""
    invoice_type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reference_type_display = serializers.CharField(source='get_reference_type_display', read_only=True)
    invoice_category_display = serializers.CharField(source='get_invoice_category_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_type', 'invoice_type_display', 
            'invoice_no', 'invoice_code', 'digital_invoice_no', 'invoice_date',
            'seller_tax_no', 'seller_name', 'buyer_tax_no', 'buyer_name',
            'party_name', 'tax_number', 
            'amount_before_tax', 'tax_amount', 'total_amount',
            'invoice_source', 'invoice_category', 'invoice_category_display',
            'reference_type', 'reference_type_display', 'reference_id',
            'project', 'project_code', 'project_name',
            'status', 'status_display', 'notes', 'created_by_name',
            'items', 'item_count', 'attachment_count',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['total_amount', 'created_at', 'updated_at']
    
    def get_item_count(self, obj):
        return obj.items.count()
    
    def get_attachment_count(self, obj):
        from apps.core.models import Attachment
        return Attachment.objects.filter(related_model='Invoice', related_id=obj.id).count()


class SharedExpenseAllocationSerializer(serializers.ModelSerializer):
    """SharedExpenseAllocation serializer."""
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = SharedExpenseAllocation
        fields = [
            'id', 'shared_expense', 'project', 'project_code', 'project_name',
            'allocation_ratio', 'allocated_amount', 'notes', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SharedExpenseSerializer(serializers.ModelSerializer):
    """SharedExpense serializer."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    allocation_method_display = serializers.CharField(source='get_allocation_method_display', read_only=True)
    allocated_by_name = serializers.CharField(source='allocated_by.get_full_name', read_only=True)
    allocations = SharedExpenseAllocationSerializer(many=True, read_only=True)
    total_allocated = serializers.SerializerMethodField()
    
    class Meta:
        model = SharedExpense
        fields = [
            'id', 'expense_no', 'name', 'category', 'category_display',
            'description', 'expense_date', 'period_start', 'period_end',
            'amount', 'allocation_method', 'allocation_method_display',
            'status', 'status_display', 'allocated_at', 'allocated_by', 
            'allocated_by_name', 'notes', 'allocations', 'total_allocated',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['expense_no', 'allocated_at', 'created_at', 'updated_at']
    
    def get_total_allocated(self, obj):
        return sum(a.allocated_amount for a in obj.allocations.all())


class PaymentScheduleSerializer(serializers.ModelSerializer):
    """PaymentSchedule serializer for tracking payment milestones."""
    
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reminder_status_display = serializers.CharField(source='get_reminder_status_display', read_only=True)
    
    # 关联对象信息
    sales_order_no = serializers.CharField(source='sales_order.order_no', read_only=True)
    customer_name = serializers.CharField(source='sales_order.customer.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    # 计算属性
    amount_remaining = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    payment_progress = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'id', 'schedule_no', 'sales_order', 'sales_order_no', 'customer_name',
            'project', 'project_code', 'project_name',
            'milestone_type', 'milestone_type_display', 'milestone_name', 'milestone_order',
            'percentage', 'amount_due', 'amount_paid', 'amount_remaining', 'payment_progress',
            'due_date', 'actual_paid_date', 'is_overdue', 'days_until_due',
            'status', 'status_display',
            'reminder_status', 'reminder_status_display', 'reminder_days_before', 'last_reminded_at',
            'account_receivable', 'notes',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['schedule_no', 'created_at', 'updated_at']


class PaymentScheduleSummarySerializer(serializers.Serializer):
    """Summary serializer for payment schedule overview."""
    
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_remaining = serializers.DecimalField(max_digits=15, decimal_places=2)
    overall_progress = serializers.FloatField()
    
    pending_count = serializers.IntegerField()
    partial_count = serializers.IntegerField()
    paid_count = serializers.IntegerField()
    overdue_count = serializers.IntegerField()
    
    upcoming_payments = PaymentScheduleSerializer(many=True)
    overdue_payments = PaymentScheduleSerializer(many=True)


class PurchasePaymentScheduleSerializer(serializers.ModelSerializer):
    """PurchasePaymentSchedule serializer for tracking purchase payment milestones."""
    
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reminder_status_display = serializers.CharField(source='get_reminder_status_display', read_only=True)
    
    # 关联对象信息
    purchase_order_no = serializers.CharField(source='purchase_order.order_no', read_only=True)
    supplier_name = serializers.CharField(source='purchase_order.supplier.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    # 计算属性
    amount_remaining = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    payment_progress = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PurchasePaymentSchedule
        fields = [
            'id', 'schedule_no', 'purchase_order', 'purchase_order_no', 'supplier_name',
            'project', 'project_code', 'project_name',
            'milestone_type', 'milestone_type_display', 'milestone_name', 'milestone_order',
            'percentage', 'amount_due', 'amount_paid', 'amount_remaining', 'payment_progress',
            'due_date', 'actual_paid_date', 'is_overdue', 'days_until_due',
            'status', 'status_display',
            'reminder_status', 'reminder_status_display', 'reminder_days_before', 'last_reminded_at',
            'account_payable', 'notes',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['schedule_no', 'created_at', 'updated_at']

