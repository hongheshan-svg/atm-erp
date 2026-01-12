"""
CAD集成模块
CAD Integration
SolidWorks、AutoCAD集成接口、BOM自动导入等
为桌面插件和API对接提供后端支持
"""
from datetime import date, datetime
from django.db import models
from django.db.models import Count, Q
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class CADSoftware(BaseModel):
    """CAD软件配置"""
    SOFTWARE_TYPE_CHOICES = [
        ('SOLIDWORKS', 'SolidWorks'),
        ('AUTOCAD', 'AutoCAD'),
        ('INVENTOR', 'Inventor'),
        ('CREO', 'Creo/ProE'),
        ('CATIA', 'CATIA'),
        ('UG', 'UG/NX'),
        ('FUSION360', 'Fusion 360'),
        ('OTHER', '其他'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='名称')
    software_type = models.CharField(
        max_length=20,
        choices=SOFTWARE_TYPE_CHOICES,
        verbose_name='软件类型'
    )
    version = models.CharField(max_length=50, blank=True, verbose_name='版本')
    
    # 插件信息
    plugin_version = models.CharField(max_length=50, blank=True, verbose_name='插件版本')
    plugin_download_url = models.CharField(max_length=500, blank=True, verbose_name='插件下载地址')
    
    # API配置
    api_endpoint = models.CharField(max_length=500, blank=True, verbose_name='API端点')
    api_key = models.CharField(max_length=200, blank=True, verbose_name='API密钥')
    
    # 文件格式配置
    supported_extensions = models.JSONField(default=list, blank=True, verbose_name='支持的扩展名')
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='描述')
    
    class Meta:
        db_table = 'plm_cad_software'
        verbose_name = 'CAD软件配置'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.name} {self.version}"


class CADSession(BaseModel):
    """CAD会话"""
    STATUS_CHOICES = [
        ('ACTIVE', '活跃'),
        ('IDLE', '空闲'),
        ('CLOSED', '已关闭'),
    ]
    
    software = models.ForeignKey(
        CADSoftware,
        on_delete=models.PROTECT,
        related_name='sessions',
        verbose_name='CAD软件'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cad_sessions',
        verbose_name='用户'
    )
    
    session_id = models.CharField(max_length=100, unique=True, verbose_name='会话ID')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name='状态'
    )
    
    # 机器信息
    machine_name = models.CharField(max_length=100, blank=True, verbose_name='机器名')
    machine_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    
    # 会话信息
    started_at = models.DateTimeField(default=timezone.now, verbose_name='开始时间')
    last_activity_at = models.DateTimeField(default=timezone.now, verbose_name='最后活动时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    
    # 当前文件
    current_file = models.CharField(max_length=500, blank=True, verbose_name='当前文件')
    
    class Meta:
        db_table = 'plm_cad_session'
        verbose_name = 'CAD会话'
        verbose_name_plural = verbose_name
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.software.name}"


class CADFile(BaseModel):
    """CAD文件"""
    FILE_TYPE_CHOICES = [
        ('PART', '零件'),
        ('ASSEMBLY', '装配体'),
        ('DRAWING', '工程图'),
        ('SHEET', '钣金'),
        ('WELDMENT', '焊件'),
        ('OTHER', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('UPLOADING', '上传中'),
        ('PROCESSING', '处理中'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
    ]
    
    software = models.ForeignKey(
        CADSoftware,
        on_delete=models.PROTECT,
        related_name='files',
        verbose_name='CAD软件'
    )
    
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小')
    file_hash = models.CharField(max_length=64, blank=True, verbose_name='文件哈希')
    
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        default='PART',
        verbose_name='文件类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='UPLOADING',
        verbose_name='状态'
    )
    
    # 版本信息
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    revision = models.CharField(max_length=20, blank=True, verbose_name='修订号')
    
    # 关联项目
    project_id = models.IntegerField(null=True, blank=True, verbose_name='项目ID')
    drawing_id = models.IntegerField(null=True, blank=True, verbose_name='图纸ID')
    
    # 元数据
    metadata = models.JSONField(default=dict, blank=True, verbose_name='元数据')
    
    # 预览
    thumbnail_path = models.CharField(max_length=500, blank=True, verbose_name='缩略图路径')
    preview_path = models.CharField(max_length=500, blank=True, verbose_name='预览图路径')
    
    # 上传信息
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_cad_files',
        verbose_name='上传者'
    )
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='上传时间')
    
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    class Meta:
        db_table = 'plm_cad_file'
        verbose_name = 'CAD文件'
        verbose_name_plural = verbose_name
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.file_name


class CADBOMImport(BaseModel):
    """CAD BOM导入记录"""
    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('PARSING', '解析中'),
        ('REVIEWING', '待确认'),
        ('IMPORTING', '导入中'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
        ('CANCELLED', '已取消'),
    ]
    
    SOURCE_TYPE_CHOICES = [
        ('SOLIDWORKS', 'SolidWorks装配体'),
        ('AUTOCAD', 'AutoCAD属性'),
        ('EXCEL', 'Excel文件'),
        ('CSV', 'CSV文件'),
        ('API', 'API导入'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='导入名称')
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default='SOLIDWORKS',
        verbose_name='来源类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 来源文件
    source_file = models.ForeignKey(
        CADFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_imports',
        verbose_name='来源CAD文件'
    )
    source_file_path = models.CharField(max_length=500, blank=True, verbose_name='来源文件路径')
    
    # 目标项目/BOM
    project_id = models.IntegerField(null=True, blank=True, verbose_name='目标项目ID')
    bom_id = models.IntegerField(null=True, blank=True, verbose_name='目标BOM ID')
    
    # 解析结果
    parsed_data = models.JSONField(default=list, blank=True, verbose_name='解析数据')
    total_items = models.IntegerField(default=0, verbose_name='总行数')
    
    # 导入结果
    imported_count = models.IntegerField(default=0, verbose_name='已导入')
    skipped_count = models.IntegerField(default=0, verbose_name='已跳过')
    error_count = models.IntegerField(default=0, verbose_name='错误数')
    
    # 映射配置
    field_mapping = models.JSONField(default=dict, blank=True, verbose_name='字段映射')
    import_options = models.JSONField(default=dict, blank=True, verbose_name='导入选项')
    
    # 时间信息
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    error_log = models.TextField(blank=True, verbose_name='错误日志')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'plm_cad_bom_import'
        verbose_name = 'CAD BOM导入'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class CADBOMItem(BaseModel):
    """CAD BOM导入项"""
    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('MATCHED', '已匹配'),
        ('NEW', '新物料'),
        ('IMPORTED', '已导入'),
        ('SKIPPED', '已跳过'),
        ('ERROR', '错误'),
    ]
    
    bom_import = models.ForeignKey(
        CADBOMImport,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='导入记录'
    )
    
    # 原始数据
    row_number = models.IntegerField(default=0, verbose_name='行号')
    raw_data = models.JSONField(default=dict, verbose_name='原始数据')
    
    # 解析后的物料信息
    part_number = models.CharField(max_length=100, blank=True, verbose_name='物料编码')
    part_name = models.CharField(max_length=200, blank=True, verbose_name='物料名称')
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1, verbose_name='数量')
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')
    
    # 额外属性
    material = models.CharField(max_length=100, blank=True, verbose_name='材料')
    weight = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True, verbose_name='重量')
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 层级
    level = models.IntegerField(default=0, verbose_name='层级')
    parent_row = models.IntegerField(null=True, blank=True, verbose_name='父行号')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 匹配结果
    matched_material_id = models.IntegerField(null=True, blank=True, verbose_name='匹配的物料ID')
    match_score = models.FloatField(default=0, verbose_name='匹配度')
    
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    class Meta:
        db_table = 'plm_cad_bom_item'
        verbose_name = 'CAD BOM导入项'
        verbose_name_plural = verbose_name
        ordering = ['bom_import', 'row_number']


class CADPropertyMapping(BaseModel):
    """CAD属性映射"""
    software = models.ForeignKey(
        CADSoftware,
        on_delete=models.CASCADE,
        related_name='property_mappings',
        verbose_name='CAD软件'
    )
    
    cad_property = models.CharField(max_length=100, verbose_name='CAD属性名')
    system_field = models.CharField(max_length=100, verbose_name='系统字段')
    target_model = models.CharField(max_length=100, verbose_name='目标模型')
    
    # 值转换
    transform_type = models.CharField(max_length=50, blank=True, verbose_name='转换类型')
    transform_config = models.JSONField(default=dict, blank=True, verbose_name='转换配置')
    
    is_required = models.BooleanField(default=False, verbose_name='是否必填')
    default_value = models.CharField(max_length=200, blank=True, verbose_name='默认值')
    
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'plm_cad_property_mapping'
        verbose_name = 'CAD属性映射'
        verbose_name_plural = verbose_name
        ordering = ['software', 'sort_order']
        unique_together = ['software', 'cad_property', 'target_model']


# =====================
# BOM Parser Service
# =====================

class BOMParserService:
    """BOM解析服务"""
    
    @staticmethod
    def parse_solidworks_bom(file_path):
        """解析SolidWorks BOM"""
        # 模拟解析
        # 实际需要读取SolidWorks导出的XML或Excel
        return [
            {
                'level': 0,
                'part_number': 'ASM-001',
                'part_name': '主装配体',
                'quantity': 1,
                'unit': 'PCS',
            },
            {
                'level': 1,
                'part_number': 'PART-001',
                'part_name': '零件1',
                'quantity': 2,
                'unit': 'PCS',
                'material': '45#钢',
            },
        ]
    
    @staticmethod
    def parse_excel_bom(file_path, field_mapping):
        """解析Excel BOM"""
        # 实际使用openpyxl或pandas
        return []
    
    @staticmethod
    def match_materials(items, threshold=0.8):
        """匹配系统物料"""
        # 实际需要查询物料主数据并进行模糊匹配
        for item in items:
            item['matched_material_id'] = None
            item['match_score'] = 0
            item['status'] = 'NEW'
        return items


# =====================
# Serializers
# =====================

class CADSoftwareSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_software_type_display', read_only=True)
    
    class Meta:
        model = CADSoftware
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
        extra_kwargs = {
            'api_key': {'write_only': True},
        }


class CADSessionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    software_name = serializers.CharField(source='software.name', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = CADSession
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'session_id']


class CADFileSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_file_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    software_name = serializers.CharField(source='software.name', read_only=True)
    
    class Meta:
        model = CADFile
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'uploaded_at', 'file_hash']


class CADBOMItemSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CADBOMItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CADBOMImportSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items = CADBOMItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = CADBOMImport
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'parsed_data', 'total_items',
                           'imported_count', 'skipped_count', 'error_count']


class CADPropertyMappingSerializer(serializers.ModelSerializer):
    software_name = serializers.CharField(source='software.name', read_only=True)
    
    class Meta:
        model = CADPropertyMapping
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================

class CADSoftwareViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """CAD软件管理"""
    queryset = CADSoftware.objects.filter(is_deleted=False)
    serializer_class = CADSoftwareSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['software_type', 'is_active']
    search_fields = ['name']


class CADSessionViewSet(viewsets.ModelViewSet):
    """CAD会话管理"""
    queryset = CADSession.objects.filter(is_deleted=False)
    serializer_class = CADSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['software', 'user', 'status']
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """注册会话（插件调用）"""
        import uuid
        
        session = CADSession.objects.create(
            software_id=request.data.get('software_id'),
            user=request.user,
            session_id=str(uuid.uuid4()),
            machine_name=request.data.get('machine_name', ''),
            machine_ip=request.META.get('REMOTE_ADDR'),
            created_by=request.user
        )
        
        return Response(self.get_serializer(session).data)
    
    @action(detail=True, methods=['post'])
    def heartbeat(self, request, pk=None):
        """心跳更新"""
        session = self.get_object()
        session.last_activity_at = timezone.now()
        session.current_file = request.data.get('current_file', '')
        session.save()
        return Response({'status': 'ok'})
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭会话"""
        session = self.get_object()
        session.status = 'CLOSED'
        session.closed_at = timezone.now()
        session.save()
        return Response(self.get_serializer(session).data)


class CADFileViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """CAD文件管理"""
    queryset = CADFile.objects.filter(is_deleted=False)
    serializer_class = CADFileSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['software', 'file_type', 'status', 'project_id']
    search_fields = ['file_name']
    
    @action(detail=True, methods=['post'])
    def extract_bom(self, request, pk=None):
        """提取BOM"""
        cad_file = self.get_object()
        
        if cad_file.file_type not in ['ASSEMBLY']:
            return Response({'error': '只能从装配体提取BOM'}, status=400)
        
        # 创建BOM导入记录
        bom_import = CADBOMImport.objects.create(
            name=f'从{cad_file.file_name}导入BOM',
            source_type=cad_file.software.software_type,
            source_file=cad_file,
            project_id=cad_file.project_id,
            created_by=request.user
        )
        
        # 解析BOM
        parser = BOMParserService()
        parsed_items = parser.parse_solidworks_bom(cad_file.file_path)
        
        # 创建BOM项
        for i, item in enumerate(parsed_items):
            CADBOMItem.objects.create(
                bom_import=bom_import,
                row_number=i + 1,
                raw_data=item,
                part_number=item.get('part_number', ''),
                part_name=item.get('part_name', ''),
                quantity=item.get('quantity', 1),
                unit=item.get('unit', 'PCS'),
                material=item.get('material', ''),
                level=item.get('level', 0),
                created_by=request.user
            )
        
        bom_import.total_items = len(parsed_items)
        bom_import.status = 'REVIEWING'
        bom_import.save()
        
        return Response(CADBOMImportSerializer(bom_import).data)


class CADBOMImportViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """CAD BOM导入管理"""
    queryset = CADBOMImport.objects.filter(is_deleted=False)
    serializer_class = CADBOMImportSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['source_type', 'status', 'project_id']
    search_fields = ['name']
    
    @action(detail=True, methods=['post'])
    def match_materials(self, request, pk=None):
        """匹配物料"""
        bom_import = self.get_object()
        
        items = list(bom_import.items.values())
        matched = BOMParserService.match_materials(items)
        
        for item_data in matched:
            bom_import.items.filter(row_number=item_data.get('row_number', 0)).update(
                matched_material_id=item_data.get('matched_material_id'),
                match_score=item_data.get('match_score', 0),
                status=item_data.get('status', 'PENDING')
            )
        
        return Response(self.get_serializer(bom_import).data)
    
    @action(detail=True, methods=['post'])
    def confirm_import(self, request, pk=None):
        """确认导入"""
        bom_import = self.get_object()
        
        if bom_import.status != 'REVIEWING':
            return Response({'error': '当前状态无法导入'}, status=400)
        
        bom_import.status = 'IMPORTING'
        bom_import.started_at = timezone.now()
        bom_import.save()
        
        imported = 0
        skipped = 0
        errors = 0
        
        for item in bom_import.items.all():
            try:
                # TODO: 实际导入到BOM
                # 1. 如果matched_material_id存在，使用已有物料
                # 2. 如果是新物料，创建物料并添加到BOM
                
                if item.status == 'SKIPPED':
                    skipped += 1
                else:
                    item.status = 'IMPORTED'
                    item.save()
                    imported += 1
            except Exception as e:
                item.status = 'ERROR'
                item.error_message = str(e)
                item.save()
                errors += 1
        
        bom_import.imported_count = imported
        bom_import.skipped_count = skipped
        bom_import.error_count = errors
        bom_import.status = 'COMPLETED' if errors == 0 else 'FAILED'
        bom_import.completed_at = timezone.now()
        bom_import.save()
        
        return Response(self.get_serializer(bom_import).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消导入"""
        bom_import = self.get_object()
        
        if bom_import.status in ['COMPLETED', 'IMPORTING']:
            return Response({'error': '无法取消'}, status=400)
        
        bom_import.status = 'CANCELLED'
        bom_import.save()
        return Response(self.get_serializer(bom_import).data)


class CADPropertyMappingViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """CAD属性映射管理"""
    queryset = CADPropertyMapping.objects.filter(is_deleted=False)
    serializer_class = CADPropertyMappingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['software', 'target_model']
