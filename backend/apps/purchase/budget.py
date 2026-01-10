"""
采购预算管理
Purchase Budget Management
支持年度预算、项目预算、部门预算的设置和执行跟踪
"""
from decimal import Decimal
from django.db import models
from django.db.models import Sum, F
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class PurchaseBudget(BaseModel):
    """
    采购预算
    """
    BUDGET_TYPES = [
        ('ANNUAL', '年度预算'),
        ('PROJECT', '项目预算'),
        ('DEPARTMENT', '部门预算'),
        ('CATEGORY', '品类预算'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('ACTIVE', '执行中'),
        ('CLOSED', '已关闭'),
        ('EXCEEDED', '已超支'),
    ]
    
    budget_no = models.CharField(max_length=50, unique=True, verbose_name='预算编号')
    name = models.CharField(max_length=200, verbose_name='预算名称')
    budget_type = models.CharField(
        max_length=20,
        choices=BUDGET_TYPES,
        default='ANNUAL',
        verbose_name='预算类型'
    )
    
    # 预算期间
    year = models.IntegerField(verbose_name='预算年度')
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    
    # 预算金额
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='预算总额'
    )
    used_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='已使用金额'
    )
    reserved_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='预留金额'
    )
    
    # 预警阈值
    warning_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=80,
        verbose_name='预警阈值(%)'
    )
    
    # 关联
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_budgets',
        verbose_name='部门'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_budgets',
        verbose_name='项目'
    )
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 审批
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_budgets',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    description = models.TextField(blank=True, verbose_name='备注说明')
    
    class Meta:
        db_table = 'purchase_budget'
        verbose_name = '采购预算'
        verbose_name_plural = verbose_name
        ordering = ['-year', '-created_at']
    
    def __str__(self):
        return f'{self.budget_no} - {self.name}'
    
    @property
    def available_amount(self):
        """可用金额"""
        return self.total_amount - self.used_amount - self.reserved_amount
    
    @property
    def usage_rate(self):
        """使用率"""
        if self.total_amount == 0:
            return 0
        return round((self.used_amount / self.total_amount) * 100, 2)
    
    @property
    def is_warning(self):
        """是否达到预警"""
        return self.usage_rate >= float(self.warning_threshold)
    
    @property
    def is_exceeded(self):
        """是否超支"""
        return self.used_amount > self.total_amount


class BudgetLine(BaseModel):
    """
    预算明细行
    """
    budget = models.ForeignKey(
        PurchaseBudget,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='预算'
    )
    
    # 预算项
    category = models.CharField(max_length=100, verbose_name='物料类别')
    description = models.CharField(max_length=500, blank=True, verbose_name='说明')
    
    # 金额
    planned_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='计划金额'
    )
    used_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='已使用金额'
    )
    
    # 月度分解（可选）
    monthly_plan = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='月度计划',
        help_text='格式：{"1": 10000, "2": 15000, ...}'
    )
    
    class Meta:
        db_table = 'purchase_budget_line'
        verbose_name = '预算明细'
        verbose_name_plural = verbose_name
        ordering = ['category']
    
    def __str__(self):
        return f'{self.budget.budget_no} - {self.category}'
    
    @property
    def available_amount(self):
        return self.planned_amount - self.used_amount


class BudgetUsageRecord(BaseModel):
    """
    预算使用记录
    """
    USAGE_TYPES = [
        ('PURCHASE_ORDER', '采购订单'),
        ('PURCHASE_REQUEST', '采购申请'),
        ('EXPENSE', '费用报销'),
        ('ADJUSTMENT', '预算调整'),
        ('RELEASE', '释放预留'),
    ]
    
    budget = models.ForeignKey(
        PurchaseBudget,
        on_delete=models.CASCADE,
        related_name='usage_records',
        verbose_name='预算'
    )
    budget_line = models.ForeignKey(
        BudgetLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_records',
        verbose_name='预算明细'
    )
    
    usage_type = models.CharField(
        max_length=30,
        choices=USAGE_TYPES,
        verbose_name='使用类型'
    )
    reference_no = models.CharField(max_length=50, verbose_name='参考单号')
    reference_id = models.IntegerField(null=True, blank=True, verbose_name='参考ID')
    
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='金额'
    )
    is_reserved = models.BooleanField(default=False, verbose_name='是否预留')
    
    description = models.CharField(max_length=500, blank=True, verbose_name='说明')
    
    class Meta:
        db_table = 'purchase_budget_usage'
        verbose_name = '预算使用记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.budget.budget_no} - {self.reference_no}'


# =====================
# Budget Service
# =====================

class BudgetService:
    """预算服务"""
    
    @staticmethod
    def check_budget(
        project_id: int = None,
        department_id: int = None,
        amount: Decimal = 0,
        category: str = None
    ) -> dict:
        """
        检查预算
        返回：{available: bool, message: str, budget: Budget, available_amount: Decimal}
        """
        from datetime import date
        
        today = date.today()
        
        # 查找适用的预算
        filters = {
            'status__in': ['APPROVED', 'ACTIVE'],
            'start_date__lte': today,
            'end_date__gte': today,
            'is_deleted': False,
        }
        
        if project_id:
            filters['project_id'] = project_id
        if department_id:
            filters['department_id'] = department_id
        
        budget = PurchaseBudget.objects.filter(**filters).first()
        
        if not budget:
            return {
                'available': True,
                'message': '无适用预算，跳过预算检查',
                'budget': None,
                'available_amount': None
            }
        
        available = budget.available_amount
        
        if amount > available:
            return {
                'available': False,
                'message': f'预算不足，可用金额：{available}，申请金额：{amount}',
                'budget': budget,
                'available_amount': available
            }
        
        if budget.is_warning:
            return {
                'available': True,
                'message': f'预算已达预警阈值（{budget.usage_rate}%），请谨慎使用',
                'budget': budget,
                'available_amount': available,
                'warning': True
            }
        
        return {
            'available': True,
            'message': '预算充足',
            'budget': budget,
            'available_amount': available
        }
    
    @staticmethod
    def use_budget(
        budget_id: int,
        amount: Decimal,
        usage_type: str,
        reference_no: str,
        reference_id: int = None,
        budget_line_id: int = None,
        description: str = '',
        user=None
    ) -> BudgetUsageRecord:
        """使用预算"""
        budget = PurchaseBudget.objects.get(id=budget_id)
        
        record = BudgetUsageRecord.objects.create(
            budget=budget,
            budget_line_id=budget_line_id,
            usage_type=usage_type,
            reference_no=reference_no,
            reference_id=reference_id,
            amount=amount,
            description=description,
            created_by=user
        )
        
        # 更新预算已使用金额
        budget.used_amount = F('used_amount') + amount
        budget.save()
        budget.refresh_from_db()
        
        # 检查是否超支
        if budget.is_exceeded:
            budget.status = 'EXCEEDED'
            budget.save()
        
        # 更新明细行
        if budget_line_id:
            BudgetLine.objects.filter(id=budget_line_id).update(
                used_amount=F('used_amount') + amount
            )
        
        return record
    
    @staticmethod
    def reserve_budget(
        budget_id: int,
        amount: Decimal,
        reference_no: str,
        reference_id: int = None,
        description: str = '',
        user=None
    ) -> BudgetUsageRecord:
        """预留预算"""
        budget = PurchaseBudget.objects.get(id=budget_id)
        
        record = BudgetUsageRecord.objects.create(
            budget=budget,
            usage_type='PURCHASE_REQUEST',
            reference_no=reference_no,
            reference_id=reference_id,
            amount=amount,
            is_reserved=True,
            description=description,
            created_by=user
        )
        
        budget.reserved_amount = F('reserved_amount') + amount
        budget.save()
        
        return record
    
    @staticmethod
    def release_reserve(
        budget_id: int,
        amount: Decimal,
        reference_no: str,
        user=None
    ):
        """释放预留"""
        budget = PurchaseBudget.objects.get(id=budget_id)
        
        BudgetUsageRecord.objects.create(
            budget=budget,
            usage_type='RELEASE',
            reference_no=reference_no,
            amount=-amount,
            is_reserved=True,
            description='释放预留',
            created_by=user
        )
        
        budget.reserved_amount = F('reserved_amount') - amount
        budget.save()


# =====================
# Serializers
# =====================

class BudgetLineSerializer(serializers.ModelSerializer):
    available_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    usage_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = BudgetLine
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'used_amount']
    
    def get_usage_rate(self, obj):
        if obj.planned_amount == 0:
            return 0
        return round((obj.used_amount / obj.planned_amount) * 100, 2)


class PurchaseBudgetSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True, read_only=True)
    budget_type_display = serializers.CharField(source='get_budget_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    available_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    usage_rate = serializers.FloatField(read_only=True)
    is_warning = serializers.BooleanField(read_only=True)
    is_exceeded = serializers.BooleanField(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    
    class Meta:
        model = PurchaseBudget
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'used_amount', 'reserved_amount', 'approver', 'approved_at']


class PurchaseBudgetListSerializer(serializers.ModelSerializer):
    budget_type_display = serializers.CharField(source='get_budget_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    available_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    usage_rate = serializers.FloatField(read_only=True)
    is_warning = serializers.BooleanField(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = PurchaseBudget
        fields = [
            'id', 'budget_no', 'name', 'budget_type', 'budget_type_display',
            'year', 'start_date', 'end_date', 'total_amount', 'used_amount',
            'available_amount', 'usage_rate', 'is_warning', 'status', 'status_display',
            'department_name', 'project_name', 'created_at'
        ]


class BudgetUsageRecordSerializer(serializers.ModelSerializer):
    usage_type_display = serializers.CharField(source='get_usage_type_display', read_only=True)
    budget_no = serializers.CharField(source='budget.budget_no', read_only=True)
    
    class Meta:
        model = BudgetUsageRecord
        fields = '__all__'


# =====================
# ViewSets
# =====================

class PurchaseBudgetViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """采购预算管理"""
    queryset = PurchaseBudget.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['budget_type', 'status', 'year', 'department', 'project']
    search_fields = ['budget_no', 'name', 'description']
    ordering_fields = ['year', 'created_at', 'total_amount']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseBudgetListSerializer
        return PurchaseBudgetSerializer
    
    @action(detail=False, methods=['get'])
    def budget_types(self, request):
        """获取预算类型"""
        return Response([
            {'value': t[0], 'label': t[1]}
            for t in PurchaseBudget.BUDGET_TYPES
        ])
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批预算"""
        from django.utils import timezone
        
        budget = self.get_object()
        if budget.status != 'PENDING':
            return Response({'error': '只有待审批的预算才能审批'}, status=400)
        
        budget.status = 'APPROVED'
        budget.approver = request.user
        budget.approved_at = timezone.now()
        budget.save()
        
        return Response(self.get_serializer(budget).data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活预算"""
        budget = self.get_object()
        if budget.status != 'APPROVED':
            return Response({'error': '只有已审批的预算才能激活'}, status=400)
        
        budget.status = 'ACTIVE'
        budget.save()
        return Response(self.get_serializer(budget).data)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭预算"""
        budget = self.get_object()
        budget.status = 'CLOSED'
        budget.save()
        return Response(self.get_serializer(budget).data)
    
    @action(detail=False, methods=['post'])
    def check(self, request):
        """检查预算"""
        project_id = request.data.get('project_id')
        department_id = request.data.get('department_id')
        amount = Decimal(str(request.data.get('amount', 0)))
        category = request.data.get('category')
        
        result = BudgetService.check_budget(
            project_id=project_id,
            department_id=department_id,
            amount=amount,
            category=category
        )
        
        if result['budget']:
            result['budget'] = PurchaseBudgetListSerializer(result['budget']).data
        
        return Response(result)
    
    @action(detail=True, methods=['get'])
    def usage_records(self, request, pk=None):
        """获取预算使用记录"""
        budget = self.get_object()
        records = budget.usage_records.all()
        return Response(BudgetUsageRecordSerializer(records, many=True).data)
    
    @action(detail=True, methods=['post'])
    def add_line(self, request, pk=None):
        """添加预算明细"""
        budget = self.get_object()
        serializer = BudgetLineSerializer(data={**request.data, 'budget': budget.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        
        # 更新预算总额
        total = budget.lines.aggregate(total=Sum('planned_amount'))['total'] or 0
        budget.total_amount = total
        budget.save()
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """预算统计"""
        from datetime import date
        
        year = request.query_params.get('year', date.today().year)
        qs = self.get_queryset().filter(year=year)
        
        total_budget = qs.aggregate(total=Sum('total_amount'))['total'] or 0
        total_used = qs.aggregate(total=Sum('used_amount'))['total'] or 0
        total_reserved = qs.aggregate(total=Sum('reserved_amount'))['total'] or 0
        
        # 按类型统计
        by_type = qs.values('budget_type').annotate(
            count=models.Count('id'),
            total=Sum('total_amount'),
            used=Sum('used_amount')
        )
        
        # 按状态统计
        by_status = qs.values('status').annotate(count=models.Count('id'))
        
        # 超支/预警数量
        warning_count = sum(1 for b in qs if b.is_warning and not b.is_exceeded)
        exceeded_count = qs.filter(status='EXCEEDED').count()
        
        return Response({
            'year': year,
            'total_budget': total_budget,
            'total_used': total_used,
            'total_reserved': total_reserved,
            'total_available': total_budget - total_used - total_reserved,
            'usage_rate': round((total_used / total_budget * 100), 2) if total_budget > 0 else 0,
            'warning_count': warning_count,
            'exceeded_count': exceeded_count,
            'by_type': list(by_type),
            'by_status': list(by_status)
        })


class BudgetLineViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """预算明细管理"""
    queryset = BudgetLine.objects.filter(is_deleted=False)
    serializer_class = BudgetLineSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['budget', 'category']
    search_fields = ['category', 'description']
    
    def perform_destroy(self, instance):
        # 删除明细时更新预算总额
        budget = instance.budget
        super().perform_destroy(instance)
        total = budget.lines.filter(is_deleted=False).aggregate(total=Sum('planned_amount'))['total'] or 0
        budget.total_amount = total
        budget.save()
