"""
非标自动化行业成本核算增强模块
Advanced Cost Tracking for Custom Automation Industry

功能增强：
- 多维度成本归集（按项目/阶段/部门/成本中心）
- 实际成本与标准成本对比分析
- 工时成本核算（区分设计/装配/调试/现场）
- 物料成本追溯（批次级别）
- 外协成本跟踪
- 制造费用分摊
- 成本差异分析
- 完工百分比法核算
- 项目毛利实时计算
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from django.db import models, transaction
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, OuterRef, Subquery
from django.db.models.functions import TruncMonth, TruncWeek, Coalesce
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


# =============================================================================
# 标准成本模型
# =============================================================================

class StandardCostCategory(BaseModel):
    """标准成本分类"""
    code = models.CharField(max_length=50, unique=True, verbose_name='分类编码')
    name = models.CharField(max_length=100, verbose_name='分类名称')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='上级分类'
    )
    cost_element = models.CharField(
        max_length=20,
        choices=[
            ('DIRECT_MATERIAL', '直接材料'),
            ('DIRECT_LABOR', '直接人工'),
            ('MANUFACTURING_OH', '制造费用'),
            ('OUTSOURCE', '外协费用'),
            ('TRAVEL', '差旅费用'),
            ('EQUIPMENT', '设备费用'),
            ('OTHER_DIRECT', '其他直接费用'),
            ('INDIRECT', '间接费用'),
        ],
        verbose_name='成本要素'
    )
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    class Meta:
        db_table = 'standard_cost_category'
        verbose_name = '标准成本分类'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.code} - {self.name}'


class LaborRateStandard(BaseModel):
    """人工费率标准"""
    work_type = models.CharField(
        max_length=30,
        choices=[
            ('DESIGN_MECHANICAL', '机械设计'),
            ('DESIGN_ELECTRICAL', '电气设计'),
            ('DESIGN_SOFTWARE', '软件开发'),
            ('ASSEMBLY_MECHANICAL', '机械装配'),
            ('ASSEMBLY_ELECTRICAL', '电气安装'),
            ('DEBUGGING', '调试'),
            ('FIELD_INSTALL', '现场安装'),
            ('FIELD_DEBUG', '现场调试'),
            ('FIELD_TRAIN', '现场培训'),
            ('QUALITY_CHECK', '质量检验'),
            ('PROJECT_MGMT', '项目管理'),
            ('TECH_SUPPORT', '技术支持'),
        ],
        unique=True,
        verbose_name='工作类型'
    )
    
    standard_rate = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='标准费率(元/小时)')
    overtime_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='加班费率(元/小时)')
    weekend_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='周末费率(元/小时)')
    holiday_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='节假日费率(元/小时)')
    
    effective_from = models.DateField(verbose_name='生效日期')
    effective_to = models.DateField(null=True, blank=True, verbose_name='失效日期')
    
    description = models.TextField(blank=True, verbose_name='说明')
    
    class Meta:
        db_table = 'labor_rate_standard'
        verbose_name = '人工费率标准'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.get_work_type_display()} - ¥{self.standard_rate}/小时'


class ManufacturingOverheadRate(BaseModel):
    """制造费用分摊率"""
    name = models.CharField(max_length=100, verbose_name='名称')
    allocation_base = models.CharField(
        max_length=20,
        choices=[
            ('LABOR_HOURS', '人工工时'),
            ('MACHINE_HOURS', '机器工时'),
            ('DIRECT_MATERIAL', '直接材料'),
            ('DIRECT_LABOR', '直接人工'),
            ('PRODUCTION_VALUE', '产值'),
        ],
        verbose_name='分摊基础'
    )
    
    rate = models.DecimalField(max_digits=8, decimal_places=4, verbose_name='分摊率')
    fixed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='固定金额')
    
    effective_from = models.DateField(verbose_name='生效日期')
    effective_to = models.DateField(null=True, blank=True, verbose_name='失效日期')
    
    class Meta:
        db_table = 'manufacturing_overhead_rate'
        verbose_name = '制造费用分摊率'
        verbose_name_plural = verbose_name


# =============================================================================
# 项目成本明细
# =============================================================================

class ProjectCostDetail(BaseModel):
    """项目成本明细（增强版）"""
    COST_SOURCE_CHOICES = [
        ('PURCHASE_ORDER', '采购订单'),
        ('GOODS_RECEIPT', '到货入库'),
        ('MATERIAL_ISSUE', '生产领料'),
        ('TIMESHEET', '工时记录'),
        ('OUTSOURCE_ORDER', '外协订单'),
        ('EXPENSE_CLAIM', '费用报销'),
        ('OVERHEAD_ALLOC', '费用分摊'),
        ('MANUAL_ENTRY', '手工录入'),
        ('ADJUSTMENT', '成本调整'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='cost_details',
        verbose_name='项目'
    )
    
    # 成本分类
    cost_category = models.ForeignKey(
        StandardCostCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='成本分类'
    )
    cost_element = models.CharField(
        max_length=20,
        choices=StandardCostCategory._meta.get_field('cost_element').choices,
        verbose_name='成本要素'
    )
    
    # 来源追溯
    source_type = models.CharField(max_length=30, choices=COST_SOURCE_CHOICES, verbose_name='成本来源')
    source_doc_type = models.CharField(max_length=50, blank=True, verbose_name='单据类型')
    source_doc_no = models.CharField(max_length=50, blank=True, verbose_name='单据编号')
    source_doc_id = models.IntegerField(null=True, blank=True, verbose_name='单据ID')
    source_line_id = models.IntegerField(null=True, blank=True, verbose_name='明细行ID')
    
    # 成本日期和阶段
    cost_date = models.DateField(verbose_name='成本日期')
    project_phase = models.CharField(
        max_length=30,
        choices=[
            ('REQUIREMENT', '需求分析'),
            ('DESIGN', '设计阶段'),
            ('PROCUREMENT', '采购阶段'),
            ('PRODUCTION', '生产制造'),
            ('ASSEMBLY', '装配阶段'),
            ('TESTING', '测试调试'),
            ('SHIPPING', '发货运输'),
            ('INSTALLATION', '现场安装'),
            ('COMMISSIONING', '现场调试'),
            ('ACCEPTANCE', '验收阶段'),
            ('WARRANTY', '质保期'),
            ('AFTER_SALE', '售后服务'),
        ],
        verbose_name='项目阶段'
    )
    
    # 成本金额
    description = models.CharField(max_length=500, verbose_name='描述')
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1, verbose_name='数量')
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='单位成本')
    actual_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='实际金额')
    standard_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='标准金额')
    
    # 成本差异
    variance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='差异金额')
    variance_type = models.CharField(
        max_length=20,
        choices=[
            ('PRICE', '价格差异'),
            ('QUANTITY', '数量差异'),
            ('EFFICIENCY', '效率差异'),
            ('MIXED', '混合差异'),
        ],
        blank=True,
        verbose_name='差异类型'
    )
    variance_reason = models.TextField(blank=True, verbose_name='差异原因')
    
    # 责任归属
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='责任部门'
    )
    responsible_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cost_responsibilities',
        verbose_name='责任人'
    )
    
    # 物料追溯
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='物料'
    )
    batch_no = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    
    # 审核状态
    is_verified = models.BooleanField(default=False, verbose_name='已审核')
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_cost_details',
        verbose_name='审核人'
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'project_cost_detail'
        verbose_name = '项目成本明细'
        verbose_name_plural = verbose_name
        ordering = ['-cost_date', '-created_at']
        indexes = [
            models.Index(fields=['project', 'cost_element']),
            models.Index(fields=['project', 'project_phase']),
            models.Index(fields=['project', 'cost_date']),
            models.Index(fields=['source_doc_no']),
        ]
    
    def __str__(self):
        return f'{self.project.project_no} - {self.description}'
    
    def save(self, *args, **kwargs):
        # 自动计算差异
        if self.standard_amount:
            self.variance_amount = self.actual_amount - self.standard_amount
        super().save(*args, **kwargs)


class ProjectCostSummary(BaseModel):
    """项目成本汇总"""
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='cost_summary',
        verbose_name='项目'
    )
    
    # 合同信息
    contract_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='合同金额')
    estimated_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='预估成本')
    estimated_profit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='预估毛利')
    estimated_margin = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='预估毛利率')
    
    # 实际成本汇总
    direct_material_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='直接材料')
    direct_labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='直接人工')
    manufacturing_overhead = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='制造费用')
    outsource_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='外协成本')
    travel_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='差旅费用')
    equipment_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='设备费用')
    other_direct_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='其他直接')
    indirect_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='间接费用')
    
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='总成本')
    
    # 毛利计算
    actual_profit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际毛利')
    actual_margin = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='实际毛利率')
    
    # 工时汇总
    design_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='设计工时')
    production_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='生产工时')
    field_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='现场工时')
    total_hours = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总工时')
    
    # 完工百分比
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='完工百分比')
    
    # CPI/SPI指标
    cpi = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='成本绩效指数')
    spi = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='进度绩效指数')
    eac = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='完工估算')
    etc = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='尚需估算')
    
    last_calculated_at = models.DateTimeField(null=True, blank=True, verbose_name='最后计算时间')
    
    class Meta:
        db_table = 'project_cost_summary'
        verbose_name = '项目成本汇总'
        verbose_name_plural = verbose_name
    
    def recalculate(self):
        """重新计算成本汇总"""
        details = ProjectCostDetail.objects.filter(
            project=self.project, is_deleted=False
        )
        
        # 按成本要素汇总
        element_totals = details.values('cost_element').annotate(
            total=Sum('actual_amount')
        )
        element_map = {e['cost_element']: e['total'] for e in element_totals}
        
        self.direct_material_cost = element_map.get('DIRECT_MATERIAL', 0) or 0
        self.direct_labor_cost = element_map.get('DIRECT_LABOR', 0) or 0
        self.manufacturing_overhead = element_map.get('MANUFACTURING_OH', 0) or 0
        self.outsource_cost = element_map.get('OUTSOURCE', 0) or 0
        self.travel_cost = element_map.get('TRAVEL', 0) or 0
        self.equipment_cost = element_map.get('EQUIPMENT', 0) or 0
        self.other_direct_cost = element_map.get('OTHER_DIRECT', 0) or 0
        self.indirect_cost = element_map.get('INDIRECT', 0) or 0
        
        self.total_cost = (
            self.direct_material_cost + self.direct_labor_cost +
            self.manufacturing_overhead + self.outsource_cost +
            self.travel_cost + self.equipment_cost +
            self.other_direct_cost + self.indirect_cost
        )
        
        # 计算毛利
        if self.contract_amount > 0:
            self.actual_profit = self.contract_amount - self.total_cost
            self.actual_margin = Decimal(self.actual_profit / self.contract_amount).quantize(
                Decimal('0.0001'), rounding=ROUND_HALF_UP
            )
        
        # 计算CPI
        if self.estimated_cost > 0 and self.completion_percentage > 0:
            ev = self.estimated_cost * (self.completion_percentage / 100)  # 挣值
            self.cpi = Decimal(ev / self.total_cost).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ) if self.total_cost > 0 else Decimal('1')
            
            # EAC = BAC / CPI
            if self.cpi > 0:
                self.eac = Decimal(self.estimated_cost / self.cpi).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                self.etc = self.eac - self.total_cost
        
        self.last_calculated_at = timezone.now()
        self.save()


class CostVarianceAnalysis(BaseModel):
    """成本差异分析"""
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='variance_analyses',
        verbose_name='项目'
    )
    
    analysis_date = models.DateField(verbose_name='分析日期')
    analysis_period = models.CharField(
        max_length=20,
        choices=[
            ('WEEKLY', '周分析'),
            ('MONTHLY', '月分析'),
            ('PHASE', '阶段分析'),
            ('FINAL', '完工分析'),
        ],
        verbose_name='分析周期'
    )
    
    # 预算vs实际
    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='预算金额')
    actual_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际金额')
    variance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='差异金额')
    variance_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='差异率')
    
    # 分项差异
    material_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='材料差异')
    labor_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='人工差异')
    overhead_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='制费差异')
    outsource_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='外协差异')
    
    # 差异分析
    price_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='价格差异')
    quantity_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='数量差异')
    efficiency_variance = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='效率差异')
    
    analysis_summary = models.TextField(blank=True, verbose_name='分析总结')
    corrective_actions = models.TextField(blank=True, verbose_name='纠正措施')
    
    analyzed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='分析人'
    )
    
    class Meta:
        db_table = 'cost_variance_analysis'
        verbose_name = '成本差异分析'
        verbose_name_plural = verbose_name
        ordering = ['-analysis_date']


# =============================================================================
# 序列化器
# =============================================================================

class StandardCostCategorySerializer(serializers.ModelSerializer):
    cost_element_display = serializers.CharField(source='get_cost_element_display', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = StandardCostCategory
        fields = '__all__'


class LaborRateStandardSerializer(serializers.ModelSerializer):
    work_type_display = serializers.CharField(source='get_work_type_display', read_only=True)
    
    class Meta:
        model = LaborRateStandard
        fields = '__all__'


class ProjectCostDetailSerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    cost_element_display = serializers.CharField(source='get_cost_element_display', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    project_phase_display = serializers.CharField(source='get_project_phase_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    
    class Meta:
        model = ProjectCostDetail
        fields = '__all__'


class ProjectCostSummarySerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_status = serializers.CharField(source='project.status', read_only=True)
    
    class Meta:
        model = ProjectCostSummary
        fields = '__all__'


class CostVarianceAnalysisSerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    analysis_period_display = serializers.CharField(source='get_analysis_period_display', read_only=True)
    
    class Meta:
        model = CostVarianceAnalysis
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================

class StandardCostCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """标准成本分类"""
    queryset = StandardCostCategory.objects.filter(is_deleted=False)
    serializer_class = StandardCostCategorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['cost_element', 'is_active', 'parent']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取树形结构"""
        categories = self.get_queryset().filter(parent__isnull=True)
        
        def build_tree(cat):
            children = self.get_queryset().filter(parent=cat)
            return {
                'id': cat.id,
                'code': cat.code,
                'name': cat.name,
                'cost_element': cat.cost_element,
                'children': [build_tree(c) for c in children]
            }
        
        return Response([build_tree(c) for c in categories])


class LaborRateStandardViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """人工费率标准"""
    queryset = LaborRateStandard.objects.filter(is_deleted=False)
    serializer_class = LaborRateStandardSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_type']
    
    @action(detail=False, methods=['get'])
    def current_rates(self, request):
        """获取当前有效费率"""
        today = date.today()
        rates = self.get_queryset().filter(
            effective_from__lte=today
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=today)
        )
        return Response(self.get_serializer(rates, many=True).data)


class ProjectCostDetailViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目成本明细"""
    queryset = ProjectCostDetail.objects.filter(is_deleted=False)
    serializer_class = ProjectCostDetailSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'cost_element', 'source_type', 'project_phase', 'is_verified']
    search_fields = ['description', 'source_doc_no', 'batch_no']
    ordering_fields = ['cost_date', 'actual_amount']
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """审核成本"""
        detail = self.get_object()
        detail.is_verified = True
        detail.verified_by = request.user
        detail.verified_at = timezone.now()
        detail.save()
        return Response(self.get_serializer(detail).data)
    
    @action(detail=False, methods=['post'])
    def batch_import(self, request):
        """批量导入成本"""
        items = request.data.get('items', [])
        created_count = 0
        
        with transaction.atomic():
            for item in items:
                item['created_by'] = request.user.id
                serializer = self.get_serializer(data=item)
                if serializer.is_valid():
                    serializer.save()
                    created_count += 1
        
        return Response({
            'success': True,
            'created_count': created_count,
            'total': len(items)
        })


class ProjectCostSummaryViewSet(viewsets.ModelViewSet):
    """项目成本汇总"""
    queryset = ProjectCostSummary.objects.filter(is_deleted=False)
    serializer_class = ProjectCostSummarySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project']
    
    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """重新计算汇总"""
        summary = self.get_object()
        summary.recalculate()
        return Response(self.get_serializer(summary).data)
    
    @action(detail=False, methods=['post'])
    def recalculate_all(self, request):
        """重新计算所有项目"""
        project_ids = request.data.get('project_ids', [])
        
        if project_ids:
            summaries = self.get_queryset().filter(project_id__in=project_ids)
        else:
            summaries = self.get_queryset().filter(
                project__status__in=['IN_PROGRESS', 'DEBUGGING', 'INSTALLATION']
            )
        
        count = 0
        for summary in summaries:
            summary.recalculate()
            count += 1
        
        return Response({
            'success': True,
            'recalculated_count': count
        })


class CostVarianceAnalysisViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """成本差异分析"""
    queryset = CostVarianceAnalysis.objects.filter(is_deleted=False)
    serializer_class = CostVarianceAnalysisSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'analysis_period']


# =============================================================================
# 成本分析报表API
# =============================================================================

class ProjectCostAnalysisDashboardView(APIView):
    """项目成本分析看板（增强版）"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        from apps.projects.models import Project
        
        try:
            project = Project.objects.get(id=project_id, is_deleted=False)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=404)
        
        # 获取或创建成本汇总
        summary, created = ProjectCostSummary.objects.get_or_create(
            project=project,
            defaults={
                'contract_amount': project.budget_total or 0
            }
        )
        
        if created or not summary.last_calculated_at:
            summary.recalculate()
        
        # 获取成本明细分析
        details = ProjectCostDetail.objects.filter(
            project=project, is_deleted=False
        )
        
        # 按成本要素分析
        by_element = details.values('cost_element').annotate(
            actual=Sum('actual_amount'),
            standard=Sum('standard_amount'),
            variance=Sum('variance_amount'),
            count=Count('id')
        )
        
        # 按阶段分析
        by_phase = details.values('project_phase').annotate(
            total=Sum('actual_amount'),
            count=Count('id')
        ).order_by('project_phase')
        
        # 按来源分析
        by_source = details.values('source_type').annotate(
            total=Sum('actual_amount'),
            count=Count('id')
        )
        
        # 成本趋势（按月）
        trend = details.annotate(
            month=TruncMonth('cost_date')
        ).values('month').annotate(
            total=Sum('actual_amount'),
            material=Sum(Case(
                When(cost_element='DIRECT_MATERIAL', then='actual_amount'),
                default=Value(0)
            )),
            labor=Sum(Case(
                When(cost_element='DIRECT_LABOR', then='actual_amount'),
                default=Value(0)
            ))
        ).order_by('month')
        
        # 差异TOP10
        top_variances = details.exclude(
            variance_amount=0
        ).order_by('-variance_amount')[:10]
        
        return Response({
            'project': {
                'id': project.id,
                'project_no': project.project_no,
                'name': project.name,
                'status': project.status,
            },
            'summary': ProjectCostSummarySerializer(summary).data,
            'analysis': {
                'by_element': list(by_element),
                'by_phase': list(by_phase),
                'by_source': list(by_source),
            },
            'trend': list(trend),
            'top_variances': ProjectCostDetailSerializer(top_variances, many=True).data,
        })


class CostComparisonReportView(APIView):
    """成本对比报表"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        project_ids = request.query_params.getlist('projects')
        
        if not project_ids:
            # 获取活跃项目
            from apps.projects.models import Project
            projects = Project.objects.filter(
                status__in=['IN_PROGRESS', 'DEBUGGING', 'INSTALLATION'],
                is_deleted=False
            )[:20]
            project_ids = [p.id for p in projects]
        
        summaries = ProjectCostSummary.objects.filter(
            project_id__in=project_ids
        ).select_related('project')
        
        comparison = []
        for s in summaries:
            comparison.append({
                'project_id': s.project.id,
                'project_no': s.project.project_no,
                'project_name': s.project.name,
                'contract_amount': float(s.contract_amount),
                'estimated_cost': float(s.estimated_cost),
                'actual_cost': float(s.total_cost),
                'estimated_profit': float(s.estimated_profit),
                'actual_profit': float(s.actual_profit),
                'estimated_margin': float(s.estimated_margin * 100),
                'actual_margin': float(s.actual_margin * 100),
                'margin_variance': float((s.actual_margin - s.estimated_margin) * 100),
                'cpi': float(s.cpi),
                'completion': float(s.completion_percentage),
            })
        
        # 按实际毛利率排序
        comparison.sort(key=lambda x: x['actual_margin'], reverse=True)
        
        # 计算汇总
        total_contract = sum(c['contract_amount'] for c in comparison)
        total_actual_cost = sum(c['actual_cost'] for c in comparison)
        total_actual_profit = sum(c['actual_profit'] for c in comparison)
        avg_margin = total_actual_profit / total_contract * 100 if total_contract > 0 else 0
        
        return Response({
            'comparison': comparison,
            'summary': {
                'project_count': len(comparison),
                'total_contract_amount': total_contract,
                'total_actual_cost': total_actual_cost,
                'total_actual_profit': total_actual_profit,
                'average_margin': round(avg_margin, 2),
                'profitable_count': len([c for c in comparison if c['actual_profit'] > 0]),
                'loss_count': len([c for c in comparison if c['actual_profit'] < 0]),
            }
        })


class CostElementReportView(APIView):
    """成本要素分析报表"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        project_id = request.query_params.get('project')
        
        details = ProjectCostDetail.objects.filter(is_deleted=False)
        
        if start_date:
            details = details.filter(cost_date__gte=start_date)
        if end_date:
            details = details.filter(cost_date__lte=end_date)
        if project_id:
            details = details.filter(project_id=project_id)
        
        # 按成本要素汇总
        by_element = details.values('cost_element').annotate(
            total_actual=Sum('actual_amount'),
            total_standard=Sum('standard_amount'),
            total_variance=Sum('variance_amount'),
            count=Count('id'),
            avg_unit_cost=Avg('unit_cost')
        ).order_by('-total_actual')
        
        # 计算总计和占比
        grand_total = details.aggregate(total=Sum('actual_amount'))['total'] or 0
        
        result = []
        for item in by_element:
            item['percentage'] = round(
                float(item['total_actual']) / float(grand_total) * 100, 2
            ) if grand_total > 0 else 0
            item['variance_rate'] = round(
                float(item['total_variance']) / float(item['total_standard']) * 100, 2
            ) if item['total_standard'] and item['total_standard'] > 0 else 0
            result.append(item)
        
        return Response({
            'by_element': result,
            'grand_total': float(grand_total),
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            }
        })
