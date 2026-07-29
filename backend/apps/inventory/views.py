"""
Views for inventory app.
"""

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin
from apps.core.workflow.mixins import WorkflowEnforcementMixin

from .cost_methods import FIFOCostingService
from .models import Stock, StockAdjustment, StockAdjustmentLine, StockMove
from .serializers import StockAdjustmentLineSerializer, StockAdjustmentSerializer, StockMoveSerializer, StockSerializer


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
            qty_on_hand__lt=F('item__min_stock'), item__min_stock__gt=0
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
            valuation_data.append(
                {
                    'warehouse': stock.warehouse.name,
                    'item_sku': stock.item.sku,
                    'item_name': stock.item.name,
                    'qty': float(stock.qty_on_hand),
                    'cost': float(stock.weighted_avg_cost),
                    'value': float(value),
                }
            )

        return Response({'total_value': float(total_value), 'items': valuation_data})

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
            return Response({'error': '请提供 warehouse, item, qty 参数'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from apps.masterdata.models import Item, Warehouse

            warehouse = Warehouse.objects.get(id=warehouse_id)
            item = Item.objects.get(id=item_id)
            qty = float(qty)
        except (Warehouse.DoesNotExist, Item.DoesNotExist, ValueError):
            return Response({'error': '无效的参数'}, status=status.HTTP_400_BAD_REQUEST)

        total_cost, avg_cost, details = FIFOCostingService.get_fifo_cost(warehouse, item, qty)

        return Response(
            {
                'warehouse': warehouse.name,
                'item_sku': item.sku,
                'item_name': item.name,
                'requested_qty': qty,
                'total_cost': float(total_cost),
                'average_unit_cost': float(avg_cost),
                'lot_details': details,
            }
        )

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
            data.append(
                {
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
                }
            )

        return Response(data)

    @action(detail=False, methods=['get'])
    def costing_method(self, request):
        """Get current inventory costing method."""
        method = getattr(settings, 'INVENTORY_COSTING_METHOD', 'WEIGHTED_AVG')
        return Response({'method': method, 'description': 'FIFO (先进先出)' if method == 'FIFO' else '加权平均法'})


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

    def get_queryset(self):
        """支持前端的 warehouse(匹配来源/目标仓任一)与 start_date/end_date 日期范围过滤。

        StockMove 只有 warehouse_from/warehouse_to,没有单一 warehouse 字段;filterset 也无
        日期过滤。前端库存流水页发来的 warehouse / start_date / end_date 此前被后端静默忽略,
        用户以为筛选生效却拿到全量数据。此处补齐,与列表页筛选控件保持一致。
        """
        from django.db.models import Q

        queryset = super().get_queryset()

        warehouse = self.request.query_params.get('warehouse')
        if warehouse:
            queryset = queryset.filter(Q(warehouse_from_id=warehouse) | Q(warehouse_to_id=warehouse))

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(move_date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(move_date__lte=end_date)

        return queryset

    # 按移动方向归类 move_type:qty 恒为正,方向由类型(及调整的仓库字段)决定。
    IN_MOVE_TYPES = ['IN_PURCHASE', 'IN_OUTSOURCE']
    OUT_MOVE_TYPES = ['OUT_SALES', 'OUT_PROJECT', 'OUT_RETURN', 'OUT_OUTSOURCE']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """按当前筛选条件对全量数据聚合入库/出库数量与金额(不受分页限制)。

        前端此前只对当前页 tableData 累加,且用 qty>0 判方向——但 StockMove.qty 恒为正,
        导致出库恒为 0、且统计只覆盖一页。此处按 move_type 在数据库层聚合全量结果:
        - 入库:IN_PURCHASE/IN_OUTSOURCE,加上调拨入库(warehouse_to)与盘盈(ADJUSTMENT+warehouse_to)
        - 出库:OUT_*,加上调拨出库(warehouse_from)与盘亏(ADJUSTMENT+warehouse_from)
        调拨在两侧各计一次(物料确实流出源仓、流入目标仓)。
        """
        from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum

        queryset = self.filter_queryset(self.get_queryset())

        value_expr = ExpressionWrapper(
            F('qty') * F('unit_cost'), output_field=DecimalField(max_digits=24, decimal_places=4)
        )

        in_filter = (
            Q(move_type__in=self.IN_MOVE_TYPES)
            | Q(move_type='TRANSFER', warehouse_to__isnull=False)
            | Q(move_type='ADJUSTMENT', warehouse_to__isnull=False)
        )
        out_filter = (
            Q(move_type__in=self.OUT_MOVE_TYPES)
            | Q(move_type='TRANSFER', warehouse_from__isnull=False)
            | Q(move_type='ADJUSTMENT', warehouse_from__isnull=False)
        )

        agg = queryset.aggregate(
            total_in=Sum('qty', filter=in_filter),
            total_out=Sum('qty', filter=out_filter),
            total_in_value=Sum(value_expr, filter=in_filter),
            total_out_value=Sum(value_expr, filter=out_filter),
        )

        return Response(
            {
                'total_in': float(agg['total_in'] or 0),
                'total_out': float(agg['total_out'] or 0),
                'total_in_value': float(agg['total_in_value'] or 0),
                'total_out_value': float(agg['total_out_value'] or 0),
            }
        )

    @action(detail=False, methods=['post'])
    def transfer(self, request):
        """Create a warehouse transfer with multiple lines."""
        data = request.data
        lines = data.get('lines', [])

        if not lines:
            return Response({'error': '请添加调拨明细'}, status=status.HTTP_400_BAD_REQUEST)

        created_moves = []
        try:
            with transaction.atomic():
                for line in lines:
                    if not line.get('item') or not line.get('qty') or line.get('qty') <= 0:
                        continue

                    # Get unit cost from stock
                    unit_cost = 0
                    try:
                        stock = Stock.objects.get(warehouse_id=data.get('from_warehouse'), item_id=line.get('item'))
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
                        created_by=request.user,
                    )
                    created_moves.append(move)
        except ValueError as e:
            # 库存不足等业务校验错误转为可读的 400，避免未捕获 ValueError 冒泡为 500
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not created_moves:
            return Response({'error': '没有有效的调拨明细'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {'message': f'成功创建 {len(created_moves)} 条调拨记录', 'count': len(created_moves)},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'])
    def project_consumption(self, request):
        """Get material consumption by project."""
        project_id = request.query_params.get('project')
        if not project_id:
            return Response({'error': '请提供project参数'}, status=status.HTTP_400_BAD_REQUEST)

        moves = (
            StockMove.objects.filter(project_id=project_id, move_type='OUT_PROJECT', status='COMPLETED')
            .select_related('item')
            .values('item__sku', 'item__name', 'item__unit')
            .annotate(total_qty=Sum('qty'), total_cost=Sum(F('qty') * F('unit_cost')))
        )

        return Response(list(moves))


class StockAdjustmentViewSet(
    PermissionMixin,
    WorkflowEnforcementMixin,
    SoftDeleteMixin,
    UserTrackingMixin,
    viewsets.ModelViewSet,
):
    permission_module = 'inventory'
    permission_resource = 'stock_adjustment'
    workflow_business_type = 'STOCK_ADJUSTMENT'
    workflow_amount_field = None
    workflow_no_field = 'adjustment_no'
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
        """计算库存调整的成本影响(金额),用于按金额分级的审批路由。

        不能读 line.cost_impact —— 它是存储字段、仅在 confirm() 时才赋值,提交审批时恒为 0,
        会让大额盘亏以 amount=0 命中最低级流程并跳过高额审批步(审计 batch1 #2)。
        故在此按 confirm() 同样的口径实时计算:|qty_diff| × 当前加权均价(无库存回退标准成本)。
        """
        from decimal import Decimal

        total = Decimal('0')
        for line in adjustment.lines.filter(is_deleted=False):
            if not line.qty_diff:
                continue
            try:
                stock = Stock.objects.get(warehouse=adjustment.warehouse, item=line.item)
                unit_cost = stock.weighted_avg_cost or Decimal('0')
            except Stock.DoesNotExist:
                unit_cost = getattr(line.item, 'standard_cost', 0) or Decimal('0')
            total += abs(Decimal(str(line.qty_diff)) * Decimal(str(unit_cost)))
        return total

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交库存调整审批 - 审批步骤由流程配置决定"""
        adjustment = self.get_object()
        if adjustment.status not in ['DRAFT', 'REJECTED']:
            return Response({'error': '只能提交草稿或已拒绝状态的调整单'}, status=status.HTTP_400_BAD_REQUEST)

        # 使用成本影响作为金额
        amount = self._calculate_cost_impact(adjustment)

        try:
            result = self.start_workflow_or_auto_approve(
                adjustment,
                request.user,
                approved_status='CONFIRMED',
                submitted_status='PENDING',
                amount_override=amount,
            )

            if result['workflow_started']:
                adjustment.status = 'PENDING'
                adjustment.save()
                return Response(
                    {
                        **StockAdjustmentSerializer(adjustment).data,
                        'workflow_started': True,
                        'workflow_id': result['instance'].id,
                        'message': '已提交审批，请在审批中心查看审批进度',
                    }
                )
            elif result['auto_approved']:
                # 未配置审批流程，直接确认
                return self._do_confirm(adjustment, request)

            return Response({'error': result['message']}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            return Response(
                {'error': f'审批服务暂时不可用，请稍后重试: {e}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """直接确认库存调整（跳过审批）"""
        adjustment = self.get_object()
        if adjustment.status not in ['DRAFT', 'APPROVED']:
            return Response({'error': '只能确认草稿或已审批状态的调整单'}, status=status.HTTP_400_BAD_REQUEST)

        workflow_error = self.check_workflow_allows_direct_action(adjustment, '确认')
        if workflow_error:
            return workflow_error

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
                        stock = Stock.objects.get(warehouse=adjustment.warehouse, item=line.item)
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
                        notes=f'库存调整: {adjustment.reason}',
                        created_by=request.user,
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
