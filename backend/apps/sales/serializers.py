"""
Serializers for sales app.
"""
from rest_framework import serializers
from django.db import transaction
from django.db.models import Sum
from .models import (
    SalesQuotation, SalesQuotationLine,
    SalesOrder, SalesOrderLine,
    DeliveryOrder, DeliveryOrderLine
)


class SalesQuotationLineSerializer(serializers.ModelSerializer):
    """SalesQuotationLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    
    class Meta:
        model = SalesQuotationLine
        fields = [
            'id', 'quotation', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'unit_price', 'line_amount', 'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount']


class SalesQuotationSerializer(serializers.ModelSerializer):
    """SalesQuotation serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = SalesQuotationLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = SalesQuotation
        fields = [
            'id', 'quote_no', 'customer', 'customer_name', 'project', 'project_name',
            'quote_date', 'valid_until', 'status', 'status_display', 'version',
            'total_amount', 'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['quote_no', 'quote_date', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create quotation with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            quotation = SalesQuotation.objects.create(**validated_data)
            
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    SalesQuotationLine.objects.create(
                        quotation=quotation,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=quotation.created_by
                    )
            
            # Update total amount
            total = quotation.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            quotation.total_amount = total
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
                if line_data.get('item') and line_data.get('qty'):
                    SalesQuotationLine.objects.create(
                        quotation=instance,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )
            
            # Update total amount
            total = instance.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            instance.total_amount = total
            instance.save()
        
        return instance


class SalesOrderLineSerializer(serializers.ModelSerializer):
    """SalesOrderLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    remaining_qty = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesOrderLine
        fields = [
            'id', 'so', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'unit_price', 'line_amount', 'delivered_qty', 'remaining_qty',
            'notes', 'is_deleted'
        ]
        read_only_fields = ['line_amount', 'delivered_qty']
    
    def get_remaining_qty(self, obj):
        return float(obj.qty - obj.delivered_qty)


class SalesOrderLineWriteSerializer(serializers.Serializer):
    """Serializer for creating/updating SO lines."""
    item = serializers.IntegerField()
    qty = serializers.DecimalField(max_digits=15, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class SalesOrderSerializer(serializers.ModelSerializer):
    """SalesOrder serializer."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = SalesOrderLineSerializer(many=True, read_only=True)
    
    def get_project_name(self, obj):
        return obj.project.name if obj.project else '未关联项目'
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'order_no', 'customer', 'customer_name', 'project', 'project_name',
            'order_date', 'delivery_date', 'status', 'status_display', 'total_amount',
            'payment_terms', 'notes', 'lines', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['order_no', 'order_date', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create SO with lines."""
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            so = SalesOrder.objects.create(**validated_data)
            
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    SalesOrderLine.objects.create(
                        so=so,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=so.created_by
                    )
            
            # Update total amount
            total = so.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            so.total_amount = total
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
                if line_data.get('item') and line_data.get('qty'):
                    SalesOrderLine.objects.create(
                        so=instance,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        unit_price=line_data.get('unit_price', 0),
                        notes=line_data.get('notes', ''),
                        created_by=instance.created_by
                    )
            
            # Update total amount
            total = instance.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            instance.total_amount = total
            instance.save()
        
        return instance


class DeliveryOrderLineSerializer(serializers.ModelSerializer):
    """DeliveryOrderLine serializer."""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_unit = serializers.CharField(source='item.get_unit_display', read_only=True)
    
    class Meta:
        model = DeliveryOrderLine
        fields = [
            'id', 'delivery', 'so_line', 'item', 'item_sku', 'item_name', 'item_unit',
            'qty', 'notes', 'is_deleted'
        ]


class DeliveryOrderSerializer(serializers.ModelSerializer):
    """DeliveryOrder serializer."""
    so_no = serializers.CharField(source='so.order_no', read_only=True)
    customer_name = serializers.CharField(source='so.customer.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = DeliveryOrderLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = DeliveryOrder
        fields = [
            'id', 'delivery_no', 'so', 'so_no', 'customer_name', 'warehouse', 'warehouse_name',
            'delivery_date', 'status', 'status_display', 'notes', 'lines',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['delivery_no', 'created_at', 'updated_at']
    
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

