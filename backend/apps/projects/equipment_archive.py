"""
设备档案管理模块 - 针对非标自动化行业
包含：设备铭牌、技术参数、维保记录、备件清单
"""
from django.db import models
from django.db.models import Sum, F
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin


# =============================================================================
# 模型定义
# =============================================================================

class EquipmentArchive(BaseModel):
    """设备档案"""
    STATUS_CHOICES = [
        ('MANUFACTURING', '生产中'),
        ('TESTING', '调试中'),
        ('DELIVERED', '已交付'),
        ('INSTALLED', '已安装'),
        ('RUNNING', '运行中'),
        ('MAINTENANCE', '维护中'),
        ('DECOMMISSIONED', '已报废'),
    ]
    
    EQUIPMENT_TYPE_CHOICES = [
        ('ASSEMBLY_LINE', '组装线'),
        ('TESTING_EQUIPMENT', '检测设备'),
        ('PROCESSING_EQUIPMENT', '加工设备'),
        ('HANDLING_EQUIPMENT', '搬运设备'),
        ('PACKAGING_EQUIPMENT', '包装设备'),
        ('INSPECTION_EQUIPMENT', '检查设备'),
        ('OTHER', '其他'),
    ]
    
    # 基本信息
    equipment_no = models.CharField(max_length=50, unique=True, verbose_name='设备编号')
    serial_number = models.CharField(max_length=100, unique=True, verbose_name='出厂序列号')
    name = models.CharField(max_length=200, verbose_name='设备名称')
    model = models.CharField(max_length=100, verbose_name='设备型号')
    equipment_type = models.CharField(max_length=30, choices=EQUIPMENT_TYPE_CHOICES, verbose_name='设备类型')
    
    # 关联信息
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='equipment_archives',
        verbose_name='所属项目'
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='equipment_archives',
        verbose_name='客户'
    )
    
    # 铭牌信息
    manufacturer = models.CharField(max_length=200, default='深圳市奥特迈智能装备有限公司', verbose_name='制造商')
    manufacture_date = models.DateField(verbose_name='制造日期')
    rated_power = models.CharField(max_length=50, blank=True, verbose_name='额定功率')
    rated_voltage = models.CharField(max_length=50, blank=True, verbose_name='额定电压')
    rated_current = models.CharField(max_length=50, blank=True, verbose_name='额定电流')
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='设备重量(kg)')
    dimensions = models.CharField(max_length=100, blank=True, verbose_name='外形尺寸(L×W×H)')
    
    # 技术参数
    technical_specs = models.JSONField(default=dict, blank=True, verbose_name='技术参数')
    performance_specs = models.JSONField(default=dict, blank=True, verbose_name='性能参数')
    
    # 质保信息
    warranty_start_date = models.DateField(null=True, blank=True, verbose_name='质保开始日期')
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='质保结束日期')
    warranty_terms = models.TextField(blank=True, verbose_name='质保条款')
    
    # 安装信息
    installation_address = models.TextField(blank=True, verbose_name='安装地址')
    installation_date = models.DateField(null=True, blank=True, verbose_name='安装日期')
    acceptance_date = models.DateField(null=True, blank=True, verbose_name='验收日期')
    
    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MANUFACTURING', verbose_name='状态')
    
    # 文档附件
    documents = models.JSONField(default=list, blank=True, verbose_name='技术文档')
    images = models.JSONField(default=list, blank=True, verbose_name='设备图片')
    
    # 备注
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'equipment_archive'
        verbose_name = '设备档案'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.equipment_no} - {self.name}"


class EquipmentMaintenancePlan(BaseModel):
    """设备保养计划"""
    FREQUENCY_CHOICES = [
        ('DAILY', '每日'),
        ('WEEKLY', '每周'),
        ('MONTHLY', '每月'),
        ('QUARTERLY', '每季度'),
        ('SEMI_ANNUAL', '每半年'),
        ('ANNUAL', '每年'),
    ]
    
    equipment = models.ForeignKey(
        EquipmentArchive,
        on_delete=models.CASCADE,
        related_name='maintenance_plans',
        verbose_name='设备'
    )
    name = models.CharField(max_length=200, verbose_name='保养项目名称')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, verbose_name='保养频率')
    description = models.TextField(verbose_name='保养内容')
    
    # 工时和费用
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='预计工时')
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='预计费用')
    
    # 提醒设置
    reminder_days = models.IntegerField(default=7, verbose_name='提前提醒天数')
    next_maintenance_date = models.DateField(null=True, blank=True, verbose_name='下次保养日期')
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'equipment_maintenance_plan'
        verbose_name = '设备保养计划'
        verbose_name_plural = verbose_name
        ordering = ['equipment', 'frequency']
    
    def __str__(self):
        return f"{self.equipment.equipment_no} - {self.name}"


class EquipmentMaintenanceRecord(BaseModel):
    """设备保养/维修记录"""
    TYPE_CHOICES = [
        ('PREVENTIVE', '预防性保养'),
        ('CORRECTIVE', '故障维修'),
        ('UPGRADE', '设备升级'),
        ('INSPECTION', '定期检查'),
    ]
    
    STATUS_CHOICES = [
        ('PLANNED', '已计划'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    equipment = models.ForeignKey(
        EquipmentArchive,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name='设备'
    )
    maintenance_plan = models.ForeignKey(
        EquipmentMaintenancePlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='records',
        verbose_name='保养计划'
    )
    
    record_no = models.CharField(max_length=50, verbose_name='记录编号')
    maintenance_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='维护类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED', verbose_name='状态')
    
    # 时间信息
    planned_date = models.DateField(verbose_name='计划日期')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    
    # 维护内容
    description = models.TextField(verbose_name='维护描述')
    findings = models.TextField(blank=True, verbose_name='检查发现')
    actions_taken = models.TextField(blank=True, verbose_name='处理措施')
    
    # 人员
    technician = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='maintenance_records',
        verbose_name='维护人员'
    )
    
    # 费用
    labor_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='工时')
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='人工费用')
    parts_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='备件费用')
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='总费用')
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'equipment_maintenance_record'
        verbose_name = '设备维护记录'
        verbose_name_plural = verbose_name
        ordering = ['-planned_date']
    
    def __str__(self):
        return f"{self.record_no} - {self.equipment.equipment_no}"


class EquipmentSparePart(BaseModel):
    """设备备件清单"""
    CRITICALITY_CHOICES = [
        ('HIGH', '高'),
        ('MEDIUM', '中'),
        ('LOW', '低'),
    ]
    
    equipment = models.ForeignKey(
        EquipmentArchive,
        on_delete=models.CASCADE,
        related_name='spare_parts',
        verbose_name='设备'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='equipment_spare_parts',
        verbose_name='物料'
    )
    
    part_no = models.CharField(max_length=100, verbose_name='备件编号')
    name = models.CharField(max_length=200, verbose_name='备件名称')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格型号')
    manufacturer = models.CharField(max_length=200, blank=True, verbose_name='生产厂家')
    
    # 数量和周期
    recommended_qty = models.IntegerField(default=1, verbose_name='建议备货数量')
    replacement_cycle = models.IntegerField(null=True, blank=True, verbose_name='更换周期(天)')
    lead_time = models.IntegerField(default=0, verbose_name='采购周期(天)')
    
    # 价格
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价')
    
    # 重要性
    criticality = models.CharField(max_length=10, choices=CRITICALITY_CHOICES, default='MEDIUM', verbose_name='重要性')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'equipment_spare_part'
        verbose_name = '设备备件'
        verbose_name_plural = verbose_name
        ordering = ['equipment', '-criticality']
    
    def __str__(self):
        return f"{self.part_no} - {self.name}"


# =============================================================================
# 序列化器
# =============================================================================

class EquipmentSparePartSerializer(serializers.ModelSerializer):
    criticality_display = serializers.CharField(source='get_criticality_display', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    
    class Meta:
        model = EquipmentSparePart
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class EquipmentMaintenancePlanSerializer(serializers.ModelSerializer):
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    
    class Meta:
        model = EquipmentMaintenancePlan
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class EquipmentMaintenanceRecordSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    
    class Meta:
        model = EquipmentMaintenanceRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class EquipmentArchiveSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_equipment_type_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    spare_parts = EquipmentSparePartSerializer(many=True, read_only=True)
    maintenance_plans = EquipmentMaintenancePlanSerializer(many=True, read_only=True)
    spare_part_count = serializers.SerializerMethodField()
    maintenance_record_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EquipmentArchive
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_spare_part_count(self, obj):
        return obj.spare_parts.count()
    
    def get_maintenance_record_count(self, obj):
        return obj.maintenance_records.count()


class EquipmentArchiveListSerializer(serializers.ModelSerializer):
    """列表用简化序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_equipment_type_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = EquipmentArchive
        fields = [
            'id', 'equipment_no', 'serial_number', 'name', 'model',
            'equipment_type', 'type_display', 'project', 'project_name',
            'customer', 'customer_name', 'manufacture_date', 'status',
            'status_display', 'warranty_end_date', 'created_at'
        ]


# =============================================================================
# 视图集
# =============================================================================

class EquipmentArchiveViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备档案管理"""
    permission_module = 'projects'
    permission_resource = 'equipment_archive'
    queryset = EquipmentArchive.objects.all()
    filterset_fields = ['project', 'customer', 'equipment_type', 'status', 'is_deleted']
    search_fields = ['equipment_no', 'serial_number', 'name', 'model']
    ordering_fields = ['equipment_no', 'manufacture_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EquipmentArchiveListSerializer
        return EquipmentArchiveSerializer
    
    def get_queryset(self):
        return super().get_queryset().select_related('project', 'customer')
    
    @action(detail=True, methods=['get'])
    def nameplate(self, request, pk=None):
        """获取设备铭牌信息"""
        equipment = self.get_object()
        nameplate_data = {
            'equipment_no': equipment.equipment_no,
            'serial_number': equipment.serial_number,
            'name': equipment.name,
            'model': equipment.model,
            'manufacturer': equipment.manufacturer,
            'manufacture_date': equipment.manufacture_date,
            'rated_power': equipment.rated_power,
            'rated_voltage': equipment.rated_voltage,
            'rated_current': equipment.rated_current,
            'weight': equipment.weight,
            'dimensions': equipment.dimensions,
        }
        return Response(nameplate_data)
    
    @action(detail=True, methods=['get'])
    def maintenance_history(self, request, pk=None):
        """获取设备维护历史"""
        equipment = self.get_object()
        records = equipment.maintenance_records.all().order_by('-planned_date')
        serializer = EquipmentMaintenanceRecordSerializer(records, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def spare_parts_list(self, request, pk=None):
        """获取设备备件清单"""
        equipment = self.get_object()
        parts = equipment.spare_parts.all()
        serializer = EquipmentSparePartSerializer(parts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def warranty_expiring(self, request):
        """获取即将过保的设备"""
        from datetime import date, timedelta
        days = int(request.query_params.get('days', 30))
        expiry_date = date.today() + timedelta(days=days)
        
        equipments = self.get_queryset().filter(
            warranty_end_date__lte=expiry_date,
            warranty_end_date__gte=date.today(),
            is_deleted=False
        )
        serializer = EquipmentArchiveListSerializer(equipments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """设备统计"""
        queryset = self.get_queryset().filter(is_deleted=False)
        
        stats = {
            'total': queryset.count(),
            'by_status': {},
            'by_type': {},
            'warranty_expiring_30_days': 0,
        }
        
        # 按状态统计
        for status_code, status_name in EquipmentArchive.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            stats['by_status'][status_code] = {'name': status_name, 'count': count}
        
        # 按类型统计
        for type_code, type_name in EquipmentArchive.EQUIPMENT_TYPE_CHOICES:
            count = queryset.filter(equipment_type=type_code).count()
            stats['by_type'][type_code] = {'name': type_name, 'count': count}
        
        # 即将过保
        from datetime import date, timedelta
        expiry_date = date.today() + timedelta(days=30)
        stats['warranty_expiring_30_days'] = queryset.filter(
            warranty_end_date__lte=expiry_date,
            warranty_end_date__gte=date.today()
        ).count()
        
        return Response(stats)


class EquipmentMaintenancePlanViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备保养计划管理"""
    permission_module = 'projects'
    permission_resource = 'equipment_maintenance_plan'
    queryset = EquipmentMaintenancePlan.objects.all()
    serializer_class = EquipmentMaintenancePlanSerializer
    filterset_fields = ['equipment', 'frequency', 'is_active', 'is_deleted']
    search_fields = ['name']
    ordering_fields = ['equipment', 'frequency', 'created_at']


class EquipmentMaintenanceRecordViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备维护记录管理"""
    permission_module = 'projects'
    permission_resource = 'equipment_maintenance_record'
    queryset = EquipmentMaintenanceRecord.objects.all()
    serializer_class = EquipmentMaintenanceRecordSerializer
    filterset_fields = ['equipment', 'maintenance_type', 'status', 'technician', 'is_deleted']
    search_fields = ['record_no', 'description']
    ordering_fields = ['planned_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始维护"""
        record = self.get_object()
        if record.status != 'PLANNED':
            return Response({'error': '只有已计划状态才能开始'}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone
        record.status = 'IN_PROGRESS'
        record.start_time = timezone.now()
        record.save()
        return Response(EquipmentMaintenanceRecordSerializer(record).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成维护"""
        record = self.get_object()
        if record.status != 'IN_PROGRESS':
            return Response({'error': '只有进行中状态才能完成'}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.utils import timezone
        record.status = 'COMPLETED'
        record.end_time = timezone.now()
        record.findings = request.data.get('findings', '')
        record.actions_taken = request.data.get('actions_taken', '')
        record.labor_hours = request.data.get('labor_hours', 0)
        record.labor_cost = request.data.get('labor_cost', 0)
        record.parts_cost = request.data.get('parts_cost', 0)
        record.total_cost = record.labor_cost + record.parts_cost
        record.save()
        
        # 更新保养计划的下次保养日期
        if record.maintenance_plan:
            plan = record.maintenance_plan
            from datetime import timedelta
            frequency_days = {
                'DAILY': 1, 'WEEKLY': 7, 'MONTHLY': 30,
                'QUARTERLY': 90, 'SEMI_ANNUAL': 180, 'ANNUAL': 365
            }
            days = frequency_days.get(plan.frequency, 30)
            plan.next_maintenance_date = timezone.now().date() + timedelta(days=days)
            plan.save()
        
        return Response(EquipmentMaintenanceRecordSerializer(record).data)


class EquipmentSparePartViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备备件管理"""
    permission_module = 'projects'
    permission_resource = 'equipment_spare_part'
    queryset = EquipmentSparePart.objects.all()
    serializer_class = EquipmentSparePartSerializer
    filterset_fields = ['equipment', 'criticality', 'is_deleted']
    search_fields = ['part_no', 'name', 'specification']
    ordering_fields = ['equipment', 'criticality', 'created_at']
