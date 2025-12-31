"""
Views for sales app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.db import transaction
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.data_permission import DataPermissionMixin
from .models import (
    SalesQuotation, SalesQuotationLine,
    SalesOrder, SalesOrderLine,
    DeliveryOrder, DeliveryOrderLine
)
from .serializers import (
    SalesQuotationSerializer, SalesQuotationLineSerializer,
    SalesOrderSerializer, SalesOrderLineSerializer,
    DeliveryOrderSerializer, DeliveryOrderLineSerializer
)


class SalesQuotationViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for SalesQuotation management.
    """
    queryset = SalesQuotation.objects.all()
    serializer_class = SalesQuotationSerializer
    filterset_fields = ['customer', 'project', 'status', 'is_deleted']
    search_fields = ['quote_no']
    ordering_fields = ['quote_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def create_new_version(self, request, pk=None):
        """Create a new version of the quotation."""
        old_quotation = self.get_object()
        
        with transaction.atomic():
            new_quotation = SalesQuotation.objects.create(
                customer=old_quotation.customer,
                project=old_quotation.project,
                valid_until=request.data.get('valid_until', old_quotation.valid_until),
                version=old_quotation.version + 1,
                created_by=request.user
            )
            
            for line in old_quotation.lines.filter(is_deleted=False):
                SalesQuotationLine.objects.create(
                    quotation=new_quotation,
                    item=line.item,
                    qty=line.qty,
                    unit_price=line.unit_price,
                    notes=line.notes,
                    created_by=request.user
                )
            
            # Update total
            from django.db.models import Sum
            total = new_quotation.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            new_quotation.total_amount = total
            new_quotation.save()
        
        return Response(SalesQuotationSerializer(new_quotation).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def convert_to_so(self, request, pk=None):
        """Convert quotation to sales order."""
        quotation = self.get_object()
        
        if not quotation.project:
            return Response(
                {'error': '报价单必须关联项目才能转换为订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            so = SalesOrder.objects.create(
                customer=quotation.customer,
                project=quotation.project,
                delivery_date=request.data.get('delivery_date'),
                created_by=request.user
            )
            
            for line in quotation.lines.filter(is_deleted=False):
                SalesOrderLine.objects.create(
                    so=so,
                    item=line.item,
                    qty=line.qty,
                    unit_price=line.unit_price,
                    created_by=request.user
                )
            
            # Update total
            from django.db.models import Sum
            total = so.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            so.total_amount = total
            so.save()
            
            quotation.status = 'ACCEPTED'
            quotation.save()
        
        return Response(SalesOrderSerializer(so).data, status=status.HTTP_201_CREATED)


class SalesQuotationLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for SalesQuotationLine management.
    """
    queryset = SalesQuotationLine.objects.all()
    serializer_class = SalesQuotationLineSerializer
    filterset_fields = ['quotation', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class SalesOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for SalesOrder management.
    """
    queryset = SalesOrder.objects.all()
    serializer_class = SalesOrderSerializer
    filterset_fields = ['customer', 'project', 'status', 'is_deleted']
    search_fields = ['order_no']
    ordering_fields = ['order_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm sales order."""
        so = self.get_object()
        if so.status != 'DRAFT':
            return Response(
                {'error': '只能确认草稿状态的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        so.status = 'CONFIRMED'
        so.save()
        
        # Auto-create AR - 使用含税金额
        from apps.finance.models import AccountReceivable, PaymentSchedule
        AccountReceivable.objects.create(
            customer=so.customer,
            so=so,
            project=so.project,
            invoice_date=so.order_date,
            amount_due=so.total_with_tax or so.total_amount,  # 优先使用含税金额
            due_date=request.data.get('due_date', so.delivery_date),
            created_by=request.user
        )
        
        # 自动生成付款计划
        schedules = PaymentSchedule.generate_from_sales_order(so)
        
        response_data = SalesOrderSerializer(so).data
        response_data['payment_schedules_count'] = len(schedules)
        
        return Response(response_data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel sales order."""
        so = self.get_object()
        if so.status in ['COMPLETED', 'CANCELLED']:
            return Response(
                {'error': '无法取消已完成或已取消的订单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        so.status = 'CANCELLED'
        so.save()
        return Response(SalesOrderSerializer(so).data)
    
    @action(detail=True, methods=['get'])
    def generate_invoice(self, request, pk=None):
        """Generate PDF invoice for sales order."""
        so = self.get_object()
        
        try:
            from apps.finance.invoice_generator import InvoiceGenerator
            pdf_buffer = InvoiceGenerator.generate_invoice(so)
            
            response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="invoice_{so.order_no}.pdf"'
            return response
        except Exception as e:
            return Response(
                {'error': f'发票生成失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SalesOrderLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for SalesOrderLine management.
    """
    queryset = SalesOrderLine.objects.all()
    serializer_class = SalesOrderLineSerializer
    filterset_fields = ['so', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class DeliveryOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for DeliveryOrder management.
    
    发货流程:
    1. 销售发货通知 (DRAFT) - 销售创建发货单
    2. 提交审批 (PENDING) - 进入审批中心，审批步骤由流程配置决定
    3. 审批通过后进入操作流程:
       - 仓库备货 (PREPARING)
       - 采购预约物流 (LOGISTICS_BOOKING)
       - 客户签署送货单 (CUSTOMER_SIGNING)
       - 采购上传送货单 (UPLOADING_RECEIPT)
       - 项目确认 (PROJECT_CONFIRMING)
    4. 完成 (COMPLETED)
    
    注意: 审批步骤由审批中心的流程配置决定，修改流程配置会自动影响审批流程
    """
    queryset = DeliveryOrder.objects.all()
    serializer_class = DeliveryOrderSerializer
    filterset_fields = ['so', 'warehouse', 'status', 'is_deleted']
    search_fields = ['delivery_no']
    ordering_fields = ['delivery_date', 'created_at']
    
    def _calculate_delivery_amount(self, delivery):
        """计算发货单总金额"""
        total = 0
        for line in delivery.lines.filter(is_deleted=False):
            total += line.qty * line.so_line.unit_price
        return total
    
    # 提交审批 - 使用审批中心的流程配置
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交发货申请 - 进入审批中心，审批步骤由流程配置决定"""
        delivery = self.get_object()
        if delivery.status not in ['DRAFT', 'REJECTED']:
            return Response(
                {'error': '只能提交草稿或已拒绝状态的发货单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 计算金额用于流程路由
        amount = self._calculate_delivery_amount(delivery)
        
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='DELIVERY_ORDER',
                business_id=delivery.id,
                business_no=delivery.delivery_no,
                submitter=request.user,
                amount=amount
            )
            
            if instance:
                delivery.status = 'PENDING'
                delivery.rejection_reason = ''  # 清除之前的拒绝原因
                delivery.save()
                return Response({
                    **DeliveryOrderSerializer(delivery).data,
                    'workflow_started': True,
                    'workflow_id': instance.id,
                    'message': '已提交审批，请在审批中心查看审批进度'
                })
            else:
                # 未配置审批流程，直接进入备货
                delivery.status = 'PREPARING'
                delivery.save()
                return Response({
                    **DeliveryOrderSerializer(delivery).data,
                    'workflow_started': False,
                    'message': error or '未配置审批流程，已直接进入备货环节'
                })
                
        except Exception as e:
            # 审批模块不可用，直接进入备货
            delivery.status = 'PREPARING'
            delivery.save()
            return Response({
                **DeliveryOrderSerializer(delivery).data,
                'workflow_started': False,
                'message': f'提交成功，但工作流服务异常: {e}'
            })
    
    # 获取当前审批状态
    @action(detail=True, methods=['get'])
    def workflow_status(self, request, pk=None):
        """获取发货单的审批状态"""
        delivery = self.get_object()
        
        try:
            from apps.core.workflow.models import WorkflowInstance, WorkflowTask
            
            instance = WorkflowInstance.objects.filter(
                business_type='DELIVERY_ORDER',
                business_id=delivery.id,
                is_deleted=False
            ).order_by('-created_at').first()
            
            if instance:
                pending_task = instance.tasks.filter(status='PENDING', is_deleted=False).first()
                return Response({
                    'has_workflow': True,
                    'workflow_id': instance.id,
                    'workflow_status': instance.status,
                    'current_step': instance.current_step,
                    'pending_task': {
                        'id': pending_task.id,
                        'step_name': pending_task.step.name,
                        'assignee': pending_task.assignee.username if pending_task.assignee else None,
                    } if pending_task else None
                })
            else:
                return Response({
                    'has_workflow': False,
                    'message': '无审批流程'
                })
        except Exception as e:
            return Response({
                'has_workflow': False,
                'error': str(e)
            })
    
    # 仓库确认备货完成
    @action(detail=True, methods=['post'])
    def confirm_prepared(self, request, pk=None):
        """仓库确认备货完成"""
        delivery = self.get_object()
        # 允许从 APPROVED 或 PREPARING 状态确认备货
        if delivery.status not in ['APPROVED', 'PREPARING']:
            return Response(
                {'error': '当前状态不能确认备货'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建出库记录
        with transaction.atomic():
            from apps.inventory.models import StockMove
            from django.utils import timezone
            
            for line in delivery.lines.filter(is_deleted=False):
                StockMove.objects.create(
                    item=line.item,
                    warehouse_from=delivery.warehouse,
                    qty=line.qty,
                    unit_cost=line.so_line.unit_price,
                    move_type='OUT_SALES',
                    reference_type='DeliveryOrder',
                    reference_id=delivery.id,
                    project=delivery.so.project,
                    move_date=timezone.now().date(),
                    status='COMPLETED',
                    created_by=request.user
                )
                
                # 更新销售订单发货数量
                line.so_line.delivered_qty += line.qty
                line.so_line.save()
        
        delivery.status = 'LOGISTICS_BOOKING'
        delivery.save()
        
        return Response({
            **DeliveryOrderSerializer(delivery).data,
            'message': '备货完成，请采购预约物流'
        })
    
    # 采购确认物流
    @action(detail=True, methods=['post'])
    def confirm_logistics(self, request, pk=None):
        """采购确认物流信息"""
        delivery = self.get_object()
        if delivery.status != 'LOGISTICS_BOOKING':
            return Response(
                {'error': '当前状态不能确认物流'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 更新物流信息
        logistics_company = request.data.get('logistics_company')
        tracking_number = request.data.get('tracking_number')
        logistics_cost = request.data.get('logistics_cost')
        
        if logistics_company:
            delivery.logistics_company = logistics_company
        if tracking_number:
            delivery.tracking_number = tracking_number
        if logistics_cost:
            delivery.logistics_cost = logistics_cost
        
        delivery.status = 'CUSTOMER_SIGNING'
        delivery.save()
        
        return Response({
            **DeliveryOrderSerializer(delivery).data,
            'message': '物流已预约，等待客户签收'
        })
    
    # Step 6 -> 7: 客户签收
    @action(detail=True, methods=['post'])
    def confirm_signed(self, request, pk=None):
        """确认客户已签收"""
        delivery = self.get_object()
        if delivery.status != 'CUSTOMER_SIGNING':
            return Response(
                {'error': '当前状态不能确认签收'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        signed_by = request.data.get('signed_by')
        signed_date = request.data.get('signed_date')
        
        if signed_by:
            delivery.signed_by = signed_by
        if signed_date:
            delivery.signed_date = signed_date
        
        delivery.status = 'UPLOADING_RECEIPT'
        delivery.save()
        
        return Response({
            **DeliveryOrderSerializer(delivery).data,
            'message': '已确认签收，请上传送货单'
        })
    
    # Step 7 -> 8: 上传送货单
    @action(detail=True, methods=['post'])
    def upload_receipt(self, request, pk=None):
        """上传签收单据"""
        delivery = self.get_object()
        if delivery.status != 'UPLOADING_RECEIPT':
            return Response(
                {'error': '当前状态不能上传送货单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if 'signed_receipt' in request.FILES:
            delivery.signed_receipt = request.FILES['signed_receipt']
        
        delivery.status = 'PROJECT_CONFIRMING'
        delivery.save()
        
        return Response({
            **DeliveryOrderSerializer(delivery).data,
            'message': '送货单已上传，等待项目确认'
        })
    
    # Step 8 -> 9: 项目确认
    @action(detail=True, methods=['post'])
    def project_confirm(self, request, pk=None):
        """项目确认完成"""
        delivery = self.get_object()
        if delivery.status != 'PROJECT_CONFIRMING':
            return Response(
                {'error': '当前状态不能进行项目确认'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        
        delivery.status = 'COMPLETED'
        delivery.actual_delivery_date = timezone.now().date()
        delivery.save()
        
        # 更新销售订单状态
        so = delivery.so
        all_delivered = all(
            line.delivered_qty >= line.qty
            for line in so.lines.filter(is_deleted=False)
        )
        if all_delivered:
            so.status = 'COMPLETED'
        else:
            so.status = 'PARTIAL'
        so.save()
        
        return Response({
            **DeliveryOrderSerializer(delivery).data,
            'message': '发货流程已完成'
        })
    
    # 拒绝操作（可在任意审批环节拒绝）
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝发货申请"""
        delivery = self.get_object()
        if delivery.status in ['DRAFT', 'COMPLETED', 'REJECTED']:
            return Response(
                {'error': '当前状态不能拒绝'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', '')
        delivery.status = 'REJECTED'
        delivery.rejection_reason = reason
        delivery.save()
        
        return Response({
            **DeliveryOrderSerializer(delivery).data,
            'message': '已拒绝'
        })


class DeliveryOrderLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for DeliveryOrderLine management.
    """
    queryset = DeliveryOrderLine.objects.all()
    serializer_class = DeliveryOrderLineSerializer
    filterset_fields = ['delivery', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']

