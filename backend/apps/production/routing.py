"""
工艺路线管理模块
Manufacturing Routing Management

功能：
- 项目工艺路线管理（核心功能，适合非标自动化）
- 工位/工作站定义
- 工序工时记录
- 工艺与BOM联动

注：工艺模板(RoutingTemplate)为可选参考功能，非标自动化行业应主要使用
项目工艺路线(ProjectRouting)来管理每个项目的独特工艺流程。
"""

from decimal import Decimal

from django.db import models
from django.db.models import Avg, Sum
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# =============================================================================
# 模型定义
# =============================================================================


class WorkStation(BaseModel):
    """工位/工作站"""

    STATION_TYPE_CHOICES = [
        ('MACHINING', '机加工'),
        ('ASSEMBLY', '装配'),
        ('WELDING', '焊接'),
        ('PAINTING', '喷涂'),
        ('TESTING', '测试'),
        ('PACKING', '包装'),
        ('DEBUGGING', '调试'),
        ('OTHER', '其他'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='工位编码')
    name = models.CharField(max_length=100, verbose_name='工位名称')
    station_type = models.CharField(
        max_length=20, choices=STATION_TYPE_CHOICES, default='OTHER', verbose_name='工位类型'
    )

    # 所属工作中心
    work_center = models.ForeignKey(
        'production.WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stations',
        verbose_name='工作中心',
    )

    # 能力参数（可选，主要用于产能规划参考，非标项目可不填）
    standard_capacity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='标准产能(件/班)')
    cycle_time = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='标准节拍(秒)', help_text='可选'
    )
    uph = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='UPH(件/小时)', help_text='可选，自动计算'
    )

    # 人员配置
    operators_required = models.IntegerField(default=1, verbose_name='所需人员')
    skill_level = models.CharField(
        max_length=20,
        choices=[
            ('JUNIOR', '初级'),
            ('MIDDLE', '中级'),
            ('SENIOR', '高级'),
            ('EXPERT', '专家'),
        ],
        default='MIDDLE',
        verbose_name='技能要求',
    )

    # 设备关联
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_stations',
        verbose_name='关联设备',
    )

    # 状态
    is_active = models.BooleanField(default=True, verbose_name='启用')
    location = models.CharField(max_length=100, blank=True, verbose_name='位置')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'production_workstation'
        verbose_name = '工位'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def save(self, *args, **kwargs):
        # 自动计算UPH
        if self.cycle_time > 0:
            self.uph = Decimal('3600') / self.cycle_time
        super().save(*args, **kwargs)


class RoutingTemplate(BaseModel):
    """工艺路线模板"""

    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    name = models.CharField(max_length=200, verbose_name='模板名称')

    # 分类
    product_category = models.ForeignKey(
        'masterdata.ItemCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='routing_templates',
        verbose_name='产品类别',
    )

    # 关联物料（可选，用于标准产品）
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='routing_templates',
        verbose_name='关联物料',
    )

    # 版本控制
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    is_current = models.BooleanField(default=True, verbose_name='当前版本')

    # 工艺参数
    total_standard_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='标准工时合计')
    total_setup_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='准备工时合计')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('APPROVED', '已批准'),
            ('OBSOLETE', '已废弃'),
        ],
        default='DRAFT',
        verbose_name='状态',
    )

    description = models.TextField(blank=True, verbose_name='工艺说明')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'production_routing_template'
        verbose_name = '工艺路线模板'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name} (v{self.version})'

    def calculate_totals(self):
        """计算工时合计"""
        totals = self.operations.filter(is_deleted=False).aggregate(
            total_standard=Sum('standard_hours'), total_setup=Sum('setup_hours')
        )
        self.total_standard_hours = totals['total_standard'] or 0
        self.total_setup_hours = totals['total_setup'] or 0
        self.save(update_fields=['total_standard_hours', 'total_setup_hours'])


class RoutingOperation(BaseModel):
    """工艺工序"""

    OPERATION_TYPE_CHOICES = [
        ('MACHINING', '机加工'),
        ('ASSEMBLY', '装配'),
        ('WELDING', '焊接'),
        ('PAINTING', '喷涂'),
        ('TESTING', '测试'),
        ('INSPECTION', '检验'),
        ('PACKING', '包装'),
        ('DEBUGGING', '调试'),
        ('HEAT_TREAT', '热处理'),
        ('SURFACE', '表面处理'),
        ('OTHER', '其他'),
    ]

    routing = models.ForeignKey(
        RoutingTemplate, on_delete=models.CASCADE, related_name='operations', verbose_name='工艺路线'
    )

    # 工序信息
    sequence = models.IntegerField(verbose_name='工序号')
    operation_code = models.CharField(max_length=50, verbose_name='工序编码')
    operation_name = models.CharField(max_length=200, verbose_name='工序名称')
    operation_type = models.CharField(
        max_length=20, choices=OPERATION_TYPE_CHOICES, default='OTHER', verbose_name='工序类型'
    )

    # 工位/工作中心
    work_station = models.ForeignKey(
        WorkStation, on_delete=models.SET_NULL, null=True, blank=True, related_name='operations', verbose_name='工位'
    )
    work_center = models.ForeignKey(
        'production.WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='routing_operations',
        verbose_name='工作中心',
    )

    # 工时标准
    setup_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='准备工时(h)')
    standard_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='标准工时(h/件)')
    min_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='最小工时(h)')
    max_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='最大工时(h)')

    # 产能参数
    cycle_time = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='节拍时间(秒)')
    batch_size = models.IntegerField(default=1, verbose_name='批量大小')

    # 人员配置
    operators_required = models.IntegerField(default=1, verbose_name='所需人员')
    skill_requirements = models.CharField(max_length=200, blank=True, verbose_name='技能要求')

    # 设备/工具
    equipment_required = models.CharField(max_length=500, blank=True, verbose_name='所需设备')
    tools_required = models.CharField(max_length=500, blank=True, verbose_name='所需工具')

    # 质量控制
    inspection_required = models.BooleanField(default=False, verbose_name='需要检验')
    inspection_method = models.CharField(max_length=200, blank=True, verbose_name='检验方法')
    quality_standard = models.TextField(blank=True, verbose_name='质量标准')

    # 操作说明
    work_instruction = models.TextField(blank=True, verbose_name='作业指导')
    safety_notes = models.TextField(blank=True, verbose_name='安全注意事项')

    # 附件
    drawings = models.JSONField(default=list, blank=True, verbose_name='相关图纸')
    documents = models.JSONField(default=list, blank=True, verbose_name='相关文档')

    # 外协标记
    is_outsourced = models.BooleanField(default=False, verbose_name='外协工序')
    outsource_supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='外协供应商'
    )
    outsource_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='外协成本')

    class Meta:
        db_table = 'production_routing_operation'
        verbose_name = '工艺工序'
        verbose_name_plural = verbose_name
        ordering = ['routing', 'sequence']
        unique_together = ['routing', 'sequence']

    def __str__(self):
        return f'{self.routing.code}-{self.sequence:03d} {self.operation_name}'


class OperationMaterial(BaseModel):
    """工序物料消耗"""

    operation = models.ForeignKey(
        RoutingOperation, on_delete=models.CASCADE, related_name='materials', verbose_name='工序'
    )

    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='operation_consumptions', verbose_name='物料'
    )

    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='消耗数量')
    unit = models.CharField(max_length=20, default='件', verbose_name='单位')

    # 消耗类型
    consumption_type = models.CharField(
        max_length=20,
        choices=[
            ('COMPONENT', '组件'),
            ('CONSUMABLE', '耗材'),
            ('AUXILIARY', '辅料'),
        ],
        default='COMPONENT',
        verbose_name='消耗类型',
    )

    remarks = models.CharField(max_length=200, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'production_operation_material'
        verbose_name = '工序物料消耗'
        verbose_name_plural = verbose_name
        ordering = ['id']


class ProjectRouting(BaseModel):
    """项目工艺路线（基于模板生成）"""

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='routings', verbose_name='项目'
    )

    name = models.CharField(max_length=200, verbose_name='工艺名称')
    template = models.ForeignKey(
        RoutingTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='基于模板'
    )

    # 关联BOM
    bom = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='routings',
        verbose_name='关联BOM',
    )

    # 工时合计
    total_standard_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='标准工时合计')
    total_actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='实际工时合计')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('CONFIRMED', '已确认'),
            ('IN_PROGRESS', '进行中'),
            ('COMPLETED', '已完成'),
        ],
        default='DRAFT',
        verbose_name='状态',
    )

    description = models.TextField(blank=True, verbose_name='说明')

    class Meta:
        db_table = 'project_routing'
        verbose_name = '项目工艺路线'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.code} - {self.name}'


class ProjectRoutingOperation(BaseModel):
    """项目工艺工序"""

    routing = models.ForeignKey(
        ProjectRouting, on_delete=models.CASCADE, related_name='operations', verbose_name='工艺路线'
    )

    sequence = models.IntegerField(verbose_name='工序号')
    operation_name = models.CharField(max_length=200, verbose_name='工序名称')
    operation_type = models.CharField(
        max_length=20, choices=RoutingOperation.OPERATION_TYPE_CHOICES, default='OTHER', verbose_name='工序类型'
    )

    # 工位
    work_station = models.ForeignKey(WorkStation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='工位')

    # 工时
    standard_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='标准工时(h)')
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='计划工时(h)')
    actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='实际工时(h)')

    # 执行状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待开始'),
            ('IN_PROGRESS', '进行中'),
            ('COMPLETED', '已完成'),
            ('SKIPPED', '已跳过'),
        ],
        default='PENDING',
        verbose_name='状态',
    )

    # 执行信息
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    operator = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='操作员'
    )

    work_instruction = models.TextField(blank=True, verbose_name='作业指导')
    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'project_routing_operation'
        verbose_name = '项目工艺工序'
        verbose_name_plural = verbose_name
        ordering = ['routing', 'sequence']


# =============================================================================
# 序列化器
# =============================================================================


class WorkStationSerializer(serializers.ModelSerializer):
    station_type_display = serializers.CharField(source='get_station_type_display', read_only=True)
    skill_level_display = serializers.CharField(source='get_skill_level_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)

    class Meta:
        model = WorkStation
        fields = '__all__'


class OperationMaterialSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    consumption_type_display = serializers.CharField(source='get_consumption_type_display', read_only=True)

    class Meta:
        model = OperationMaterial
        fields = '__all__'


class RoutingOperationSerializer(serializers.ModelSerializer):
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    work_station_name = serializers.CharField(source='work_station.name', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    materials = OperationMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = RoutingOperation
        fields = '__all__'


class RoutingTemplateSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    product_category_name = serializers.CharField(source='product_category.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    operations = RoutingOperationSerializer(many=True, read_only=True)
    operation_count = serializers.SerializerMethodField()

    class Meta:
        model = RoutingTemplate
        fields = '__all__'

    def get_operation_count(self, obj):
        return obj.operations.filter(is_deleted=False).count()


class RoutingTemplateListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    product_category_name = serializers.CharField(source='product_category.name', read_only=True)
    operation_count = serializers.SerializerMethodField()

    class Meta:
        model = RoutingTemplate
        fields = [
            'id',
            'code',
            'name',
            'product_category',
            'product_category_name',
            'version',
            'is_current',
            'total_standard_hours',
            'total_setup_hours',
            'status',
            'status_display',
            'operation_count',
            'is_active',
            'created_at',
        ]

    def get_operation_count(self, obj):
        return obj.operations.filter(is_deleted=False).count()


class ProjectRoutingOperationSerializer(serializers.ModelSerializer):
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    work_station_name = serializers.CharField(source='work_station.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = ProjectRoutingOperation
        fields = '__all__'


class ProjectRoutingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_no = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    operations = ProjectRoutingOperationSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectRouting
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================


class WorkStationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """工位管理"""

    permission_module = 'production'
    permission_resource = 'work_station'
    queryset = WorkStation.objects.filter(is_deleted=False)
    serializer_class = WorkStationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['station_type', 'work_center', 'is_active', 'skill_level']
    search_fields = ['code', 'name', 'location']
    ordering_fields = ['code', 'name', 'uph']

    @action(detail=False, methods=['get'])
    def capacity_summary(self, request):
        """产能汇总"""
        stations = self.get_queryset().filter(is_active=True)

        by_type = stations.values('station_type').annotate(
            count=models.Count('id'), total_capacity=Sum('standard_capacity'), avg_uph=Avg('uph')
        )

        return Response({'total_stations': stations.count(), 'by_type': list(by_type)})


class RoutingTemplateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """工艺路线模板管理"""

    permission_module = 'production'
    permission_resource = 'routing_template'
    queryset = RoutingTemplate.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'product_category', 'is_active', 'is_current']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return RoutingTemplateListSerializer
        return RoutingTemplateSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批工艺路线"""
        routing = self.get_object()
        if routing.status != 'DRAFT':
            return Response({'error': '只能审批草稿状态的工艺'}, status=400)

        routing.status = 'APPROVED'
        routing.save()
        routing.calculate_totals()

        return Response(RoutingTemplateSerializer(routing).data)

    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """创建新版本"""
        original = self.get_object()

        # 计算新版本号
        new_version = f'{float(original.version) + 0.1:.1f}'

        # 复制模板
        new_routing = RoutingTemplate.objects.create(
            code=f'{original.code}_V{new_version}',
            name=original.name,
            product_category=original.product_category,
            item=original.item,
            version=new_version,
            is_current=True,
            description=original.description,
            created_by=request.user,
        )

        # 设置原版本为非当前
        original.is_current = False
        original.save()

        # 复制工序
        for op in original.operations.filter(is_deleted=False):
            new_op = RoutingOperation.objects.create(
                routing=new_routing,
                sequence=op.sequence,
                operation_code=op.operation_code,
                operation_name=op.operation_name,
                operation_type=op.operation_type,
                work_station=op.work_station,
                work_center=op.work_center,
                setup_hours=op.setup_hours,
                standard_hours=op.standard_hours,
                cycle_time=op.cycle_time,
                operators_required=op.operators_required,
                skill_requirements=op.skill_requirements,
                equipment_required=op.equipment_required,
                tools_required=op.tools_required,
                inspection_required=op.inspection_required,
                work_instruction=op.work_instruction,
                safety_notes=op.safety_notes,
                created_by=request.user,
            )

            # 复制物料
            for mat in op.materials.filter(is_deleted=False):
                OperationMaterial.objects.create(
                    operation=new_op,
                    item=mat.item,
                    quantity=mat.quantity,
                    unit=mat.unit,
                    consumption_type=mat.consumption_type,
                    created_by=request.user,
                )

        new_routing.calculate_totals()

        return Response(RoutingTemplateSerializer(new_routing).data)

    @action(detail=True, methods=['post'])
    def apply_to_project(self, request, pk=None):
        """应用到项目"""
        template = self.get_object()
        project_id = request.data.get('project_id')

        if not project_id:
            return Response({'error': '请选择项目'}, status=400)

        from apps.projects.models import Project

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=404)

        # 创建项目工艺路线
        routing = ProjectRouting.objects.create(
            project=project,
            name=template.name,
            template=template,
            total_standard_hours=template.total_standard_hours,
            created_by=request.user,
        )

        # 复制工序
        for op in template.operations.filter(is_deleted=False):
            ProjectRoutingOperation.objects.create(
                routing=routing,
                sequence=op.sequence,
                operation_name=op.operation_name,
                operation_type=op.operation_type,
                work_station=op.work_station,
                standard_hours=op.standard_hours,
                planned_hours=op.standard_hours,
                work_instruction=op.work_instruction,
                created_by=request.user,
            )

        return Response({'message': '工艺路线已应用到项目', 'routing_id': routing.id})


class RoutingOperationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """工艺工序管理"""

    permission_module = 'production'
    permission_resource = 'routing_operation'
    queryset = RoutingOperation.objects.filter(is_deleted=False)
    serializer_class = RoutingOperationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['routing', 'operation_type', 'work_station', 'is_outsourced']

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        instance.routing.calculate_totals()

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        instance.routing.calculate_totals()


class ProjectRoutingViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目工艺路线管理"""

    permission_module = 'production'
    permission_resource = 'project_routing'
    queryset = ProjectRouting.objects.filter(is_deleted=False)
    serializer_class = ProjectRoutingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'status']
    search_fields = ['name', 'project__project_no', 'project__name']

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认工艺路线"""
        routing = self.get_object()
        routing.status = 'CONFIRMED'
        routing.save()
        return Response(ProjectRoutingSerializer(routing).data)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """工序进度"""
        routing = self.get_object()
        operations = routing.operations.filter(is_deleted=False)

        total = operations.count()
        completed = operations.filter(status='COMPLETED').count()
        in_progress = operations.filter(status='IN_PROGRESS').count()

        return Response(
            {
                'total': total,
                'completed': completed,
                'in_progress': in_progress,
                'pending': total - completed - in_progress,
                'progress_rate': round(completed / total * 100, 1) if total > 0 else 0,
            }
        )


class ProjectRoutingOperationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目工艺工序管理"""

    permission_module = 'production'
    permission_resource = 'project_routing_operation'
    queryset = ProjectRoutingOperation.objects.filter(is_deleted=False)
    serializer_class = ProjectRoutingOperationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['routing', 'status', 'operator']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始工序"""
        from django.utils import timezone

        operation = self.get_object()
        if operation.status != 'PENDING':
            return Response({'error': '工序已开始或已完成'}, status=400)

        operation.status = 'IN_PROGRESS'
        operation.started_at = timezone.now()
        operation.operator = request.user
        operation.save()

        # 更新路线状态
        operation.routing.status = 'IN_PROGRESS'
        operation.routing.save()

        return Response(ProjectRoutingOperationSerializer(operation).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成工序"""
        from django.utils import timezone

        operation = self.get_object()
        if operation.status != 'IN_PROGRESS':
            return Response({'error': '工序未开始'}, status=400)

        operation.status = 'COMPLETED'
        operation.completed_at = timezone.now()
        operation.actual_hours = request.data.get('actual_hours', operation.planned_hours)
        operation.remarks = request.data.get('remarks', '')
        operation.save()

        # 更新路线实际工时
        routing = operation.routing
        routing.total_actual_hours = (
            routing.operations.filter(is_deleted=False).aggregate(total=Sum('actual_hours'))['total'] or 0
        )

        # 检查是否全部完成
        pending = routing.operations.filter(status__in=['PENDING', 'IN_PROGRESS']).count()
        if pending == 0:
            routing.status = 'COMPLETED'

        routing.save()

        return Response(ProjectRoutingOperationSerializer(operation).data)
