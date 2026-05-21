"""
Serializers for purchase app.
"""

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseContract,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
)
from .services import BudgetValidationService


class PurchaseRequestLineSerializer(serializers.ModelSerializer):
    """PurchaseRequestLine serializer - 支持BOM关联."""

    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    item_property = serializers.CharField(source='item.get_item_property_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    # BOM关联信息
    bom_item_id = serializers.IntegerField(source='bom_item.id', read_only=True, allow_null=True)
    bom_planned_qty = serializers.DecimalField(
        source='bom_item.planned_qty', max_digits=15, decimal_places=2, read_only=True, allow_null=True
    )

    class Meta:
        model = PurchaseRequestLine
        fields = [
            'id',
            'pr',
            'item',
            'item_sku',
            'item_name',
            'item_unit',
            'item_property',
            'qty',
            'estimated_price',
            'line_amount',
            'required_date',
            'project',
            'project_name',
            # BOM关联字段
            'bom_item',
            'bom_item_id',
            'bom_planned_qty',
            'is_critical',
            'is_long_lead',
            'function_module',
            'notes',
            'is_deleted',
        ]
        read_only_fields = ['line_amount', 'bom_item_id', 'bom_planned_qty']


class PurchaseRequestLineCreateSerializer(serializers.ModelSerializer):
    """PurchaseRequestLine serializer for create/update - 支持BOM关联."""

    class Meta:
        model = PurchaseRequestLine
        fields = [
            'id',
            'item',
            'qty',
            'estimated_price',
            'required_date',
            'project',
            'bom_item',
            'is_critical',
            'is_long_lead',
            'function_module',
            'notes',
        ]
        extra_kwargs = {
            'id': {'required': False},
            'bom_item': {'required': False},
        }


class PurchaseRequestSerializer(serializers.ModelSerializer):
    """PurchaseRequest serializer."""

    project_name = serializers.CharField(source='project.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    requestor_name = serializers.CharField(source='requestor.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    lines = PurchaseRequestLineSerializer(many=True, read_only=True)
    budget_info = serializers.SerializerMethodField()
    # 物料摘要信息（用于列表展示）
    item_summary = serializers.SerializerMethodField()
    lines_count = serializers.SerializerMethodField()
    total_qty = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequest
        fields = [
            'id',
            'request_no',
            'project',
            'project_name',
            'supplier',
            'supplier_name',
            'requestor',
            'requestor_name',
            'request_date',
            'required_date',
            'status',
            'status_display',
            'tax_rate',
            'tax_rate_display',
            'total_amount',
            'tax_amount',
            'total_with_tax',
            'notes',
            'lines',
            'is_deleted',
            'created_at',
            'updated_at',
            'budget_info',
            'item_summary',
            'lines_count',
            'total_qty',
        ]
        read_only_fields = [
            'request_no',
            'requestor',
            'request_date',
            'tax_amount',
            'total_with_tax',
            'status',
            'created_at',
            'updated_at',
        ]

    def get_item_summary(self, obj):
        """获取物料摘要信息（用于列表展示）"""
        lines = obj.lines.filter(is_deleted=False).select_related('item')[:1]
        if not lines:
            return None
        first_line = lines[0]
        return {
            'item_name': first_line.item.name if first_line.item else '',
            'item_sku': first_line.item.sku if first_line.item else '',
            'specification': first_line.item.specification if first_line.item else '',
            'unit': first_line.item.get_unit_display() if first_line.item else '',
            'qty': float(first_line.qty or 0),
            'unit_price': float(first_line.estimated_price or 0),
        }

    def get_lines_count(self, obj):
        """获取明细行数"""
        return obj.lines.filter(is_deleted=False).count()

    def get_total_qty(self, obj):
        """获取总数量"""
        from django.db.models import Sum

        result = obj.lines.filter(is_deleted=False).aggregate(total=Sum('qty'))
        return float(result['total'] or 0)

    def get_budget_info(self, obj):
        """Get budget validation info for this request."""
        if not obj.project:
            return None
        return BudgetValidationService.validate_purchase_request(
            obj.project, obj.total_amount, exclude_pr_id=obj.id if obj.status in ['APPROVED', 'CONVERTED'] else None
        )

    def create(self, validated_data):
        """Create PR with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            pr = PurchaseRequest.objects.create(**validated_data)

            total_amount = 0
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    qty = line_data['qty']
                    estimated_price = line_data.get('estimated_price', 0)
                    line = PurchaseRequestLine.objects.create(
                        pr=pr,
                        item_id=line_data['item'],
                        qty=qty,
                        estimated_price=estimated_price,
                        required_date=line_data.get('required_date'),
                        project_id=line_data.get('project'),
                        notes=line_data.get('notes', ''),
                        created_by=pr.created_by,
                    )
                    total_amount += qty * estimated_price

            pr.total_amount = total_amount
            pr.tax_amount = total_amount * pr.tax_rate / 100
            pr.total_with_tax = total_amount + pr.tax_amount
            pr.save()

        return pr

    def update(self, instance, validated_data):
        """Update PR with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            # Update PR fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Delete old lines and create new ones
            instance.lines.all().delete()

            total_amount = 0
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    qty = line_data['qty']
                    estimated_price = line_data.get('estimated_price', 0)
                    PurchaseRequestLine.objects.create(
                        pr=instance,
                        item_id=line_data['item'],
                        qty=qty,
                        estimated_price=estimated_price,
                        required_date=line_data.get('required_date'),
                        project_id=line_data.get('project'),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by,
                    )
                    total_amount += qty * estimated_price

            instance.total_amount = total_amount
            instance.tax_amount = total_amount * instance.tax_rate / 100
            instance.total_with_tax = total_amount + instance.tax_amount
            instance.save()

        return instance


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    """PurchaseOrderLine serializer - 支持BOM关联."""

    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    unit = serializers.CharField(source='item.get_unit_display', read_only=True)  # 前端兼容字段
    item_property = serializers.CharField(source='item.get_item_property_display', read_only=True)
    specification = serializers.CharField(source='item.specification', read_only=True, allow_null=True)  # 规格型号
    remaining_qty = serializers.SerializerMethodField()
    # BOM关联信息
    bom_item_id = serializers.IntegerField(source='bom_item.id', read_only=True, allow_null=True)
    bom_planned_qty = serializers.DecimalField(
        source='bom_item.planned_qty', max_digits=15, decimal_places=2, read_only=True, allow_null=True
    )
    bom_project_code = serializers.CharField(source='bom_item.project.code', read_only=True, allow_null=True)

    class Meta:
        model = PurchaseOrderLine
        fields = [
            'id',
            'po',
            'item',
            'item_sku',
            'item_name',
            'item_unit',
            'unit',
            'item_property',
            'specification',
            'qty',
            'unit_price',
            'line_amount',
            'received_qty',
            'remaining_qty',
            # BOM关联字段
            'bom_item',
            'bom_item_id',
            'bom_planned_qty',
            'bom_project_code',
            'is_critical',
            'is_long_lead',
            'function_module',
            'drawing_no',
            'technical_requirement',
            'notes',
            'is_deleted',
        ]
        read_only_fields = ['line_amount', 'received_qty', 'bom_item_id', 'bom_planned_qty', 'bom_project_code']

    def get_remaining_qty(self, obj):
        return float(obj.qty - obj.received_qty)


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """PurchaseOrder serializer."""

    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    payment_terms_display = serializers.CharField(source='get_payment_terms_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    expected_date = serializers.DateField(source='delivery_date', read_only=True)  # 前端兼容字段
    created_by_name = serializers.SerializerMethodField()
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    # 物料摘要信息（用于列表展示）
    item_summary = serializers.SerializerMethodField()
    lines_count = serializers.SerializerMethodField()
    total_qty = serializers.SerializerMethodField()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''

    def get_item_summary(self, obj):
        """获取物料摘要信息（用于列表展示）"""
        lines = obj.lines.filter(is_deleted=False).select_related('item')[:1]
        if not lines:
            return None
        first_line = lines[0]
        return {
            'item_name': first_line.item.name if first_line.item else '',
            'item_sku': first_line.item.sku if first_line.item else '',
            'specification': first_line.item.specification if first_line.item else '',
            'unit': first_line.item.get_unit_display() if first_line.item else '',
            'qty': float(first_line.qty or 0),
            'unit_price': float(first_line.unit_price or 0),
        }

    def get_lines_count(self, obj):
        """获取明细行数"""
        return obj.lines.filter(is_deleted=False).count()

    def get_total_qty(self, obj):
        """获取总数量"""
        from django.db.models import Sum

        result = obj.lines.filter(is_deleted=False).aggregate(total=Sum('qty'))
        return float(result['total'] or 0)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id',
            'order_no',
            'supplier',
            'supplier_name',
            'project',
            'project_name',
            'order_date',
            'delivery_date',
            'expected_date',
            'status',
            'status_display',
            'tax_rate',
            'tax_rate_display',
            'total_amount',
            'tax_amount',
            'total_with_tax',
            'payment_terms',
            'payment_terms_display',
            'payment_method',
            'payment_method_display',
            'payment_terms_detail',
            'notes',
            'lines',
            'is_deleted',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
            'item_summary',
            'lines_count',
            'total_qty',
        ]
        read_only_fields = ['order_no', 'order_date', 'tax_amount', 'total_with_tax', 'status', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create PO with lines."""
        lines_data = self.initial_data.get('lines', [])
        for line_data in lines_data:
            if not line_data.get('qty') or float(line_data.get('qty', 0)) <= 0:
                raise serializers.ValidationError({'lines': '数量必须大于0'})
            if float(line_data.get('unit_price', 0)) < 0:
                raise serializers.ValidationError({'lines': '单价不能为负数'})

        with transaction.atomic():
            po = PurchaseOrder.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    PurchaseOrderLine.objects.create(
                        po=po,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=po.created_by,
                    )

            # Update total amount and tax
            total = po.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            po.total_amount = total
            po.tax_amount = total * po.tax_rate / 100
            po.total_with_tax = total + po.tax_amount
            po.save()

        return po

    def update(self, instance, validated_data):
        """Update PO with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            # Update PO fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Delete old lines and create new ones
            instance.lines.all().delete()

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    PurchaseOrderLine.objects.create(
                        po=instance,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by,
                    )

            # Update total amount and tax
            total = instance.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            instance.total_amount = total
            instance.tax_amount = total * instance.tax_rate / 100
            instance.total_with_tax = total + instance.tax_amount
            instance.save()

        return instance


class GoodsReceiptLineSerializer(serializers.ModelSerializer):
    """GoodsReceiptLine serializer."""

    item_name = serializers.SerializerMethodField()
    item_sku = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()  # 前端兼容字段
    item_unit = serializers.SerializerMethodField()
    quality_status_display = serializers.CharField(source='get_quality_status_display', read_only=True)
    ordered_qty = serializers.SerializerMethodField()  # 订单数量
    received_qty = serializers.SerializerMethodField()  # 已收货数量

    def get_item_name(self, obj):
        if obj.item:
            return obj.item.name
        return ''

    def get_item_sku(self, obj):
        if obj.item:
            return obj.item.sku
        return ''

    def get_sku(self, obj):
        if obj.item:
            return obj.item.sku
        return ''

    def get_item_unit(self, obj):
        if obj.item:
            return obj.item.get_unit_display()
        return ''

    def get_ordered_qty(self, obj):
        """获取订单数量"""
        if obj.po_line:
            return float(obj.po_line.qty or 0)
        return 0

    def get_received_qty(self, obj):
        """获取已收货数量"""
        if obj.po_line:
            return float(obj.po_line.received_qty or 0)
        return 0

    class Meta:
        model = GoodsReceiptLine
        fields = [
            'id',
            'receipt',
            'po_line',
            'item',
            'item_sku',
            'sku',
            'item_name',
            'item_unit',
            'qty',
            'ordered_qty',
            'received_qty',
            'quality_status',
            'quality_status_display',
            'notes',
            'is_deleted',
        ]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    """GoodsReceipt serializer."""

    po_no = serializers.CharField(source='po.order_no', read_only=True)
    purchase_order_no = serializers.CharField(source='po.order_no', read_only=True)  # 前端兼容字段
    supplier_name = serializers.CharField(source='po.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)

    def get_created_by_name(self, obj):
        """获取创建人姓名"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''

    class Meta:
        model = GoodsReceipt
        fields = [
            'id',
            'receipt_no',
            'po',
            'po_no',
            'purchase_order_no',
            'supplier_name',
            'warehouse',
            'warehouse_name',
            'receipt_date',
            'status',
            'status_display',
            'notes',
            'lines',
            'created_by',
            'created_by_name',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['receipt_no', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create GoodsReceipt with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    GoodsReceiptLine.objects.create(
                        receipt=receipt,
                        po_line_id=line_data.get('po_line'),
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        quality_status=line_data.get('quality_status', 'PENDING'),
                        notes=line_data.get('notes', ''),
                        created_by=receipt.created_by,
                    )

        return receipt

    def update(self, instance, validated_data):
        """Update GoodsReceipt with lines."""
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            # Update receipt fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Delete old lines and create new ones
            instance.lines.all().delete()

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    GoodsReceiptLine.objects.create(
                        receipt=instance,
                        po_line_id=line_data.get('po_line'),
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        quality_status=line_data.get('quality_status', 'PENDING'),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by,
                    )

        return instance


class PurchaseContractSerializer(serializers.ModelSerializer):
    """PurchaseContract serializer."""

    po_no = serializers.CharField(source='po.order_no', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    po_lines = PurchaseOrderLineSerializer(source='po.lines', many=True, read_only=True)

    class Meta:
        model = PurchaseContract
        fields = [
            'id',
            'contract_no',
            'po',
            'po_no',
            'supplier',
            'supplier_name',
            'project',
            'project_name',
            'title',
            'contract_date',
            'effective_date',
            'expiry_date',
            'total_amount',
            'tax_rate',
            'tax_amount',
            'total_with_tax',
            'payment_terms',
            'delivery_terms',
            'quality_terms',
            'warranty_terms',
            'buyer_signer',
            'seller_signer',
            'signed_date',
            'status',
            'status_display',
            'notes',
            'po_lines',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['contract_no', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create contract and auto-fill from PO."""
        po = validated_data.get('po')
        if po:
            if not validated_data.get('supplier'):
                validated_data['supplier'] = po.supplier
            if not validated_data.get('project'):
                validated_data['project'] = po.project
            if not validated_data.get('total_amount'):
                validated_data['total_amount'] = po.total_amount
            if not validated_data.get('tax_rate'):
                validated_data['tax_rate'] = po.tax_rate
            if not validated_data.get('tax_amount'):
                validated_data['tax_amount'] = po.tax_amount
            if not validated_data.get('total_with_tax'):
                validated_data['total_with_tax'] = po.total_with_tax

        return super().create(validated_data)
