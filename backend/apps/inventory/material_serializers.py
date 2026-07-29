"""
生产领料/退料序列化器
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from rest_framework import serializers

from .material_models import MaterialRequisition, MaterialRequisitionLine, MaterialReturn, MaterialReturnLine


class MaterialRequisitionLineSerializer(serializers.ModelSerializer):
    """领料单明细序列化器"""

    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_spec = serializers.CharField(source='item.specification', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    pending_qty = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    line_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = MaterialRequisitionLine
        fields = [
            'id',
            'requisition',
            'item',
            'item_sku',
            'item_name',
            'item_spec',
            'item_unit',
            'qty',
            'issued_qty',
            'pending_qty',
            'unit_cost',
            'line_amount',
            'notes',
        ]
        read_only_fields = ['requisition', 'issued_qty']


class MaterialRequisitionSerializer(serializers.ModelSerializer):
    """领料单序列化器"""

    requisition_type_display = serializers.CharField(source='get_requisition_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    aftersales_order_no = serializers.CharField(source='aftersales_order.order_no', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    requestor_name = serializers.SerializerMethodField()
    warehouse_operator_name = serializers.SerializerMethodField()
    total_qty = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    issued_qty = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    lines = MaterialRequisitionLineSerializer(many=True, read_only=True)

    class Meta:
        model = MaterialRequisition
        fields = [
            'id',
            'requisition_no',
            'requisition_type',
            'requisition_type_display',
            'project',
            'project_name',
            'project_code',
            'aftersales_order',
            'aftersales_order_no',
            'warehouse',
            'warehouse_name',
            'status',
            'status_display',
            'requestor',
            'requestor_name',
            'request_date',
            'required_date',
            'warehouse_operator',
            'warehouse_operator_name',
            'issue_date',
            'total_qty',
            'issued_qty',
            'notes',
            'lines',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['requisition_no', 'requestor', 'warehouse_operator', 'issue_date']

    def get_requestor_name(self, obj) -> str:
        if obj.requestor:
            return f'{obj.requestor.last_name}{obj.requestor.first_name}' or obj.requestor.username
        return ''

    def get_warehouse_operator_name(self, obj) -> str:
        if obj.warehouse_operator:
            return (
                f'{obj.warehouse_operator.last_name}{obj.warehouse_operator.first_name}'
                or obj.warehouse_operator.username
            )
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
                        created_by=self.context['request'].user,
                    )

            return requisition

    def update(self, instance, validated_data):
        """更新领料单表头并同步明细（软删旧行后重建），否则编辑明细会被静默丢弃。"""
        from django.utils import timezone

        lines_data = self.initial_data.get('lines', None)
        user = self.context['request'].user

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # lines 未提供则只更新表头，避免误删既有明细
            if lines_data is not None:
                instance.lines.filter(is_deleted=False).update(is_deleted=True, deleted_at=timezone.now())
                for line_data in lines_data:
                    if line_data.get('item') and line_data.get('qty'):
                        MaterialRequisitionLine.objects.create(
                            requisition=instance,
                            item_id=line_data['item'],
                            qty=line_data['qty'],
                            notes=line_data.get('notes', ''),
                            created_by=user,
                        )

        return instance


class MaterialRequisitionListSerializer(serializers.ModelSerializer):
    """领料单列表序列化器（简化版）"""

    requisition_type_display = serializers.CharField(source='get_requisition_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    aftersales_order_no = serializers.CharField(source='aftersales_order.order_no', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    requestor_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = MaterialRequisition
        fields = [
            'id',
            'requisition_no',
            'requisition_type',
            'requisition_type_display',
            'project',
            'project_name',
            'aftersales_order',
            'aftersales_order_no',
            'warehouse',
            'warehouse_name',
            'status',
            'status_display',
            'requestor',
            'requestor_name',
            'request_date',
            'required_date',
            'line_count',
            'created_at',
        ]

    def get_requestor_name(self, obj) -> str:
        if obj.requestor:
            return f'{obj.requestor.last_name}{obj.requestor.first_name}' or obj.requestor.username
        return ''

    def get_line_count(self, obj) -> int:
        return obj.lines.count()


# =========== 退料单序列化器 ===========


class MaterialReturnLineSerializer(serializers.ModelSerializer):
    """退料单明细序列化器"""

    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_spec = serializers.CharField(source='item.specification', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    pending_qty = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    line_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = MaterialReturnLine
        fields = [
            'id',
            'material_return',
            'item',
            'item_sku',
            'item_name',
            'item_spec',
            'item_unit',
            'qty',
            'received_qty',
            'pending_qty',
            'condition',
            'condition_display',
            'unit_cost',
            'line_amount',
            'notes',
        ]
        read_only_fields = ['material_return', 'received_qty']


class MaterialReturnSerializer(serializers.ModelSerializer):
    """退料单序列化器"""

    return_type_display = serializers.CharField(source='get_return_type_display', read_only=True)
    return_reason_display = serializers.CharField(source='get_return_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    aftersales_order_no = serializers.CharField(source='aftersales_order.order_no', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    requestor_name = serializers.SerializerMethodField()
    warehouse_operator_name = serializers.SerializerMethodField()
    total_qty = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    received_qty = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    lines = MaterialReturnLineSerializer(many=True, read_only=True)

    class Meta:
        model = MaterialReturn
        fields = [
            'id',
            'return_no',
            'return_type',
            'return_type_display',
            'return_reason',
            'return_reason_display',
            'project',
            'project_name',
            'project_code',
            'aftersales_order',
            'aftersales_order_no',
            'warehouse',
            'warehouse_name',
            'status',
            'status_display',
            'requestor',
            'requestor_name',
            'request_date',
            'warehouse_operator',
            'warehouse_operator_name',
            'receive_date',
            'total_qty',
            'received_qty',
            'notes',
            'lines',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['return_no', 'requestor', 'warehouse_operator', 'receive_date']

    def get_requestor_name(self, obj) -> str:
        if obj.requestor:
            return f'{obj.requestor.last_name}{obj.requestor.first_name}' or obj.requestor.username
        return ''

    def get_warehouse_operator_name(self, obj) -> str:
        if obj.warehouse_operator:
            return (
                f'{obj.warehouse_operator.last_name}{obj.warehouse_operator.first_name}'
                or obj.warehouse_operator.username
            )
        return ''

    @staticmethod
    def _project_return_unit_cost(project_id, item_id, requested_qty, exclude_return_id=None):
        from apps.inventory.models import StockMove

        outbound = StockMove.objects.filter(
            project_id=project_id,
            item_id=item_id,
            move_type='OUT_PROJECT',
            status='COMPLETED',
            is_deleted=False,
        ).aggregate(total_qty=Sum('qty'), total_cost=Sum(F('qty') * F('unit_cost')))
        returned = StockMove.objects.filter(
            StockMove.material_return_q(),
            project_id=project_id,
            item_id=item_id,
            status='COMPLETED',
            is_deleted=False,
        ).aggregate(total_qty=Sum('qty'), total_cost=Sum(F('qty') * F('unit_cost')))

        pending = MaterialReturnLine.objects.filter(
            material_return__project_id=project_id,
            material_return__status__in=['DRAFT', 'PENDING', 'INSPECTING', 'PARTIAL'],
            item_id=item_id,
            is_deleted=False,
        )
        if exclude_return_id:
            pending = pending.exclude(material_return_id=exclude_return_id)
        pending_qty = pending.aggregate(total=Sum(F('qty') - F('received_qty')))['total'] or Decimal('0')

        issued_qty = outbound['total_qty'] or Decimal('0')
        returned_qty = returned['total_qty'] or Decimal('0')
        available_qty = issued_qty - returned_qty - pending_qty
        if requested_qty > available_qty:
            raise serializers.ValidationError(
                f'物料 {item_id} 退料数量 {requested_qty} 超过项目净可退数量 {available_qty}'
            )

        net_qty = issued_qty - returned_qty
        net_cost = (outbound['total_cost'] or Decimal('0')) - (returned['total_cost'] or Decimal('0'))
        return net_cost / net_qty if net_qty > 0 else Decimal('0')

    def _prepare_lines(self, attrs, lines_data, exclude_return_id=None):
        project = attrs.get('project')
        warehouse = attrs.get('warehouse')
        return_type = attrs.get('return_type')
        requested_by_item = {}
        prepared = []

        for line_data in lines_data:
            if not line_data.get('item') or line_data.get('qty') in (None, ''):
                continue
            item_id = int(line_data['item'])
            qty = Decimal(str(line_data['qty']))
            if qty <= 0:
                raise serializers.ValidationError(f'物料 {item_id} 的退料数量必须大于 0')
            requested_by_item[item_id] = requested_by_item.get(item_id, Decimal('0')) + qty

            if return_type == 'PROJECT':
                if project is None:
                    raise serializers.ValidationError('项目退料必须关联项目')
                unit_cost = self._project_return_unit_cost(
                    project.id,
                    item_id,
                    requested_by_item[item_id],
                    exclude_return_id=exclude_return_id,
                )
            else:
                from apps.inventory.models import Stock

                stock = Stock.objects.filter(warehouse=warehouse, item_id=item_id, is_deleted=False).first()
                unit_cost = stock.weighted_avg_cost if stock else Decimal('0')

            prepared.append(
                {
                    'item_id': item_id,
                    'qty': qty,
                    'unit_cost': unit_cost,
                    'condition': line_data.get('condition', 'GOOD'),
                    'notes': line_data.get('notes', ''),
                }
            )
        return prepared

    def create(self, validated_data):
        validated_data['requestor'] = self.context['request'].user
        lines_data = self.initial_data.get('lines', [])

        with transaction.atomic():
            if validated_data.get('project'):
                from apps.projects.models import Project

                Project.objects.select_for_update().get(pk=validated_data['project'].pk)
            prepared_lines = self._prepare_lines(validated_data, lines_data)
            material_return = MaterialReturn.objects.create(**validated_data)

            for line_data in prepared_lines:
                MaterialReturnLine.objects.create(
                    material_return=material_return,
                    created_by=self.context['request'].user,
                    **line_data,
                )

            return material_return

    def update(self, instance, validated_data):
        """更新退料单表头并同步明细（软删旧行后重建），否则编辑明细会被静默丢弃。"""
        from django.utils import timezone

        lines_data = self.initial_data.get('lines', None)
        user = self.context['request'].user

        with transaction.atomic():
            instance = MaterialReturn.objects.select_for_update().get(pk=instance.pk)
            prospective = {
                'project': validated_data.get('project', instance.project),
                'warehouse': validated_data.get('warehouse', instance.warehouse),
                'return_type': validated_data.get('return_type', instance.return_type),
            }
            if prospective['project']:
                from apps.projects.models import Project

                Project.objects.select_for_update().get(pk=prospective['project'].pk)
            prepared_lines = (
                self._prepare_lines(prospective, lines_data, exclude_return_id=instance.pk)
                if lines_data is not None
                else None
            )
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if prepared_lines is not None:
                instance.lines.filter(is_deleted=False).update(is_deleted=True, deleted_at=timezone.now())
                for line_data in prepared_lines:
                    MaterialReturnLine.objects.create(material_return=instance, created_by=user, **line_data)

        return instance


class MaterialReturnListSerializer(serializers.ModelSerializer):
    """退料单列表序列化器（简化版）"""

    return_type_display = serializers.CharField(source='get_return_type_display', read_only=True)
    return_reason_display = serializers.CharField(source='get_return_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    aftersales_order_no = serializers.CharField(source='aftersales_order.order_no', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    requestor_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()

    class Meta:
        model = MaterialReturn
        fields = [
            'id',
            'return_no',
            'return_type',
            'return_type_display',
            'return_reason',
            'return_reason_display',
            'project',
            'project_name',
            'aftersales_order',
            'aftersales_order_no',
            'warehouse',
            'warehouse_name',
            'status',
            'status_display',
            'requestor',
            'requestor_name',
            'request_date',
            'line_count',
            'created_at',
        ]

    def get_requestor_name(self, obj) -> str:
        if obj.requestor:
            return f'{obj.requestor.last_name}{obj.requestor.first_name}' or obj.requestor.username
        return ''

    def get_line_count(self, obj) -> int:
        return obj.lines.count()
