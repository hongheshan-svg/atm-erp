"""
进销存报表数据准确性模块
Inventory Data Accuracy and Reconciliation Module

功能：
- 库存账实核对
- 进销存三表平衡校验
- 数据一致性检查
- 异常数据检测
- 差异自动追溯
- 数据修复建议
- 定期对账任务
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import SoftDeleteMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# =============================================================================
# 数据校验规则模型
# =============================================================================


class DataValidationRule(BaseModel):
    """数据校验规则"""

    RULE_TYPE_CHOICES = [
        ('STOCK_BALANCE', '库存余额校验'),
        ('STOCK_NEGATIVE', '负库存检查'),
        ('COST_MISMATCH', '成本不匹配'),
        ('QTY_MISMATCH', '数量不匹配'),
        ('DOC_INCOMPLETE', '单据不完整'),
        ('DUPLICATE_DOC', '重复单据'),
        ('ORPHAN_RECORD', '孤立记录'),
        ('DATE_SEQUENCE', '日期顺序'),
        ('CUSTOM', '自定义规则'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='规则编码')
    name = models.CharField(max_length=200, verbose_name='规则名称')
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES, verbose_name='规则类型')

    description = models.TextField(verbose_name='规则描述')
    sql_expression = models.TextField(blank=True, verbose_name='SQL表达式')
    python_expression = models.TextField(blank=True, verbose_name='Python表达式')

    severity = models.CharField(
        max_length=20,
        choices=[
            ('INFO', '信息'),
            ('WARNING', '警告'),
            ('ERROR', '错误'),
            ('CRITICAL', '严重'),
        ],
        default='WARNING',
        verbose_name='严重级别',
    )

    is_active = models.BooleanField(default=True, verbose_name='启用')
    auto_fix = models.BooleanField(default=False, verbose_name='支持自动修复')

    check_frequency = models.CharField(
        max_length=20,
        choices=[
            ('REALTIME', '实时'),
            ('HOURLY', '每小时'),
            ('DAILY', '每日'),
            ('WEEKLY', '每周'),
            ('MONTHLY', '每月'),
            ('MANUAL', '手动'),
        ],
        default='DAILY',
        verbose_name='检查频率',
    )

    class Meta:
        db_table = 'data_validation_rule'
        verbose_name = '数据校验规则'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.code} - {self.name}'


class DataValidationResult(BaseModel):
    """数据校验结果"""

    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('INVESTIGATING', '调查中'),
        ('FIXED', '已修复'),
        ('IGNORED', '已忽略'),
        ('FALSE_POSITIVE', '误报'),
    ]

    rule = models.ForeignKey(
        DataValidationRule, on_delete=models.CASCADE, related_name='results', verbose_name='校验规则'
    )

    check_date = models.DateTimeField(auto_now_add=True, verbose_name='检查时间')

    # 问题定位
    entity_type = models.CharField(max_length=50, verbose_name='实体类型')
    entity_id = models.IntegerField(null=True, blank=True, verbose_name='实体ID')
    entity_code = models.CharField(max_length=100, blank=True, verbose_name='实体编码')

    warehouse = models.ForeignKey(
        'masterdata.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='仓库'
    )
    item = models.ForeignKey('masterdata.Item', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='物料')

    # 问题详情
    issue_description = models.TextField(verbose_name='问题描述')
    expected_value = models.CharField(max_length=200, blank=True, verbose_name='期望值')
    actual_value = models.CharField(max_length=200, blank=True, verbose_name='实际值')
    variance = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='差异值')

    # 处理状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # 处理信息
    handled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_validations',
        verbose_name='处理人',
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    resolution = models.TextField(blank=True, verbose_name='处理说明')

    # 修复操作
    fix_action = models.TextField(blank=True, verbose_name='修复操作')
    fix_result = models.TextField(blank=True, verbose_name='修复结果')

    class Meta:
        db_table = 'data_validation_result'
        verbose_name = '数据校验结果'
        verbose_name_plural = verbose_name
        ordering = ['-check_date']
        indexes = [
            models.Index(fields=['rule', 'status']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['item', 'warehouse']),
        ]


class ReconciliationSession(BaseModel):
    """对账会话"""

    session_no = models.CharField(max_length=50, unique=True, verbose_name='会话编号')
    session_type = models.CharField(
        max_length=30,
        choices=[
            ('STOCK_PHYSICAL', '库存实物盘点'),
            ('STOCK_COST', '库存成本对账'),
            ('IN_OUT_BALANCE', '进销存平衡'),
            ('SUPPLIER_STATEMENT', '供应商对账'),
            ('CUSTOMER_STATEMENT', '客户对账'),
            ('FULL_AUDIT', '全面审计'),
        ],
        verbose_name='对账类型',
    )

    # 对账范围
    warehouse = models.ForeignKey(
        'masterdata.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='仓库'
    )
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('IN_PROGRESS', '进行中'),
            ('COMPLETED', '已完成'),
            ('CANCELLED', '已取消'),
        ],
        default='DRAFT',
        verbose_name='状态',
    )

    # 统计
    total_items_checked = models.IntegerField(default=0, verbose_name='检查物料数')
    issues_found = models.IntegerField(default=0, verbose_name='发现问题数')
    issues_resolved = models.IntegerField(default=0, verbose_name='已解决数')

    # 结果
    summary = models.TextField(blank=True, verbose_name='对账总结')

    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'reconciliation_session'
        verbose_name = '对账会话'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class ReconciliationItem(BaseModel):
    """对账明细"""

    session = models.ForeignKey(
        ReconciliationSession, on_delete=models.CASCADE, related_name='items', verbose_name='对账会话'
    )

    item = models.ForeignKey('masterdata.Item', on_delete=models.CASCADE, verbose_name='物料')
    warehouse = models.ForeignKey(
        'masterdata.Warehouse', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='仓库'
    )

    # 期初数据
    opening_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='期初数量')
    opening_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期初金额')

    # 入库汇总
    in_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='入库数量')
    in_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='入库金额')

    # 出库汇总
    out_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='出库数量')
    out_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='出库金额')

    # 理论期末
    calculated_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='计算数量')
    calculated_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='计算金额')

    # 实际期末（从库存表读取）
    actual_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='实际数量')
    actual_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际金额')

    # 差异
    qty_variance = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='数量差异')
    cost_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额差异')

    # 状态
    is_matched = models.BooleanField(default=False, verbose_name='是否平衡')
    variance_reason = models.TextField(blank=True, verbose_name='差异原因')

    class Meta:
        db_table = 'reconciliation_item'
        verbose_name = '对账明细'
        verbose_name_plural = verbose_name
        unique_together = ['session', 'item', 'warehouse']


# =============================================================================
# 数据校验服务
# =============================================================================


class InventoryDataValidator:
    """库存数据校验服务"""

    @classmethod
    def check_negative_stock(cls):
        """检查负库存"""
        from .models import Stock

        results = []
        negative_stocks = Stock.objects.filter(qty_on_hand__lt=0, is_deleted=False).select_related('item', 'warehouse')

        for stock in negative_stocks:
            results.append(
                {
                    'rule_type': 'STOCK_NEGATIVE',
                    'entity_type': 'Stock',
                    'entity_id': stock.id,
                    'item_id': stock.item_id,
                    'warehouse_id': stock.warehouse_id,
                    'issue_description': f'物料 [{stock.item.sku}] 在仓库 [{stock.warehouse.name}] 存在负库存',
                    'expected_value': '>=0',
                    'actual_value': str(stock.qty_on_hand),
                    'variance': stock.qty_on_hand,
                    'severity': 'ERROR',
                }
            )

        return results

    @classmethod
    def check_stock_cost_mismatch(cls):
        """检查库存成本不匹配"""
        from .cost_accounting import ItemCostRecord
        from .models import Stock

        results = []

        stocks = Stock.objects.filter(qty_on_hand__gt=0, is_deleted=False).select_related('item', 'warehouse')

        for stock in stocks:
            # 获取最新成本记录
            last_cost = (
                ItemCostRecord.objects.filter(item=stock.item, warehouse=stock.warehouse, is_deleted=False)
                .order_by('-created_at')
                .first()
            )

            if last_cost:
                if abs(stock.qty_on_hand - last_cost.balance_qty) > Decimal('0.0001'):
                    results.append(
                        {
                            'rule_type': 'QTY_MISMATCH',
                            'entity_type': 'Stock',
                            'entity_id': stock.id,
                            'item_id': stock.item_id,
                            'warehouse_id': stock.warehouse_id,
                            'issue_description': f'物料 [{stock.item.sku}] 库存数量与成本账不一致',
                            'expected_value': str(last_cost.balance_qty),
                            'actual_value': str(stock.qty_on_hand),
                            'variance': stock.qty_on_hand - last_cost.balance_qty,
                            'severity': 'WARNING',
                        }
                    )

        return results

    @classmethod
    def check_in_out_balance(cls, warehouse_id=None, start_date=None, end_date=None):
        """检查进销存平衡"""
        from .models import Stock, StockMove

        results = []

        # 获取期间汇总
        filters = {'is_deleted': False}
        if warehouse_id:
            filters['warehouse_id'] = warehouse_id

        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()

        # 获取所有物料-仓库组合
        stocks = Stock.objects.filter(**filters).select_related('item', 'warehouse')

        for stock in stocks:
            # 计算期初结存 = 期初日期之前所有移动的净额（入-出），而非硬编码 0
            # （原先恒为 0，任何有期初结存的物料都会被误判"进销存不平衡" —— 审计 medium）
            opening_in = StockMove.objects.filter(
                item=stock.item,
                warehouse_to=stock.warehouse,
                move_date__lt=start_date,
                status='COMPLETED',
                is_deleted=False,
            ).aggregate(total=Sum('qty'))['total'] or Decimal('0')
            opening_out = StockMove.objects.filter(
                item=stock.item,
                warehouse_from=stock.warehouse,
                move_date__lt=start_date,
                status='COMPLETED',
                is_deleted=False,
            ).aggregate(total=Sum('qty'))['total'] or Decimal('0')
            opening_qty = opening_in - opening_out

            # 计算本期入库
            in_moves = StockMove.objects.filter(
                item=stock.item,
                warehouse_to=stock.warehouse,
                move_date__gte=start_date,
                move_date__lte=end_date,
                status='COMPLETED',
                is_deleted=False,
            ).aggregate(total=Sum('qty'))
            in_qty = in_moves['total'] or Decimal('0')

            # 计算本期出库
            out_moves = StockMove.objects.filter(
                item=stock.item,
                warehouse_from=stock.warehouse,
                move_date__gte=start_date,
                move_date__lte=end_date,
                status='COMPLETED',
                is_deleted=False,
            ).aggregate(total=Sum('qty'))
            out_qty = out_moves['total'] or Decimal('0')

            # 计算理论期末
            calculated_qty = opening_qty + in_qty - out_qty

            # 比较差异
            variance = stock.qty_on_hand - calculated_qty
            if abs(variance) > Decimal('0.0001'):
                results.append(
                    {
                        'rule_type': 'STOCK_BALANCE',
                        'entity_type': 'Stock',
                        'entity_id': stock.id,
                        'item_id': stock.item_id,
                        'warehouse_id': stock.warehouse_id,
                        'issue_description': f'物料 [{stock.item.sku}] 进销存不平衡',
                        'expected_value': str(calculated_qty),
                        'actual_value': str(stock.qty_on_hand),
                        'variance': variance,
                        'severity': 'WARNING' if abs(variance) < 10 else 'ERROR',
                    }
                )

        return results

    @classmethod
    def check_orphan_moves(cls):
        """检查孤立的库存移动记录"""
        from .models import StockMove

        results = []

        # 检查没有关联单据的移动记录
        orphan_moves = StockMove.objects.filter(reference_type='', is_deleted=False).exclude(
            move_type__in=['ADJUSTMENT', 'INITIAL']
        )

        for move in orphan_moves:
            results.append(
                {
                    'rule_type': 'ORPHAN_RECORD',
                    'entity_type': 'StockMove',
                    'entity_id': move.id,
                    'entity_code': move.move_no,
                    'item_id': move.item_id,
                    'warehouse_id': move.warehouse_from_id or move.warehouse_to_id,
                    'issue_description': f'库存移动 [{move.move_no}] 没有关联源单据',
                    'expected_value': '有关联单据',
                    'actual_value': '无关联单据',
                    'severity': 'INFO',
                }
            )

        return results

    @classmethod
    def run_all_checks(cls, warehouse_id=None):
        """运行所有校验"""
        all_results = []

        # 负库存检查
        all_results.extend(cls.check_negative_stock())

        # 成本不匹配检查
        all_results.extend(cls.check_stock_cost_mismatch())

        # 进销存平衡检查
        all_results.extend(cls.check_in_out_balance(warehouse_id=warehouse_id))

        # 孤立记录检查
        all_results.extend(cls.check_orphan_moves())

        # 保存结果
        saved_count = 0
        for result in all_results:
            rule = DataValidationRule.objects.filter(rule_type=result['rule_type'], is_active=True).first()

            if rule:
                DataValidationResult.objects.create(
                    rule=rule,
                    entity_type=result['entity_type'],
                    entity_id=result.get('entity_id'),
                    entity_code=result.get('entity_code', ''),
                    warehouse_id=result.get('warehouse_id'),
                    item_id=result.get('item_id'),
                    issue_description=result['issue_description'],
                    expected_value=result.get('expected_value', ''),
                    actual_value=result.get('actual_value', ''),
                    variance=result.get('variance'),
                )
                saved_count += 1

        return {'total_issues': len(all_results), 'saved_count': saved_count, 'by_type': {}}


class ReconciliationService:
    """对账服务"""

    @classmethod
    def create_session(cls, session_type, warehouse_id, start_date, end_date, user):
        """创建对账会话"""
        from apps.core.models import CodeRule

        session_no = CodeRule.generate_code('RECONCILE')

        session = ReconciliationSession.objects.create(
            session_no=session_no,
            session_type=session_type,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
            created_by=user,
        )

        return session

    @classmethod
    def run_in_out_balance_check(cls, session):
        """运行进销存平衡检查"""
        from .cost_accounting import ItemCostRecord
        from .models import Stock

        session.status = 'IN_PROGRESS'
        session.started_at = timezone.now()
        session.save()

        # 获取需要检查的物料
        filters = {'is_deleted': False}
        if session.warehouse:
            filters['warehouse'] = session.warehouse

        stocks = Stock.objects.filter(**filters).select_related('item', 'warehouse')

        items_checked = 0
        issues_found = 0

        for stock in stocks:
            # 计算期初
            # 从前一期的期末获取，或者从最早的成本记录反推
            prev_period = session.start_date - timedelta(days=1)

            opening_record = (
                ItemCostRecord.objects.filter(
                    item=stock.item, warehouse=stock.warehouse, transaction_date__lte=prev_period, is_deleted=False
                )
                .order_by('-transaction_date', '-created_at')
                .first()
            )

            opening_qty = opening_record.balance_qty if opening_record else Decimal('0')
            opening_cost = opening_record.balance_cost if opening_record else Decimal('0')

            # 计算期间入库
            in_records = ItemCostRecord.objects.filter(
                item=stock.item,
                warehouse=stock.warehouse,
                transaction_date__gte=session.start_date,
                transaction_date__lte=session.end_date,
                quantity__gt=0,
                is_deleted=False,
            ).aggregate(qty=Coalesce(Sum('quantity'), Decimal('0')), cost=Coalesce(Sum('total_cost'), Decimal('0')))
            in_qty = in_records['qty']
            in_cost = in_records['cost']

            # 计算期间出库
            out_records = ItemCostRecord.objects.filter(
                item=stock.item,
                warehouse=stock.warehouse,
                transaction_date__gte=session.start_date,
                transaction_date__lte=session.end_date,
                quantity__lt=0,
                is_deleted=False,
            ).aggregate(qty=Coalesce(Sum('quantity'), Decimal('0')), cost=Coalesce(Sum('total_cost'), Decimal('0')))
            out_qty = abs(out_records['qty'])
            out_cost = abs(out_records['cost'])

            # 计算理论期末
            calculated_qty = opening_qty + in_qty - out_qty
            calculated_cost = opening_cost + in_cost - out_cost

            # 获取实际库存
            actual_qty = stock.qty_on_hand
            actual_cost = (
                stock.qty_on_hand * stock.weighted_avg_cost if hasattr(stock, 'weighted_avg_cost') else Decimal('0')
            )

            # 计算差异
            qty_variance = actual_qty - calculated_qty
            cost_variance = actual_cost - calculated_cost

            is_matched = abs(qty_variance) < Decimal('0.0001') and abs(cost_variance) < Decimal('0.01')

            # 保存对账明细
            ReconciliationItem.objects.update_or_create(
                session=session,
                item=stock.item,
                warehouse=stock.warehouse,
                defaults={
                    'opening_qty': opening_qty,
                    'opening_cost': opening_cost,
                    'in_qty': in_qty,
                    'in_cost': in_cost,
                    'out_qty': out_qty,
                    'out_cost': out_cost,
                    'calculated_qty': calculated_qty,
                    'calculated_cost': calculated_cost,
                    'actual_qty': actual_qty,
                    'actual_cost': actual_cost,
                    'qty_variance': qty_variance,
                    'cost_variance': cost_variance,
                    'is_matched': is_matched,
                },
            )

            items_checked += 1
            if not is_matched:
                issues_found += 1

        # 更新会话统计
        session.total_items_checked = items_checked
        session.issues_found = issues_found
        session.status = 'COMPLETED'
        session.completed_at = timezone.now()
        session.save()

        return session


# =============================================================================
# 序列化器
# =============================================================================


class DataValidationRuleSerializer(serializers.ModelSerializer):
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = DataValidationRule
        fields = '__all__'


class DataValidationResultSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_type = serializers.CharField(source='rule.rule_type', read_only=True)
    severity = serializers.CharField(source='rule.severity', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    item_code = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = DataValidationResult
        fields = '__all__'


class ReconciliationSessionSerializer(serializers.ModelSerializer):
    session_type_display = serializers.CharField(source='get_session_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = ReconciliationSession
        fields = '__all__'


class ReconciliationItemSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = ReconciliationItem
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================


class DataValidationRuleViewSet(PermissionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """数据校验规则"""
    permission_module = 'inventory'
    permission_resource = 'data_validation_rule'

    queryset = DataValidationRule.objects.filter(is_deleted=False)
    serializer_class = DataValidationRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['rule_type', 'severity', 'is_active', 'check_frequency']

    @action(detail=False, methods=['post'])
    def init_default_rules(self, request):
        """初始化默认规则"""
        default_rules = [
            {
                'code': 'STOCK_NEGATIVE_CHECK',
                'name': '负库存检查',
                'rule_type': 'STOCK_NEGATIVE',
                'description': '检查系统中是否存在负库存情况',
                'severity': 'ERROR',
                'check_frequency': 'DAILY',
            },
            {
                'code': 'STOCK_COST_MATCH',
                'name': '库存成本一致性检查',
                'rule_type': 'COST_MISMATCH',
                'description': '检查库存账与成本账数量是否一致',
                'severity': 'WARNING',
                'check_frequency': 'DAILY',
            },
            {
                'code': 'IN_OUT_BALANCE',
                'name': '进销存平衡检查',
                'rule_type': 'STOCK_BALANCE',
                'description': '检查期初+入库-出库=期末是否平衡',
                'severity': 'WARNING',
                'check_frequency': 'DAILY',
            },
            {
                'code': 'ORPHAN_MOVE_CHECK',
                'name': '孤立移动记录检查',
                'rule_type': 'ORPHAN_RECORD',
                'description': '检查没有关联源单据的库存移动记录',
                'severity': 'INFO',
                'check_frequency': 'WEEKLY',
            },
        ]

        created_count = 0
        for rule_data in default_rules:
            rule, created = DataValidationRule.objects.get_or_create(code=rule_data['code'], defaults=rule_data)
            if created:
                created_count += 1

        return Response({'success': True, 'created_count': created_count, 'total_rules': len(default_rules)})


class DataValidationResultViewSet(PermissionMixin, viewsets.ModelViewSet):
    """数据校验结果"""
    permission_module = 'inventory'
    permission_resource = 'data_validation_result'

    queryset = DataValidationResult.objects.filter(is_deleted=False)
    serializer_class = DataValidationResultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['rule', 'status', 'item', 'warehouse']
    ordering = ['-check_date']

    @action(detail=True, methods=['post'])
    def handle(self, request, pk=None):
        """处理校验结果"""
        result = self.get_object()
        result.status = request.data.get('status', 'FIXED')
        result.resolution = request.data.get('resolution', '')
        result.handled_by = request.user
        result.handled_at = timezone.now()
        result.save()
        return Response(self.get_serializer(result).data)

    @action(detail=False, methods=['post'])
    def run_checks(self, request):
        """运行校验"""
        warehouse_id = request.data.get('warehouse_id')
        result = InventoryDataValidator.run_all_checks(warehouse_id=warehouse_id)
        return Response(result)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """校验结果汇总"""
        results = self.get_queryset()

        # 按状态统计
        by_status = results.values('status').annotate(count=Count('id'))

        # 按规则类型统计
        by_type = results.values('rule__rule_type').annotate(count=Count('id'))

        # 按严重程度统计
        by_severity = results.values('rule__severity').annotate(count=Count('id'))

        # 最近7天趋势
        week_ago = timezone.now() - timedelta(days=7)
        trend = (
            results.filter(check_date__gte=week_ago)
            .annotate(day=TruncDate('check_date'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        return Response(
            {
                'total': results.count(),
                'pending': results.filter(status='PENDING').count(),
                'by_status': list(by_status),
                'by_type': list(by_type),
                'by_severity': list(by_severity),
                'trend': list(trend),
            }
        )


class ReconciliationSessionViewSet(PermissionMixin, viewsets.ModelViewSet):
    """对账会话"""
    permission_module = 'inventory'
    permission_resource = 'reconciliation_session'

    queryset = ReconciliationSession.objects.filter(is_deleted=False)
    serializer_class = ReconciliationSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['session_type', 'status', 'warehouse']

    @action(detail=False, methods=['post'])
    def create_and_run(self, request):
        """创建并运行对账"""
        session_type = request.data.get('session_type', 'IN_OUT_BALANCE')
        warehouse_id = request.data.get('warehouse_id')
        start_date = request.data.get('start_date', date.today().replace(day=1))
        end_date = request.data.get('end_date', date.today())

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # 创建会话
        session = ReconciliationService.create_session(
            session_type=session_type,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date,
            user=request.user,
        )

        # 运行对账
        if session_type == 'IN_OUT_BALANCE':
            session = ReconciliationService.run_in_out_balance_check(session)

        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """获取对账明细"""
        session = self.get_object()
        items = ReconciliationItem.objects.filter(session=session)

        # 筛选
        show_variance_only = request.query_params.get('variance_only', 'false').lower() == 'true'
        if show_variance_only:
            items = items.filter(is_matched=False)

        return Response(ReconciliationItemSerializer(items, many=True).data)


# =============================================================================
# 报表API
# =============================================================================


class InventoryAccuracyReportView(APIView):
    """库存准确性报表"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import Stock

        warehouse_id = request.query_params.get('warehouse')

        # 获取最近的对账会话
        filters = {'status': 'COMPLETED'}
        if warehouse_id:
            filters['warehouse_id'] = warehouse_id

        sessions = ReconciliationSession.objects.filter(**filters).order_by('-completed_at')[:10]

        # 计算准确率趋势
        accuracy_trend = []
        for session in sessions:
            items = ReconciliationItem.objects.filter(session=session)
            total = items.count()
            matched = items.filter(is_matched=True).count()
            accuracy = round(matched / total * 100, 2) if total > 0 else 100

            accuracy_trend.append(
                {
                    'session_no': session.session_no,
                    'date': session.completed_at.date().isoformat() if session.completed_at else None,
                    'total_items': total,
                    'matched_items': matched,
                    'accuracy': accuracy,
                }
            )

        # 当前待处理问题
        pending_issues = DataValidationResult.objects.filter(status='PENDING').count()

        # 按严重程度分布
        issue_by_severity = (
            DataValidationResult.objects.filter(status='PENDING').values('rule__severity').annotate(count=Count('id'))
        )

        # 当前库存状态
        total_items = Stock.objects.filter(is_deleted=False, qty_on_hand__gt=0).count()
        negative_items = Stock.objects.filter(is_deleted=False, qty_on_hand__lt=0).count()

        return Response(
            {
                'accuracy_trend': accuracy_trend,
                'current_status': {
                    'pending_issues': pending_issues,
                    'total_items_with_stock': total_items,
                    'negative_stock_items': negative_items,
                },
                'issue_by_severity': list(issue_by_severity),
            }
        )


class InOutBalanceReportView(APIView):
    """进销存平衡报表"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .cost_accounting import PeriodCostSummary

        year = int(request.query_params.get('year', date.today().year))
        month = int(request.query_params.get('month', date.today().month))
        warehouse_id = request.query_params.get('warehouse')

        # 获取期间汇总
        filters = {'period_year': year, 'period_month': month, 'is_deleted': False}
        if warehouse_id:
            filters['warehouse_id'] = warehouse_id

        summaries = PeriodCostSummary.objects.filter(**filters).select_related('item', 'warehouse')

        # 汇总统计
        totals = summaries.aggregate(
            opening_qty=Coalesce(Sum('opening_qty'), Decimal('0')),
            opening_cost=Coalesce(Sum('opening_cost'), Decimal('0')),
            in_qty=Coalesce(Sum('in_qty'), Decimal('0')),
            in_cost=Coalesce(Sum('in_cost'), Decimal('0')),
            out_qty=Coalesce(Sum('out_qty'), Decimal('0')),
            out_cost=Coalesce(Sum('out_cost'), Decimal('0')),
            closing_qty=Coalesce(Sum('closing_qty'), Decimal('0')),
            closing_cost=Coalesce(Sum('closing_cost'), Decimal('0')),
        )

        # 验证平衡
        calculated_closing_qty = totals['opening_qty'] + totals['in_qty'] - totals['out_qty']
        calculated_closing_cost = totals['opening_cost'] + totals['in_cost'] - totals['out_cost']

        qty_balanced = abs(calculated_closing_qty - totals['closing_qty']) < Decimal('0.01')
        cost_balanced = abs(calculated_closing_cost - totals['closing_cost']) < Decimal('0.01')

        # 按仓库分组
        by_warehouse = summaries.values('warehouse__name').annotate(
            opening_cost=Sum('opening_cost'),
            in_cost=Sum('in_cost'),
            out_cost=Sum('out_cost'),
            closing_cost=Sum('closing_cost'),
        )

        # 按物料类别分组
        by_category = summaries.values('item__category__name').annotate(
            closing_qty=Sum('closing_qty'),
            closing_cost=Sum('closing_cost'),
        )

        return Response(
            {
                'period': f'{year}年{month}月',
                'totals': {
                    'opening_qty': float(totals['opening_qty']),
                    'opening_cost': float(totals['opening_cost']),
                    'in_qty': float(totals['in_qty']),
                    'in_cost': float(totals['in_cost']),
                    'out_qty': float(totals['out_qty']),
                    'out_cost': float(totals['out_cost']),
                    'closing_qty': float(totals['closing_qty']),
                    'closing_cost': float(totals['closing_cost']),
                },
                'balance_check': {
                    'calculated_closing_qty': float(calculated_closing_qty),
                    'calculated_closing_cost': float(calculated_closing_cost),
                    'qty_balanced': qty_balanced,
                    'cost_balanced': cost_balanced,
                },
                'by_warehouse': list(by_warehouse),
                'by_category': list(by_category),
                'item_count': summaries.count(),
            }
        )
