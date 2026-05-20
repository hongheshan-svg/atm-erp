"""
设备点检记录
Equipment Inspection Records
支持日常点检、定期巡检、异常记录等
"""

from datetime import date, timedelta

from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class InspectionTemplate(BaseModel):
    """
    点检模板
    """

    TEMPLATE_TYPES = [
        ('DAILY', '日常点检'),
        ('WEEKLY', '周点检'),
        ('MONTHLY', '月点检'),
        ('SPECIAL', '专项点检'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    name = models.CharField(max_length=200, verbose_name='模板名称')
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, default='DAILY', verbose_name='模板类型')

    # 适用设备类型
    equipment_type = models.CharField(max_length=100, blank=True, verbose_name='适用设备类型')

    description = models.TextField(blank=True, verbose_name='说明')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'project_inspection_template'
        verbose_name = '点检模板'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class InspectionItem(BaseModel):
    """
    点检项目
    """

    # 覆盖 BaseModel 的字段以避免 related_name 冲突
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_inspection_items_created',
        verbose_name='创建人',
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_inspection_items_updated',
        verbose_name='更新人',
    )

    CHECK_TYPES = [
        ('VISUAL', '目视检查'),
        ('MEASURE', '测量检查'),
        ('FUNCTION', '功能检查'),
        ('LISTEN', '听音检查'),
        ('SMELL', '嗅觉检查'),
        ('TOUCH', '触感检查'),
    ]

    RESULT_TYPES = [
        ('OK_NG', '正常/异常'),
        ('NUMBER', '数值'),
        ('TEXT', '文本'),
        ('SELECT', '选择'),
    ]

    template = models.ForeignKey(
        InspectionTemplate, on_delete=models.CASCADE, related_name='items', verbose_name='所属模板'
    )

    code = models.CharField(max_length=50, verbose_name='项目编码')
    name = models.CharField(max_length=200, verbose_name='项目名称')
    check_type = models.CharField(max_length=20, choices=CHECK_TYPES, default='VISUAL', verbose_name='检查方式')
    result_type = models.CharField(max_length=20, choices=RESULT_TYPES, default='OK_NG', verbose_name='结果类型')

    # 标准值（用于数值类型）
    standard_value = models.CharField(max_length=100, blank=True, verbose_name='标准值')
    upper_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='上限')
    lower_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='下限')
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')

    # 选项（用于选择类型）
    options = models.JSONField(default=list, blank=True, verbose_name='选项列表')

    # 检查点位/部位
    check_point = models.CharField(max_length=200, blank=True, verbose_name='检查点位')

    is_required = models.BooleanField(default=True, verbose_name='必检项')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'project_inspection_item'
        verbose_name = '点检项目'
        verbose_name_plural = verbose_name
        ordering = ['template', 'sort_order']

    def __str__(self):
        return f'{self.template.name} - {self.name}'


class InspectionRecord(BaseModel):
    """
    点检记录
    """

    STATUS_CHOICES = [
        ('PENDING', '待点检'),
        ('IN_PROGRESS', '点检中'),
        ('COMPLETED', '已完成'),
        ('ABNORMAL', '有异常'),
    ]

    record_no = models.CharField(max_length=50, unique=True, verbose_name='记录编号')

    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='inspection_records', verbose_name='设备'
    )
    template = models.ForeignKey(
        InspectionTemplate, on_delete=models.SET_NULL, null=True, related_name='records', verbose_name='使用模板'
    )

    # 点检时间
    inspection_date = models.DateField(verbose_name='点检日期')
    shift = models.CharField(
        max_length=20,
        choices=[
            ('DAY', '白班'),
            ('NIGHT', '夜班'),
            ('ALL', '全天'),
        ],
        default='DAY',
        verbose_name='班次',
    )
    start_time = models.TimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.TimeField(null=True, blank=True, verbose_name='结束时间')

    # 点检人
    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='equipment_inspections',
        verbose_name='点检人',
    )

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # 统计
    total_items = models.IntegerField(default=0, verbose_name='总项目数')
    checked_items = models.IntegerField(default=0, verbose_name='已检项目数')
    normal_items = models.IntegerField(default=0, verbose_name='正常项目数')
    abnormal_items = models.IntegerField(default=0, verbose_name='异常项目数')

    # 备注
    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'project_inspection_record'
        verbose_name = '点检记录'
        verbose_name_plural = verbose_name
        ordering = ['-inspection_date', '-created_at']

    def __str__(self):
        return f'{self.record_no} - {self.equipment.name}'

    def update_statistics(self):
        """更新统计"""
        results = self.results.filter(is_deleted=False)
        self.total_items = results.count()
        self.checked_items = results.exclude(result_value='').count()
        self.normal_items = results.filter(is_normal=True).count()
        self.abnormal_items = results.filter(is_normal=False).exclude(result_value='').count()

        if self.abnormal_items > 0:
            self.status = 'ABNORMAL'
        elif self.checked_items >= self.total_items and self.total_items > 0:
            self.status = 'COMPLETED'
        elif self.checked_items > 0:
            self.status = 'IN_PROGRESS'

        self.save()


class InspectionResult(BaseModel):
    """
    点检结果
    """

    record = models.ForeignKey(
        InspectionRecord, on_delete=models.CASCADE, related_name='results', verbose_name='点检记录'
    )
    item = models.ForeignKey(
        InspectionItem, on_delete=models.SET_NULL, null=True, related_name='results', verbose_name='点检项目'
    )

    # 结果
    result_value = models.CharField(max_length=500, blank=True, verbose_name='结果值')
    is_normal = models.BooleanField(default=True, verbose_name='是否正常')

    # 异常信息
    abnormal_desc = models.TextField(blank=True, verbose_name='异常描述')
    abnormal_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', '轻微'),
            ('MEDIUM', '一般'),
            ('HIGH', '严重'),
            ('CRITICAL', '紧急'),
        ],
        blank=True,
        verbose_name='异常等级',
    )

    # 处理
    is_handled = models.BooleanField(default=False, verbose_name='已处理')
    handle_notes = models.TextField(blank=True, verbose_name='处理说明')
    handled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_inspections',
        verbose_name='处理人',
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')

    # 附件（照片等）
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    check_time = models.DateTimeField(null=True, blank=True, verbose_name='检查时间')

    class Meta:
        db_table = 'project_inspection_result'
        verbose_name = '点检结果'
        verbose_name_plural = verbose_name
        ordering = ['record', 'item__sort_order']

    def __str__(self):
        return f'{self.record.record_no} - {self.item.name if self.item else ""}'


# =====================
# Serializers
# =====================


class InspectionItemSerializer(serializers.ModelSerializer):
    check_type_display = serializers.CharField(source='get_check_type_display', read_only=True)
    result_type_display = serializers.CharField(source='get_result_type_display', read_only=True)

    class Meta:
        model = InspectionItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class InspectionTemplateSerializer(serializers.ModelSerializer):
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    items = InspectionItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = InspectionTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_item_count(self, obj):
        return obj.items.filter(is_deleted=False).count()


class InspectionResultSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_check_type = serializers.CharField(source='item.check_type', read_only=True)
    item_result_type = serializers.CharField(source='item.result_type', read_only=True)
    item_standard = serializers.CharField(source='item.standard_value', read_only=True)
    handled_by_name = serializers.CharField(source='handled_by.get_full_name', read_only=True)

    class Meta:
        model = InspectionResult
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class InspectionRecordSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    results = InspectionResultSerializer(many=True, read_only=True)

    class Meta:
        model = InspectionRecord
        fields = '__all__'
        read_only_fields = [
            'created_by',
            'updated_by',
            'total_items',
            'checked_items',
            'normal_items',
            'abnormal_items',
        ]


class InspectionRecordListSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = InspectionRecord
        fields = [
            'id',
            'record_no',
            'equipment',
            'equipment_name',
            'template',
            'template_name',
            'inspection_date',
            'shift',
            'inspector',
            'inspector_name',
            'status',
            'status_display',
            'total_items',
            'checked_items',
            'normal_items',
            'abnormal_items',
            'created_at',
        ]


# =====================
# ViewSets
# =====================


class InspectionTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """点检模板管理"""

    queryset = InspectionTemplate.objects.filter(is_deleted=False)
    serializer_class = InspectionTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template_type', 'is_active', 'equipment_type']
    search_fields = ['code', 'name']

    @action(detail=True, methods=['post'])
    def add_items(self, request, pk=None):
        """添加点检项"""
        template = self.get_object()
        items = request.data.get('items', [])

        created = []
        for item_data in items:
            item = InspectionItem.objects.create(template=template, **item_data, created_by=request.user)
            created.append(InspectionItemSerializer(item).data)

        return Response(created)

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None):
        """复制模板"""
        template = self.get_object()
        new_code = request.data.get('code', f'{template.code}_copy')
        new_name = request.data.get('name', f'{template.name}(副本)')

        new_template = InspectionTemplate.objects.create(
            code=new_code,
            name=new_name,
            template_type=template.template_type,
            equipment_type=template.equipment_type,
            description=template.description,
            created_by=request.user,
        )

        for item in template.items.filter(is_deleted=False):
            InspectionItem.objects.create(
                template=new_template,
                code=item.code,
                name=item.name,
                check_type=item.check_type,
                result_type=item.result_type,
                standard_value=item.standard_value,
                upper_limit=item.upper_limit,
                lower_limit=item.lower_limit,
                unit=item.unit,
                options=item.options,
                check_point=item.check_point,
                is_required=item.is_required,
                sort_order=item.sort_order,
                created_by=request.user,
            )

        return Response(self.get_serializer(new_template).data)


class InspectionItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """点检项管理"""

    queryset = InspectionItem.objects.filter(is_deleted=False)
    serializer_class = InspectionItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'check_type', 'result_type', 'is_required']


class InspectionRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """点检记录管理"""

    queryset = InspectionRecord.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'template', 'status', 'inspector', 'inspection_date']
    search_fields = ['record_no', 'equipment__name']
    ordering_fields = ['inspection_date', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return InspectionRecordListSerializer
        return InspectionRecordSerializer

    @action(detail=False, methods=['post'])
    def create_from_template(self, request):
        """从模板创建点检记录"""
        equipment_id = request.data.get('equipment_id')
        template_id = request.data.get('template_id')
        inspection_date = request.data.get('inspection_date', date.today().isoformat())

        if not equipment_id or not template_id:
            return Response({'error': '请选择设备和模板'}, status=400)

        template = InspectionTemplate.objects.get(id=template_id)

        # 生成记录编号
        record_no = f'INS-{date.today().strftime("%Y%m%d")}-{str(timezone.now().timestamp())[-4:]}'

        record = InspectionRecord.objects.create(
            record_no=record_no,
            equipment_id=equipment_id,
            template=template,
            inspection_date=inspection_date,
            inspector=request.user,
            created_by=request.user,
        )

        # 创建点检结果
        for item in template.items.filter(is_deleted=False):
            InspectionResult.objects.create(record=record, item=item, created_by=request.user)

        record.update_statistics()

        return Response(InspectionRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def submit_result(self, request, pk=None):
        """提交点检结果"""
        record = self.get_object()
        results = request.data.get('results', [])

        for result_data in results:
            result_id = result_data.get('id')
            if result_id:
                result = InspectionResult.objects.get(id=result_id, record=record)
                result.result_value = result_data.get('result_value', '')
                result.is_normal = result_data.get('is_normal', True)
                result.abnormal_desc = result_data.get('abnormal_desc', '')
                result.abnormal_level = result_data.get('abnormal_level', '')
                result.check_time = timezone.now()
                result.save()

        record.update_statistics()

        return Response(InspectionRecordSerializer(record).data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """今日点检"""
        records = self.get_queryset().filter(inspection_date=date.today())
        return Response(InspectionRecordListSerializer(records, many=True).data)

    @action(detail=False, methods=['get'])
    def my_inspections(self, request):
        """我的点检"""
        records = self.get_queryset().filter(inspector=request.user)[:50]
        return Response(InspectionRecordListSerializer(records, many=True).data)

    @action(detail=False, methods=['get'])
    def abnormal_records(self, request):
        """异常记录"""
        records = self.get_queryset().filter(status='ABNORMAL')
        return Response(InspectionRecordListSerializer(records, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """点检统计"""

        qs = self.get_queryset()

        # 今日统计
        today_records = qs.filter(inspection_date=date.today())
        today_stats = {
            'total': today_records.count(),
            'completed': today_records.filter(status='COMPLETED').count(),
            'abnormal': today_records.filter(status='ABNORMAL').count(),
            'pending': today_records.filter(status='PENDING').count(),
        }

        # 本周趋势
        week_start = date.today() - timedelta(days=date.today().weekday())
        weekly = (
            qs.filter(inspection_date__gte=week_start)
            .values('inspection_date')
            .annotate(total=Count('id'), abnormal=Count('id', filter=Q(status='ABNORMAL')))
            .order_by('inspection_date')
        )

        return Response({'today': today_stats, 'weekly_trend': list(weekly)})


class InspectionResultViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """点检结果管理"""

    queryset = InspectionResult.objects.filter(is_deleted=False)
    serializer_class = InspectionResultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['record', 'is_normal', 'is_handled']

    @action(detail=True, methods=['post'])
    def handle(self, request, pk=None):
        """处理异常"""
        result = self.get_object()
        result.is_handled = True
        result.handle_notes = request.data.get('notes', '')
        result.handled_by = request.user
        result.handled_at = timezone.now()
        result.save()
        return Response(self.get_serializer(result).data)

    @action(detail=False, methods=['get'])
    def unhandled_abnormal(self, request):
        """未处理的异常"""
        results = self.get_queryset().filter(is_normal=False, is_handled=False).select_related('record', 'item')
        return Response(self.get_serializer(results, many=True).data)
