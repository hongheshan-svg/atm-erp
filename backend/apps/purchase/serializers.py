"""
Serializers for purchase app.
"""
from rest_framework import serializers
from django.db import transaction
from django.db.models import Sum
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine
)
from .services import BudgetValidationService


class PurchaseRequestLineSerializer(serializers.ModelSerializer):
    """PurchaseRequestLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = PurchaseRequestLine
        fields = [
            'id', 'pr', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'estimated_price', 'line_amount', 'project', 'project_name',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount']


class PurchaseRequestLineCreateSerializer(serializers.ModelSerializer):
    """PurchaseRequestLine serializer for create/update."""
    class Meta:
        model = PurchaseRequestLine
        fields = ['id', 'item', 'qty', 'estimated_price', 'project', 'notes']
        extra_kwargs = {
            'id': {'required': False}
        }


class PurchaseRequestSerializer(serializers.ModelSerializer):
    """PurchaseRequest serializer."""
    project_name = serializers.CharField(source='project.name', read_only=True)
    requestor_name = serializers.CharField(source='requestor.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    lines = PurchaseRequestLineSerializer(many=True, read_only=True)
    budget_info = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseRequest
        fields = [
            'id', 'request_no', 'project', 'project_name', 'requestor', 'requestor_name',
            'request_date', 'required_date', 'status', 'status_display',
            'tax_rate', 'tax_rate_display', 'total_amount', 'tax_amount', 'total_with_tax',
            'notes', 'lines', 'is_deleted', 'created_at', 'updated_at', 'budget_info'
        ]
        read_only_fields = ['request_no', 'requestor', 'request_date', 'tax_amount', 'total_with_tax', 'created_at', 'updated_at']
    
    def get_budget_info(self, obj):
        """Get budget validation info for this request."""
        if not obj.project:
            return None
        return BudgetValidationService.validate_purchase_request(
            obj.project, 
            obj.total_amount,
            exclude_pr_id=obj.id if obj.status in ['APPROVED', 'CONVERTED'] else None
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
                        project_id=line_data.get('project'),
                        notes=line_data.get('notes', ''),
                        created_by=pr.created_by
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
                        project_id=line_data.get('project'),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )
                    total_amount += qty * estimated_price
            
            instance.total_amount = total_amount
            instance.tax_amount = total_amount * instance.tax_rate / 100
            instance.total_with_tax = total_amount + instance.tax_amount
            instance.save()
        
        return instance


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    """PurchaseOrderLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    remaining_qty = serializers.SerializerMethodField()
    
    class Meta:
        model = PurchaseOrderLine
        fields = [
            'id', 'po', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'unit_price', 'line_amount', 'received_qty', 'remaining_qty',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount', 'received_qty']
    
    def get_remaining_qty(self, obj):
        return float(obj.qty - obj.received_qty)


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """PurchaseOrder serializer."""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_rate_display = serializers.CharField(source='get_tax_rate_display', read_only=True)
    payment_terms_display = serializers.CharField(source='get_payment_terms_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'order_no', 'supplier', 'supplier_name', 'project', 'project_name',
            'order_date', 'delivery_date', 'status', 'status_display',
            'tax_rate', 'tax_rate_display', 'total_amount', 'tax_amount', 'total_with_tax',
            'payment_terms', 'payment_terms_display', 'payment_method', 'payment_method_display',
            'payment_terms_detail', 'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order_no', 'order_date', 'tax_amount', 'total_with_tax', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create PO with lines."""
        lines_data = self.initial_data.get('lines', [])
        
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
                        created_by=po.created_by
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
                        created_by=instance.created_by
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
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    quality_status_display = serializers.CharField(source='get_quality_status_display', read_only=True)
    
    class Meta:
        model = GoodsReceiptLine
        fields = [
            'id', 'receipt', 'po_line', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'quality_status', 'quality_status_display', 'notes', 'is_deleted'
        ]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    """GoodsReceipt serializer."""
    po_no = serializers.CharField(source='po.order_no', read_only=True)
    supplier_name = serializers.CharField(source='po.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'receipt_no', 'po', 'po_no', 'supplier_name', 'warehouse', 'warehouse_name',
            'receipt_date', 'status', 'status_display', 'notes', 'lines',
            'is_deleted', 'created_at', 'updated_at'
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
                        created_by=receipt.created_by
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
                        created_by=instance.created_by
                    )
        
        return instance

