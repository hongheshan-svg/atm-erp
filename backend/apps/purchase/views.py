"""
Views for purchase app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.data_permission import DataPermissionMixin
from apps.projects.models import Project
from apps.inventory.cost_methods import CostingMethodFactory, FIFOCostingService
from .models import (
    PurchaseRequest, PurchaseRequestLine,
    PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine,
    PurchaseContract
)
from .serializers import (
    PurchaseRequestSerializer, PurchaseRequestLineSerializer,
    PurchaseOrderSerializer, PurchaseOrderLineSerializer,
    GoodsReceiptSerializer, GoodsReceiptLineSerializer,
    PurchaseContractSerializer
)
from .services import BudgetValidationService


class PurchaseRequestViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseRequest management.
    """
    queryset = PurchaseRequest.objects.all()
    serializer_class = PurchaseRequestSerializer
    filterset_fields = ['project', 'requestor', 'status', 'is_deleted']
    search_fields = ['request_no']
    ordering_fields = ['request_date', 'created_at']
    data_scope_field = 'requestor'
    
    def create(self, request, *args, **kwargs):
        """Override create to add debugging."""
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"PR Create request data: {request.data}")
        
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"PR Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_create(self, serializer):
        """Auto-set requestor to current user."""
        serializer.save(
            created_by=self.request.user,
            requestor=self.request.user
        )
    
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
    def withdraw(self, request, pk=None):
        """Withdraw/Revoke submitted PR - 反审/撤回采购申请."""
        pr = self.get_object()
        if pr.status not in ['SUBMITTED', 'APPROVED']:
            return Response(
                {'error': '只能撤回已提交或已批准的申请'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查是否已经转为采购订单
        if pr.status == 'CONVERTED':
            return Response(
                {'error': '该申请已转为采购订单，无法撤回'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pr.status = 'DRAFT'
        pr.save()
        
        # 尝试取消工作流
        try:
            from apps.core.workflow.services import WorkflowService
            WorkflowService.cancel_workflow(
                business_type='PURCHASE_REQUEST',
                business_id=pr.id
            )
        except Exception:
            pass
        
        return Response({
            **PurchaseRequestSerializer(pr).data,
            'message': '采购申请已撤回'
        })
    
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
            
            # Update total amount and tax
            total = po.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            po.total_amount = total
            po.tax_amount = total * po.tax_rate / 100
            po.total_with_tax = total + po.tax_amount
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


class PurchaseOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseOrder management.
    """
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    filterset_fields = ['supplier', 'project', 'status', 'is_deleted']
    search_fields = ['order_no']
    ordering_fields = ['order_date', 'created_at']
    
    @action(detail=False, methods=['get'])
    def for_linking(self, request):
        """获取可用于关联的采购订单（不受数据权限限制）"""
        from django.db import models as db_models
        queryset = PurchaseOrder.objects.filter(is_deleted=False).order_by('-created_at')
        
        # 支持搜索
        search = request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                db_models.Q(order_no__icontains=search) |
                db_models.Q(supplier__name__icontains=search)
            )
        
        # 简化返回数据
        data = [{
            'id': po.id,
            'order_no': po.order_no,
            'supplier': po.supplier_id,
            'supplier_name': po.supplier.name if po.supplier else '',
            'project': po.project_id,
            'project_name': po.project.name if po.project else '',
            'status': po.status,
            'total_amount': float(po.total_amount or 0),
            'total_with_tax': float(po.total_with_tax or 0),
        } for po in queryset[:100]]  # 限制返回数量
        
        return Response(data)
    
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
        
        # Auto-create AP - 使用含税金额（避免重复创建）
        from apps.finance.models import AccountPayable, PurchasePaymentSchedule
        
        # 检查是否已存在该PO的应付账款
        existing_ap = AccountPayable.objects.filter(po=po, is_deleted=False).first()
        if not existing_ap:
            AccountPayable.objects.create(
                supplier=po.supplier,
                po=po,
                project=po.project,
                invoice_date=po.order_date,
                amount_due=po.total_with_tax or po.total_amount,  # 优先使用含税金额
                due_date=request.data.get('due_date', po.delivery_date),
                created_by=request.user
            )
        
        # 自动生成付款计划（避免重复创建）
        existing_schedules = PurchasePaymentSchedule.objects.filter(po=po, is_deleted=False).exists()
        if existing_schedules:
            schedules = []
        else:
            schedules = PurchasePaymentSchedule.generate_from_purchase_order(po)
        
        response_data = PurchaseOrderSerializer(po).data
        response_data['payment_schedules_count'] = len(schedules)
        
        return Response(response_data)
    
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
    
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Withdraw/Revoke confirmed PO - 反审/撤回采购订单."""
        po = self.get_object()
        if po.status not in ['CONFIRMED']:
            return Response(
                {'error': '只能撤回已确认的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查是否有收货记录
        from apps.inventory.models import StockMove
        has_receipts = GoodsReceipt.objects.filter(po=po, status='CONFIRMED', is_deleted=False).exists()
        if has_receipts:
            return Response(
                {'error': '该订单已有收货记录，无法撤回'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 删除关联的应付账款
            from apps.finance.models import AccountPayable, PurchasePaymentSchedule
            AccountPayable.objects.filter(po=po, is_deleted=False).update(is_deleted=True)
            
            # 删除付款计划
            PurchasePaymentSchedule.objects.filter(po=po, is_deleted=False).update(is_deleted=True)
            
            po.status = 'DRAFT'
            po.save()
        
        return Response({
            **PurchaseOrderSerializer(po).data,
            'message': '采购订单已撤回至草稿状态'
        })


class PurchaseOrderLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseOrderLine management.
    """
    queryset = PurchaseOrderLine.objects.all()
    serializer_class = PurchaseOrderLineSerializer
    filterset_fields = ['po', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class GoodsReceiptViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
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


class PurchaseContractViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for PurchaseContract management.
    """
    queryset = PurchaseContract.objects.all()
    serializer_class = PurchaseContractSerializer
    filterset_fields = ['po', 'supplier', 'project', 'status', 'is_deleted']
    search_fields = ['contract_no', 'title']
    ordering_fields = ['contract_date', 'created_at']
    
    @action(detail=False, methods=['post'])
    def create_from_po(self, request):
        """从采购订单创建合同."""
        po_id = request.data.get('po_id')
        if not po_id:
            return Response(
                {'error': '请选择采购订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            po = PurchaseOrder.objects.get(id=po_id, is_deleted=False)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': '采购订单不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查是否已有合同
        existing = PurchaseContract.objects.filter(po=po, is_deleted=False).first()
        if existing:
            return Response(
                {'error': f'该采购订单已存在合同: {existing.contract_no}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        contract = PurchaseContract.objects.create(
            po=po,
            supplier=po.supplier,
            project=po.project,
            title=f'{po.supplier.name}采购合同',
            contract_date=timezone.now().date(),
            total_amount=po.total_amount,
            tax_rate=po.tax_rate,
            tax_amount=po.tax_amount,
            total_with_tax=po.total_with_tax,
            payment_terms=self._get_payment_terms_text(po),
            delivery_terms=f'交货日期：{po.delivery_date}',
            created_by=request.user
        )
        
        return Response(PurchaseContractSerializer(contract).data, status=status.HTTP_201_CREATED)
    
    def _get_payment_terms_text(self, po):
        """生成付款条款文本."""
        terms_map = {
            'PREPAY': '预付款100%',
            'COD': '货到付款',
            'NET15': '货到后15天内付款',
            'NET30': '货到后30天内付款',
            'NET45': '货到后45天内付款',
            'NET60': '货到后60天内付款',
            'NET90': '货到后90天内付款',
            'NET120': '货到后120天内付款',
            'MILESTONE': '分期付款',
            'OTHER': '其他',
        }
        base_text = terms_map.get(po.payment_terms, '月结30天')
        if po.payment_terms_detail:
            base_text += f'（{po.payment_terms_detail}）'
        return base_text
    
    @action(detail=True, methods=['get'])
    def print_preview(self, request, pk=None):
        """获取合同打印预览数据."""
        contract = self.get_object()
        po = contract.po
        
        # 获取公司信息
        from apps.core.models import SystemConfig
        company_config = SystemConfig.get_config('company', {})
        
        # 获取订单明细
        lines = []
        for line in po.lines.filter(is_deleted=False):
            lines.append({
                'item_sku': line.item.sku,
                'item_name': line.item.name,
                'specification': line.item.specification or '',
                'unit': line.item.get_unit_display(),
                'qty': float(line.qty),
                'unit_price': float(line.unit_price),
                'line_amount': float(line.line_amount),
            })
        
        return Response({
            'contract': PurchaseContractSerializer(contract).data,
            'company': {
                'name': company_config.get('name', ''),
                'address': company_config.get('address', ''),
                'phone': company_config.get('phone', ''),
                'fax': company_config.get('fax', ''),
                'bank_name': company_config.get('bank_name', ''),
                'bank_account': company_config.get('bank_account', ''),
            },
            'supplier': {
                'name': contract.supplier.name,
                'address': contract.supplier.address or '',
                'contact': contract.supplier.contact_person or '',
                'phone': contract.supplier.phone or '',
                'bank_name': contract.supplier.bank_name or '',
                'bank_account': contract.supplier.bank_account or '',
            },
            'lines': lines,
        })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批合同."""
        contract = self.get_object()
        if contract.status not in ['DRAFT', 'PENDING']:
            return Response(
                {'error': '只能审批草稿或待审批状态的合同'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contract.status = 'APPROVED'
        contract.save()
        return Response(PurchaseContractSerializer(contract).data)
    
    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """签署合同."""
        contract = self.get_object()
        if contract.status != 'APPROVED':
            return Response(
                {'error': '只能签署已审批的合同'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        contract.buyer_signer = request.data.get('buyer_signer', '')
        contract.seller_signer = request.data.get('seller_signer', '')
        contract.signed_date = timezone.now().date()
        contract.status = 'SIGNED'
        contract.save()
        return Response(PurchaseContractSerializer(contract).data)

