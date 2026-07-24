"""核销工作台序列化器:待付款项台账 / 核销记录。"""

from rest_framework import serializers

from apps.finance.payable_models import PayableItem, PayableSettlement


class PayableItemSerializer(serializers.ModelSerializer):
    remaining = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, default='')

    class Meta:
        model = PayableItem
        fields = [
            'id', 'source_type', 'source_id', 'source_no', 'category', 'payee_name',
            'supplier', 'supplier_name', 'amount_due', 'amount_paid', 'remaining',
            'currency', 'status', 'due_date', 'project', 'created_at',
        ]
        read_only_fields = fields


class PayableSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayableSettlement
        fields = ['id', 'bank_statement', 'payable_item', 'payment', 'amount', 'created_at']
        read_only_fields = fields
