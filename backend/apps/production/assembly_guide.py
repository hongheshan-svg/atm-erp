"""
3D装配指导模块
3D Assembly Guide Module

功能：
- 3D模型/动画关联
- 装配步骤可视化
- BOM关联展示
- 装配工时记录
"""

from django.db import models
from django.db.models import Sum
from django.utils import timezone
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


class AssemblyGuide(BaseModel):
    """装配指导书"""

    guide_code = models.CharField(max_length=50, unique=True, verbose_name='指导书编码')
    name = models.CharField(max_length=200, verbose_name='名称')

    # 关联产品/BOM
    product = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assembly_guides',
        verbose_name='产品',
    )
    bom = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assembly_guides',
        verbose_name='关联BOM',
    )

    # 3D模型
    model_file = models.FileField(upload_to='assembly/models/', blank=True, verbose_name='3D模型文件')
    model_url = models.URLField(blank=True, verbose_name='3D模型链接')
    model_format = models.CharField(
        max_length=20,
        choices=[
            ('STEP', 'STEP'),
            ('IGES', 'IGES'),
            ('STL', 'STL'),
            ('OBJ', 'OBJ'),
            ('GLTF', 'glTF'),
            ('FBX', 'FBX'),
            ('OTHER', '其他'),
        ],
        blank=True,
        verbose_name='模型格式',
    )

    # 版本控制
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    is_current = models.BooleanField(default=True, verbose_name='当前版本')

    # 装配信息
    total_steps = models.IntegerField(default=0, verbose_name='总步骤数')
    estimated_time_minutes = models.IntegerField(default=0, verbose_name='预计工时(分钟)')
    difficulty_level = models.CharField(
        max_length=20,
        choices=[
            ('EASY', '简单'),
            ('MEDIUM', '中等'),
            ('HARD', '困难'),
            ('EXPERT', '专家'),
        ],
        default='MEDIUM',
        verbose_name='难度等级',
    )

    # 工具和材料
    required_tools = models.JSONField(default=list, blank=True, verbose_name='所需工具')
    required_materials = models.JSONField(default=list, blank=True, verbose_name='所需材料')
    safety_notes = models.TextField(blank=True, verbose_name='安全注意事项')

    description = models.TextField(blank=True, verbose_name='描述')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('REVIEW', '评审中'),
            ('APPROVED', '已批准'),
            ('OBSOLETE', '已废弃'),
        ],
        default='DRAFT',
        verbose_name='状态',
    )

    class Meta:
        db_table = 'assembly_guide'
        verbose_name = '装配指导书'
        verbose_name_plural = verbose_name
        ordering = ['guide_code']

    def __str__(self):
        return f'{self.guide_code} - {self.name}'

    def update_step_count(self):
        """更新步骤数"""
        self.total_steps = self.steps.filter(is_deleted=False).count()
        self.estimated_time_minutes = (
            self.steps.filter(is_deleted=False).aggregate(total=Sum('estimated_minutes'))['total'] or 0
        )
        self.save(update_fields=['total_steps', 'estimated_time_minutes'])


class AssemblyStep(BaseModel):
    """装配步骤"""

    guide = models.ForeignKey(AssemblyGuide, on_delete=models.CASCADE, related_name='steps', verbose_name='装配指导书')

    # 步骤信息
    step_number = models.IntegerField(verbose_name='步骤号')
    title = models.CharField(max_length=200, verbose_name='步骤标题')
    description = models.TextField(verbose_name='操作说明')

    # 3D视图
    camera_position = models.JSONField(default=dict, blank=True, verbose_name='相机位置')
    highlighted_parts = models.JSONField(default=list, blank=True, verbose_name='高亮零件')
    animation_data = models.JSONField(default=dict, blank=True, verbose_name='动画数据')

    # 关联零件
    parts = models.ManyToManyField(
        'masterdata.Item', through='AssemblyStepPart', related_name='assembly_steps', verbose_name='相关零件'
    )

    # 工时
    estimated_minutes = models.IntegerField(default=5, verbose_name='预计时间(分钟)')

    # 图片和视频
    images = models.JSONField(default=list, blank=True, verbose_name='图片')
    video_url = models.URLField(blank=True, verbose_name='视频链接')

    # 检验点
    is_checkpoint = models.BooleanField(default=False, verbose_name='检验点')
    checkpoint_items = models.JSONField(default=list, blank=True, verbose_name='检验项目')

    # 工具
    required_tools = models.JSONField(default=list, blank=True, verbose_name='所需工具')

    # 注意事项
    warnings = models.TextField(blank=True, verbose_name='警告提示')
    tips = models.TextField(blank=True, verbose_name='操作技巧')

    class Meta:
        db_table = 'assembly_step'
        verbose_name = '装配步骤'
        verbose_name_plural = verbose_name
        unique_together = ['guide', 'step_number']
        ordering = ['guide', 'step_number']

    def __str__(self):
        return f'{self.guide.guide_code}-{self.step_number:03d}: {self.title}'


class AssemblyStepPart(BaseModel):
    """装配步骤零件"""

    step = models.ForeignKey(AssemblyStep, on_delete=models.CASCADE, related_name='step_parts', verbose_name='装配步骤')
    part = models.ForeignKey(
        'masterdata.Item', on_delete=models.CASCADE, related_name='step_usages', verbose_name='零件'
    )

    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='数量')

    # 3D定位
    position = models.JSONField(default=dict, blank=True, verbose_name='安装位置')
    orientation = models.JSONField(default=dict, blank=True, verbose_name='安装方向')

    notes = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'assembly_step_part'
        verbose_name = '装配步骤零件'
        verbose_name_plural = verbose_name
        ordering = ['step', 'id']


class AssemblySession(BaseModel):
    """装配作业记录"""

    guide = models.ForeignKey(
        AssemblyGuide, on_delete=models.CASCADE, related_name='sessions', verbose_name='装配指导书'
    )

    session_no = models.CharField(max_length=50, unique=True, verbose_name='作业编号')

    # 关联生产计划
    production_plan = models.ForeignKey(
        'production.ProductionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assembly_sessions',
        verbose_name='生产计划',
    )

    # 操作员
    operator = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='assembly_sessions', verbose_name='操作员'
    )

    # 时间
    started_at = models.DateTimeField(verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    # 进度
    current_step = models.IntegerField(default=1, verbose_name='当前步骤')
    completed_steps = models.IntegerField(default=0, verbose_name='已完成步骤')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('IN_PROGRESS', '进行中'),
            ('PAUSED', '暂停'),
            ('COMPLETED', '已完成'),
            ('ABORTED', '已中止'),
        ],
        default='IN_PROGRESS',
        verbose_name='状态',
    )

    # 实际工时
    actual_time_minutes = models.IntegerField(default=0, verbose_name='实际工时(分钟)')

    # 质量
    issues_found = models.IntegerField(default=0, verbose_name='发现问题数')
    rework_count = models.IntegerField(default=0, verbose_name='返工次数')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'assembly_session'
        verbose_name = '装配作业'
        verbose_name_plural = verbose_name
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.session_no}'

    def save(self, *args, **kwargs):
        if not self.session_no:
            from apps.core.models import CodeRule

            self.session_no = CodeRule.generate_code('ASSY')
        super().save(*args, **kwargs)


class AssemblyStepRecord(BaseModel):
    """装配步骤记录"""

    session = models.ForeignKey(
        AssemblySession, on_delete=models.CASCADE, related_name='step_records', verbose_name='装配作业'
    )
    step = models.ForeignKey(AssemblyStep, on_delete=models.CASCADE, related_name='records', verbose_name='装配步骤')

    # 时间
    started_at = models.DateTimeField(verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    duration_minutes = models.IntegerField(default=0, verbose_name='耗时(分钟)')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待执行'),
            ('IN_PROGRESS', '进行中'),
            ('COMPLETED', '已完成'),
            ('SKIPPED', '已跳过'),
            ('FAILED', '失败'),
        ],
        default='PENDING',
        verbose_name='状态',
    )

    # 检验结果
    checkpoint_passed = models.BooleanField(null=True, blank=True, verbose_name='检验通过')
    checkpoint_results = models.JSONField(default=dict, blank=True, verbose_name='检验结果')

    # 问题记录
    issues = models.TextField(blank=True, verbose_name='问题记录')
    photos = models.JSONField(default=list, blank=True, verbose_name='照片')

    class Meta:
        db_table = 'assembly_step_record'
        verbose_name = '装配步骤记录'
        verbose_name_plural = verbose_name
        unique_together = ['session', 'step']
        ordering = ['step__step_number']

    def save(self, *args, **kwargs):
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_minutes = int(delta.total_seconds() / 60)
        super().save(*args, **kwargs)


# =============================================================================
# 序列化器
# =============================================================================


class AssemblyStepPartSerializer(serializers.ModelSerializer):
    part_code = serializers.CharField(source='part.code', read_only=True)
    part_name = serializers.CharField(source='part.name', read_only=True)

    class Meta:
        model = AssemblyStepPart
        fields = '__all__'


class AssemblyStepSerializer(serializers.ModelSerializer):
    step_parts = AssemblyStepPartSerializer(many=True, read_only=True)

    class Meta:
        model = AssemblyStep
        fields = '__all__'


class AssemblyGuideSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    steps = AssemblyStepSerializer(many=True, read_only=True)

    class Meta:
        model = AssemblyGuide
        fields = '__all__'


class AssemblyGuideListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_level_display', read_only=True)

    class Meta:
        model = AssemblyGuide
        fields = [
            'id',
            'guide_code',
            'name',
            'product',
            'product_name',
            'version',
            'is_current',
            'total_steps',
            'estimated_time_minutes',
            'difficulty_level',
            'difficulty_display',
            'status',
            'status_display',
        ]


class AssemblyStepRecordSerializer(serializers.ModelSerializer):
    step_number = serializers.IntegerField(source='step.step_number', read_only=True)
    step_title = serializers.CharField(source='step.title', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AssemblyStepRecord
        fields = '__all__'


class AssemblySessionSerializer(serializers.ModelSerializer):
    guide_name = serializers.CharField(source='guide.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    step_records = AssemblyStepRecordSerializer(many=True, read_only=True)
    progress_rate = serializers.SerializerMethodField()

    class Meta:
        model = AssemblySession
        fields = '__all__'
        read_only_fields = ['session_no']

    def get_progress_rate(self, obj):
        if obj.guide.total_steps > 0:
            return round(obj.completed_steps / obj.guide.total_steps * 100, 1)
        return 0


# =============================================================================
# 视图集
# =============================================================================


class AssemblyGuideViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """装配指导书管理"""

    permission_module = 'production'
    permission_resource = 'assembly_guide'
    queryset = AssemblyGuide.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['product', 'status', 'difficulty_level', 'is_current']
    search_fields = ['guide_code', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return AssemblyGuideListSerializer
        return AssemblyGuideSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准指导书"""
        guide = self.get_object()
        guide.status = 'APPROVED'
        guide.save()
        guide.update_step_count()
        return Response(AssemblyGuideSerializer(guide).data)

    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """创建新版本"""
        original = self.get_object()

        new_version = f'{float(original.version) + 0.1:.1f}'

        new_guide = AssemblyGuide.objects.create(
            guide_code=f'{original.guide_code}_V{new_version}',
            name=original.name,
            product=original.product,
            bom=original.bom,
            version=new_version,
            is_current=True,
            difficulty_level=original.difficulty_level,
            required_tools=original.required_tools,
            required_materials=original.required_materials,
            safety_notes=original.safety_notes,
            description=original.description,
            created_by=request.user,
        )

        # 设置原版本为非当前
        original.is_current = False
        original.save()

        # 复制步骤
        for step in original.steps.filter(is_deleted=False):
            new_step = AssemblyStep.objects.create(
                guide=new_guide,
                step_number=step.step_number,
                title=step.title,
                description=step.description,
                camera_position=step.camera_position,
                highlighted_parts=step.highlighted_parts,
                animation_data=step.animation_data,
                estimated_minutes=step.estimated_minutes,
                images=step.images,
                video_url=step.video_url,
                is_checkpoint=step.is_checkpoint,
                checkpoint_items=step.checkpoint_items,
                required_tools=step.required_tools,
                warnings=step.warnings,
                tips=step.tips,
                created_by=request.user,
            )

            # 复制零件
            for sp in step.step_parts.filter(is_deleted=False):
                AssemblyStepPart.objects.create(
                    step=new_step,
                    part=sp.part,
                    quantity=sp.quantity,
                    position=sp.position,
                    orientation=sp.orientation,
                    notes=sp.notes,
                    created_by=request.user,
                )

        new_guide.update_step_count()

        return Response(AssemblyGuideSerializer(new_guide).data)


class AssemblyStepViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """装配步骤管理"""

    permission_module = 'production'
    permission_resource = 'assembly_step'
    queryset = AssemblyStep.objects.filter(is_deleted=False)
    serializer_class = AssemblyStepSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['guide', 'is_checkpoint']

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        instance.guide.update_step_count()

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.request.user)
        instance.guide.update_step_count()


class AssemblySessionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """装配作业管理"""

    permission_module = 'production'
    permission_resource = 'assembly_session'
    queryset = AssemblySession.objects.filter(is_deleted=False)
    serializer_class = AssemblySessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['guide', 'operator', 'status']
    ordering_fields = ['started_at', 'actual_time_minutes']

    @action(detail=True, methods=['post'])
    def start_step(self, request, pk=None):
        """开始步骤"""
        session = self.get_object()
        step_id = request.data.get('step_id')

        record, created = AssemblyStepRecord.objects.get_or_create(
            session=session,
            step_id=step_id,
            defaults={'started_at': timezone.now(), 'status': 'IN_PROGRESS', 'created_by': request.user},
        )

        if not created:
            record.started_at = timezone.now()
            record.status = 'IN_PROGRESS'
            record.save()

        return Response(AssemblyStepRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def complete_step(self, request, pk=None):
        """完成步骤"""
        session = self.get_object()
        step_id = request.data.get('step_id')

        try:
            record = AssemblyStepRecord.objects.get(session=session, step_id=step_id)
        except AssemblyStepRecord.DoesNotExist:
            return Response({'error': '步骤记录不存在'}, status=404)

        record.completed_at = timezone.now()
        record.status = 'COMPLETED'
        record.checkpoint_passed = request.data.get('checkpoint_passed')
        record.checkpoint_results = request.data.get('checkpoint_results', {})
        record.issues = request.data.get('issues', '')
        record.save()

        # 更新作业进度
        session.completed_steps = session.step_records.filter(status='COMPLETED').count()
        session.current_step = record.step.step_number + 1
        session.actual_time_minutes = session.step_records.aggregate(total=Sum('duration_minutes'))['total'] or 0

        if record.issues:
            session.issues_found += 1

        session.save()

        return Response(AssemblyStepRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成作业"""
        session = self.get_object()
        session.status = 'COMPLETED'
        session.completed_at = timezone.now()
        session.save()
        return Response(AssemblySessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """暂停作业"""
        session = self.get_object()
        session.status = 'PAUSED'
        session.save()
        return Response(AssemblySessionSerializer(session).data)

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """恢复作业"""
        session = self.get_object()
        session.status = 'IN_PROGRESS'
        session.save()
        return Response(AssemblySessionSerializer(session).data)
