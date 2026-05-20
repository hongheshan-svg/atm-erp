"""
外协加工跟踪增强模块
Outsource Processing Tracking Enhancement

功能：
- 外协商能力管理
- 外协进度跟踪
- 外协质量追溯
- 外协成本分析
"""

from django.db import models
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel

# 导入现有外协模型
from .outsource_models import OutsourceOrder, OutsourceOrderLine

# =============================================================================
# 模型定义 - 外协能力管理
# =============================================================================


class OutsourceCapability(BaseModel):
    """外协商能力"""

    PROCESS_TYPE_CHOICES = [
        ('MACHINING', '机加工'),
        ('WELDING', '焊接'),
        ('PAINTING', '喷涂/烤漆'),
        ('PLATING', '电镀'),
        ('HEAT_TREAT', '热处理'),
        ('SURFACE', '表面处理'),
        ('ASSEMBLY', '装配'),
        ('TESTING', '测试'),
        ('LASER', '激光加工'),
        ('STAMPING', '冲压'),
        ('CASTING', '铸造'),
        ('FORGING', '锻造'),
        ('INJECTION', '注塑'),
        ('PCB', 'PCB制造'),
        ('SMT', 'SMT贴片'),
        ('OTHER', '其他'),
    ]

    supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.CASCADE, related_name='outsource_capabilities', verbose_name='供应商'
    )

    process_type = models.CharField(max_length=20, choices=PROCESS_TYPE_CHOICES, verbose_name='工艺类型')
    process_detail = models.CharField(max_length=200, blank=True, verbose_name='工艺明细')

    # 能力参数
    daily_capacity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='日产能')
    capacity_unit = models.CharField(max_length=20, default='件', verbose_name='产能单位')

    # 设备信息
    equipment_list = models.TextField(blank=True, verbose_name='设备清单')
    max_size = models.CharField(max_length=100, blank=True, verbose_name='最大加工尺寸')
    precision = models.CharField(max_length=100, blank=True, verbose_name='加工精度')

    # 资质
    certifications = models.JSONField(default=list, blank=True, verbose_name='资质认证')

    # 评分
    quality_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name='质量评分')
    delivery_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name='交期评分')
    price_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name='价格评分')
    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0, verbose_name='综合评分')

    is_verified = models.BooleanField(default=False, verbose_name='已验证')
    verified_date = models.DateField(null=True, blank=True, verbose_name='验证日期')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'outsource_capability'
        verbose_name = '外协商能力'
        verbose_name_plural = verbose_name
        unique_together = ['supplier', 'process_type']
        ordering = ['supplier', 'process_type']

    def __str__(self):
        return f'{self.supplier.name} - {self.get_process_type_display()}'


class OutsourceProgress(BaseModel):
    """外协进度跟踪"""

    outsource_order = models.ForeignKey(
        OutsourceOrder, on_delete=models.CASCADE, related_name='progress_records', verbose_name='外协单'
    )
    outsource_line = models.ForeignKey(
        OutsourceOrderLine,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='progress_records',
        verbose_name='外协明细',
    )

    progress_date = models.DateField(verbose_name='进度日期')
    progress_type = models.CharField(
        max_length=20,
        choices=[
            ('MATERIAL_SENT', '已发料'),
            ('PRODUCTION', '生产进度'),
            ('QUALITY', '质检'),
            ('SHIPPING', '发货'),
            ('RECEIVED', '已收货'),
        ],
        verbose_name='进度类型',
    )

    # 进度数据
    completed_qty = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='完成数量')
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='完成率%')

    description = models.TextField(blank=True, verbose_name='进度说明')

    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    reported_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='报告人'
    )

    class Meta:
        db_table = 'outsource_progress'
        verbose_name = '外协进度'
        verbose_name_plural = verbose_name
        ordering = ['-progress_date', '-created_at']


class OutsourceInspection(BaseModel):
    """外协质量检验"""

    outsource_order = models.ForeignKey(
        OutsourceOrder, on_delete=models.CASCADE, related_name='inspections', verbose_name='外协单'
    )
    outsource_line = models.ForeignKey(
        OutsourceOrderLine,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='inspections',
        verbose_name='外协明细',
    )

    inspection_no = models.CharField(max_length=50, unique=True, verbose_name='检验单号')
    inspection_date = models.DateField(verbose_name='检验日期')

    # 检验数量
    inspected_qty = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='检验数量')
    qualified_qty = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='合格数量')
    rejected_qty = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='不合格数量')

    # 检验结果
    result = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待检'),
            ('PASSED', '合格'),
            ('FAILED', '不合格'),
            ('CONDITIONAL', '让步接收'),
        ],
        default='PENDING',
        verbose_name='检验结果',
    )

    # 检验项目
    inspection_items = models.JSONField(default=list, blank=True, verbose_name='检验项目')

    # 不合格原因
    defect_type = models.CharField(max_length=50, blank=True, verbose_name='缺陷类型')
    defect_description = models.TextField(blank=True, verbose_name='缺陷描述')

    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outsource_inspections',
        verbose_name='检验员',
    )

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'outsource_inspection'
        verbose_name = '外协质量检验'
        verbose_name_plural = verbose_name
        ordering = ['-inspection_date']


class OutsourceClaim(BaseModel):
    """外协索赔"""

    outsource_order = models.ForeignKey(
        OutsourceOrder, on_delete=models.CASCADE, related_name='claims', verbose_name='外协单'
    )
    inspection = models.ForeignKey(
        OutsourceInspection, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联检验'
    )

    claim_no = models.CharField(max_length=50, unique=True, verbose_name='索赔单号')
    claim_date = models.DateField(verbose_name='索赔日期')

    claim_type = models.CharField(
        max_length=20,
        choices=[
            ('QUALITY', '质量问题'),
            ('DELIVERY', '交期延误'),
            ('QUANTITY', '数量短缺'),
            ('DAMAGE', '损坏'),
            ('OTHER', '其他'),
        ],
        verbose_name='索赔类型',
    )

    # 索赔金额
    claim_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='索赔金额')
    agreed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='协商金额')

    # 处理状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('SUBMITTED', '已提交'),
            ('NEGOTIATING', '协商中'),
            ('AGREED', '已达成'),
            ('CLOSED', '已结案'),
            ('CANCELLED', '已取消'),
        ],
        default='DRAFT',
        verbose_name='状态',
    )

    description = models.TextField(verbose_name='索赔说明')
    resolution = models.TextField(blank=True, verbose_name='处理结果')

    class Meta:
        db_table = 'outsource_claim'
        verbose_name = '外协索赔'
        verbose_name_plural = verbose_name
        ordering = ['-claim_date']


# =============================================================================
# 序列化器
# =============================================================================


class OutsourceCapabilitySerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    process_type_display = serializers.CharField(source='get_process_type_display', read_only=True)

    class Meta:
        model = OutsourceCapability
        fields = '__all__'


class OutsourceProgressSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='outsource_order.order_no', read_only=True)
    progress_type_display = serializers.CharField(source='get_progress_type_display', read_only=True)

    class Meta:
        model = OutsourceProgress
        fields = '__all__'


class OutsourceInspectionSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='outsource_order.order_no', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)

    class Meta:
        model = OutsourceInspection
        fields = '__all__'


class OutsourceClaimSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='outsource_order.order_no', read_only=True)
    claim_type_display = serializers.CharField(source='get_claim_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OutsourceClaim
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================


class OutsourceCapabilityViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """外协商能力管理"""

    queryset = OutsourceCapability.objects.filter(is_deleted=False)
    serializer_class = OutsourceCapabilitySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'process_type', 'is_verified']
    search_fields = ['supplier__name', 'process_detail']

    @action(detail=False, methods=['get'])
    def by_process(self, request):
        """按工艺类型查询"""
        process_type = request.query_params.get('process_type')
        if not process_type:
            return Response({'error': '请提供工艺类型'}, status=400)

        capabilities = self.get_queryset().filter(process_type=process_type).order_by('-overall_rating')

        return Response(self.get_serializer(capabilities, many=True).data)


class OutsourceProgressViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """外协进度跟踪"""

    queryset = OutsourceProgress.objects.filter(is_deleted=False)
    serializer_class = OutsourceProgressSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['outsource_order', 'outsource_line', 'progress_type']
    ordering_fields = ['progress_date']


class OutsourceInspectionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """外协质量检验"""

    queryset = OutsourceInspection.objects.filter(is_deleted=False)
    serializer_class = OutsourceInspectionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['outsource_order', 'result']

    def perform_create(self, serializer):
        from apps.core.models import CodeRule

        inspection_no = CodeRule.generate_code('OSINSP')
        serializer.save(inspection_no=inspection_no, inspector=self.request.user)


class OutsourceClaimViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """外协索赔管理"""

    queryset = OutsourceClaim.objects.filter(is_deleted=False)
    serializer_class = OutsourceClaimSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['outsource_order', 'claim_type', 'status']

    def perform_create(self, serializer):
        from apps.core.models import CodeRule

        claim_no = CodeRule.generate_code('OSCLAIM')
        serializer.save(claim_no=claim_no)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交索赔"""
        claim = self.get_object()
        claim.status = 'SUBMITTED'
        claim.save()
        return Response(self.get_serializer(claim).data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """结案"""
        claim = self.get_object()
        claim.status = 'CLOSED'
        claim.resolution = request.data.get('resolution', '')
        claim.agreed_amount = request.data.get('agreed_amount', claim.agreed_amount)
        claim.save()
        return Response(self.get_serializer(claim).data)
