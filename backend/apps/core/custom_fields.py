"""
自定义字段配置
Custom Fields Configuration
支持为各业务模块动态添加自定义字段
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin
from apps.core.permissions import IsSystemAdminOrReadOnly


class CustomFieldDefinition(BaseModel):
    """
    自定义字段定义
    """

    FIELD_TYPES = [
        ('TEXT', '单行文本'),
        ('TEXTAREA', '多行文本'),
        ('NUMBER', '数字'),
        ('DECIMAL', '小数'),
        ('DATE', '日期'),
        ('DATETIME', '日期时间'),
        ('SELECT', '下拉选择'),
        ('MULTISELECT', '多选'),
        ('CHECKBOX', '复选框'),
        ('RADIO', '单选'),
        ('FILE', '文件'),
        ('IMAGE', '图片'),
        ('URL', '链接'),
        ('EMAIL', '邮箱'),
        ('PHONE', '电话'),
        ('USER', '用户选择'),
        ('DEPARTMENT', '部门选择'),
    ]

    # 支持自定义字段的模型
    SUPPORTED_MODELS = [
        ('projects.Project', '项目'),
        ('masterdata.Customer', '客户'),
        ('masterdata.Supplier', '供应商'),
        ('masterdata.Material', '物料'),
        ('sales.SalesOrder', '销售订单'),
        ('sales.SalesContract', '销售合同'),
        ('purchase.PurchaseOrder', '采购订单'),
        ('purchase.PurchaseContract', '采购合同'),
        ('inventory.StockIn', '入库单'),
        ('inventory.StockOut', '出库单'),
    ]

    # 关联的模型
    model_name = models.CharField(max_length=100, verbose_name='所属模型', help_text='格式：app_label.model_name')

    # 字段基本信息
    field_code = models.CharField(max_length=50, verbose_name='字段编码')
    field_name = models.CharField(max_length=100, verbose_name='字段名称')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='TEXT', verbose_name='字段类型')
    description = models.TextField(blank=True, verbose_name='字段描述')

    # 字段配置
    is_required = models.BooleanField(default=False, verbose_name='是否必填')
    is_unique = models.BooleanField(default=False, verbose_name='是否唯一')
    is_searchable = models.BooleanField(default=True, verbose_name='是否可搜索')
    is_visible = models.BooleanField(default=True, verbose_name='是否显示')
    is_editable = models.BooleanField(default=True, verbose_name='是否可编辑')

    # 显示配置
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    group_name = models.CharField(max_length=50, blank=True, verbose_name='分组名称')
    placeholder = models.CharField(max_length=200, blank=True, verbose_name='占位提示')
    help_text = models.CharField(max_length=500, blank=True, verbose_name='帮助文本')

    # 验证配置
    validation_rules = models.JSONField(
        default=dict, blank=True, verbose_name='验证规则', help_text='如：{"min": 0, "max": 100, "pattern": "^[A-Z]+$"}'
    )

    # 选项配置（用于下拉、单选、多选类型）
    options = models.JSONField(
        default=list, blank=True, verbose_name='选项列表', help_text='格式：[{"value": "1", "label": "选项1"}, ...]'
    )

    # 默认值
    default_value = models.TextField(blank=True, verbose_name='默认值')

    class Meta:
        db_table = 'core_custom_field_definition'
        verbose_name = '自定义字段定义'
        verbose_name_plural = verbose_name
        ordering = ['model_name', 'sort_order', 'field_code']
        unique_together = ['model_name', 'field_code']

    def __str__(self):
        return f'{self.model_name}.{self.field_code} - {self.field_name}'


class CustomFieldValue(BaseModel):
    """
    自定义字段值
    使用GenericForeignKey关联到任意模型实例
    """

    field_definition = models.ForeignKey(
        CustomFieldDefinition, on_delete=models.CASCADE, related_name='values', verbose_name='字段定义'
    )

    # 通用外键
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # 存储值（使用JSON格式以支持各种类型）
    value_text = models.TextField(blank=True, verbose_name='文本值')
    value_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, verbose_name='数字值')
    value_date = models.DateTimeField(null=True, blank=True, verbose_name='日期值')
    value_json = models.JSONField(default=dict, blank=True, verbose_name='JSON值')
    value_file = models.FileField(upload_to='custom_fields/', blank=True, null=True, verbose_name='文件值')

    class Meta:
        db_table = 'core_custom_field_value'
        verbose_name = '自定义字段值'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['field_definition', 'content_type', 'object_id']),
        ]
        unique_together = ['field_definition', 'content_type', 'object_id']

    def __str__(self):
        return f'{self.field_definition.field_code}: {self.get_value()}'

    def get_value(self):
        """获取字段值"""
        field_type = self.field_definition.field_type

        if field_type in ('TEXT', 'TEXTAREA', 'URL', 'EMAIL', 'PHONE'):
            return self.value_text
        elif field_type in ('NUMBER',):
            return int(self.value_number) if self.value_number else None
        elif field_type in ('DECIMAL',):
            return float(self.value_number) if self.value_number else None
        elif field_type in ('DATE', 'DATETIME'):
            return self.value_date
        elif field_type in ('SELECT', 'RADIO'):
            return self.value_text
        elif field_type in ('MULTISELECT', 'CHECKBOX'):
            return self.value_json if self.value_json else []
        elif field_type in ('FILE', 'IMAGE'):
            return self.value_file.url if self.value_file else None
        elif field_type in ('USER', 'DEPARTMENT'):
            return self.value_json
        else:
            return self.value_text

    def set_value(self, value):
        """设置字段值"""
        field_type = self.field_definition.field_type

        if field_type in ('TEXT', 'TEXTAREA', 'URL', 'EMAIL', 'PHONE', 'SELECT', 'RADIO'):
            self.value_text = str(value) if value else ''
        elif field_type in ('NUMBER', 'DECIMAL'):
            self.value_number = value if value is not None else None
        elif field_type in ('DATE', 'DATETIME'):
            self.value_date = value
        elif field_type in ('MULTISELECT', 'CHECKBOX', 'USER', 'DEPARTMENT'):
            self.value_json = value if isinstance(value, (list, dict)) else []
        elif field_type in ('FILE', 'IMAGE'):
            if value:
                self.value_file = value
        else:
            self.value_text = str(value) if value else ''


# =====================
# Custom Field Service
# =====================


class CustomFieldService:
    """自定义字段服务"""

    @staticmethod
    def get_fields_for_model(model_name: str, include_hidden: bool = False):
        """获取模型的所有自定义字段定义"""
        qs = CustomFieldDefinition.objects.filter(model_name=model_name, is_deleted=False)
        if not include_hidden:
            qs = qs.filter(is_visible=True)
        return qs.order_by('sort_order', 'field_code')

    @staticmethod
    def get_values_for_object(obj) -> dict:
        """获取对象的所有自定义字段值"""
        content_type = ContentType.objects.get_for_model(obj)
        model_name = f'{content_type.app_label}.{content_type.model.capitalize()}'

        # 获取字段定义
        field_defs = CustomFieldDefinition.objects.filter(model_name=model_name, is_deleted=False, is_visible=True)

        # 获取已有值
        existing_values = CustomFieldValue.objects.filter(
            content_type=content_type, object_id=obj.pk, field_definition__in=field_defs
        ).select_related('field_definition')

        value_map = {v.field_definition_id: v for v in existing_values}

        result = {}
        for field_def in field_defs:
            if field_def.id in value_map:
                result[field_def.field_code] = value_map[field_def.id].get_value()
            else:
                # 返回默认值
                result[field_def.field_code] = field_def.default_value or None

        return result

    @staticmethod
    def set_values_for_object(obj, values: dict, user=None):
        """设置对象的自定义字段值"""
        content_type = ContentType.objects.get_for_model(obj)
        model_name = f'{content_type.app_label}.{content_type.model.capitalize()}'

        # 获取字段定义
        field_defs = {
            fd.field_code: fd for fd in CustomFieldDefinition.objects.filter(model_name=model_name, is_deleted=False)
        }

        for field_code, value in values.items():
            if field_code not in field_defs:
                continue

            field_def = field_defs[field_code]

            # 检查是否可编辑
            if not field_def.is_editable:
                continue

            # 创建或更新值
            field_value, created = CustomFieldValue.objects.update_or_create(
                field_definition=field_def,
                content_type=content_type,
                object_id=obj.pk,
            )
            if created and user:
                field_value.created_by = user
            field_value.set_value(value)
            if user:
                field_value.updated_by = user
            field_value.save()

    @staticmethod
    def validate_values(model_name: str, values: dict) -> list:
        """验证自定义字段值"""
        errors = []

        field_defs = {
            fd.field_code: fd for fd in CustomFieldDefinition.objects.filter(model_name=model_name, is_deleted=False)
        }

        for field_code, field_def in field_defs.items():
            value = values.get(field_code)

            # 必填验证
            if field_def.is_required and not value:
                errors.append(f'{field_def.field_name} 不能为空')
                continue

            if value:
                # 类型验证
                if field_def.field_type in ('NUMBER', 'DECIMAL'):
                    try:
                        float(value)
                    except (TypeError, ValueError):
                        errors.append(f'{field_def.field_name} 必须是数字')

                # 选项验证
                if field_def.field_type in ('SELECT', 'RADIO'):
                    valid_values = [opt.get('value') for opt in field_def.options]
                    if value not in valid_values:
                        errors.append(f'{field_def.field_name} 的值无效')

                # 自定义规则验证
                rules = field_def.validation_rules or {}

                if 'min' in rules and field_def.field_type in ('NUMBER', 'DECIMAL'):
                    if float(value) < rules['min']:
                        errors.append(f'{field_def.field_name} 不能小于 {rules["min"]}')

                if 'max' in rules and field_def.field_type in ('NUMBER', 'DECIMAL'):
                    if float(value) > rules['max']:
                        errors.append(f'{field_def.field_name} 不能大于 {rules["max"]}')

                if 'minLength' in rules and field_def.field_type in ('TEXT', 'TEXTAREA'):
                    if len(str(value)) < rules['minLength']:
                        errors.append(f'{field_def.field_name} 长度不能少于 {rules["minLength"]} 个字符')

                if 'maxLength' in rules and field_def.field_type in ('TEXT', 'TEXTAREA'):
                    if len(str(value)) > rules['maxLength']:
                        errors.append(f'{field_def.field_name} 长度不能超过 {rules["maxLength"]} 个字符')

                if 'pattern' in rules:
                    import re

                    if not re.match(rules['pattern'], str(value)):
                        errors.append(f'{field_def.field_name} 格式不正确')

        return errors

    @staticmethod
    def get_field_groups(model_name: str) -> list:
        """获取字段分组"""
        field_defs = CustomFieldDefinition.objects.filter(
            model_name=model_name, is_deleted=False, is_visible=True
        ).order_by('sort_order', 'field_code')

        groups = {}
        for fd in field_defs:
            group = fd.group_name or '基本信息'
            if group not in groups:
                groups[group] = []
            groups[group].append(fd)

        return [{'name': name, 'fields': fields} for name, fields in groups.items()]


# =====================
# Serializers
# =====================


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    field_type_display = serializers.CharField(source='get_field_type_display', read_only=True)

    class Meta:
        model = CustomFieldDefinition
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CustomFieldDefinitionListSerializer(serializers.ModelSerializer):
    field_type_display = serializers.CharField(source='get_field_type_display', read_only=True)

    class Meta:
        model = CustomFieldDefinition
        fields = [
            'id',
            'model_name',
            'field_code',
            'field_name',
            'field_type',
            'field_type_display',
            'is_required',
            'is_visible',
            'sort_order',
            'group_name',
        ]


class CustomFieldValueSerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source='field_definition.field_code', read_only=True)
    field_name = serializers.CharField(source='field_definition.field_name', read_only=True)
    field_type = serializers.CharField(source='field_definition.field_type', read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = CustomFieldValue
        fields = [
            'id',
            'field_definition',
            'field_code',
            'field_name',
            'field_type',
            'value',
            'created_at',
            'updated_at',
        ]

    def get_value(self, obj):
        return obj.get_value()


# =====================
# ViewSets
# =====================


class CustomFieldDefinitionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    自定义字段定义管理
    """

    permission_module = 'system'
    permission_resource = 'custom_field_definition'
    allow_authenticated_read = True
    queryset = CustomFieldDefinition.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated, IsSystemAdminOrReadOnly]
    filterset_fields = ['model_name', 'field_type', 'is_required', 'is_visible']
    search_fields = ['field_code', 'field_name', 'description']
    ordering_fields = ['model_name', 'sort_order', 'field_code']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomFieldDefinitionListSerializer
        return CustomFieldDefinitionSerializer

    @action(detail=False, methods=['get'])
    def supported_models(self, request):
        """获取支持自定义字段的模型列表"""
        return Response([{'value': m[0], 'label': m[1]} for m in CustomFieldDefinition.SUPPORTED_MODELS])

    @action(detail=False, methods=['get'])
    def field_types(self, request):
        """获取支持的字段类型"""
        return Response([{'value': t[0], 'label': t[1]} for t in CustomFieldDefinition.FIELD_TYPES])

    @action(detail=False, methods=['get'])
    def by_model(self, request):
        """获取指定模型的自定义字段"""
        model_name = request.query_params.get('model')
        if not model_name:
            return Response({'error': '请提供模型名称'}, status=400)

        fields = CustomFieldService.get_fields_for_model(model_name)
        return Response(CustomFieldDefinitionListSerializer(fields, many=True).data)

    @action(detail=False, methods=['get'])
    def groups(self, request):
        """获取字段分组"""
        model_name = request.query_params.get('model')
        if not model_name:
            return Response({'error': '请提供模型名称'}, status=400)

        groups = CustomFieldService.get_field_groups(model_name)
        result = []
        for group in groups:
            result.append(
                {'name': group['name'], 'fields': CustomFieldDefinitionListSerializer(group['fields'], many=True).data}
            )
        return Response(result)

    @action(detail=True, methods=['post'])
    def toggle_visible(self, request, pk=None):
        """切换显示状态"""
        instance = self.get_object()
        instance.is_visible = not instance.is_visible
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=['post'])
    def batch_sort(self, request):
        """批量排序"""
        items = request.data.get('items', [])
        for item in items:
            CustomFieldDefinition.objects.filter(id=item['id']).update(sort_order=item['sort_order'])
        return Response({'success': True})


class CustomFieldValueViewSet(PermissionMixin, viewsets.ModelViewSet):
    """
    自定义字段值管理
    """

    permission_module = 'system'
    permission_resource = 'custom_field_value'
    queryset = CustomFieldValue.objects.all()
    serializer_class = CustomFieldValueSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def for_object(self, request):
        """获取对象的自定义字段值"""
        model_name = request.query_params.get('model')
        object_id = request.query_params.get('object_id')

        if not model_name or not object_id:
            return Response({'error': '请提供模型名称和对象ID'}, status=400)

        try:
            app_label, model = model_name.lower().split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            model_class = content_type.model_class()
            obj = model_class.objects.get(pk=object_id)
        except (ValueError, ContentType.DoesNotExist, Exception) as e:
            return Response({'error': f'无法找到对象: {str(e)}'}, status=404)

        values = CustomFieldService.get_values_for_object(obj)

        # 获取字段定义
        field_defs = CustomFieldService.get_fields_for_model(model_name)

        result = []
        for fd in field_defs:
            result.append(
                {
                    'field_code': fd.field_code,
                    'field_name': fd.field_name,
                    'field_type': fd.field_type,
                    'field_type_display': fd.get_field_type_display(),
                    'is_required': fd.is_required,
                    'options': fd.options,
                    'placeholder': fd.placeholder,
                    'help_text': fd.help_text,
                    'value': values.get(fd.field_code),
                }
            )

        return Response(result)

    @action(detail=False, methods=['post'])
    def save_values(self, request):
        """保存对象的自定义字段值"""
        model_name = request.data.get('model')
        object_id = request.data.get('object_id')
        values = request.data.get('values', {})

        if not model_name or not object_id:
            return Response({'error': '请提供模型名称和对象ID'}, status=400)

        # 验证
        errors = CustomFieldService.validate_values(model_name, values)
        if errors:
            return Response({'errors': errors}, status=400)

        try:
            app_label, model = model_name.lower().split('.')
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            model_class = content_type.model_class()
            obj = model_class.objects.get(pk=object_id)
        except (ValueError, ContentType.DoesNotExist, Exception) as e:
            return Response({'error': f'无法找到对象: {str(e)}'}, status=404)

        CustomFieldService.set_values_for_object(obj, values, request.user)

        return Response({'success': True})
