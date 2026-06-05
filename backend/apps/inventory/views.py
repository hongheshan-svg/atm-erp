"""
Views for inventory app.
"""
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, F
from django.conf import settings
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin
from .models import Stock, StockMove, StockAdjustment, StockAdjustmentLine
from .serializers import (
    StockSerializer, StockMoveSerializer,
    StockAdjustmentSerializer, StockAdjustmentLineSerializer
)
from .cost_methods import FIFOCostingService, CostingMethodFactory


class StockViewSet(PermissionMixin, SoftDeleteMixin, mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):

    permission_module = 'inventory'
    permission_resource = 'stock'
    """
    ViewSet for Stock - Read-only.
    Stock is updated automatically by StockMove.
    """
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    filterset_fields = ['warehouse', 'item']
    search_fields = ['item__sku', 'item__name']
    ordering_fields = ['warehouse', 'item', 'qty_on_hand', 'updated_at']

    def destroy(self, request, *args, **kwargs):
        """库存只读,由 StockMove 自动维护;仅系统管理员/超管可软删除(账实敏感)。"""
        user = request.user
        is_admin = user.is_superuser or user.roles.filter(code='admin').exists()
        if not is_admin:
            raise PermissionDenied('仅系统管理员可删除库存记录')
        return super().destroy(request, *args, **kwargs)

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
    
    @action(detail=False, methods=['get'])
    def fifo_cost(self, request):
        """
        Get FIFO cost calculation for a specific item and quantity.
        Query params: warehouse, item, qty
        """
        warehouse_id = request.query_params.get('warehouse')
        item_id = request.query_params.get('item')
        qty = request.query_params.get('qty')
        
        if not all([warehouse_id, item_id, qty]):
            return Response(
                {'error': '请提供 warehouse, item, qty 参数'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.masterdata.models import Warehouse, Item
            warehouse = Warehouse.objects.get(id=warehouse_id)
            item = Item.objects.get(id=item_id)
            qty = float(qty)
        except (Warehouse.DoesNotExist, Item.DoesNotExist, ValueError):
            return Response(
                {'error': '无效的参数'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        total_cost, avg_cost, details = FIFOCostingService.get_fifo_cost(
            warehouse, item, qty
        )
        
        return Response({
            'warehouse': warehouse.name,
            'item_sku': item.sku,
            'item_name': item.name,
            'requested_qty': qty,
            'total_cost': float(total_cost),
            'average_unit_cost': float(avg_cost),
            'lot_details': details
        })
    
    @action(detail=False, methods=['get'])
    def fifo_lots(self, request):
        """
        Get FIFO inventory lots.
        Query params: warehouse (optional), item (optional)
        """
        warehouse_id = request.query_params.get('warehouse')
        item_id = request.query_params.get('item')
        
        warehouse = None
        item = None
        
        if warehouse_id:
            from apps.masterdata.models import Warehouse
            try:
                warehouse = Warehouse.objects.get(id=warehouse_id)
            except Warehouse.DoesNotExist:
                pass
        
        if item_id:
            from apps.masterdata.models import Item
            try:
                item = Item.objects.get(id=item_id)
            except Item.DoesNotExist:
                pass
        
        lots = FIFOCostingService.get_lot_inventory(warehouse, item)
        
        data = []
        for lot in lots:
            data.append({
                'id': lot.id,
                'lot_no': lot.lot_no,
                'warehouse': lot.warehouse.name,
                'item_sku': lot.item.sku,
                'item_name': lot.item.name,
                'initial_qty': float(lot.initial_qty),
                'remaining_qty': float(lot.remaining_qty),
                'consumed_qty': float(lot.consumed_qty),
                'unit_cost': float(lot.unit_cost),
                'total_value': float(lot.total_value),
                'receipt_date': lot.receipt_date.isoformat(),
            })
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def costing_method(self, request):
        """Get current inventory costing method."""
        method = getattr(settings, 'INVENTORY_COSTING_METHOD', 'WEIGHTED_AVG')
        return Response({
            'method': method,
            'description': 'FIFO (先进先出)' if method == 'FIFO' else '加权平均法'
        })


class StockMoveViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):

    permission_module = 'inventory'
    permission_resource = 'stock_move'
    """
    ViewSet for StockMove management.
    """
    queryset = StockMove.objects.all()
    serializer_class = StockMoveSerializer
    filterset_fields = ['item', 'warehouse_from', 'warehouse_to', 'move_type', 'project', 'status', 'is_deleted']
    search_fields = ['move_no', 'item__sku', 'item__name']
    ordering_fields = ['move_date', 'created_at']
    
    @action(detail=False, methods=['post'])
    def transfer(self, request):
        """Create a warehouse transfer with multiple lines."""
        data = request.data
        lines = data.get('lines', [])
        
        if not lines:
            return Response({'error': '请添加调拨明细'}, status=status.HTTP_400_BAD_REQUEST)
        
        created_moves = []
        with transaction.atomic():
            for line in lines:
                if not line.get('item') or not line.get('qty') or line.get('qty') <= 0:
                    continue
                    
                # Get unit cost from stock
                unit_cost = 0
                try:
                    stock = Stock.objects.get(
                        warehouse_id=data.get('from_warehouse'),
                        item_id=line.get('item')
                    )
                    unit_cost = stock.weighted_avg_cost
                except Stock.DoesNotExist:
                    pass
                
                move = StockMove.objects.create(
                    item_id=line.get('item'),
                    warehouse_from_id=data.get('from_warehouse'),
                    warehouse_to_id=data.get('to_warehouse'),
                    qty=line.get('qty'),
                    unit_cost=unit_cost,
                    move_type='TRANSFER',
                    move_date=data.get('transfer_date'),
                    notes=line.get('notes') or data.get('notes', ''),
                    status='COMPLETED',
                    created_by=request.user
                )
                created_moves.append(move)
        
        if not created_moves:
            return Response({'error': '没有有效的调拨明细'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': f'成功创建 {len(created_moves)} 条调拨记录',
            'count': len(created_moves)
        }, status=status.HTTP_201_CREATED)
    
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


class StockAdjustmentViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'inventory'
    permission_resource = 'stock_adjustment'
    """
    ViewSet for StockAdjustment management.
    
    库存调整审批流程由审批中心的流程配置决定。
    """
    queryset = StockAdjustment.objects.all()
    serializer_class = StockAdjustmentSerializer
    filterset_fields = ['warehouse', 'status', 'is_deleted']
    search_fields = ['adjustment_no']
    ordering_fields = ['adjustment_date', 'created_at']
    
    def _calculate_cost_impact(self, adjustment):
        """计算库存调整的成本影响"""
        total = 0
        for line in adjustment.lines.filter(is_deleted=False):
            total += abs(line.cost_impact or 0)
        return total
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交库存调整审批 - 审批步骤由流程配置决定"""
        adjustment = self.get_object()
        if adjustment.status not in ['DRAFT', 'REJECTED']:
            return Response(
                {'error': '只能提交草稿或已拒绝状态的调整单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 使用成本影响作为金额
        amount = self._calculate_cost_impact(adjustment)
        
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='STOCK_ADJUSTMENT',
                business_id=adjustment.id,
                business_no=adjustment.adjustment_no,
                submitter=request.user,
                amount=amount
            )
            
            if instance:
                adjustment.status = 'PENDING'
                adjustment.save()
                return Response({
                    **StockAdjustmentSerializer(adjustment).data,
                    'workflow_started': True,
                    'workflow_id': instance.id,
                    'message': '已提交审批，请在审批中心查看审批进度'
                })
            else:
                # 未配置审批流程，直接确认
                return self._do_confirm(adjustment, request)
                
        except Exception as e:
            # 审批模块不可用，直接确认
            return self._do_confirm(adjustment, request)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """直接确认库存调整（跳过审批）"""
        adjustment = self.get_object()
        if adjustment.status not in ['DRAFT', 'APPROVED']:
            return Response(
                {'error': '只能确认草稿或已审批状态的调整单'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._do_confirm(adjustment, request)
    
    def _do_confirm(self, adjustment, request):
        """执行库存调整确认逻辑"""
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
                        unit_cost = line.item.standard_cost if hasattr(line.item, 'standard_cost') else 0
                    
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


class StockAdjustmentLineViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):

    permission_module = 'inventory'
    permission_resource = 'stock_adjustment_line'
    """
    ViewSet for StockAdjustmentLine management.
    """
    queryset = StockAdjustmentLine.objects.all()
    serializer_class = StockAdjustmentLineSerializer
    filterset_fields = ['adjustment', 'item', 'is_deleted']
    search_fields = ['item__sku', 'item__name']

