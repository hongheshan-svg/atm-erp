"""
Batch tracking views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from .batch_models import Batch, BatchMove
from .batch_serializers import BatchSerializer, BatchMoveSerializer


class BatchViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """Batch management viewset"""
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    filterset_fields = ['item', 'warehouse', 'quality_status', 'is_deleted']
    search_fields = ['batch_no', 'supplier_batch_no']
    ordering_fields = ['manufacture_date', 'expiry_date', 'created_at']
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get batches expiring within specified days"""
        days = int(request.query_params.get('days', 30))
        
        expiry_threshold = timezone.now().date() + timedelta(days=days)
        
        expiring_batches = self.get_queryset().filter(
            expiry_date__lte=expiry_threshold,
            expiry_date__gte=timezone.now().date(),
            qty_on_hand__gt=0
        )
        
        serializer = self.get_serializer(expiring_batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get expired batches"""
        expired_batches = self.get_queryset().filter(
            expiry_date__lt=timezone.now().date(),
            qty_on_hand__gt=0
        )
        
        serializer = self.get_serializer(expired_batches, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def adjust_qty(self, request, pk=None):
        """Adjust batch quantity"""
        batch = self.get_object()
        new_qty = request.data.get('qty')
        reason = request.data.get('reason', '')
        
        if new_qty is None:
            return Response(
                {'error': '请提供新数量'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_qty = float(new_qty)
        qty_diff = new_qty - float(batch.qty_on_hand)
        
        # Create batch move record
        BatchMove.objects.create(
            batch=batch,
            move_type='ADJUST',
            qty=qty_diff,
            reference_type='MANUAL_ADJUSTMENT',
            reference_id=batch.id,
            notes=reason,
            created_by=request.user
        )
        
        batch.qty_on_hand = new_qty
        batch.save()
        
        return Response(BatchSerializer(batch).data)
    
    @action(detail=False, methods=['get'])
    def by_item(self, request):
        """Get batches grouped by item"""
        item_id = request.query_params.get('item_id')
        
        if not item_id:
            return Response(
                {'error': '请提供物料ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        batches = self.get_queryset().filter(
            item_id=item_id,
            qty_on_hand__gt=0
        ).order_by('expiry_date')  # FEFO - First Expiry, First Out
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)


class BatchMoveViewSet(viewsets.ReadOnlyModelViewSet):
    """Batch move history viewset (read-only)"""
    queryset = BatchMove.objects.all()
    serializer_class = BatchMoveSerializer
    filterset_fields = ['batch', 'move_type']
    ordering_fields = ['move_date']
    
    @action(detail=False, methods=['get'])
    def by_batch(self, request):
        """Get move history for a specific batch"""
        batch_id = request.query_params.get('batch_id')
        
        if not batch_id:
            return Response(
                {'error': '请提供批次ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        moves = self.get_queryset().filter(batch_id=batch_id)
        serializer = self.get_serializer(moves, many=True)
        return Response(serializer.data)

