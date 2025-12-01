"""
Views for purchase app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
from apps.projects.models import Project
from apps.inventory.cost_methods import CostingMethodFactory, FIFOCostingService
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine
)
from .serializers import (
    PurchaseRequestSerializer, PurchaseRequestLineSerializer,
    PurchaseOrderSerializer, PurchaseOrderLineSerializer,
    GoodsReceiptSerializer, GoodsReceiptLineSerializer
)
from .services import BudgetValidationService


class PurchaseRequestViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseRequest management.
    """
    queryset = PurchaseRequest.objects.all()
    serializer_class = PurchaseRequestSerializer
    filterset_fields = ['project', 'requestor', 'status', 'is_deleted']
    search_fields = ['request_no']
    ordering_fields = ['request_date', 'created_at']
    data_scope_field = 'requestor'
    
    @action(detail=False, methods=['get'])
    def check_budget(self, request):
        """
        Check budget for a project before creating purchase request.
        Query params: project_id, amount
        """
        project_id = request.query_params.get('project_id')
        amount = request.query_params.get('amount', 0)
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = 0
        
        if not project_id:
            return Response({
                'valid': True,
                'message': '未选择项目，无需预算校验'
            })
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = BudgetValidationService.validate_purchase_request(project, amount)
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def project_budget_summary(self, request):
        """Get budget summary for a project."""
        project_id = request.query_params.get('project_id')
        
        if not project_id:
            return Response(
                {'error': '请提供项目ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        summary = BudgetValidationService.get_project_budget_summary(project)
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit PR for approval with budget validation and workflow."""
        pr = self.get_object()
        if pr.status != 'DRAFT':
            return Response(
                {'error': '只能提交草稿状态的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Budget validation
        budget_warning = None
        if pr.project:
            budget_result = BudgetValidationService.validate_purchase_request(
                pr.project, pr.total_amount
            )
            if not budget_result['valid']:
                budget_warning = budget_result['message']
        
        # Try to start workflow
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='PURCHASE_REQUEST',
                business_id=pr.id,
                business_no=pr.request_no,
                submitter=request.user,
                amount=pr.total_amount
            )
            
            if instance:
                pr.status = 'SUBMITTED'
                pr.save()
                response_data = {
                    **PurchaseRequestSerializer(pr).data,
                    'workflow_started': True,
                    'workflow_id': instance.id
                }
                if budget_warning:
                    response_data['budget_warning'] = budget_warning
                    response_data['over_budget'] = True
                return Response(response_data)
            else:
                # No workflow configured, just submit
                pr.status = 'SUBMITTED'
                pr.save()
                response_data = {
                    **PurchaseRequestSerializer(pr).data,
                    'workflow_started': False,
                    'message': error or '未配置审批流程，已直接提交'
                }
                if budget_warning:
                    response_data['budget_warning'] = budget_warning
                return Response(response_data)
                
        except Exception as e:
            # Workflow module not available, fallback to simple submit
            pr.status = 'SUBMITTED'
            pr.save()
            response_data = PurchaseRequestSerializer(pr).data
            if budget_warning:
                response_data['budget_warning'] = budget_warning
            return Response(response_data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve PR."""
        pr = self.get_object()
        if pr.status != 'SUBMITTED':
            return Response(
                {'error': '只能批准已提交的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pr.status = 'APPROVED'
        pr.save()
        return Response(PurchaseRequestSerializer(pr).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject PR."""
        pr = self.get_object()
        if pr.status != 'SUBMITTED':
            return Response(
                {'error': '只能拒绝已提交的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pr.status = 'REJECTED'
        pr.save()
        return Response(PurchaseRequestSerializer(pr).data)
    
    @action(detail=True, methods=['post'])
    def convert_to_po(self, request, pk=None):
        """Convert PR to PO."""
        pr = self.get_object()
        if pr.status != 'APPROVED':
            return Response(
                {'error': '只能转换已批准的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        supplier_id = request.data.get('supplier')
        if not supplier_id:
            return Response(
                {'error': '请选择供应商'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            po = PurchaseOrder.objects.create(
                supplier_id=supplier_id,
                project=pr.project,
                delivery_date=pr.required_date,
                created_by=request.user
            )
            
            for pr_line in pr.lines.filter(is_deleted=False):
                PurchaseOrderLine.objects.create(
                    po=po,
                    item=pr_line.item,
                    qty=pr_line.qty,
                    unit_price=pr_line.estimated_price,
                    created_by=request.user
                )
            
            # Update total amount
            total = po.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            po.total_amount = total
            po.save()
            
            pr.status = 'CONVERTED'
            pr.save()
        
        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)


class PurchaseRequestLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseRequestLine management.
    """
    queryset = PurchaseRequestLine.objects.all()
    serializer_class = PurchaseRequestLineSerializer
    filterset_fields = ['pr', 'item', 'project', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class PurchaseOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseOrder management.
    """
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    filterset_fields = ['supplier', 'project', 'status', 'is_deleted']
    search_fields = ['order_no']
    ordering_fields = ['order_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm PO."""
        po = self.get_object()
        if po.status != 'DRAFT':
            return Response(
                {'error': '只能确认草稿状态的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        po.status = 'CONFIRMED'
        po.save()
        return Response(PurchaseOrderSerializer(po).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel PO."""
        po = self.get_object()
        if po.status in ['COMPLETED', 'CANCELLED']:
            return Response(
                {'error': '无法取消已完成或已取消的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        po.status = 'CANCELLED'
        po.save()
        return Response(PurchaseOrderSerializer(po).data)


class PurchaseOrderLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseOrderLine management.
    """
    queryset = PurchaseOrderLine.objects.all()
    serializer_class = PurchaseOrderLineSerializer
    filterset_fields = ['po', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class GoodsReceiptViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    ViewSet for GoodsReceipt management.
    """
    queryset = GoodsReceipt.objects.all()
    serializer_class = GoodsReceiptSerializer
    filterset_fields = ['po', 'warehouse', 'status', 'is_deleted']
    search_fields = ['receipt_no']
    ordering_fields = ['receipt_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm goods receipt and create stock moves with FIFO support."""
        receipt = self.get_object()
        if receipt.status != 'DRAFT':
            return Response(
                {'error': '只能确认草稿状态的收货单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            from apps.inventory.models import StockMove
            from django.conf import settings
            
            costing_method = getattr(settings, 'INVENTORY_COSTING_METHOD', 'WEIGHTED_AVG')
            
            for line in receipt.lines.filter(is_deleted=False):
                # Create stock move for receipt
                StockMove.objects.create(
                    item=line.item,
                    warehouse_to=receipt.warehouse,
                    qty=line.qty,
                    unit_cost=line.po_line.unit_price,
                    move_type='IN_PURCHASE',
                    reference_type='GoodsReceipt',
                    reference_id=receipt.id,
                    move_date=receipt.receipt_date,
                    status='COMPLETED',
                    created_by=request.user
                )
                
                # If using FIFO, also create inventory lot
                if costing_method == 'FIFO':
                    FIFOCostingService.record_purchase(
                        warehouse=receipt.warehouse,
                        item=line.item,
                        qty=line.qty,
                        unit_cost=line.po_line.unit_price,
                        reference_type='GoodsReceipt',
                        reference_id=receipt.id
                    )
                
                # Update received qty on PO line
                line.po_line.received_qty += line.qty
                line.po_line.save()
            
            receipt.status = 'CONFIRMED'
            receipt.save()
            
            # Check if PO is fully received
            po = receipt.po
            all_received = all(
                line.received_qty >= line.qty
                for line in po.lines.filter(is_deleted=False)
            )
            if all_received:
                po.status = 'COMPLETED'
            else:
                po.status = 'PARTIAL'
            po.save()
        
        return Response(GoodsReceiptSerializer(receipt).data)


class GoodsReceiptLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for GoodsReceiptLine management.
    """
    queryset = GoodsReceiptLine.objects.all()
    serializer_class = GoodsReceiptLineSerializer
    filterset_fields = ['receipt', 'item', 'quality_status', 'is_deleted']
    search_fields = ['item__sku', 'item__name']

