"""
外协加工管理视图
"""

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin

from .outsource_models import (
    OutsourceMaterialIssue,
    OutsourceMaterialIssueLine,
    OutsourceOrder,
    OutsourceOrderLine,
    OutsourceReceipt,
    OutsourceReceiptLine,
)
from .outsource_serializers import (
    OutsourceMaterialIssueLineSerializer,
    OutsourceMaterialIssueSerializer,
    OutsourceOrderLineSerializer,
    OutsourceOrderSerializer,
    OutsourceReceiptLineSerializer,
    OutsourceReceiptSerializer,
)


class OutsourceOrderViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    外协加工单管理
    """

    queryset = OutsourceOrder.objects.all()
    serializer_class = OutsourceOrderSerializer
    filterset_fields = ['supplier', 'project', 'status', 'is_deleted']
    search_fields = ['order_no']
    ordering_fields = ['order_date', 'required_date', 'created_at']
    ordering = ['-created_at']

    permission_module = 'purchase'
    permission_resource = 'outsource_order'

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认外协单"""
        order = self.get_object()
        if order.status != 'DRAFT':
            return Response({'error': '只能确认草稿状态的外协单'}, status=status.HTTP_400_BAD_REQUEST)

        # 检查是否有明细
        if not order.lines.filter(is_deleted=False).exists():
            return Response({'error': '请添加加工明细'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = 'CONFIRMED'
        order.save()

        # 创建应付账款
        from apps.finance.models import AccountPayable

        AccountPayable.objects.create(
            supplier=order.supplier,
            project=order.project,
            invoice_date=order.order_date,
            amount_due=order.total_with_tax,
            due_date=order.required_date,
            notes=f'外协加工单: {order.order_no}',
            created_by=request.user,
        )

        return Response(OutsourceOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消外协单"""
        order = self.get_object()
        if order.status in ['COMPLETED', 'CANCELLED']:
            return Response({'error': '无法取消已完成或已取消的外协单'}, status=status.HTTP_400_BAD_REQUEST)

        # 检查是否有发料
        if order.lines.filter(sent_qty__gt=0).exists():
            return Response({'error': '已有发料记录，无法取消'}, status=status.HTTP_400_BAD_REQUEST)

        order.status = 'CANCELLED'
        order.save()
        return Response(OutsourceOrderSerializer(order).data)

    @action(detail=True, methods=['get'])
    def pending_lines(self, request, pk=None):
        """获取待发料的明细"""
        order = self.get_object()
        lines = order.lines.filter(is_deleted=False, sent_qty__lt=models.F('qty'))
        return Response(OutsourceOrderLineSerializer(lines, many=True).data)


class OutsourceOrderLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    外协加工单明细管理
    """

    queryset = OutsourceOrderLine.objects.all()
    serializer_class = OutsourceOrderLineSerializer
    filterset_fields = ['outsource_order', 'item', 'process_type', 'is_deleted']

    permission_module = 'purchase'
    permission_resource = 'outsource_order_line'
    search_fields = ['item__sku', 'item__name', 'drawing_no']


class OutsourceMaterialIssueViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    外协发料单管理
    """

    queryset = OutsourceMaterialIssue.objects.all()
    serializer_class = OutsourceMaterialIssueSerializer
    filterset_fields = ['outsource_order', 'warehouse', 'status', 'is_deleted']
    search_fields = ['issue_no']
    ordering_fields = ['issue_date', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认发料"""
        issue = self.get_object()
        if issue.status != 'DRAFT':
            return Response({'error': '只能确认草稿状态的发料单'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # 创建库存出库记录
            from apps.inventory.models import StockMove

            for line in issue.lines.filter(is_deleted=False):
                # 创建库存移动
                StockMove.objects.create(
                    item=line.item,
                    warehouse_from=issue.warehouse,
                    qty=line.qty,
                    move_type='OUT_OUTSOURCE',
                    reference_type='OutsourceMaterialIssue',
                    reference_id=issue.id,
                    move_date=issue.issue_date,
                    status='COMPLETED',
                    created_by=request.user,
                )

                # 更新外协单明细的发料数量
                line.outsource_line.sent_qty += line.qty
                line.outsource_line.save()

            issue.status = 'CONFIRMED'
            issue.save()

            # 更新外协单状态
            order = issue.outsource_order
            if order.status == 'CONFIRMED':
                order.status = 'PROCESSING'
                order.save()

        return Response(OutsourceMaterialIssueSerializer(issue).data)


class OutsourceMaterialIssueLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    外协发料单明细管理
    """

    queryset = OutsourceMaterialIssueLine.objects.all()
    serializer_class = OutsourceMaterialIssueLineSerializer
    filterset_fields = ['issue', 'item', 'is_deleted']


class OutsourceReceiptViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    外协收货单管理
    """

    queryset = OutsourceReceipt.objects.all()
    serializer_class = OutsourceReceiptSerializer
    filterset_fields = ['outsource_order', 'warehouse', 'status', 'quality_status', 'is_deleted']
    search_fields = ['receipt_no']
    ordering_fields = ['receipt_date', 'created_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def start_inspect(self, request, pk=None):
        """开始质检"""
        receipt = self.get_object()
        if receipt.status != 'DRAFT':
            return Response({'error': '只能对草稿状态的收货单进行质检'}, status=status.HTTP_400_BAD_REQUEST)

        receipt.status = 'INSPECTING'
        receipt.inspector = request.user
        receipt.save()
        return Response(OutsourceReceiptSerializer(receipt).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认收货入库"""
        receipt = self.get_object()
        if receipt.status not in ['DRAFT', 'INSPECTING']:
            return Response({'error': '只能确认草稿或质检中的收货单'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            from django.utils import timezone

            from apps.inventory.models import StockMove

            total_qty = 0
            qualified_qty = 0

            for line in receipt.lines.filter(is_deleted=False):
                # 创建库存入库记录（只入合格品）
                if line.qualified_qty > 0:
                    StockMove.objects.create(
                        item=line.item,
                        warehouse_to=receipt.warehouse,
                        qty=line.qualified_qty,
                        move_type='IN_OUTSOURCE',
                        reference_type='OutsourceReceipt',
                        reference_id=receipt.id,
                        move_date=receipt.receipt_date,
                        status='COMPLETED',
                        created_by=request.user,
                    )

                # 更新外协单明细的收货数量
                line.outsource_line.received_qty += line.qualified_qty
                line.outsource_line.save()

                total_qty += line.qty
                qualified_qty += line.qualified_qty

            # 更新质检状态
            if qualified_qty == 0:
                receipt.quality_status = 'FAILED'
            elif qualified_qty == total_qty:
                receipt.quality_status = 'PASSED'
            else:
                receipt.quality_status = 'PARTIAL'

            receipt.status = 'CONFIRMED'
            receipt.inspect_date = timezone.now().date()
            receipt.save()

            # 检查外协单是否完成
            order = receipt.outsource_order
            all_received = all(line.received_qty >= line.qty for line in order.lines.filter(is_deleted=False))
            if all_received:
                order.status = 'COMPLETED'
            else:
                any_received = any(line.received_qty > 0 for line in order.lines.filter(is_deleted=False))
                if any_received:
                    order.status = 'PARTIAL'
            order.save()

        return Response(OutsourceReceiptSerializer(receipt).data)


class OutsourceReceiptLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    外协收货单明细管理
    """

    queryset = OutsourceReceiptLine.objects.all()
    serializer_class = OutsourceReceiptLineSerializer
    filterset_fields = ['receipt', 'item', 'quality_status', 'is_deleted']


# 需要在views.py中导入models
from django.db import models
