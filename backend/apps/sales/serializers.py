"""
Serializers for sales app.
"""
from rest_framework import serializers
from django.db import transaction
from django.db.models import Sum
from .models import (
    SalesQuotation, SalesQuotationLine,
    SalesOrder, SalesOrderLine,
    DeliveryOrder, DeliveryOrderLine,
    SalesContract
)


class SalesQuotationLineSerializer(serializers.ModelSerializer):
    """SalesQuotationLine serializer."""
    # 物料关联信息（可选）
    item_name = serializers.SerializerMethodField()
    item_sku = serializers.SerializerMethodField()
    item_unit = serializers.SerializerMethodField()
    item_spec = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesQuotationLine
        fields = [
            'id', 'quotation', 'item', 'item_sku', 'item_name', 'item_unit', 'item_spec',
            'custom_name', 'custom_spec', 'custom_unit',
            'qty', 'unit_price', 'line_amount', 'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount']
    
    def get_item_name(self, obj):
        """返回产品名称：优先物料，其次手动填写"""
        if obj.item:
            return obj.item.name
        return obj.custom_name or ''
    
    def get_item_sku(self, obj):
        """返回产品编码"""
        if obj.item:
            return obj.item.sku
        return ''
    
    def get_item_unit(self, obj):
        """返回单位"""
        if obj.item:
            return obj.item.get_unit_display()
        return obj.custom_unit or '件'
    
    def get_item_spec(self, obj):
        """返回规格型号"""
        if obj.item:
            return obj.item.specification or ''
        return obj.custom_spec or ''


class SalesQuotationSerializer(serializers.ModelSerializer):
    """SalesQuotation serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    lines = SalesQuotationLineSerializer(many=True, read_only=True)
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''
    
    class Meta:
        model = SalesQuotation
        fields = [
            'id', 'quote_no', 'customer', 'customer_name', 'project', 'project_name',
            'quote_date', 'valid_until', 'status', 'status_display', 'version',
            'tax_rate', 'tax_rate_display', 'total_amount', 'tax_amount', 'total_with_tax',
            'notes', 'lines', 'is_deleted', 'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['quote_no', 'quote_date', 'tax_amount', 'total_with_tax', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create quotation with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            quotation = SalesQuotation.objects.create(**validated_data)
            
            for line_data in lines_data:
                # 支持两种模式：选择物料 或 手动填写产品信息
                has_item = line_data.get('item')
                has_custom = line_data.get('custom_name')
                
                if (has_item or has_custom) and line_data.get('qty'):
                    SalesQuotationLine.objects.create(
                        quotation=quotation,
                        item_id=line_data.get('item') if has_item else None,
                        custom_name=line_data.get('custom_name', ''),
                        custom_spec=line_data.get('custom_spec', ''),
                        custom_unit=line_data.get('custom_unit', '件'),
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=quotation.created_by
                    )
            
            # Update total amount and tax
            total = quotation.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            quotation.total_amount = total
            quotation.tax_amount = total * quotation.tax_rate / 100
            quotation.total_with_tax = total + quotation.tax_amount
            quotation.save()
        
        return quotation
    
    def update(self, instance, validated_data):
        """Update quotation with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            # Update quotation fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Delete old lines and create new ones
            instance.lines.all().delete()
            
            for line_data in lines_data:
                # 支持两种模式：选择物料 或 手动填写产品信息
                has_item = line_data.get('item')
                has_custom = line_data.get('custom_name')
                
                if (has_item or has_custom) and line_data.get('qty'):
                    SalesQuotationLine.objects.create(
                        quotation=instance,
                        item_id=line_data.get('item') if has_item else None,
                        custom_name=line_data.get('custom_name', ''),
                        custom_spec=line_data.get('custom_spec', ''),
                        custom_unit=line_data.get('custom_unit', '件'),
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )
            
            # Update total amount and tax
            total = instance.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            instance.total_amount = total
            instance.tax_amount = total * instance.tax_rate / 100
            instance.total_with_tax = total + instance.tax_amount
            instance.save()
        
        return instance


class SalesOrderLineSerializer(serializers.ModelSerializer):
    """SalesOrderLine serializer."""
    # 物料关联信息（可选）
    item_name = serializers.SerializerMethodField()
    item_sku = serializers.SerializerMethodField()
    item_unit = serializers.SerializerMethodField()
    item_spec = serializers.SerializerMethodField()
    remaining_qty = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesOrderLine
        fields = [
            'id', 'so', 'item', 'item_sku', 'item_name', 'item_unit', 'item_spec',
            'custom_name', 'custom_spec', 'custom_unit',
            'qty', 'unit_price', 'line_amount', 'delivered_qty', 'remaining_qty',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount', 'delivered_qty']
    
    def get_item_name(self, obj):
        """返回产品名称：优先物料，其次手动填写"""
        if obj.item:
            return obj.item.name
        return obj.custom_name or ''
    
    def get_item_sku(self, obj):
        """返回产品编码"""
        if obj.item:
            return obj.item.sku
        return ''
    
    def get_item_unit(self, obj):
        """返回单位"""
        if obj.item:
            return obj.item.get_unit_display()
        return obj.custom_unit or '件'
    
    def get_item_spec(self, obj):
        """返回规格型号"""
        if obj.item:
            return obj.item.specification or ''
        return obj.custom_spec or ''
    
    def get_remaining_qty(self, obj):
        return float(obj.qty - obj.delivered_qty)


class SalesOrderLineWriteSerializer(serializers.Serializer):
    """Serializer for creating/updating SO lines."""
    # 物料可选（非标定制可不选）
    item = serializers.IntegerField(required=False, allow_null=True)
    # 手动填写的产品信息
    custom_name = serializers.CharField(required=False, allow_blank=True, default='')
    custom_spec = serializers.CharField(required=False, allow_blank=True, default='')
    custom_unit = serializers.CharField(required=False, allow_blank=True, default='件')
    
    qty = serializers.DecimalField(max_digits=15, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class SalesOrderSerializer(serializers.ModelSerializer):
    """SalesOrder serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_address = serializers.CharField(source='customer.address', read_only=True, allow_null=True)
    customer_contact = serializers.CharField(source='customer.contact_person', read_only=True, allow_null=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, allow_null=True)
    project_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    payment_terms_display = serializers.CharField(source='get_payment_terms_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    lines = SalesOrderLineSerializer(many=True, read_only=True)
    
    def get_project_name(self, obj):
        return obj.project.name if obj.project else '未关联项目'
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_no', 'customer_order_no', 'customer', 'customer_name', 
            'customer_address', 'customer_contact', 'customer_phone',
            'project', 'project_name',
            'order_date', 'delivery_date', 'status', 'status_display',
            'tax_rate', 'tax_rate_display', 'total_amount', 'tax_amount', 'total_with_tax',
            'payment_terms', 'payment_terms_display', 'payment_method', 'payment_method_display',
            'payment_terms_detail', 'notes', 'lines', 'is_deleted', 
            'created_by', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order_date', 'tax_amount', 'total_with_tax', 'created_at', 'updated_at']
        extra_kwargs = {
            # 创建时可填写，留空则后端自动生成；更新时不提交也不报错
            'order_no': {'required': False, 'allow_blank': True},
            # 客户订单号可选
            'customer_order_no': {'required': False, 'allow_blank': True},
        }
    
    def create(self, validated_data):
        """Create SO with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            so = SalesOrder.objects.create(**validated_data)
            
            for line_data in lines_data:
                # 支持两种模式：选择物料 或 手动填写产品信息
                has_item = line_data.get('item')
                has_custom = line_data.get('custom_name')
                
                if (has_item or has_custom) and line_data.get('qty'):
                    SalesOrderLine.objects.create(
                        so=so,
                        item_id=line_data.get('item') if has_item else None,
                        custom_name=line_data.get('custom_name', ''),
                        custom_spec=line_data.get('custom_spec', ''),
                        custom_unit=line_data.get('custom_unit', '件'),
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=so.created_by
                    )
            
            # Update total amount and tax
            total = so.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            so.total_amount = total
            so.tax_amount = total * so.tax_rate / 100
            so.total_with_tax = total + so.tax_amount
            so.save()
        
        return so
    
    def update(self, instance, validated_data):
        """Update SO with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            # Update SO fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Delete old lines and create new ones
            instance.lines.all().delete()
            
            for line_data in lines_data:
                # 支持两种模式：选择物料 或 手动填写产品信息
                has_item = line_data.get('item')
                has_custom = line_data.get('custom_name')
                
                if (has_item or has_custom) and line_data.get('qty'):
                    SalesOrderLine.objects.create(
                        so=instance,
                        item_id=line_data.get('item') if has_item else None,
                        custom_name=line_data.get('custom_name', ''),
                        custom_spec=line_data.get('custom_spec', ''),
                        custom_unit=line_data.get('custom_unit', '件'),
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )
            
            # Update total amount and tax
            total = instance.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            instance.total_amount = total
            instance.tax_amount = total * instance.tax_rate / 100
            instance.total_with_tax = total + instance.tax_amount
            instance.save()
        
        return instance


class DeliveryOrderLineSerializer(serializers.ModelSerializer):
    """DeliveryOrderLine serializer."""
    item_name = serializers.SerializerMethodField()
    item_sku = serializers.SerializerMethodField()
    item_unit = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()  # 前端兼容字段
    specification = serializers.SerializerMethodField()  # 规格型号
    
    def get_item_name(self, obj):
        if obj.item:
            return obj.item.name
        return ''
    
    def get_item_sku(self, obj):
        if obj.item:
            return obj.item.sku
        return ''
    
    def get_item_unit(self, obj):
        if obj.item:
            return obj.item.get_unit_display()
        return ''
    
    def get_unit(self, obj):
        if obj.item:
            return obj.item.get_unit_display()
        return ''
    
    def get_specification(self, obj):
        if obj.item:
            return obj.item.specification or ''
        return ''
    
    class Meta:
        model = DeliveryOrderLine
        fields = [
            'id', 'delivery', 'so_line', 'item', 'item_sku', 'item_name', 'item_unit',
            'unit', 'specification',
            'qty', 'notes', 'is_deleted'
        ]


class DeliveryOrderSerializer(serializers.ModelSerializer):
    """DeliveryOrder serializer."""
    so_no = serializers.CharField(source='so.order_no', read_only=True)
    customer_name = serializers.CharField(source='so.customer.name', read_only=True)
    customer_contact = serializers.CharField(source='so.customer.contact_person', read_only=True)
    customer_phone = serializers.CharField(source='so.customer.phone', read_only=True)
    customer_address = serializers.CharField(source='so.customer.address', read_only=True)
    project_name = serializers.CharField(source='so.project.name', read_only=True, allow_null=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    packaging_type_display = serializers.CharField(source='get_packaging_type_display', read_only=True)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    lines = DeliveryOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = DeliveryOrder
        fields = [
            'id', 'delivery_no', 'so', 'so_no', 
            # 客户信息
            'customer_name', 'customer_contact', 'customer_phone', 'customer_address',
            'project_name',
            # 仓库和日期
            'warehouse', 'warehouse_name', 'delivery_date', 'actual_delivery_date',
            # 状态
            'status', 'status_display',
            # 收货信息
            'receiver_name', 'receiver_phone', 'receiver_address',
            # 包装和保险
            'packaging_type', 'packaging_type_display', 'packaging_notes',
            'needs_insurance', 'insurance_amount',
            # 物流信息
            'logistics_company', 'logistics_contact', 'logistics_phone',
            'tracking_number', 'logistics_notes', 'logistics_cost',
            # 签收信息
            'signed_receipt', 'signed_date', 'signed_by',
            # 其他
            'notes', 'rejection_reason', 'total_amount', 'lines',
            'is_deleted', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['delivery_no', 'created_at', 'updated_at', 'total_amount']
    
    def create(self, validated_data):
        """Create delivery order with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            delivery = DeliveryOrder.objects.create(**validated_data)
            
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    DeliveryOrderLine.objects.create(
                        delivery=delivery,
                        so_line_id=line_data.get('so_line'),
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        notes=line_data.get('notes', ''),
                        created_by=delivery.created_by
                    )
        
        return delivery
    
    def update(self, instance, validated_data):
        """Update delivery order with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            # Update delivery fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Delete old lines and create new ones
            instance.lines.all().delete()
            
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    DeliveryOrderLine.objects.create(
                        delivery=instance,
                        so_line_id=line_data.get('so_line'),
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )
        
        return instance


class SalesContractSerializer(serializers.ModelSerializer):
    """SalesContract serializer."""
    so_no = serializers.CharField(source='so.order_no', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    so_lines = SalesOrderLineSerializer(source='so.lines', many=True, read_only=True)
    
    class Meta:
        model = SalesContract
        fields = [
            'id', 'contract_no', 'so', 'so_no', 'customer', 'customer_name', 
            'project', 'project_name', 'title', 'contract_date', 
            'effective_date', 'expiry_date', 'total_amount', 'tax_rate',
            'tax_amount', 'total_with_tax', 'payment_terms', 'delivery_terms',
            'quality_terms', 'warranty_terms', 'buyer_signer', 'seller_signer',
            'signed_date', 'status', 'status_display', 'notes', 'so_lines',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['contract_no', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create contract and auto-fill from SO."""
        so = validated_data.get('so')
        if so:
            if not validated_data.get('customer'):
                validated_data['customer'] = so.customer
            if not validated_data.get('project'):
                validated_data['project'] = so.project
            if not validated_data.get('total_amount'):
                validated_data['total_amount'] = so.total_amount
            if not validated_data.get('tax_rate'):
                validated_data['tax_rate'] = so.tax_rate
            if not validated_data.get('tax_amount'):
                validated_data['tax_amount'] = so.tax_amount
            if not validated_data.get('total_with_tax'):
                validated_data['total_with_tax'] = so.total_with_tax
        
        return super().create(validated_data)
