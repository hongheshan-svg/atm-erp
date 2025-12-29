"""
生产领料/退料序列化器
"""
from rest_framework import serializers
from django.db import transaction
from .material_models import (
    MaterialRequisition, MaterialRequisitionLine,
    MaterialReturn, MaterialReturnLine
)


class MaterialRequisitionLineSerializer(serializers.ModelSerializer):
    """领料单明细序列化器"""
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_spec = serializers.CharField(source='item.spec', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    pending_qty = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    line_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = MaterialRequisitionLine
        fields = [
            'id', 'requisition', 'item', 'item_sku', 'item_name',
            'item_spec', 'item_unit', 'qty', 'issued_qty', 'pending_qty',
            'unit_cost', 'line_amount', 'notes'
        ]
        read_only_fields = ['requisition', 'issued_qty']


class MaterialRequisitionSerializer(serializers.ModelSerializer):
    """领料单序列化器"""
    requisition_type_display = serializers.CharField(
        source='get_requisition_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    project_name = serializers.CharField(
        source='project.name', read_only=True
    )
    project_code = serializers.CharField(
        source='project.code', read_only=True
    )
    aftersales_order_no = serializers.CharField(
        source='aftersales_order.order_no', read_only=True
    )
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True
    )
    requestor_name = serializers.SerializerMethodField()
    warehouse_operator_name = serializers.SerializerMethodField()
    total_qty = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    issued_qty = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    
    lines = MaterialRequisitionLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = MaterialRequisition
        fields = [
            'id', 'requisition_no', 'requisition_type', 'requisition_type_display',
            'project', 'project_name', 'project_code',
            'aftersales_order', 'aftersales_order_no',
            'warehouse', 'warehouse_name',
            'status', 'status_display',
            'requestor', 'requestor_name', 'request_date', 'required_date',
            'warehouse_operator', 'warehouse_operator_name', 'issue_date',
            'total_qty', 'issued_qty',
            'notes', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'requisition_no', 'requestor', 'warehouse_operator', 'issue_date'
        ]
    
    def get_requestor_name(self, obj):
        if obj.requestor:
            return f"{obj.requestor.last_name}{obj.requestor.first_name}" or obj.requestor.username
        return ''
    
    def get_warehouse_operator_name(self, obj):
        if obj.warehouse_operator:
            return f"{obj.warehouse_operator.last_name}{obj.warehouse_operator.first_name}" or obj.warehouse_operator.username
        return ''
    
    def create(self, validated_data):
        validated_data['requestor'] = self.context['request'].user
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            requisition = MaterialRequisition.objects.create(**validated_data)
            
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    MaterialRequisitionLine.objects.create(
                        requisition=requisition,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        notes=line_data.get('notes', ''),
                        created_by=self.context['request'].user
                    )
            
            return requisition


class MaterialRequisitionListSerializer(serializers.ModelSerializer):
    """领料单列表序列化器（简化版）"""
    requisition_type_display = serializers.CharField(
        source='get_requisition_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    project_name = serializers.CharField(
        source='project.name', read_only=True
    )
    aftersales_order_no = serializers.CharField(
        source='aftersales_order.order_no', read_only=True
    )
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True
    )
    requestor_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MaterialRequisition
        fields = [
            'id', 'requisition_no', 'requisition_type', 'requisition_type_display',
            'project', 'project_name', 'aftersales_order', 'aftersales_order_no',
            'warehouse', 'warehouse_name', 'status', 'status_display',
            'requestor', 'requestor_name', 'request_date', 'required_date',
            'line_count', 'created_at'
        ]
    
    def get_requestor_name(self, obj):
        if obj.requestor:
            return f"{obj.requestor.last_name}{obj.requestor.first_name}" or obj.requestor.username
        return ''
    
    def get_line_count(self, obj):
        return obj.lines.count()


# =========== 退料单序列化器 ===========

class MaterialReturnLineSerializer(serializers.ModelSerializer):
    """退料单明细序列化器"""
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_spec = serializers.CharField(source='item.spec', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    condition_display = serializers.CharField(
        source='get_condition_display', read_only=True
    )
    pending_qty = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    line_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = MaterialReturnLine
        fields = [
            'id', 'material_return', 'item', 'item_sku', 'item_name',
            'item_spec', 'item_unit', 'qty', 'received_qty', 'pending_qty',
            'condition', 'condition_display', 'unit_cost', 'line_amount', 'notes'
        ]
        read_only_fields = ['material_return', 'received_qty']


class MaterialReturnSerializer(serializers.ModelSerializer):
    """退料单序列化器"""
    return_type_display = serializers.CharField(
        source='get_return_type_display', read_only=True
    )
    return_reason_display = serializers.CharField(
        source='get_return_reason_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    project_name = serializers.CharField(
        source='project.name', read_only=True
    )
    project_code = serializers.CharField(
        source='project.code', read_only=True
    )
    aftersales_order_no = serializers.CharField(
        source='aftersales_order.order_no', read_only=True
    )
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True
    )
    requestor_name = serializers.SerializerMethodField()
    warehouse_operator_name = serializers.SerializerMethodField()
    total_qty = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    received_qty = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True
    )
    
    lines = MaterialReturnLineSerializer(many=True, read_only=True)
    
    class Meta:
        model = MaterialReturn
        fields = [
            'id', 'return_no', 'return_type', 'return_type_display',
            'return_reason', 'return_reason_display',
            'project', 'project_name', 'project_code',
            'aftersales_order', 'aftersales_order_no',
            'warehouse', 'warehouse_name',
            'status', 'status_display',
            'requestor', 'requestor_name', 'request_date',
            'warehouse_operator', 'warehouse_operator_name', 'receive_date',
            'total_qty', 'received_qty',
            'notes', 'lines',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'return_no', 'requestor', 'warehouse_operator', 'receive_date'
        ]
    
    def get_requestor_name(self, obj):
        if obj.requestor:
            return f"{obj.requestor.last_name}{obj.requestor.first_name}" or obj.requestor.username
        return ''
    
    def get_warehouse_operator_name(self, obj):
        if obj.warehouse_operator:
            return f"{obj.warehouse_operator.last_name}{obj.warehouse_operator.first_name}" or obj.warehouse_operator.username
        return ''
    
    def create(self, validated_data):
        validated_data['requestor'] = self.context['request'].user
        lines_data = self.initial_data.get('lines', [])
        
        with transaction.atomic():
            material_return = MaterialReturn.objects.create(**validated_data)
            
            for line_data in lines_data:
                if line_data.get('item') and line_data.get('qty'):
                    MaterialReturnLine.objects.create(
                        material_return=material_return,
                        item_id=line_data['item'],
                        qty=line_data['qty'],
                        condition=line_data.get('condition', 'GOOD'),
                        notes=line_data.get('notes', ''),
                        created_by=self.context['request'].user
                    )
            
            return material_return


class MaterialReturnListSerializer(serializers.ModelSerializer):
    """退料单列表序列化器（简化版）"""
    return_type_display = serializers.CharField(
        source='get_return_type_display', read_only=True
    )
    return_reason_display = serializers.CharField(
        source='get_return_reason_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    project_name = serializers.CharField(
        source='project.name', read_only=True
    )
    aftersales_order_no = serializers.CharField(
        source='aftersales_order.order_no', read_only=True
    )
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True
    )
    requestor_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MaterialReturn
        fields = [
            'id', 'return_no', 'return_type', 'return_type_display',
            'return_reason', 'return_reason_display',
            'project', 'project_name', 'aftersales_order', 'aftersales_order_no',
            'warehouse', 'warehouse_name', 'status', 'status_display',
            'requestor', 'requestor_name', 'request_date',
            'line_count', 'created_at'
        ]
    
    def get_requestor_name(self, obj):
        if obj.requestor:
            return f"{obj.requestor.last_name}{obj.requestor.first_name}" or obj.requestor.username
        return ''
    
    def get_line_count(self, obj):
        return obj.lines.count()

