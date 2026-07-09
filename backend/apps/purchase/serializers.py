"""
Serializers for purchase app.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers


def _to_decimal(value, default='0'):
    """把前端明细行的数值字段(可能是字符串数字/None)安全转 Decimal，
    避免原始字符串塞入模型后 qty*price 触发 TypeError 500(契约脆弱性)。"""
    if value is None or value == '':
        value = default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)

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

        # 预算事前控制：先汇总不含税总额，超项目材料预算则直接拒绝（raise ValidationError）。
        # 在建单前拦截，避免生成又回滚的孤儿单号。
        parsed_lines = []
        total_amount = Decimal('0')
        for line_data in lines_data:
            if line_data.get('item') and line_data.get('qty'):
                qty = _to_decimal(line_data['qty'])
                estimated_price = _to_decimal(line_data.get('estimated_price', 0))
                total_amount += qty * estimated_price
                parsed_lines.append((line_data, qty, estimated_price))
        BudgetValidationService.enforce_purchase_request(validated_data.get('project'), total_amount)

        with transaction.atomic():
            pr = PurchaseRequest.objects.create(**validated_data)

            for line_data, qty, estimated_price in parsed_lines:
                PurchaseRequestLine.objects.create(
                    pr=pr,
                    item_id=line_data['item'],
                    qty=qty,
                    estimated_price=estimated_price,
                    required_date=line_data.get('required_date'),
                    project_id=line_data.get('project'),
                    notes=line_data.get('notes', ''),
                    created_by=pr.created_by,
                )

            pr.total_amount = total_amount
            pr.tax_amount = total_amount * pr.tax_rate / 100
            pr.total_with_tax = total_amount + pr.tax_amount
            pr.save()

        return pr

    def update(self, instance, validated_data):
        """Update PR with lines."""
        lines_data = self.initial_data.get('lines', [])

        # 预算事前控制：改单时同样按新明细汇总校验（排除本单已计入的用量）。
        new_total = Decimal('0')
        for line_data in lines_data:
            if line_data.get('item') and line_data.get('qty'):
                new_total += _to_decimal(line_data['qty']) * _to_decimal(line_data.get('estimated_price', 0))
        BudgetValidationService.enforce_purchase_request(
            validated_data.get('project', instance.project), new_total, exclude_pr_id=instance.id
        )

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
                    qty = _to_decimal(line_data['qty'])
                    estimated_price = _to_decimal(line_data.get('estimated_price', 0))
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
                        qty=_to_decimal(line_data['qty']),
                        unit_price=_to_decimal(line_data.get('unit_price', 0)),
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

            # 软删除旧明细（避免硬删触发收货明细 PROTECT 外键 ProtectedError 500）
            for old_line in instance.lines.filter(is_deleted=False):
                old_line.soft_delete()

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    PurchaseOrderLine.objects.create(
                        po=instance,
                        item_id=line_data['item'],
                        qty=_to_decimal(line_data['qty']),
                        unit_price=_to_decimal(line_data.get('unit_price', 0)),
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

    def _validate_receipt_lines(self, po, lines_data, exclude_receipt_id=None):
        """校验收货明细：PO 状态、po_line 归属、剩余可收数量（含同 PO 其他草稿收货单占用）。"""
        if po is None:
            raise serializers.ValidationError({'po': '请选择采购订单'})

        # PO 状态校验：只能对已确认/部分收货的订单收货
        if po.status not in ('CONFIRMED', 'PARTIAL'):
            raise serializers.ValidationError({'po': '只能对已确认或部分收货状态的采购订单创建收货单'})

        # 统计同一 PO 下其他未确认（草稿）收货单已占用的待收数量（按 po_line 归集）
        draft_receipts = GoodsReceipt.objects.filter(po=po, status='DRAFT', is_deleted=False)
        if exclude_receipt_id:
            draft_receipts = draft_receipts.exclude(pk=exclude_receipt_id)
        reserved_by_line = {}
        for draft_line in GoodsReceiptLine.objects.filter(
            receipt__in=draft_receipts, is_deleted=False
        ):
            reserved_by_line[draft_line.po_line_id] = (
                reserved_by_line.get(draft_line.po_line_id, 0) + float(draft_line.qty or 0)
            )

        for line_data in lines_data:
            if not line_data.get('item') or not line_data.get('qty'):
                continue
            po_line_id = line_data.get('po_line')
            if not po_line_id:
                raise serializers.ValidationError({'lines': '收货明细必须关联采购订单明细(po_line)'})
            try:
                po_line = PurchaseOrderLine.objects.get(pk=po_line_id, is_deleted=False)
            except PurchaseOrderLine.DoesNotExist:
                raise serializers.ValidationError({'lines': f'采购订单明细 {po_line_id} 不存在'})
            # po_line 归属校验
            if po_line.po_id != po.id:
                raise serializers.ValidationError({'lines': '收货明细的采购订单明细不属于该采购订单'})

            qty = float(line_data['qty'] or 0)
            if qty <= 0:
                raise serializers.ValidationError({'lines': '收货数量必须大于0'})

            # 剩余可收 = 订单数量 - 已收 - 同PO其他草稿占用
            remaining = float(po_line.qty) - float(po_line.received_qty) - reserved_by_line.get(po_line_id, 0)
            if qty > remaining:
                raise serializers.ValidationError(
                    {'lines': f'物料超收：明细可收数量为 {remaining}，本次收货 {qty}'}
                )
            # 累计本次提交各行占用，避免同一收货单内重复行超收
            reserved_by_line[po_line_id] = reserved_by_line.get(po_line_id, 0) + qty

    def create(self, validated_data):
        """Create GoodsReceipt with lines."""
        lines_data = self.initial_data.get('lines', [])
        self._validate_receipt_lines(validated_data.get('po'), lines_data)

        with transaction.atomic():
            receipt = GoodsReceipt.objects.create(**validated_data)

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    GoodsReceiptLine.objects.create(
                        receipt=receipt,
                        po_line_id=line_data.get('po_line'),
                        item_id=line_data['item'],
                        qty=_to_decimal(line_data['qty']),
                        quality_status=line_data.get('quality_status', 'PENDING'),
                        notes=line_data.get('notes', ''),
                        created_by=receipt.created_by,
                    )

        return receipt

    def update(self, instance, validated_data):
        """Update GoodsReceipt with lines."""
        # 已确认/完成的收货单不允许改写明细（避免库存与已收数量账实分离）
        if instance.status != 'DRAFT':
            raise serializers.ValidationError({'status': '只能修改草稿状态的收货单，已确认收货单请走退货冲销'})

        lines_data = self.initial_data.get('lines', [])
        target_po = validated_data.get('po', instance.po)
        self._validate_receipt_lines(target_po, lines_data, exclude_receipt_id=instance.id)

        with transaction.atomic():
            # Update receipt fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Delete old lines and create new ones (软删除，避免 PROTECT 外键硬删失败)
            for old_line in instance.lines.filter(is_deleted=False):
                old_line.soft_delete()

            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    GoodsReceiptLine.objects.create(
                        receipt=instance,
                        po_line_id=line_data.get('po_line'),
                        item_id=line_data['item'],
                        qty=_to_decimal(line_data['qty']),
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
