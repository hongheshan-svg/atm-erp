"""
生产领料/退料视图
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin

from .material_models import MaterialRequisition, MaterialRequisitionLine, MaterialReturn, MaterialReturnLine
from .material_serializers import (
    MaterialRequisitionLineSerializer,
    MaterialRequisitionListSerializer,
    MaterialRequisitionSerializer,
    MaterialReturnLineSerializer,
    MaterialReturnListSerializer,
    MaterialReturnSerializer,
)
from .models import Stock, StockMove


class MaterialRequisitionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'inventory'
    permission_resource = 'material_requisition'
    """
    领料单视图集
    
    支持操作：
    - 创建领料单（项目领料/售后领料）
    - 提交领料申请
    - 仓库确认备料
    - 执行出库
    """
    queryset = MaterialRequisition.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['requisition_type', 'project', 'aftersales_order', 'warehouse', 'status', 'requestor']
    search_fields = ['requisition_no']
    ordering_fields = ['request_date', 'created_at']
    ordering = ['-created_at']

    # 数据权限规则
    permission_rules = [
        {'field': 'created_by', 'type': 'user'},
        {'field': 'requestor', 'type': 'user'},
        {'field': 'project__manager', 'type': 'user'},
        {'field': 'project__members__user', 'type': 'user'},
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return MaterialRequisitionListSerializer
        return MaterialRequisitionSerializer

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交领料申请 - 进入待审批状态"""
        requisition = self.get_object()

        if requisition.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的领料单'}, status=status.HTTP_400_BAD_REQUEST)

        if not requisition.lines.exists():
            return Response({'error': '领料单没有明细，无法提交'}, status=status.HTTP_400_BAD_REQUEST)

        requisition.status = 'SUBMITTED'  # 改为待审批状态
        requisition.save()

        # TODO: 发送通知给审批人

        return Response(MaterialRequisitionSerializer(requisition).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过领料申请 - 进入待备料状态"""
        requisition = self.get_object()

        if requisition.status != 'SUBMITTED':
            return Response({'error': '只能审批待审批状态的领料单'}, status=status.HTTP_400_BAD_REQUEST)

        requisition.status = 'PENDING'  # 审批通过后进入待备料
        requisition.save()

        # TODO: 发送通知给仓库人员

        return Response(MaterialRequisitionSerializer(requisition).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝领料申请"""
        requisition = self.get_object()

        if requisition.status != 'SUBMITTED':
            return Response({'error': '只能拒绝待审批状态的领料单'}, status=status.HTTP_400_BAD_REQUEST)

        requisition.status = 'REJECTED'
        requisition.save()

        return Response(MaterialRequisitionSerializer(requisition).data)

    @action(detail=True, methods=['post'])
    def start_preparing(self, request, pk=None):
        """开始备料 - 仓库人员开始备料"""
        requisition = self.get_object()

        if requisition.status != 'PENDING':
            return Response({'error': '只能对待备料状态的领料单进行备料'}, status=status.HTTP_400_BAD_REQUEST)

        requisition.status = 'PREPARING'
        requisition.warehouse_operator = request.user
        requisition.save()

        return Response(MaterialRequisitionSerializer(requisition).data)

    @action(detail=True, methods=['post'])
    def ready(self, request, pk=None):
        """备料完成"""
        requisition = self.get_object()

        if requisition.status != 'PREPARING':
            return Response({'error': '只能对备料中状态的领料单标记完成'}, status=status.HTTP_400_BAD_REQUEST)

        requisition.status = 'READY'
        requisition.save()

        # TODO: 发送通知给申请人

        return Response(MaterialRequisitionSerializer(requisition).data)

    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """
        执行出库
        请求体：
        {
            "lines": [
                {"id": 1, "issued_qty": 10},
                {"id": 2, "issued_qty": 5}
            ]
        }
        """
        requisition = self.get_object()

        if requisition.status not in ['READY', 'PARTIAL']:
            return Response(
                {'error': '只能对备料完成或部分出库状态的领料单执行出库'}, status=status.HTTP_400_BAD_REQUEST
            )

        lines_data = request.data.get('lines', [])
        if not lines_data:
            return Response({'error': '请指定出库明细'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            all_issued = True

            for line_data in lines_data:
                line_id = line_data.get('id')
                issued_qty = line_data.get('issued_qty', 0)

                try:
                    line = requisition.lines.get(id=line_id)
                except MaterialRequisitionLine.DoesNotExist:
                    continue

                if issued_qty <= 0:
                    continue

                # 检查库存
                try:
                    stock = Stock.objects.get(warehouse=requisition.warehouse, item=line.item)
                    if stock.qty_available < issued_qty:
                        return Response({'error': f'物料 {line.item.sku} 库存不足'}, status=status.HTTP_400_BAD_REQUEST)
                except Stock.DoesNotExist:
                    return Response({'error': f'物料 {line.item.sku} 无库存记录'}, status=status.HTTP_400_BAD_REQUEST)

                # 更新已出库数量
                line.issued_qty += issued_qty
                line.unit_cost = stock.weighted_avg_cost
                line.save()

                # 创建库存移动记录
                StockMove.objects.create(
                    item=line.item,
                    warehouse_from=requisition.warehouse,
                    qty=issued_qty,
                    unit_cost=stock.weighted_avg_cost,
                    move_type='OUT_PROJECT',
                    reference_type='MaterialRequisition',
                    reference_id=requisition.id,
                    project=requisition.project,
                    move_date=timezone.now(),
                    status='COMPLETED',
                    created_by=request.user,
                )

                # 更新库存
                stock.qty_on_hand -= issued_qty
                stock.save()

                # 检查是否全部出库
                if line.issued_qty < line.qty:
                    all_issued = False

            # 更新领料单状态
            if all_issued and all(l.issued_qty >= l.qty for l in requisition.lines.all()):
                requisition.status = 'ISSUED'
            else:
                requisition.status = 'PARTIAL'

            requisition.issue_date = timezone.now()
            requisition.warehouse_operator = request.user
            requisition.save()

        return Response(MaterialRequisitionSerializer(requisition).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消领料单"""
        requisition = self.get_object()

        if requisition.status in ['ISSUED', 'CANCELLED']:
            return Response({'error': '已出库或已取消的领料单无法取消'}, status=status.HTTP_400_BAD_REQUEST)

        # 如果有部分出库，需要处理退回
        if requisition.issued_qty > 0:
            return Response({'error': '已有物料出库，请使用退料功能'}, status=status.HTTP_400_BAD_REQUEST)

        requisition.status = 'CANCELLED'
        requisition.save()

        return Response(MaterialRequisitionSerializer(requisition).data)


class MaterialRequisitionLineViewSet(PermissionMixin, viewsets.ModelViewSet):
    permission_module = 'inventory'
    permission_resource = 'material_requisition_line'
    """领料单明细视图集"""
    queryset = MaterialRequisitionLine.objects.all()
    serializer_class = MaterialRequisitionLineSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['requisition', 'item']


class MaterialReturnViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'inventory'
    permission_resource = 'material_return'
    """
    退料单视图集
    
    支持操作：
    - 创建退料单（项目退料/售后退料）
    - 提交退料申请
    - 仓库检验
    - 执行入库
    """
    queryset = MaterialReturn.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = [
        'return_type',
        'return_reason',
        'project',
        'aftersales_order',
        'warehouse',
        'status',
        'requestor',
    ]
    search_fields = ['return_no']
    ordering_fields = ['request_date', 'created_at']
    ordering = ['-created_at']

    # 数据权限规则
    permission_rules = [
        {'field': 'created_by', 'type': 'user'},
        {'field': 'requestor', 'type': 'user'},
        {'field': 'project__manager', 'type': 'user'},
        {'field': 'project__members__user', 'type': 'user'},
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return MaterialReturnListSerializer
        return MaterialReturnSerializer

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交退料申请"""
        material_return = self.get_object()

        if material_return.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的退料单'}, status=status.HTTP_400_BAD_REQUEST)

        if not material_return.lines.exists():
            return Response({'error': '退料单没有明细，无法提交'}, status=status.HTTP_400_BAD_REQUEST)

        material_return.status = 'PENDING'
        material_return.save()

        # TODO: 发送通知给仓库人员

        return Response(MaterialReturnSerializer(material_return).data)

    @action(detail=True, methods=['post'])
    def start_inspect(self, request, pk=None):
        """开始检验"""
        material_return = self.get_object()

        if material_return.status != 'PENDING':
            return Response({'error': '只能对待入库状态的退料单进行检验'}, status=status.HTTP_400_BAD_REQUEST)

        material_return.status = 'INSPECTING'
        material_return.warehouse_operator = request.user
        material_return.save()

        return Response(MaterialReturnSerializer(material_return).data)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """
        执行入库
        请求体：
        {
            "lines": [
                {"id": 1, "received_qty": 10, "condition": "GOOD"},
                {"id": 2, "received_qty": 5, "condition": "DAMAGED"}
            ]
        }
        """
        material_return = self.get_object()

        if material_return.status not in ['PENDING', 'INSPECTING', 'PARTIAL']:
            return Response(
                {'error': '只能对待入库、检验中或部分入库状态的退料单执行入库'}, status=status.HTTP_400_BAD_REQUEST
            )

        lines_data = request.data.get('lines', [])
        if not lines_data:
            return Response({'error': '请指定入库明细'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            all_received = True

            for line_data in lines_data:
                line_id = line_data.get('id')
                received_qty = line_data.get('received_qty', 0)
                condition = line_data.get('condition', 'GOOD')

                try:
                    line = material_return.lines.get(id=line_id)
                except MaterialReturnLine.DoesNotExist:
                    continue

                if received_qty <= 0:
                    continue

                # 更新物料状态
                line.condition = condition
                line.received_qty += received_qty
                line.save()

                # 只有良品才入库
                if condition == 'GOOD':
                    # 创建库存移动记录
                    StockMove.objects.create(
                        item=line.item,
                        warehouse_to=material_return.warehouse,
                        qty=received_qty,
                        unit_cost=line.unit_cost,
                        move_type='ADJUSTMENT',  # 退料入库
                        reference_type='MaterialReturn',
                        reference_id=material_return.id,
                        project=material_return.project,
                        move_date=timezone.now(),
                        status='COMPLETED',
                        notes=f'退料入库 - {material_return.get_return_reason_display()}',
                        created_by=request.user,
                    )

                    # 更新库存
                    stock, created = Stock.objects.get_or_create(
                        warehouse=material_return.warehouse,
                        item=line.item,
                        defaults={'qty_on_hand': 0, 'weighted_avg_cost': line.unit_cost},
                    )
                    stock.qty_on_hand += received_qty
                    stock.save()

                # 检查是否全部入库
                if line.received_qty < line.qty:
                    all_received = False

            # 更新退料单状态
            if all_received and all(l.received_qty >= l.qty for l in material_return.lines.all()):
                material_return.status = 'COMPLETED'
            else:
                material_return.status = 'PARTIAL'

            material_return.receive_date = timezone.now()
            material_return.warehouse_operator = request.user
            material_return.save()

        return Response(MaterialReturnSerializer(material_return).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝退料"""
        material_return = self.get_object()

        if material_return.status not in ['PENDING', 'INSPECTING']:
            return Response({'error': '只能拒绝待入库或检验中状态的退料单'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', '')

        material_return.status = 'REJECTED'
        material_return.notes = f'拒绝原因：{reason}\n' + material_return.notes
        material_return.warehouse_operator = request.user
        material_return.save()

        return Response(MaterialReturnSerializer(material_return).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消退料单"""
        material_return = self.get_object()

        if material_return.status in ['COMPLETED', 'CANCELLED']:
            return Response({'error': '已完成或已取消的退料单无法取消'}, status=status.HTTP_400_BAD_REQUEST)

        # 如果有部分入库，需要特殊处理
        if material_return.received_qty > 0:
            return Response({'error': '已有物料入库，无法取消'}, status=status.HTTP_400_BAD_REQUEST)

        material_return.status = 'CANCELLED'
        material_return.save()

        return Response(MaterialReturnSerializer(material_return).data)


class MaterialReturnLineViewSet(PermissionMixin, viewsets.ModelViewSet):
    permission_module = 'inventory'
    permission_resource = 'material_return_line'
    """退料单明细视图集"""
    queryset = MaterialReturnLine.objects.all()
    serializer_class = MaterialReturnLineSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['material_return', 'item', 'condition']
