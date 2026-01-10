"""
库存成本核算
Inventory Cost Accounting
支持加权平均法、先进先出法、移动加权平均法等库存计价方法
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from django.db import models, transaction
from django.db.models import Sum, F, Q, Avg
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class InventoryCostConfig(BaseModel):
    """
    库存成本配置
    """
    COSTING_METHODS = [
        ('WEIGHTED_AVG', '加权平均法'),
        ('MOVING_AVG', '移动加权平均法'),
        ('FIFO', '先进先出法'),
        ('LIFO', '后进先出法'),
        ('STANDARD', '标准成本法'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='配置名称')
    costing_method = models.CharField(
        max_length=20,
        choices=COSTING_METHODS,
        default='WEIGHTED_AVG',
        verbose_name='计价方法'
    )
    is_default = models.BooleanField(default=False, verbose_name='默认配置')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    # 期间设置
    period_type = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', '月结'),
            ('QUARTERLY', '季结'),
            ('YEARLY', '年结'),
        ],
        default='MONTHLY',
        verbose_name='结算周期'
    )
    
    # 成本要素
    include_purchase_price = models.BooleanField(default=True, verbose_name='包含采购价')
    include_freight = models.BooleanField(default=True, verbose_name='包含运费')
    include_tax = models.BooleanField(default=False, verbose_name='包含税费')
    include_handling = models.BooleanField(default=False, verbose_name='包含装卸费')
    
    description = models.TextField(blank=True, verbose_name='说明')
    
    class Meta:
        db_table = 'inventory_cost_config'
        verbose_name = '库存成本配置'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.name} - {self.get_costing_method_display()}'
    
    def save(self, *args, **kwargs):
        if self.is_default:
            InventoryCostConfig.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ItemCostRecord(BaseModel):
    """
    物料成本记录
    每次入库/出库后记录成本变化
    """
    TRANSACTION_TYPES = [
        ('PURCHASE_IN', '采购入库'),
        ('RETURN_IN', '退货入库'),
        ('TRANSFER_IN', '调拨入库'),
        ('ADJUST_IN', '盘盈入库'),
        ('PRODUCTION_IN', '生产入库'),
        ('SALES_OUT', '销售出库'),
        ('RETURN_OUT', '退货出库'),
        ('TRANSFER_OUT', '调拨出库'),
        ('ADJUST_OUT', '盘亏出库'),
        ('PRODUCTION_OUT', '生产领料'),
        ('COST_ADJUST', '成本调整'),
    ]
    
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.CASCADE,
        related_name='cost_records',
        verbose_name='物料'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cost_records',
        verbose_name='仓库'
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        verbose_name='交易类型'
    )
    reference_type = models.CharField(max_length=50, blank=True, verbose_name='参考类型')
    reference_no = models.CharField(max_length=50, blank=True, verbose_name='参考单号')
    reference_id = models.IntegerField(null=True, blank=True, verbose_name='参考ID')
    
    transaction_date = models.DateField(verbose_name='交易日期')
    
    # 数量
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name='数量'
    )
    
    # 单价
    unit_cost = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name='单位成本'
    )
    
    # 金额
    total_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='总成本'
    )
    
    # 结存
    balance_qty = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name='结存数量'
    )
    balance_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='结存金额'
    )
    balance_unit_cost = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name='结存单价'
    )
    
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_item_cost_record'
        verbose_name = '物料成本记录'
        verbose_name_plural = verbose_name
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['item', 'transaction_date']),
            models.Index(fields=['reference_no']),
        ]
    
    def __str__(self):
        return f'{self.item.name} - {self.get_transaction_type_display()}'


class PeriodCostSummary(BaseModel):
    """
    期间成本汇总
    按月/季/年汇总物料成本
    """
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.CASCADE,
        related_name='period_summaries',
        verbose_name='物料'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='仓库'
    )
    
    period_year = models.IntegerField(verbose_name='年份')
    period_month = models.IntegerField(verbose_name='月份')
    
    # 期初
    opening_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='期初数量')
    opening_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期初金额')
    
    # 入库汇总
    in_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='入库数量')
    in_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='入库金额')
    
    # 出库汇总
    out_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='出库数量')
    out_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='出库金额')
    
    # 期末
    closing_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='期末数量')
    closing_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期末金额')
    closing_unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='期末单价')
    
    is_closed = models.BooleanField(default=False, verbose_name='已结账')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='结账时间')
    closed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_cost_summaries',
        verbose_name='结账人'
    )
    
    class Meta:
        db_table = 'inventory_period_cost_summary'
        verbose_name = '期间成本汇总'
        verbose_name_plural = verbose_name
        unique_together = ['item', 'warehouse', 'period_year', 'period_month']
        ordering = ['-period_year', '-period_month']
    
    def __str__(self):
        return f'{self.item.name} - {self.period_year}年{self.period_month}月'


# =====================
# Cost Calculation Service
# =====================

class CostCalculationService:
    """成本计算服务"""
    
    def __init__(self, method='WEIGHTED_AVG'):
        self.method = method
    
    def calculate_weighted_average(self, item_id, warehouse_id=None) -> Decimal:
        """计算加权平均成本"""
        filters = {'item_id': item_id, 'is_deleted': False}
        if warehouse_id:
            filters['warehouse_id'] = warehouse_id
        
        # 获取最新的成本记录
        last_record = ItemCostRecord.objects.filter(**filters).order_by('-created_at').first()
        
        if last_record and last_record.balance_qty > 0:
            return last_record.balance_unit_cost
        
        # 没有记录时，从采购历史获取平均价
        from apps.purchase.models import PurchaseOrderLine
        avg_price = PurchaseOrderLine.objects.filter(
            item_id=item_id,
            order__status='COMPLETED'
        ).aggregate(avg_price=Avg('unit_price'))['avg_price']
        
        return Decimal(str(avg_price)) if avg_price else Decimal('0')
    
    def process_inbound(
        self,
        item_id: int,
        warehouse_id: int,
        quantity: Decimal,
        unit_cost: Decimal,
        transaction_type: str,
        reference_no: str = '',
        reference_id: int = None,
        transaction_date: date = None,
        user=None
    ) -> ItemCostRecord:
        """处理入库成本"""
        transaction_date = transaction_date or date.today()
        
        # 获取当前结存
        last_record = ItemCostRecord.objects.filter(
            item_id=item_id,
            warehouse_id=warehouse_id,
            is_deleted=False
        ).order_by('-created_at').first()
        
        if last_record:
            prev_qty = last_record.balance_qty
            prev_cost = last_record.balance_cost
        else:
            prev_qty = Decimal('0')
            prev_cost = Decimal('0')
        
        total_cost = quantity * unit_cost
        
        # 计算新的加权平均
        new_qty = prev_qty + quantity
        new_total_cost = prev_cost + total_cost
        
        if new_qty > 0:
            new_unit_cost = (new_total_cost / new_qty).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        else:
            new_unit_cost = unit_cost
        
        record = ItemCostRecord.objects.create(
            item_id=item_id,
            warehouse_id=warehouse_id,
            transaction_type=transaction_type,
            reference_no=reference_no,
            reference_id=reference_id,
            transaction_date=transaction_date,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            balance_qty=new_qty,
            balance_cost=new_total_cost,
            balance_unit_cost=new_unit_cost,
            created_by=user
        )
        
        return record
    
    def process_outbound(
        self,
        item_id: int,
        warehouse_id: int,
        quantity: Decimal,
        transaction_type: str,
        reference_no: str = '',
        reference_id: int = None,
        transaction_date: date = None,
        user=None
    ) -> ItemCostRecord:
        """处理出库成本"""
        transaction_date = transaction_date or date.today()
        
        # 获取当前结存
        last_record = ItemCostRecord.objects.filter(
            item_id=item_id,
            warehouse_id=warehouse_id,
            is_deleted=False
        ).order_by('-created_at').first()
        
        if last_record:
            prev_qty = last_record.balance_qty
            prev_cost = last_record.balance_cost
            unit_cost = last_record.balance_unit_cost
        else:
            prev_qty = Decimal('0')
            prev_cost = Decimal('0')
            unit_cost = Decimal('0')
        
        total_cost = (quantity * unit_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        new_qty = prev_qty - quantity
        new_total_cost = prev_cost - total_cost
        
        if new_qty > 0:
            new_unit_cost = (new_total_cost / new_qty).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        else:
            new_unit_cost = unit_cost
            new_total_cost = Decimal('0')
        
        record = ItemCostRecord.objects.create(
            item_id=item_id,
            warehouse_id=warehouse_id,
            transaction_type=transaction_type,
            reference_no=reference_no,
            reference_id=reference_id,
            transaction_date=transaction_date,
            quantity=-quantity,
            unit_cost=unit_cost,
            total_cost=-total_cost,
            balance_qty=new_qty,
            balance_cost=new_total_cost,
            balance_unit_cost=new_unit_cost,
            created_by=user
        )
        
        return record
    
    @staticmethod
    def generate_period_summary(year: int, month: int, warehouse_id: int = None):
        """生成期间成本汇总"""
        from apps.masterdata.models import Item
        
        items = Item.objects.filter(is_deleted=False)
        summaries = []
        
        for item in items:
            filters = {'item': item, 'is_deleted': False}
            if warehouse_id:
                filters['warehouse_id'] = warehouse_id
            
            # 获取期初（上月期末）
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            
            prev_summary = PeriodCostSummary.objects.filter(
                item=item,
                period_year=prev_year,
                period_month=prev_month,
                warehouse_id=warehouse_id
            ).first()
            
            if prev_summary:
                opening_qty = prev_summary.closing_qty
                opening_cost = prev_summary.closing_cost
            else:
                opening_qty = Decimal('0')
                opening_cost = Decimal('0')
            
            # 计算本期入库
            in_records = ItemCostRecord.objects.filter(
                item=item,
                transaction_date__year=year,
                transaction_date__month=month,
                quantity__gt=0,
                is_deleted=False
            )
            if warehouse_id:
                in_records = in_records.filter(warehouse_id=warehouse_id)
            
            in_agg = in_records.aggregate(
                total_qty=Sum('quantity'),
                total_cost=Sum('total_cost')
            )
            in_qty = in_agg['total_qty'] or Decimal('0')
            in_cost = in_agg['total_cost'] or Decimal('0')
            
            # 计算本期出库
            out_records = ItemCostRecord.objects.filter(
                item=item,
                transaction_date__year=year,
                transaction_date__month=month,
                quantity__lt=0,
                is_deleted=False
            )
            if warehouse_id:
                out_records = out_records.filter(warehouse_id=warehouse_id)
            
            out_agg = out_records.aggregate(
                total_qty=Sum('quantity'),
                total_cost=Sum('total_cost')
            )
            out_qty = abs(out_agg['total_qty'] or Decimal('0'))
            out_cost = abs(out_agg['total_cost'] or Decimal('0'))
            
            # 计算期末
            closing_qty = opening_qty + in_qty - out_qty
            closing_cost = opening_cost + in_cost - out_cost
            closing_unit_cost = (closing_cost / closing_qty).quantize(
                Decimal('0.0001'), rounding=ROUND_HALF_UP
            ) if closing_qty > 0 else Decimal('0')
            
            summary, created = PeriodCostSummary.objects.update_or_create(
                item=item,
                warehouse_id=warehouse_id,
                period_year=year,
                period_month=month,
                defaults={
                    'opening_qty': opening_qty,
                    'opening_cost': opening_cost,
                    'in_qty': in_qty,
                    'in_cost': in_cost,
                    'out_qty': out_qty,
                    'out_cost': out_cost,
                    'closing_qty': closing_qty,
                    'closing_cost': closing_cost,
                    'closing_unit_cost': closing_unit_cost,
                }
            )
            summaries.append(summary)
        
        return summaries


# =====================
# Serializers
# =====================

class InventoryCostConfigSerializer(serializers.ModelSerializer):
    costing_method_display = serializers.CharField(source='get_costing_method_display', read_only=True)
    period_type_display = serializers.CharField(source='get_period_type_display', read_only=True)
    
    class Meta:
        model = InventoryCostConfig
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ItemCostRecordSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    
    class Meta:
        model = ItemCostRecord
        fields = '__all__'


class PeriodCostSummarySerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = PeriodCostSummary
        fields = '__all__'


# =====================
# ViewSets
# =====================

class InventoryCostConfigViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """库存成本配置管理"""
    queryset = InventoryCostConfig.objects.filter(is_deleted=False)
    serializer_class = InventoryCostConfigSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设为默认配置"""
        config = self.get_object()
        config.is_default = True
        config.save()
        return Response(self.get_serializer(config).data)
    
    @action(detail=False, methods=['get'])
    def costing_methods(self, request):
        """获取计价方法"""
        return Response([
            {'value': m[0], 'label': m[1]}
            for m in InventoryCostConfig.COSTING_METHODS
        ])


class ItemCostRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """物料成本记录"""
    queryset = ItemCostRecord.objects.filter(is_deleted=False)
    serializer_class = ItemCostRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['item', 'warehouse', 'transaction_type']
    search_fields = ['item__code', 'item__name', 'reference_no']
    ordering_fields = ['transaction_date', 'created_at']
    
    @action(detail=False, methods=['get'])
    def by_item(self, request):
        """按物料查询成本记录"""
        item_id = request.query_params.get('item_id')
        if not item_id:
            return Response({'error': '请提供物料ID'}, status=400)
        
        records = self.get_queryset().filter(item_id=item_id)[:100]
        return Response(self.get_serializer(records, many=True).data)
    
    @action(detail=False, methods=['get'])
    def current_cost(self, request):
        """获取当前成本"""
        item_id = request.query_params.get('item_id')
        warehouse_id = request.query_params.get('warehouse_id')
        
        if not item_id:
            return Response({'error': '请提供物料ID'}, status=400)
        
        service = CostCalculationService()
        unit_cost = service.calculate_weighted_average(item_id, warehouse_id)
        
        filters = {'item_id': item_id, 'is_deleted': False}
        if warehouse_id:
            filters['warehouse_id'] = warehouse_id
        
        last_record = ItemCostRecord.objects.filter(**filters).order_by('-created_at').first()
        
        return Response({
            'item_id': item_id,
            'unit_cost': unit_cost,
            'balance_qty': last_record.balance_qty if last_record else 0,
            'balance_cost': last_record.balance_cost if last_record else 0
        })


class PeriodCostSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """期间成本汇总"""
    queryset = PeriodCostSummary.objects.filter(is_deleted=False)
    serializer_class = PeriodCostSummarySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['item', 'warehouse', 'period_year', 'period_month', 'is_closed']
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """生成期间汇总"""
        year = request.data.get('year', date.today().year)
        month = request.data.get('month', date.today().month)
        warehouse_id = request.data.get('warehouse_id')
        
        summaries = CostCalculationService.generate_period_summary(year, month, warehouse_id)
        
        return Response({
            'success': True,
            'count': len(summaries),
            'message': f'已生成{year}年{month}月成本汇总'
        })
    
    @action(detail=False, methods=['post'])
    def close_period(self, request):
        """期末结账"""
        year = request.data.get('year')
        month = request.data.get('month')
        
        if not year or not month:
            return Response({'error': '请提供年份和月份'}, status=400)
        
        count = PeriodCostSummary.objects.filter(
            period_year=year,
            period_month=month,
            is_closed=False
        ).update(
            is_closed=True,
            closed_at=datetime.now(),
            closed_by=request.user
        )
        
        return Response({
            'success': True,
            'count': count,
            'message': f'{year}年{month}月已结账'
        })
    
    @action(detail=False, methods=['get'])
    def inventory_valuation(self, request):
        """库存估值报表"""
        year = request.query_params.get('year', date.today().year)
        month = request.query_params.get('month', date.today().month)
        
        summaries = self.get_queryset().filter(
            period_year=year,
            period_month=month
        ).select_related('item', 'warehouse')
        
        total_opening = summaries.aggregate(total=Sum('opening_cost'))['total'] or 0
        total_in = summaries.aggregate(total=Sum('in_cost'))['total'] or 0
        total_out = summaries.aggregate(total=Sum('out_cost'))['total'] or 0
        total_closing = summaries.aggregate(total=Sum('closing_cost'))['total'] or 0
        
        # 按仓库分组
        by_warehouse = summaries.values('warehouse__name').annotate(
            total_qty=Sum('closing_qty'),
            total_cost=Sum('closing_cost')
        )
        
        # 按物料类别分组
        by_category = summaries.values('item__category__name').annotate(
            total_qty=Sum('closing_qty'),
            total_cost=Sum('closing_cost')
        )
        
        return Response({
            'period': f'{year}年{month}月',
            'total_opening_cost': total_opening,
            'total_in_cost': total_in,
            'total_out_cost': total_out,
            'total_closing_cost': total_closing,
            'by_warehouse': list(by_warehouse),
            'by_category': list(by_category),
            'details': self.get_serializer(summaries, many=True).data
        })
