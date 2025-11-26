"""
Views for inventory app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, F
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from .models import Stock, StockMove, StockAdjustment, StockAdjustmentLine
from .serializers import (
    StockSerializer, StockMoveSerializer,
    StockAdjustmentSerializer, StockAdjustmentLineSerializer
)


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Stock - Read-only.
    Stock is updated automatically by StockMove.
    """
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    filterset_fields = ['warehouse', 'item']
    search_fields = ['item__sku', 'item__name']
    ordering_fields = ['warehouse', 'item', 'qty_on_hand', 'last_updated']
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get items with low stock (below min_stock)."""
        stocks = Stock.objects.select_related('item', 'warehouse').filter(
            qty_on_hand__lt=F('item__min_stock'),
            item__min_stock__gt=0
        )
        serializer = self.get_serializer(stocks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def valuation(self, request):
        """Get total stock valuation."""
        warehouse_id = request.query_params.get('warehouse')
        
        stocks = Stock.objects.all()
        if warehouse_id:
            stocks = stocks.filter(warehouse_id=warehouse_id)
        
        valuation_data = []
        total_value = 0
        
        for stock in stocks.select_related('warehouse', 'item'):
            value = stock.qty_on_hand * stock.weighted_avg_cost
            total_value += value
            valuation_data.append({
                'warehouse': stock.warehouse.name,
                'item_sku': stock.item.sku,
                'item_name': stock.item.name,
                'qty': float(stock.qty_on_hand),
                'cost': float(stock.weighted_avg_cost),
                'value': float(value)
            })
        
        return Response({
            'total_value': float(total_value),
            'items': valuation_data
        })


class StockMoveViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for StockMove management.
    """
    queryset = StockMove.objects.all()
    serializer_class = StockMoveSerializer
    filterset_fields = ['item', 'warehouse_from', 'warehouse_to', 'move_type', 'project', 'status', 'is_deleted']
    search_fields = ['move_no', 'item__sku', 'item__name']
    ordering_fields = ['move_date', 'created_at']
    
    @action(detail=False, methods=['post'])
    def create_transfer(self, request):
        """Create a warehouse transfer."""
        data = request.data
        
        with transaction.atomic():
            move = StockMove.objects.create(
                item_id=data.get('item'),
                warehouse_from_id=data.get('warehouse_from'),
                warehouse_to_id=data.get('warehouse_to'),
                qty=data.get('qty'),
                unit_cost=data.get('unit_cost', 0),
                move_type='TRANSFER',
                move_date=data.get('move_date'),
                status='COMPLETED',
                created_by=request.user
            )
        
        return Response(StockMoveSerializer(move).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def project_consumption(self, request):
        """Get material consumption by project."""
        project_id = request.query_params.get('project')
        if not project_id:
            return Response(
                {'error': '请提供project参数'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        moves = StockMove.objects.filter(
            project_id=project_id,
            move_type='OUT_PROJECT',
            status='COMPLETED'
        ).select_related('item').values(
            'item__sku',
            'item__name',
            'item__unit'
        ).annotate(
            total_qty=Sum('qty'),
            total_cost=Sum(F('qty') * F('unit_cost'))
        )
        
        return Response(list(moves))


class StockAdjustmentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for StockAdjustment management.
    """
    queryset = StockAdjustment.objects.all()
    serializer_class = StockAdjustmentSerializer
    filterset_fields = ['warehouse', 'status', 'is_deleted']
    search_fields = ['adjustment_no']
    ordering_fields = ['adjustment_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm adjustment and create stock moves."""
        adjustment = self.get_object()
        if adjustment.status != 'DRAFT':
            return Response(
                {'error': '只能确认草稿状态的调整单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            for line in adjustment.lines.filter(is_deleted=False):
                if line.qty_diff != 0:
                    # Create stock move for adjustment
                    warehouse_to = adjustment.warehouse if line.qty_diff > 0 else None
                    warehouse_from = adjustment.warehouse if line.qty_diff < 0 else None
                    
                    # Get current weighted average cost
                    try:
                        stock = Stock.objects.get(
                            warehouse=adjustment.warehouse,
                            item=line.item
                        )
                        unit_cost = stock.weighted_avg_cost
                    except Stock.DoesNotExist:
                        unit_cost = line.item.standard_cost
                    
                    StockMove.objects.create(
                        item=line.item,
                        warehouse_from=warehouse_from,
                        warehouse_to=warehouse_to,
                        qty=abs(line.qty_diff),
                        unit_cost=unit_cost,
                        move_type='ADJUSTMENT',
                        reference_type='StockAdjustment',
                        reference_id=adjustment.id,
                        move_date=adjustment.adjustment_date,
                        status='COMPLETED',
                        notes=f"库存调整: {adjustment.reason}",
                        created_by=request.user
                    )
                    
                    # Update cost impact
                    line.cost_impact = abs(line.qty_diff) * unit_cost
                    line.save()
            
            adjustment.status = 'CONFIRMED'
            adjustment.save()
        
        return Response(StockAdjustmentSerializer(adjustment).data)


class StockAdjustmentLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    ViewSet for StockAdjustmentLine management.
    """
    queryset = StockAdjustmentLine.objects.all()
    serializer_class = StockAdjustmentLineSerializer
    filterset_fields = ['adjustment', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']

