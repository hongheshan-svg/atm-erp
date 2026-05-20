"""
CAD集成模块
CAD Integration
SolidWorks、AutoCAD集成接口、BOM自动导入等
为桌面插件和API对接提供后端支持
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


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

# =====================
# CAD软件文件格式配置
# =====================

CAD_FILE_EXTENSIONS = {
    'SOLIDWORKS': {
        'part': ['.sldprt'],
        'assembly': ['.sldasm'],
        'drawing': ['.slddrw'],
        'export': ['.step', '.stp', '.iges', '.igs', '.x_t', '.x_b', '.stl'],
    },
    'AUTOCAD': {
        'drawing': ['.dwg', '.dxf'],
        'export': ['.pdf', '.dwf', '.dwfx'],
    },
    'INVENTOR': {
        'part': ['.ipt'],
        'assembly': ['.iam'],
        'drawing': ['.idw', '.dwg'],
        'export': ['.step', '.stp', '.iges', '.igs', '.stl'],
    },
    'CREO': {
        'part': ['.prt', '.prt.*'],  # Creo零件文件
        'assembly': ['.asm', '.asm.*'],  # Creo装配体
        'drawing': ['.drw', '.drw.*'],  # Creo工程图
        'manufacturing': ['.mfg', '.mfg.*'],  # 制造文件
        'format': ['.frm'],  # 格式文件
        'export': ['.step', '.stp', '.iges', '.igs', '.stl', '.jt', '.pvz'],
        'bom_export': ['.csv', '.xml', '.xlsx', '.bom'],  # BOM导出格式
    },
    'CATIA': {
        'part': ['.catpart'],
        'assembly': ['.catproduct'],
        'drawing': ['.catdrawing'],
        'export': ['.step', '.stp', '.iges', '.igs', '.stl', '.jt'],
    },
    'UG': {
        'part': ['.prt'],
        'assembly': ['.prt'],  # UG使用相同扩展名
        'drawing': ['.prt'],
        'export': ['.step', '.stp', '.iges', '.igs', '.stl', '.jt'],
    },
    'FUSION360': {
        'part': ['.f3d', '.f3z'],
        'export': ['.step', '.stp', '.iges', '.igs', '.stl', '.obj', '.3mf'],
    },
}

# Creo参数属性映射
CREO_PARAMETER_MAPPING = {
    # 基本参数
    'DESCRIPTION': 'part_name',
    'PART_NUMBER': 'part_number',
    'MATERIAL': 'material',
    'MASS': 'weight',
    'DENSITY': 'density',
    'VOLUME': 'volume',
    'SURFACE_AREA': 'surface_area',

    # 自定义参数
    'VENDOR': 'vendor',
    'COST': 'unit_cost',
    'REVISION': 'revision',
    'AUTHOR': 'designer',
    'CREATED_DATE': 'created_date',
    'MODIFIED_DATE': 'modified_date',

    # BOM相关
    'QTY': 'quantity',
    'UNIT': 'unit',
    'PROCUREMENT_TYPE': 'procurement_type',  # 自制/外购
    'MAKE_BUY': 'make_or_buy',
}


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
    def parse_creo_bom(file_path, bom_format='csv'):
        """
        解析Creo/Pro-E BOM
        
        支持的格式:
        - CSV: Creo导出的CSV格式BOM
        - XML: Creo导出的XML格式BOM
        - REP: Creo Rep文件(.rep)
        
        Creo BOM导出路径: 
        Info > BOM > Top Level / Indented / Multi-Level
        """
        items = []

        # 模拟Creo BOM数据结构
        # 实际实现需要根据Creo导出的具体格式解析
        if bom_format == 'csv':
            items = BOMParserService._parse_creo_csv(file_path)
        elif bom_format == 'xml':
            items = BOMParserService._parse_creo_xml(file_path)
        else:
            # 默认模拟数据
            items = [
                {
                    'level': 0,
                    'part_number': 'CREO-ASM-001',
                    'part_name': 'Creo主装配体',
                    'quantity': 1,
                    'unit': 'PCS',
                    'file_name': 'main_assembly.asm.1',
                    'type': 'ASSEMBLY',
                },
                {
                    'level': 1,
                    'part_number': 'CREO-PRT-001',
                    'part_name': '底板',
                    'quantity': 1,
                    'unit': 'PCS',
                    'material': 'AL6061-T6',
                    'file_name': 'base_plate.prt.5',
                    'type': 'PART',
                    'weight': 2.5,
                },
                {
                    'level': 1,
                    'part_number': 'CREO-PRT-002',
                    'part_name': '支架',
                    'quantity': 4,
                    'unit': 'PCS',
                    'material': 'SUS304',
                    'file_name': 'bracket.prt.3',
                    'type': 'PART',
                    'weight': 0.35,
                },
                {
                    'level': 1,
                    'part_number': 'CREO-SUB-001',
                    'part_name': '传动组件',
                    'quantity': 1,
                    'unit': 'SET',
                    'file_name': 'drive_unit.asm.2',
                    'type': 'SUBASSEMBLY',
                },
                {
                    'level': 2,
                    'part_number': 'CREO-PRT-003',
                    'part_name': '主动轴',
                    'quantity': 1,
                    'unit': 'PCS',
                    'material': '45#钢',
                    'file_name': 'drive_shaft.prt.4',
                    'type': 'PART',
                    'weight': 1.2,
                    'parent_row': 3,
                },
            ]

        return items

    @staticmethod
    def _parse_creo_csv(file_path):
        """解析Creo导出的CSV格式BOM"""
        items = []
        # 实际实现:
        # import csv
        # with open(file_path, 'r', encoding='utf-8') as f:
        #     reader = csv.DictReader(f)
        #     for row in reader:
        #         items.append({
        #             'level': int(row.get('Level', 0)),
        #             'part_number': row.get('Part Number', ''),
        #             'part_name': row.get('Description', ''),
        #             'quantity': float(row.get('Qty', 1)),
        #             'unit': row.get('Unit', 'PCS'),
        #             'material': row.get('Material', ''),
        #             'file_name': row.get('File Name', ''),
        #         })
        return items

    @staticmethod
    def _parse_creo_xml(file_path):
        """解析Creo导出的XML格式BOM"""
        items = []
        # 实际实现:
        # import xml.etree.ElementTree as ET
        # tree = ET.parse(file_path)
        # root = tree.getroot()
        # for component in root.findall('.//Component'):
        #     items.append({...})
        return items

    @staticmethod
    def parse_creo_parameters(prt_file_path):
        """
        提取Creo零件参数
        
        Creo参数来源:
        - 模型参数 (Model Parameters)
        - 族表参数 (Family Table)
        - 关系式 (Relations)
        """
        # 模拟提取的参数
        parameters = {
            'DESCRIPTION': '示例零件',
            'PART_NUMBER': 'CREO-PRT-001',
            'MATERIAL': 'AL6061-T6',
            'MASS': 2.5,
            'REVISION': 'A',
            'AUTHOR': 'Designer',
            'VENDOR': '',
            'MAKE_BUY': 'MAKE',
        }

        # 转换为系统字段
        result = {}
        for creo_param, sys_field in CREO_PARAMETER_MAPPING.items():
            if creo_param in parameters:
                result[sys_field] = parameters[creo_param]

        return result

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

    @staticmethod
    def get_supported_extensions(software_type):
        """获取指定CAD软件支持的文件扩展名"""
        return CAD_FILE_EXTENSIONS.get(software_type, {})


class CreoIntegrationService:
    """Creo集成服务"""

    @staticmethod
    def get_default_config():
        """获取Creo默认配置"""
        return {
            'software_type': 'CREO',
            'name': 'PTC Creo',
            'supported_extensions': CAD_FILE_EXTENSIONS['CREO'],
            'parameter_mapping': CREO_PARAMETER_MAPPING,
            'bom_export_formats': ['csv', 'xml', 'xlsx'],
            'supported_versions': [
                'Creo 10.0',
                'Creo 9.0',
                'Creo 8.0',
                'Creo 7.0',
                'Creo 6.0',
                'Creo 5.0',
                'Creo 4.0',
                'Creo 3.0',
                'Pro/ENGINEER Wildfire 5.0',
                'Pro/ENGINEER Wildfire 4.0',
            ],
            'plugin_info': {
                'name': 'ERP Creo Connector',
                'description': 'Creo插件，支持BOM导出、参数同步、文件上传',
                'features': [
                    '一键导出多级BOM',
                    '参数自动映射',
                    '文件版本管理',
                    '族表实例展开',
                    '简化表示支持',
                ],
            },
        }

    @staticmethod
    def validate_creo_file(file_path):
        """验证Creo文件格式"""
        import os
        ext = os.path.splitext(file_path)[1].lower()

        all_extensions = []
        for ext_list in CAD_FILE_EXTENSIONS['CREO'].values():
            all_extensions.extend(ext_list)

        # Creo文件可能带版本号，如 .prt.5, .asm.12
        base_ext = ext.split('.')[0] if '.' in ext else ext

        return ext in all_extensions or base_ext in ['.prt', '.asm', '.drw', '.mfg']

    @staticmethod
    def extract_version_from_filename(filename):
        """从Creo文件名提取版本号"""
        import re
        # Creo文件命名: part_name.prt.5 或 assembly.asm.12
        match = re.search(r'\.(\d+)$', filename)
        if match:
            return int(match.group(1))
        return 1


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

    @action(detail=False, methods=['get'])
    def supported_extensions(self, request):
        """获取各CAD软件支持的文件扩展名"""
        return Response(CAD_FILE_EXTENSIONS)

    @action(detail=False, methods=['get'])
    def creo_config(self, request):
        """获取Creo默认配置"""
        return Response(CreoIntegrationService.get_default_config())

    @action(detail=False, methods=['post'])
    def init_creo(self, request):
        """初始化Creo软件配置"""
        config = CreoIntegrationService.get_default_config()
        version = request.data.get('version', 'Creo 10.0')

        # 检查是否已存在
        existing = CADSoftware.objects.filter(
            software_type='CREO',
            is_deleted=False
        ).first()

        if existing:
            return Response({
                'message': 'Creo配置已存在',
                'data': CADSoftwareSerializer(existing).data
            })

        # 创建Creo配置
        creo = CADSoftware.objects.create(
            name=f'PTC {version}',
            software_type='CREO',
            version=version,
            supported_extensions=config['supported_extensions'],
            description=f"PTC {version} - 支持零件(.prt)、装配体(.asm)、工程图(.drw)文件",
            is_active=True,
            created_by=request.user
        )

        # 创建默认属性映射
        for creo_prop, sys_field in CREO_PARAMETER_MAPPING.items():
            CADPropertyMapping.objects.create(
                software=creo,
                cad_property=creo_prop,
                system_field=sys_field,
                target_model='Material',
                is_required=creo_prop in ['PART_NUMBER', 'DESCRIPTION'],
                created_by=request.user
            )

        return Response({
            'message': 'Creo配置初始化成功',
            'data': CADSoftwareSerializer(creo).data
        })


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
        """提取BOM（自动识别CAD软件类型）"""
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

        # 根据软件类型选择解析器
        parser = BOMParserService()
        software_type = cad_file.software.software_type
        bom_format = request.data.get('format', 'csv')

        if software_type == 'CREO':
            parsed_items = parser.parse_creo_bom(cad_file.file_path, bom_format)
        elif software_type == 'SOLIDWORKS':
            parsed_items = parser.parse_solidworks_bom(cad_file.file_path)
        else:
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
