"""
Views for sales app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.db import transaction
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin, DataScopeMixin
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


class SalesQuotationViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
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


class SalesOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
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
        
        # Auto-create AR
        from apps.finance.models import AccountReceivable
        AccountReceivable.objects.create(
            customer=so.customer,
            so=so,
            project=so.project,
            invoice_date=so.order_date,
            amount_due=so.total_amount,
            due_date=request.data.get('due_date', so.delivery_date),
            created_by=request.user
        )
        
        return Response(SalesOrderSerializer(so).data)
    
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


class DeliveryOrderViewSet(SoftDeleteMixin, UserTrackingMixin, DataScopeMixin, viewsets.ModelViewSet):
    """
    ViewSet for DeliveryOrder management.
    """
    queryset = DeliveryOrder.objects.all()
    serializer_class = DeliveryOrderSerializer
    filterset_fields = ['so', 'warehouse', 'status', 'is_deleted']
    search_fields = ['delivery_no']
    ordering_fields = ['delivery_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm delivery and create stock moves."""
        delivery = self.get_object()
        if delivery.status != 'DRAFT':
            return Response(
                {'error': '只能确认草稿状态的发货单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            from apps.inventory.models import StockMove
            
            for line in delivery.lines.filter(is_deleted=False):
                # Create stock move for delivery
                StockMove.objects.create(
                    item=line.item,
                    warehouse_from=delivery.warehouse,
                    qty=line.qty,
                    unit_cost=line.so_line.unit_price,  # Use selling price as reference
                    move_type='OUT_SALES',
                    reference_type='DeliveryOrder',
                    reference_id=delivery.id,
                    project=delivery.so.project,
                    move_date=delivery.delivery_date,
                    status='COMPLETED',
                    created_by=request.user
                )
                
                # Update delivered qty on SO line
                line.so_line.delivered_qty += line.qty
                line.so_line.save()
            
            delivery.status = 'CONFIRMED'
            delivery.save()
            
            # Check if SO is fully delivered
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
        
        return Response(DeliveryOrderSerializer(delivery).data)


class DeliveryOrderLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for DeliveryOrderLine management.
    """
    queryset = DeliveryOrderLine.objects.all()
    serializer_class = DeliveryOrderLineSerializer
    filterset_fields = ['delivery', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']

