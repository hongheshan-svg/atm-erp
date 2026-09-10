from django.utils import timezone
from rest_framework import serializers

from apps.core.permissions import MONEY_READERS, has_role

from .models import (
    BOMLine,
    Delivery,
    Entry,
    Item,
    Partner,
    Payment,
    Project,
    PurchaseLine,
    PurchaseOrder,
    Stock,
    StockMove,
    Task,
    TimeEntry,
)
from .services import payment_terms
from .services.finance import balance, paid


class MoneyFilter:
    sensitive_fields = ()
    money_roles = MONEY_READERS

    def to_representation(self, instance):
        result = super().to_representation(instance)
        if not has_role(self.context['request'].user, self.money_roles):
            for field in self.sensitive_fields:
                result.pop(field, None)
        return result


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'code', 'name', 'specification', 'brand', 'part_type', 'unit', 'is_active', 'updated_at']


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            'id',
            'code',
            'name',
            'kind',
            'contact',
            'phone',
            'address',
            'payment_term',
            'payment_days',
            'is_active',
            'updated_at',
        ]


class ProjectSerializer(MoneyFilter, serializers.ModelSerializer):
    quote_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    contract_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    contract_date = serializers.DateField(read_only=True)
    sensitive_fields = ('quote_amount', 'contract_amount')
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    manager_name = serializers.CharField(source='manager.display_name', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id',
            'code',
            'name',
            'customer',
            'customer_name',
            'manager',
            'manager_name',
            'members',
            'status',
            'requirements',
            'due_date',
            'quote_amount',
            'contract_amount',
            'contract_date',
            'equipment_quantity',
            'warranty_months',
            'close_reason',
            'created_at',
            'updated_at',
        ]


class BOMSerializer(serializers.ModelSerializer):
    brand = serializers.CharField(source='item.brand', read_only=True)
    part_type = serializers.CharField(source='item.part_type', read_only=True)
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    unit = serializers.CharField(source='item.unit', read_only=True)

    class Meta:
        model = BOMLine
        fields = [
            'id',
            'project',
            'item',
            'item_code',
            'item_name',
            'brand',
            'part_type',
            'assembly_unit',
            'unit',
            'quantity',
            'change_note',
            'updated_at',
        ]


class PurchaseLineSerializer(MoneyFilter, serializers.ModelSerializer):
    assembly_unit = serializers.CharField(source='bom_line.assembly_unit', read_only=True, default='')
    sensitive_fields = ('unit_price',)
    money_roles = MONEY_READERS | {'purchaser'}
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = PurchaseLine
        fields = [
            'id',
            'item',
            'item_code',
            'item_name',
            'bom_line',
            'assembly_unit',
            'due_date',
            'pending_quantity',
            'quantity',
            'unit_price',
            'received_quantity',
            'cancelled_quantity',
            'returned_quantity',
        ]


class PurchaseSerializer(serializers.ModelSerializer):
    lines = PurchaseLineSerializer(many=True, read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    next_delivery_date = serializers.SerializerMethodField()

    def get_next_delivery_date(self, obj):
        dates = [
            line.due_date or obj.due_date
            for line in obj.lines.all()
            if line.quantity > line.received_quantity + line.cancelled_quantity
        ]
        return min(dates) if dates else None

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'code',
            'project',
            'project_name',
            'supplier',
            'supplier_name',
            'payment_due_date',
            'payment_term',
            'payment_days',
            'next_delivery_date',
            'status',
            'due_date',
            'note',
            'lines',
            'updated_at',
        ]


class StockSerializer(MoneyFilter, serializers.ModelSerializer):
    sensitive_fields = ('value',)
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = Stock
        fields = ['id', 'item', 'item_code', 'item_name', 'location', 'quantity', 'value', 'updated_at']


class MoveSerializer(MoneyFilter, serializers.ModelSerializer):
    sensitive_fields = ('value', 'supplier_credit')
    item_name = serializers.CharField(source='stock.item.name', read_only=True)
    item = serializers.IntegerField(source='stock.item_id', read_only=True)
    location = serializers.CharField(source='stock.location', read_only=True)

    class Meta:
        model = StockMove
        fields = [
            'id',
            'stock',
            'item',
            'item_name',
            'location',
            'project',
            'task',
            'purchase_line',
            'source',
            'kind',
            'quantity',
            'value',
            'supplier_credit',
            'received_date',
            'reason',
            'created_at',
            'created_by',
        ]


class EntrySerializer(serializers.ModelSerializer):
    paid_amount = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    due_date = serializers.SerializerMethodField()
    payment_schedule = serializers.SerializerMethodField()
    due_amount = serializers.SerializerMethodField()

    def get_due_date(self, obj):
        return (
            payment_terms.next_due(obj) if obj.purchase_id and obj.purchase.payment_term != 'manual' else obj.due_date
        )

    def get_payment_schedule(self, obj):
        return [{'due_date': row['due_date'], 'amount': str(row['amount'])} for row in payment_terms.schedule(obj)]

    def get_due_amount(self, obj):
        return str(payment_terms.due_amount(obj, timezone.localdate(), inclusive=True))

    def get_paid_amount(self, obj):
        return str(paid(obj))

    def get_balance(self, obj):
        return str(balance(obj))

    class Meta:
        model = Entry
        fields = [
            'id',
            'project',
            'project_name',
            'purchase',
            'task',
            'kind',
            'title',
            'amount',
            'credit_amount',
            'paid_amount',
            'payment_schedule',
            'due_amount',
            'balance',
            'due_date',
            'cancelled',
            'updated_at',
        ]


class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.display_name', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id',
            'project',
            'delivery',
            'kind',
            'title',
            'description',
            'assignee',
            'assignee_name',
            'status',
            'due_date',
            'completed_at',
            'service_date',
            'created_at',
            'updated_at',
        ]


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = [
            'id',
            'code',
            'project',
            'quantity',
            'shipped_date',
            'material_requirements',
            'accepted_date',
            'warranty_until',
            'note',
            'updated_at',
        ]


class TimeSerializer(MoneyFilter, serializers.ModelSerializer):
    reversed_by = serializers.IntegerField(source='reversal.pk', read_only=True, default=None)
    sensitive_fields = ('hourly_cost', 'cost')
    user_name = serializers.CharField(source='user.display_name', read_only=True)
    project = serializers.IntegerField(source='task.project_id', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = TimeEntry
        fields = [
            'id',
            'task',
            'task_title',
            'project',
            'user',
            'user_name',
            'date',
            'hours',
            'hourly_cost',
            'cost',
            'reason',
            'reversal_of',
            'correction_of',
            'reversed_by',
            'created_at',
        ]


class PaymentSerializer(serializers.ModelSerializer):
    evidence = serializers.SerializerMethodField()
    bank_matched = serializers.BooleanField(read_only=True, default=False)
    cash_amount = serializers.SerializerMethodField()

    def get_cash_amount(self, obj):
        return str(obj.amount if obj.entry.kind == 'receivable' else -obj.amount)

    def get_evidence(self, obj):
        records = (
            [{'document': obj.document_id, 'name': obj.document.original_name, 'reason': '登记时关联'}]
            if obj.document_id
            else []
        )
        records.extend(
            {
                'document': row.document_id,
                'name': row.document.original_name,
                'reason': row.reason,
                'date': row.created_at,
                'actor': row.created_by.display_name,
            }
            for row in obj.evidence.all()
        )
        return records

    reversed_by = serializers.IntegerField(source='reversal.pk', read_only=True, default=None)
    entry_title = serializers.CharField(source='entry.title', read_only=True)
    project = serializers.IntegerField(source='entry.project_id', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'entry',
            'entry_title',
            'evidence',
            'method',
            'account',
            'reference',
            'reconciliation',
            'bank_matched',
            'cash_amount',
            'document',
            'project',
            'amount',
            'date',
            'reason',
            'reversal_of',
            'created_at',
            'created_by',
            'reversed_by',
        ]
