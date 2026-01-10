"""
RFQ views
询价单、供应商报价、比价分析视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.data_permission import DataPermissionMixin
from .rfq_models import (
    RFQ, RFQLine, RFQSupplier, SupplierQuotation, SupplierQuotationLine,
    QuotationComparison, QuotationScore, ItemPriceHistory
)
from .rfq_serializers import (
    RFQSerializer, RFQLineSerializer, RFQSupplierSerializer,
    SupplierQuotationSerializer, SupplierQuotationLineSerializer,
    QuotationComparisonSerializer, QuotationComparisonListSerializer,
    QuotationScoreSerializer, ItemPriceHistorySerializer,
    CreateComparisonSerializer, UpdateScoreSerializer
)
from .comparison_service import QuotationComparisonService


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


class QuotationComparisonViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """报价比价分析视图"""
    queryset = QuotationComparison.objects.all()
    serializer_class = QuotationComparisonSerializer
    filterset_fields = ['rfq', 'status', 'is_deleted']
    search_fields = ['comparison_no', 'rfq__rfq_no']
    ordering_fields = ['created_at', 'status']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return QuotationComparisonListSerializer
        return QuotationComparisonSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related(
            'rfq', 'rfq__project', 'recommended_quotation',
            'recommended_quotation__rfq_supplier__supplier', 'approved_by'
        ).prefetch_related('scores')
    
    @action(detail=False, methods=['post'], url_path='create-comparison')
    def create_comparison(self, request):
        """创建比价分析"""
        serializer = CreateComparisonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            weights = {
                'price': float(serializer.validated_data.get('weight_price', 40)),
                'quality': float(serializer.validated_data.get('weight_quality', 25)),
                'delivery': float(serializer.validated_data.get('weight_delivery', 20)),
                'service': float(serializer.validated_data.get('weight_service', 15)),
            }
            
            comparison = QuotationComparisonService.create_comparison(
                rfq_id=serializer.validated_data['rfq_id'],
                user=request.user,
                weights=weights
            )
            
            return Response(
                QuotationComparisonSerializer(comparison).data,
                status=status.HTTP_201_CREATED
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """获取比价报告"""
        comparison = self.get_object()
        report = QuotationComparisonService.get_comparison_report(comparison)
        return Response(report)
    
    @action(detail=True, methods=['post'], url_path='update-weights')
    def update_weights(self, request, pk=None):
        """更新比价权重"""
        comparison = self.get_object()
        
        weights = {
            'price': float(request.data.get('weight_price', comparison.weight_price)),
            'quality': float(request.data.get('weight_quality', comparison.weight_quality)),
            'delivery': float(request.data.get('weight_delivery', comparison.weight_delivery)),
            'service': float(request.data.get('weight_service', comparison.weight_service)),
        }
        
        try:
            comparison = QuotationComparisonService.update_weights(comparison.id, weights)
            return Response(QuotationComparisonSerializer(comparison).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='auto-score')
    def auto_score(self, request, pk=None):
        """自动评分（价格和交期）"""
        comparison = self.get_object()
        QuotationComparisonService.auto_score(comparison)
        return Response(QuotationComparisonSerializer(comparison).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成比价分析"""
        comparison = self.get_object()
        comparison = QuotationComparisonService.complete_comparison(comparison.id)
        return Response(QuotationComparisonSerializer(comparison).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批比价分析"""
        comparison = self.get_object()
        notes = request.data.get('notes', '')
        
        try:
            comparison = QuotationComparisonService.approve_comparison(
                comparison.id, request.user, notes
            )
            return Response(QuotationComparisonSerializer(comparison).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='convert-to-po')
    def convert_to_po(self, request, pk=None):
        """将推荐报价转换为采购订单"""
        comparison = self.get_object()
        
        try:
            from .serializers import PurchaseOrderSerializer
            po = QuotationComparisonService.convert_to_po(comparison.id, request.user)
            return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='update-score/(?P<score_id>[^/.]+)')
    def update_score(self, request, pk=None, score_id=None):
        """更新单个供应商的评分（质量和服务）"""
        serializer = UpdateScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            score = QuotationComparisonService.update_manual_scores(
                score_id=score_id,
                quality_score=serializer.validated_data.get('score_quality'),
                service_score=serializer.validated_data.get('score_service'),
                notes=serializer.validated_data.get('notes')
            )
            return Response(QuotationScoreSerializer(score).data)
        except QuotationScore.DoesNotExist:
            return Response({'error': '评分记录不存在'}, status=status.HTTP_404_NOT_FOUND)


class QuotationScoreViewSet(viewsets.ModelViewSet):
    """报价评分视图"""
    queryset = QuotationScore.objects.all()
    serializer_class = QuotationScoreSerializer
    filterset_fields = ['comparison', 'quotation', 'is_recommended']
    ordering_fields = ['ranking', 'total_score']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related(
            'comparison', 'quotation',
            'quotation__rfq_supplier__supplier'
        )
    
    @action(detail=True, methods=['post'], url_path='update-manual')
    def update_manual(self, request, pk=None):
        """更新手动评分"""
        score = self.get_object()
        serializer = UpdateScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        score = QuotationComparisonService.update_manual_scores(
            score_id=score.id,
            quality_score=serializer.validated_data.get('score_quality'),
            service_score=serializer.validated_data.get('score_service'),
            notes=serializer.validated_data.get('notes')
        )
        return Response(QuotationScoreSerializer(score).data)


class ItemPriceHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """物料价格历史视图（只读）"""
    queryset = ItemPriceHistory.objects.all()
    serializer_class = ItemPriceHistorySerializer
    filterset_fields = ['item', 'supplier', 'source_type']
    ordering_fields = ['price_date', 'unit_price']
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_deleted=False)
        return queryset.select_related('item', 'supplier')
    
    @action(detail=False, methods=['get'], url_path='by-item/(?P<item_id>[^/.]+)')
    def by_item(self, request, item_id=None):
        """获取指定物料的价格历史"""
        supplier_id = request.query_params.get('supplier_id')
        limit = int(request.query_params.get('limit', 10))
        
        history = QuotationComparisonService.get_item_price_history(
            item_id=item_id,
            supplier_id=supplier_id,
            limit=limit
        )
        return Response(history)
    
    @action(detail=False, methods=['get'], url_path='last-price')
    def last_price(self, request):
        """获取物料上次采购价格"""
        item_id = request.query_params.get('item_id')
        supplier_id = request.query_params.get('supplier_id')
        
        if not item_id or not supplier_id:
            return Response(
                {'error': '请提供 item_id 和 supplier_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        price = QuotationComparisonService.get_last_purchase_price(item_id, supplier_id)
        return Response({'last_price': price})

