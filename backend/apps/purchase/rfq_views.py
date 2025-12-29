"""
RFQ views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.data_permission import DataPermissionMixin
from .rfq_models import RFQ, RFQLine, RFQSupplier, SupplierQuotation, SupplierQuotationLine
from .rfq_serializers import (
    RFQSerializer, RFQLineSerializer, RFQSupplierSerializer,
    SupplierQuotationSerializer, SupplierQuotationLineSerializer
)


class RFQViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """RFQ viewset"""
    queryset = RFQ.objects.all()
    serializer_class = RFQSerializer
    filterset_fields = ['project', 'status', 'is_deleted']
    search_fields = ['rfq_no']
    ordering_fields = ['request_date', 'response_deadline', 'created_at']
    
    @action(detail=True, methods=['post'])
    def send_to_suppliers(self, request, pk=None):
        """Send RFQ to selected suppliers"""
        rfq = self.get_object()
        
        if rfq.status != 'DRAFT':
            return Response(
                {'error': '只能发送草稿状态的询价单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        supplier_ids = request.data.get('supplier_ids', [])
        
        if not supplier_ids:
            return Response(
                {'error': '请选择至少一个供应商'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            for supplier_id in supplier_ids:
                RFQSupplier.objects.create(
                    rfq=rfq,
                    supplier_id=supplier_id,
                    sent_date=timezone.now(),
                    created_by=request.user
                )
            
            rfq.status = 'SENT'
            rfq.save()
        
        return Response({'message': f'已发送给 {len(supplier_ids)} 个供应商'})
    
    @action(detail=True, methods=['post'])
    def accept_quotation(self, request, pk=None):
        """Accept a supplier quotation"""
        rfq = self.get_object()
        quotation_id = request.data.get('quotation_id')
        
        if not quotation_id:
            return Response(
                {'error': '请提供报价单ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quotation = SupplierQuotation.objects.get(id=quotation_id)
        
        with transaction.atomic():
            quotation.status = 'ACCEPTED'
            quotation.save()
            
            rfq.status = 'ACCEPTED'
            rfq.save()
        
        return Response({'message': '已接受该报价'})
    
    @action(detail=True, methods=['post'])
    def convert_to_po(self, request, pk=None):
        """Convert accepted quotation to purchase order"""
        rfq = self.get_object()
        
        if rfq.status != 'ACCEPTED':
            return Response(
                {'error': '只能转换已接受的询价单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quotation_id = request.data.get('quotation_id')
        
        if not quotation_id:
            return Response(
                {'error': '请提供报价单ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from .models import PurchaseOrder, PurchaseOrderLine
        quotation = SupplierQuotation.objects.get(id=quotation_id)
        
        with transaction.atomic():
            po = PurchaseOrder.objects.create(
                supplier=quotation.rfq_supplier.supplier,
                project=rfq.project,
                order_date=timezone.now().date(),
                payment_terms=quotation.payment_terms,
                created_by=request.user
            )
            
            for quot_line in quotation.lines.all():
                PurchaseOrderLine.objects.create(
                    po=po,
                    item=quot_line.rfq_line.item,
                    qty=quot_line.qty,
                    unit_price=quot_line.unit_price,
                    created_by=request.user
                )
            
            # Update PO total
            from django.db.models import Sum
            total = po.lines.aggregate(Sum('line_amount'))['line_amount__sum'] or 0
            po.total_amount = total
            po.save()
        
        from .serializers import PurchaseOrderSerializer
        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)


class RFQLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """RFQ line viewset"""
    queryset = RFQLine.objects.all()
    serializer_class = RFQLineSerializer
    filterset_fields = ['rfq', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']


class RFQSupplierViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """RFQ supplier viewset"""
    queryset = RFQSupplier.objects.all()
    serializer_class = RFQSupplierSerializer
    filterset_fields = ['rfq', 'supplier', 'is_responded']


class SupplierQuotationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """Supplier quotation viewset"""
    queryset = SupplierQuotation.objects.all()
    serializer_class = SupplierQuotationSerializer
    filterset_fields = ['rfq_supplier', 'status', 'is_deleted']
    search_fields = ['quotation_no']
    ordering_fields = ['quotation_date', 'valid_until', 'created_at']
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit quotation"""
        quotation = self.get_object()
        
        if quotation.status != 'DRAFT':
            return Response(
                {'error': '只能提交草稿状态的报价'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quotation.status = 'SUBMITTED'
        quotation.rfq_supplier.is_responded = True
        quotation.rfq_supplier.save()
        quotation.save()
        
        # Update RFQ status
        rfq = quotation.rfq_supplier.rfq
        if all(sq.is_responded for sq in rfq.supplier_rfqs.all()):
            rfq.status = 'QUOTED'
            rfq.save()
        
        return Response(SupplierQuotationSerializer(quotation).data)


class SupplierQuotationLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """Supplier quotation line viewset"""
    queryset = SupplierQuotationLine.objects.all()
    serializer_class = SupplierQuotationLineSerializer
    filterset_fields = ['quotation', 'rfq_line', 'is_deleted']

