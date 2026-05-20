"""
非标报价估算工具
Quote Estimation Tool for Non-standard Automation Equipment

功能：
- 基于BOM的成本自动估算
- 工时估算（设计/加工/装配/调试各阶段）
- 历史项目参考
- 利润率自动计算
- 成本构成分解
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, F, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel

# =============================================================================
# 模型定义
# =============================================================================


class CostCategory(BaseModel):
    """成本类别"""

    code = models.CharField(max_length=50, unique=True, verbose_name='类别编码')
    name = models.CharField(max_length=100, verbose_name='类别名称')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='上级类别'
    )
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'quote_cost_category'
        verbose_name = '成本类别'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class LaborRate(BaseModel):
    """人工费率标准"""

    WORK_TYPE_CHOICES = [
        ('DESIGN_MECHANICAL', '机械设计'),
        ('DESIGN_ELECTRICAL', '电气设计'),
        ('DESIGN_SOFTWARE', '软件开发'),
        ('MACHINING', '机加工'),
        ('ASSEMBLY', '装配'),
        ('WIRING', '接线'),
        ('DEBUGGING', '调试'),
        ('INSTALLATION', '现场安装'),
        ('TRAINING', '培训'),
        ('PROJECT_MGMT', '项目管理'),
        ('QUALITY', '质检'),
        ('OTHER', '其他'),
    ]

    work_type = models.CharField(max_length=30, choices=WORK_TYPE_CHOICES, unique=True, verbose_name='工作类型')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='小时费率')
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='日费率')
    description = models.TextField(blank=True, verbose_name='说明')
    effective_date = models.DateField(default=date.today, verbose_name='生效日期')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'quote_labor_rate'
        verbose_name = '人工费率'
        verbose_name_plural = verbose_name
        ordering = ['work_type']

    def __str__(self):
        return f'{self.get_work_type_display()} - ¥{self.hourly_rate}/h'


class QuoteEstimation(BaseModel):
    """报价估算单"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('ESTIMATING', '估算中'),
        ('REVIEW', '评审中'),
        ('APPROVED', '已批准'),
        ('QUOTED', '已报价'),
        ('WON', '已中标'),
        ('LOST', '未中标'),
        ('CANCELLED', '已取消'),
    ]

    # 基本信息
    estimation_no = models.CharField(max_length=50, unique=True, verbose_name='估算单号')
    name = models.CharField(max_length=200, verbose_name='项目名称')

    # 关联
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estimations',
        verbose_name='关联商机',
    )
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.PROTECT, related_name='quote_estimations', verbose_name='客户'
    )
    sales_person = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='quote_estimations',
        verbose_name='销售负责人',
    )

    # 项目概述
    project_type = models.CharField(max_length=50, blank=True, verbose_name='项目类型')
    project_description = models.TextField(blank=True, verbose_name='项目描述')
    technical_requirements = models.TextField(blank=True, verbose_name='技术要求')

    # 参考项目
    reference_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referenced_estimations',
        verbose_name='参考项目',
    )
    similarity_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='相似度%')

    # 成本汇总
    material_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='材料成本')
    labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='人工成本')
    outsource_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='外协成本')
    equipment_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='设备成本')
    travel_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='差旅成本')
    other_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='其他成本')

    # 管理费用
    management_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10, verbose_name='管理费率%')
    management_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='管理费用')

    # 风险预备
    risk_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5, verbose_name='风险预备率%')
    risk_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='风险预备金')

    # 成本合计
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='成本合计')

    # 报价
    target_profit_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20, verbose_name='目标利润率%')
    suggested_price = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='建议报价')
    final_price = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='最终报价')
    actual_profit_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='实际利润率%')

    # 工期
    design_days = models.IntegerField(default=0, verbose_name='设计周期(天)')
    production_days = models.IntegerField(default=0, verbose_name='生产周期(天)')
    installation_days = models.IntegerField(default=0, verbose_name='安装调试(天)')
    total_days = models.IntegerField(default=0, verbose_name='总工期(天)')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 审批
    reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_estimations',
        verbose_name='审核人',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_comments = models.TextField(blank=True, verbose_name='审核意见')

    class Meta:
        db_table = 'quote_estimation'
        verbose_name = '报价估算'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.estimation_no} - {self.name}'

    def save(self, *args, **kwargs):
        if not self.estimation_no:
            from apps.core.models import CodeRule

            self.estimation_no = CodeRule.generate_code('QUOTE_EST')
        super().save(*args, **kwargs)

    def calculate_costs(self):
        """计算成本汇总"""
        # 材料成本
        material_items = self.material_items.filter(is_deleted=False)
        self.material_cost = material_items.aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or Decimal(
            '0'
        )

        # 人工成本
        labor_items = self.labor_items.filter(is_deleted=False)
        self.labor_cost = labor_items.aggregate(total=Sum(F('hours') * F('hourly_rate')))['total'] or Decimal('0')

        # 外协成本
        outsource_items = self.outsource_items.filter(is_deleted=False)
        self.outsource_cost = outsource_items.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # 其他成本
        other_items = self.other_cost_items.filter(is_deleted=False)
        self.other_cost = other_items.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # 直接成本
        direct_cost = (
            self.material_cost
            + self.labor_cost
            + self.outsource_cost
            + self.equipment_cost
            + self.travel_cost
            + self.other_cost
        )

        # 管理费用
        self.management_cost = direct_cost * self.management_rate / 100

        # 风险预备
        self.risk_cost = direct_cost * self.risk_rate / 100

        # 总成本
        self.total_cost = direct_cost + self.management_cost + self.risk_cost

        # 建议报价
        if self.target_profit_rate > 0:
            self.suggested_price = self.total_cost / (1 - self.target_profit_rate / 100)
        else:
            self.suggested_price = self.total_cost

        # 实际利润率
        if self.final_price > 0:
            self.actual_profit_rate = (self.final_price - self.total_cost) / self.final_price * 100

        # 计算工期
        self.design_days = (
            labor_items.filter(work_type__in=['DESIGN_MECHANICAL', 'DESIGN_ELECTRICAL', 'DESIGN_SOFTWARE']).aggregate(
                total=Sum('days')
            )['total']
            or 0
        )

        self.production_days = (
            labor_items.filter(work_type__in=['MACHINING', 'ASSEMBLY', 'WIRING']).aggregate(total=Sum('days'))['total']
            or 0
        )

        self.installation_days = (
            labor_items.filter(work_type__in=['DEBUGGING', 'INSTALLATION']).aggregate(total=Sum('days'))['total'] or 0
        )

        self.total_days = self.design_days + self.production_days + self.installation_days

        self.save()
        return self


class EstimationMaterialItem(BaseModel):
    """估算材料明细"""

    estimation = models.ForeignKey(
        QuoteEstimation, on_delete=models.CASCADE, related_name='material_items', verbose_name='估算单'
    )

    # 物料信息
    item = models.ForeignKey('masterdata.Item', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='物料')
    item_code = models.CharField(max_length=50, blank=True, verbose_name='物料编码')
    item_name = models.CharField(max_length=200, verbose_name='物料名称')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格型号')

    # 数量价格
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1, verbose_name='数量')
    unit = models.CharField(max_length=20, default='件', verbose_name='单位')
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='单价')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额')

    # 分类
    category = models.ForeignKey(
        CostCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='成本类别'
    )

    # 来源
    source = models.CharField(
        max_length=20,
        choices=[
            ('MANUAL', '手工录入'),
            ('BOM', 'BOM导入'),
            ('HISTORY', '历史参考'),
        ],
        default='MANUAL',
        verbose_name='来源',
    )

    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'quote_estimation_material'
        verbose_name = '估算材料明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class EstimationLaborItem(BaseModel):
    """估算人工明细"""

    estimation = models.ForeignKey(
        QuoteEstimation, on_delete=models.CASCADE, related_name='labor_items', verbose_name='估算单'
    )

    work_type = models.CharField(max_length=30, choices=LaborRate.WORK_TYPE_CHOICES, verbose_name='工作类型')
    description = models.CharField(max_length=500, verbose_name='工作内容')

    # 工时
    hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='工时(小时)')
    days = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='工期(天)')
    persons = models.IntegerField(default=1, verbose_name='人数')

    # 费率
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='小时费率')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额')

    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'quote_estimation_labor'
        verbose_name = '估算人工明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def save(self, *args, **kwargs):
        # 自动获取费率
        if self.hourly_rate == 0:
            rate = LaborRate.objects.filter(work_type=self.work_type, is_active=True).first()
            if rate:
                self.hourly_rate = rate.hourly_rate

        self.amount = self.hours * self.hourly_rate

        # 计算工期（按8小时/天）
        if self.hours > 0 and self.persons > 0:
            self.days = self.hours / (8 * self.persons)

        super().save(*args, **kwargs)


class EstimationOutsourceItem(BaseModel):
    """估算外协明细"""

    estimation = models.ForeignKey(
        QuoteEstimation, on_delete=models.CASCADE, related_name='outsource_items', verbose_name='估算单'
    )

    description = models.CharField(max_length=500, verbose_name='外协内容')
    supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='供应商'
    )
    supplier_name = models.CharField(max_length=200, blank=True, verbose_name='供应商名称')

    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1, verbose_name='数量')
    unit = models.CharField(max_length=20, default='项', verbose_name='单位')
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='单价')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额')

    lead_time = models.IntegerField(default=0, verbose_name='交期(天)')
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'quote_estimation_outsource'
        verbose_name = '估算外协明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class EstimationOtherCost(BaseModel):
    """估算其他成本"""

    estimation = models.ForeignKey(
        QuoteEstimation, on_delete=models.CASCADE, related_name='other_cost_items', verbose_name='估算单'
    )

    cost_type = models.CharField(
        max_length=20,
        choices=[
            ('TRAVEL', '差旅费'),
            ('FREIGHT', '运费'),
            ('INSURANCE', '保险'),
            ('TAX', '税费'),
            ('CONSULTING', '咨询费'),
            ('LICENSE', '许可费'),
            ('OTHER', '其他'),
        ],
        verbose_name='费用类型',
    )
    description = models.CharField(max_length=500, verbose_name='费用说明')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额')
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'quote_estimation_other'
        verbose_name = '估算其他成本'
        verbose_name_plural = verbose_name
        ordering = ['id']


class ProjectCostHistory(BaseModel):
    """项目成本历史（用于参考）"""

    project = models.OneToOneField(
        'projects.Project', on_delete=models.CASCADE, related_name='cost_history', verbose_name='项目'
    )

    project_type = models.CharField(max_length=50, blank=True, verbose_name='项目类型')
    customer_industry = models.CharField(max_length=50, blank=True, verbose_name='客户行业')

    # 实际成本
    actual_material_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际材料成本')
    actual_labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际人工成本')
    actual_outsource_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际外协成本')
    actual_other_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际其他成本')
    actual_total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际总成本')

    # 预算
    budget_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='预算总额')
    contract_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='合同金额')

    # 实际利润
    actual_profit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际利润')
    actual_profit_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='实际利润率%')

    # 工期
    planned_days = models.IntegerField(default=0, verbose_name='计划工期')
    actual_days = models.IntegerField(default=0, verbose_name='实际工期')

    # 关键指标
    material_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='材料占比%')
    labor_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='人工占比%')

    class Meta:
        db_table = 'project_cost_history'
        verbose_name = '项目成本历史'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


# =============================================================================
# 序列化器
# =============================================================================


class CostCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = CostCategory
        fields = '__all__'

    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False)
        return CostCategorySerializer(children, many=True).data


class LaborRateSerializer(serializers.ModelSerializer):
    work_type_display = serializers.CharField(source='get_work_type_display', read_only=True)

    class Meta:
        model = LaborRate
        fields = '__all__'


class EstimationMaterialItemSerializer(serializers.ModelSerializer):
    item_name_display = serializers.CharField(source='item.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = EstimationMaterialItem
        fields = '__all__'
        read_only_fields = ['amount']


class EstimationLaborItemSerializer(serializers.ModelSerializer):
    work_type_display = serializers.CharField(source='get_work_type_display', read_only=True)

    class Meta:
        model = EstimationLaborItem
        fields = '__all__'
        read_only_fields = ['amount', 'days']


class EstimationOutsourceItemSerializer(serializers.ModelSerializer):
    supplier_name_display = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = EstimationOutsourceItem
        fields = '__all__'
        read_only_fields = ['amount']


class EstimationOtherCostSerializer(serializers.ModelSerializer):
    cost_type_display = serializers.CharField(source='get_cost_type_display', read_only=True)

    class Meta:
        model = EstimationOtherCost
        fields = '__all__'


class QuoteEstimationSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    sales_person_name = serializers.CharField(source='sales_person.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reference_project_name = serializers.CharField(source='reference_project.name', read_only=True)

    material_items = EstimationMaterialItemSerializer(many=True, read_only=True)
    labor_items = EstimationLaborItemSerializer(many=True, read_only=True)
    outsource_items = EstimationOutsourceItemSerializer(many=True, read_only=True)
    other_cost_items = EstimationOtherCostSerializer(many=True, read_only=True)

    class Meta:
        model = QuoteEstimation
        fields = '__all__'
        read_only_fields = [
            'estimation_no',
            'material_cost',
            'labor_cost',
            'outsource_cost',
            'management_cost',
            'risk_cost',
            'total_cost',
            'suggested_price',
            'actual_profit_rate',
            'design_days',
            'production_days',
            'installation_days',
            'total_days',
        ]


class QuoteEstimationListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    sales_person_name = serializers.CharField(source='sales_person.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = QuoteEstimation
        fields = [
            'id',
            'estimation_no',
            'name',
            'customer',
            'customer_name',
            'sales_person',
            'sales_person_name',
            'project_type',
            'total_cost',
            'suggested_price',
            'final_price',
            'target_profit_rate',
            'actual_profit_rate',
            'total_days',
            'status',
            'status_display',
            'created_at',
        ]


class ProjectCostHistorySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    customer_name = serializers.CharField(source='project.customer.name', read_only=True)

    class Meta:
        model = ProjectCostHistory
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================


class CostCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """成本类别管理"""

    queryset = CostCategory.objects.none()
    serializer_class = CostCategorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']

    def get_queryset(self):
        return CostCategory.objects.filter(is_deleted=False, parent__isnull=True)


class LaborRateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """人工费率管理"""

    queryset = LaborRate.objects.none()
    serializer_class = LaborRateSerializer

    def get_queryset(self):
        return LaborRate.objects.filter(is_deleted=False)

    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_type', 'is_active']


class QuoteEstimationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """报价估算管理"""

    queryset = QuoteEstimation.objects.none()
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'customer', 'sales_person', 'project_type']
    search_fields = ['estimation_no', 'name', 'customer__name']
    ordering_fields = ['created_at', 'total_cost', 'final_price']

    def get_queryset(self):
        return QuoteEstimation.objects.filter(is_deleted=False).select_related(
            'customer', 'sales_person', 'opportunity', 'reference_project'
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return QuoteEstimationListSerializer
        return QuoteEstimationSerializer

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """重新计算成本"""
        estimation = self.get_object()
        estimation.calculate_costs()
        return Response(QuoteEstimationSerializer(estimation).data)

    @action(detail=True, methods=['post'])
    def import_from_bom(self, request, pk=None):
        """从BOM导入材料"""
        from apps.projects.models import ProjectBOM

        estimation = self.get_object()
        bom_id = request.data.get('bom_id')

        if not bom_id:
            return Response({'error': '请选择BOM'}, status=400)

        try:
            bom = ProjectBOM.objects.get(id=bom_id, is_deleted=False)
        except ProjectBOM.DoesNotExist:
            return Response({'error': 'BOM不存在'}, status=404)

        # 导入BOM明细
        imported = 0
        for line in bom.lines.filter(is_deleted=False):
            EstimationMaterialItem.objects.create(
                estimation=estimation,
                item=line.item,
                item_code=line.item.code if line.item else '',
                item_name=line.item.name if line.item else line.item_name,
                specification=line.specification,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.item.standard_cost if line.item else 0,
                source='BOM',
                created_by=request.user,
            )
            imported += 1

        estimation.calculate_costs()

        return Response(
            {'message': f'成功导入 {imported} 项材料', 'estimation': QuoteEstimationSerializer(estimation).data}
        )

    @action(detail=True, methods=['post'])
    def import_from_history(self, request, pk=None):
        """从历史项目导入"""
        estimation = self.get_object()
        project_id = request.data.get('project_id')
        ratio = Decimal(str(request.data.get('ratio', 1)))  # 调整比例

        if not project_id:
            return Response({'error': '请选择参考项目'}, status=400)

        try:
            history = ProjectCostHistory.objects.get(project_id=project_id)
        except ProjectCostHistory.DoesNotExist:
            return Response({'error': '项目成本历史不存在'}, status=404)

        # 更新参考信息
        estimation.reference_project_id = project_id
        estimation.similarity_ratio = ratio * 100

        # 根据历史成本估算
        estimation.material_cost = history.actual_material_cost * ratio
        estimation.labor_cost = history.actual_labor_cost * ratio
        estimation.outsource_cost = history.actual_outsource_cost * ratio
        estimation.other_cost = history.actual_other_cost * ratio
        estimation.save()

        estimation.calculate_costs()

        return Response({'message': '已根据历史项目更新估算', 'estimation': QuoteEstimationSerializer(estimation).data})

    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交评审"""
        estimation = self.get_object()
        if estimation.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的估算单'}, status=400)

        estimation.status = 'REVIEW'
        estimation.save()
        return Response(QuoteEstimationSerializer(estimation).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过"""
        estimation = self.get_object()
        if estimation.status != 'REVIEW':
            return Response({'error': '只能审批评审中的估算单'}, status=400)

        estimation.status = 'APPROVED'
        estimation.reviewed_by = request.user
        estimation.reviewed_at = timezone.now()
        estimation.review_comments = request.data.get('comments', '')
        estimation.save()
        return Response(QuoteEstimationSerializer(estimation).data)

    @action(detail=True, methods=['post'])
    def create_quotation(self, request, pk=None):
        """生成正式报价单"""
        from apps.sales.models import SalesQuotation

        estimation = self.get_object()
        if estimation.status not in ['APPROVED', 'QUOTED']:
            return Response({'error': '只能从已批准的估算单生成报价'}, status=400)

        # 创建报价单
        quotation = SalesQuotation.objects.create(
            customer=estimation.customer,
            opportunity=estimation.opportunity,
            project_name=estimation.name,
            total_amount=estimation.final_price or estimation.suggested_price,
            valid_until=date.today() + timedelta(days=30),
            remarks=f'基于估算单 {estimation.estimation_no} 生成',
            created_by=request.user,
        )

        # 更新估算单状态
        estimation.status = 'QUOTED'
        estimation.save()

        return Response(
            {'message': '报价单创建成功', 'quotation_id': quotation.id, 'quotation_no': quotation.quotation_no}
        )

    @action(detail=False, methods=['get'])
    def similar_projects(self, request):
        """查找相似项目"""
        project_type = request.query_params.get('project_type', '')
        customer_id = request.query_params.get('customer_id')

        queryset = ProjectCostHistory.objects.select_related('project')

        if project_type:
            queryset = queryset.filter(project_type__icontains=project_type)

        if customer_id:
            queryset = queryset.filter(project__customer_id=customer_id)

        # 只返回已完成且有成本数据的项目
        queryset = queryset.filter(actual_total_cost__gt=0)[:20]

        return Response(ProjectCostHistorySerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def cost_analysis(self, request):
        """成本分析统计"""
        # 各类型项目平均成本
        type_stats = (
            ProjectCostHistory.objects.values('project_type')
            .annotate(
                count=Count('id'),
                avg_cost=Avg('actual_total_cost'),
                avg_profit_rate=Avg('actual_profit_rate'),
                avg_material_ratio=Avg('material_ratio'),
                avg_labor_ratio=Avg('labor_ratio'),
            )
            .order_by('-count')
        )

        # 整体统计
        overall = ProjectCostHistory.objects.aggregate(
            total_projects=Count('id'),
            avg_profit_rate=Avg('actual_profit_rate'),
            avg_material_ratio=Avg('material_ratio'),
            avg_labor_ratio=Avg('labor_ratio'),
        )

        return Response({'by_type': list(type_stats), 'overall': overall})


class EstimationMaterialItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """估算材料明细"""

    queryset = EstimationMaterialItem.objects.none()
    serializer_class = EstimationMaterialItemSerializer

    def get_queryset(self):
        return EstimationMaterialItem.objects.filter(is_deleted=False)

    permission_classes = [IsAuthenticated]
    filterset_fields = ['estimation', 'category', 'source']

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        instance.estimation.calculate_costs()

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        instance.estimation.calculate_costs()

    def perform_destroy(self, instance):
        estimation = instance.estimation
        super().perform_destroy(instance)
        estimation.calculate_costs()


class EstimationLaborItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """估算人工明细"""

    queryset = EstimationLaborItem.objects.none()
    serializer_class = EstimationLaborItemSerializer

    def get_queryset(self):
        return EstimationLaborItem.objects.filter(is_deleted=False)

    permission_classes = [IsAuthenticated]
    filterset_fields = ['estimation', 'work_type']

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        instance.estimation.calculate_costs()

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        instance.estimation.calculate_costs()


class EstimationOutsourceItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """估算外协明细"""

    queryset = EstimationOutsourceItem.objects.none()
    serializer_class = EstimationOutsourceItemSerializer

    def get_queryset(self):
        return EstimationOutsourceItem.objects.filter(is_deleted=False)

    permission_classes = [IsAuthenticated]
    filterset_fields = ['estimation', 'supplier']


class ProjectCostHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """项目成本历史（只读）"""

    queryset = ProjectCostHistory.objects.select_related('project')
    serializer_class = ProjectCostHistorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project_type', 'customer_industry']
    search_fields = ['project__name', 'project__project_no']
