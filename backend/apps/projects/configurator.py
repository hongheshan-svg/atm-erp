"""
产品配置器模块
Product Configurator
PLM核心功能 - 参数化配置、自动BOM生成
"""
from datetime import date, datetime
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class ProductTemplate(BaseModel):
    """产品模板"""
    name = models.CharField(max_length=200, verbose_name='模板名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    
    category = models.ForeignKey(
        'masterdata.ItemCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_templates',
        verbose_name='产品分类'
    )
    
    description = models.TextField(blank=True, verbose_name='描述')
    image = models.CharField(max_length=500, blank=True, verbose_name='产品图片')
    
    # 基础BOM模板
    base_bom = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_templates',
        verbose_name='基础BOM'
    )
    
    # 基础价格
    base_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='基础价格'
    )
    
    # 预估工期
    base_lead_time = models.IntegerField(default=30, verbose_name='基础交期(天)')
    
    is_active = models.BooleanField(default=True, verbose_name='启用')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    
    class Meta:
        db_table = 'plm_product_template'
        verbose_name = '产品模板'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f'{self.code} - {self.name}'


class ConfigParameter(BaseModel):
    """配置参数定义"""
    PARAM_TYPES = [
        ('SELECT', '选择型'),
        ('NUMBER', '数值型'),
        ('TEXT', '文本型'),
        ('BOOL', '开关型'),
        ('RANGE', '范围型'),
    ]
    
    template = models.ForeignKey(
        ProductTemplate,
        on_delete=models.CASCADE,
        related_name='parameters',
        verbose_name='产品模板'
    )
    
    name = models.CharField(max_length=100, verbose_name='参数名称')
    code = models.CharField(max_length=50, verbose_name='参数编码')
    param_type = models.CharField(
        max_length=20,
        choices=PARAM_TYPES,
        default='SELECT',
        verbose_name='参数类型'
    )
    
    # 默认值
    default_value = models.CharField(max_length=200, blank=True, verbose_name='默认值')
    
    # 数值型范围
    min_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='最小值'
    )
    max_value = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='最大值'
    )
    step = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='步长'
    )
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')
    
    # 说明
    description = models.TextField(blank=True, verbose_name='参数说明')
    help_text = models.CharField(max_length=500, blank=True, verbose_name='帮助文本')
    
    # 排序
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_required = models.BooleanField(default=True, verbose_name='必填')
    is_visible = models.BooleanField(default=True, verbose_name='显示')
    
    # 影响价格和工期
    affects_price = models.BooleanField(default=False, verbose_name='影响价格')
    affects_lead_time = models.BooleanField(default=False, verbose_name='影响工期')
    
    class Meta:
        db_table = 'plm_config_parameter'
        verbose_name = '配置参数'
        verbose_name_plural = verbose_name
        ordering = ['template', 'sort_order']
        unique_together = ['template', 'code']
    
    def __str__(self):
        return f'{self.template.code}.{self.code}'


class ParameterOption(BaseModel):
    """参数选项（用于选择型参数）"""
    parameter = models.ForeignKey(
        ConfigParameter,
        on_delete=models.CASCADE,
        related_name='options',
        verbose_name='参数'
    )
    
    label = models.CharField(max_length=100, verbose_name='显示名称')
    value = models.CharField(max_length=100, verbose_name='选项值')
    
    # 选项对价格和工期的影响
    price_adjustment = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='价格调整'
    )
    price_multiplier = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=1,
        verbose_name='价格系数'
    )
    lead_time_adjustment = models.IntegerField(default=0, verbose_name='工期调整(天)')
    
    # 关联物料
    add_item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='config_options',
        verbose_name='添加物料'
    )
    add_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=1,
        verbose_name='添加数量'
    )
    
    is_default = models.BooleanField(default=False, verbose_name='默认选项')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'plm_parameter_option'
        verbose_name = '参数选项'
        verbose_name_plural = verbose_name
        ordering = ['parameter', 'sort_order']
    
    def __str__(self):
        return f'{self.parameter.code}: {self.label}'


class ConfigRule(BaseModel):
    """配置规则"""
    RULE_TYPES = [
        ('REQUIRE', '要求'),  # 选择A时必须选择B
        ('EXCLUDE', '互斥'),  # 选择A时不能选择B
        ('INCLUDE', '包含'),  # 选择A时自动选择B
        ('FORMULA', '公式'),  # 计算公式
    ]
    
    template = models.ForeignKey(
        ProductTemplate,
        on_delete=models.CASCADE,
        related_name='rules',
        verbose_name='产品模板'
    )
    
    name = models.CharField(max_length=100, verbose_name='规则名称')
    rule_type = models.CharField(
        max_length=20,
        choices=RULE_TYPES,
        default='REQUIRE',
        verbose_name='规则类型'
    )
    
    # 条件
    condition_param = models.ForeignKey(
        ConfigParameter,
        on_delete=models.CASCADE,
        related_name='condition_rules',
        verbose_name='条件参数'
    )
    condition_value = models.CharField(max_length=200, verbose_name='条件值')
    condition_operator = models.CharField(
        max_length=20,
        choices=[
            ('EQ', '等于'),
            ('NE', '不等于'),
            ('GT', '大于'),
            ('GE', '大于等于'),
            ('LT', '小于'),
            ('LE', '小于等于'),
            ('IN', '在范围内'),
        ],
        default='EQ',
        verbose_name='条件运算符'
    )
    
    # 动作
    target_param = models.ForeignKey(
        ConfigParameter,
        on_delete=models.CASCADE,
        related_name='target_rules',
        null=True,
        blank=True,
        verbose_name='目标参数'
    )
    target_value = models.CharField(max_length=200, blank=True, verbose_name='目标值')
    
    # 公式规则
    formula = models.TextField(blank=True, verbose_name='计算公式')
    
    error_message = models.CharField(max_length=500, blank=True, verbose_name='错误提示')
    
    is_active = models.BooleanField(default=True, verbose_name='启用')
    priority = models.IntegerField(default=0, verbose_name='优先级')
    
    class Meta:
        db_table = 'plm_config_rule'
        verbose_name = '配置规则'
        verbose_name_plural = verbose_name
        ordering = ['template', 'priority']
    
    def __str__(self):
        return f'{self.template.code}: {self.name}'


class ConfigBOMRule(BaseModel):
    """BOM配置规则"""
    template = models.ForeignKey(
        ProductTemplate,
        on_delete=models.CASCADE,
        related_name='bom_rules',
        verbose_name='产品模板'
    )
    
    name = models.CharField(max_length=100, verbose_name='规则名称')
    
    # 条件
    condition_expression = models.TextField(verbose_name='条件表达式')
    
    # BOM调整
    action = models.CharField(
        max_length=20,
        choices=[
            ('ADD', '添加物料'),
            ('REMOVE', '移除物料'),
            ('REPLACE', '替换物料'),
            ('QUANTITY', '调整数量'),
        ],
        default='ADD',
        verbose_name='动作'
    )
    
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.CASCADE,
        related_name='bom_config_rules',
        verbose_name='物料'
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=1,
        verbose_name='数量'
    )
    
    # 替换物料（用于REPLACE动作）
    replace_item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_replace_rules',
        verbose_name='替换为'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    class Meta:
        db_table = 'plm_config_bom_rule'
        verbose_name = 'BOM配置规则'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.template.code}: {self.name}'


class ProductConfiguration(BaseModel):
    """产品配置实例"""
    config_no = models.CharField(max_length=50, unique=True, verbose_name='配置编号')
    
    template = models.ForeignKey(
        ProductTemplate,
        on_delete=models.CASCADE,
        related_name='configurations',
        verbose_name='产品模板'
    )
    
    name = models.CharField(max_length=200, verbose_name='配置名称')
    
    # 关联
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_configurations',
        verbose_name='客户'
    )
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_configurations',
        verbose_name='商机'
    )
    
    # 配置参数值
    config_values = models.JSONField(default=dict, verbose_name='配置参数值')
    
    # 计算结果
    total_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='总价格'
    )
    lead_time = models.IntegerField(default=0, verbose_name='交货期(天)')
    
    # 生成的BOM
    generated_bom = models.JSONField(default=list, verbose_name='生成的BOM')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('CONFIRMED', '已确认'),
            ('ORDERED', '已下单'),
            ('CANCELLED', '已取消'),
        ],
        default='DRAFT',
        verbose_name='状态'
    )
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'plm_product_configuration'
        verbose_name = '产品配置'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.config_no} - {self.name}'
    
    def save(self, *args, **kwargs):
        if not self.config_no:
            from apps.core.utils import generate_code
            self.config_no = generate_code('CFG')
        super().save(*args, **kwargs)


# =====================
# Serializers
# =====================

class ParameterOptionSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='add_item.name', read_only=True)
    item_code = serializers.CharField(source='add_item.code', read_only=True)
    
    class Meta:
        model = ParameterOption
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ConfigParameterSerializer(serializers.ModelSerializer):
    param_type_display = serializers.CharField(source='get_param_type_display', read_only=True)
    options = ParameterOptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = ConfigParameter
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ConfigRuleSerializer(serializers.ModelSerializer):
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    condition_param_name = serializers.CharField(source='condition_param.name', read_only=True)
    target_param_name = serializers.CharField(source='target_param.name', read_only=True)
    
    class Meta:
        model = ConfigRule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ConfigBOMRuleSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_code = serializers.CharField(source='item.code', read_only=True)
    replace_item_name = serializers.CharField(source='replace_item.name', read_only=True)
    
    class Meta:
        model = ConfigBOMRule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProductTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    parameters = ConfigParameterSerializer(many=True, read_only=True)
    rules = ConfigRuleSerializer(many=True, read_only=True)
    bom_rules = ConfigBOMRuleSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProductTemplateListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    parameter_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductTemplate
        fields = [
            'id', 'code', 'name', 'category', 'category_name',
            'base_price', 'base_lead_time', 'is_active', 'version',
            'parameter_count', 'image', 'description', 'created_at'
        ]
    
    def get_parameter_count(self, obj):
        return obj.parameters.filter(is_deleted=False).count()


class ProductConfigurationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    template_code = serializers.CharField(source='template.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = ProductConfiguration
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'config_no']


class ProductConfigurationListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = ProductConfiguration
        fields = [
            'id', 'config_no', 'name', 'template', 'template_name',
            'customer', 'customer_name', 'total_price', 'lead_time',
            'status', 'status_display', 'created_at'
        ]


# =====================
# ViewSets
# =====================

class ProductTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """产品模板管理"""
    queryset = ProductTemplate.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['created_at', 'code']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductTemplateListSerializer
        return ProductTemplateSerializer
    
    @action(detail=True, methods=['get'])
    def configurator(self, request, pk=None):
        """获取配置器数据"""
        template = self.get_object()
        
        parameters = template.parameters.filter(is_deleted=False, is_visible=True).order_by('sort_order')
        
        return Response({
            'template': ProductTemplateSerializer(template).data,
            'parameters': ConfigParameterSerializer(parameters, many=True).data
        })
    
    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """计算配置结果"""
        template = self.get_object()
        config_values = request.data.get('config_values', {})
        
        # 计算价格
        total_price = template.base_price or Decimal('0')
        lead_time = template.base_lead_time or 0
        bom_items = []
        
        for param in template.parameters.filter(is_deleted=False):
            value = config_values.get(param.code)
            if value is None:
                continue
            
            if param.param_type == 'SELECT':
                # 查找选中的选项
                option = param.options.filter(value=value, is_deleted=False).first()
                if option:
                    # 价格调整
                    if param.affects_price:
                        total_price += option.price_adjustment
                        total_price *= option.price_multiplier
                    
                    # 工期调整
                    if param.affects_lead_time:
                        lead_time += option.lead_time_adjustment
                    
                    # BOM物料
                    if option.add_item:
                        bom_items.append({
                            'item_id': option.add_item.id,
                            'item_code': option.add_item.code,
                            'item_name': option.add_item.name,
                            'quantity': float(option.add_quantity),
                            'source': f'参数选项: {param.name} = {option.label}'
                        })
            
            elif param.param_type == 'NUMBER':
                # 数值型参数可能有公式
                try:
                    num_value = Decimal(str(value))
                    # 简单示例：数值乘以某个系数
                    if param.affects_price:
                        # 这里可以扩展更复杂的公式
                        pass
                except:
                    pass
        
        # 应用BOM规则
        for rule in template.bom_rules.filter(is_active=True, is_deleted=False):
            try:
                # 简单的条件表达式求值（生产环境需要更安全的实现）
                if self._evaluate_condition(rule.condition_expression, config_values):
                    if rule.action == 'ADD':
                        bom_items.append({
                            'item_id': rule.item.id,
                            'item_code': rule.item.code,
                            'item_name': rule.item.name,
                            'quantity': float(rule.quantity),
                            'source': f'BOM规则: {rule.name}'
                        })
            except Exception as e:
                pass
        
        return Response({
            'total_price': float(total_price),
            'lead_time': lead_time,
            'bom_items': bom_items,
            'config_values': config_values
        })
    
    def _evaluate_condition(self, expression, config_values):
        """安全地评估条件表达式"""
        # 简单实现：只支持 param == value 格式
        try:
            if '==' in expression:
                parts = expression.split('==')
                param = parts[0].strip()
                value = parts[1].strip().strip('"\'')
                return str(config_values.get(param, '')) == value
        except:
            pass
        return False
    
    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None):
        """复制模板"""
        original = self.get_object()
        
        new_template = ProductTemplate.objects.create(
            name=f'{original.name} (复制)',
            code=f'{original.code}_COPY_{timezone.now().strftime("%Y%m%d%H%M%S")}',
            category=original.category,
            description=original.description,
            base_price=original.base_price,
            base_lead_time=original.base_lead_time,
            created_by=request.user
        )
        
        # 复制参数
        for param in original.parameters.filter(is_deleted=False):
            new_param = ConfigParameter.objects.create(
                template=new_template,
                name=param.name,
                code=param.code,
                param_type=param.param_type,
                default_value=param.default_value,
                min_value=param.min_value,
                max_value=param.max_value,
                step=param.step,
                unit=param.unit,
                description=param.description,
                sort_order=param.sort_order,
                is_required=param.is_required,
                affects_price=param.affects_price,
                affects_lead_time=param.affects_lead_time,
                created_by=request.user
            )
            
            # 复制选项
            for opt in param.options.filter(is_deleted=False):
                ParameterOption.objects.create(
                    parameter=new_param,
                    label=opt.label,
                    value=opt.value,
                    price_adjustment=opt.price_adjustment,
                    price_multiplier=opt.price_multiplier,
                    lead_time_adjustment=opt.lead_time_adjustment,
                    add_item=opt.add_item,
                    add_quantity=opt.add_quantity,
                    is_default=opt.is_default,
                    sort_order=opt.sort_order,
                    created_by=request.user
                )
        
        return Response(ProductTemplateSerializer(new_template).data)


class ConfigParameterViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """配置参数管理"""
    queryset = ConfigParameter.objects.filter(is_deleted=False)
    serializer_class = ConfigParameterSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'param_type', 'is_required']
    
    @action(detail=True, methods=['post'])
    def add_option(self, request, pk=None):
        """添加参数选项"""
        param = self.get_object()
        
        option = ParameterOption.objects.create(
            parameter=param,
            label=request.data.get('label', ''),
            value=request.data.get('value', ''),
            price_adjustment=request.data.get('price_adjustment', 0),
            price_multiplier=request.data.get('price_multiplier', 1),
            lead_time_adjustment=request.data.get('lead_time_adjustment', 0),
            add_item_id=request.data.get('add_item'),
            add_quantity=request.data.get('add_quantity', 1),
            is_default=request.data.get('is_default', False),
            sort_order=request.data.get('sort_order', 0),
            created_by=request.user
        )
        
        return Response(ParameterOptionSerializer(option).data)


class ParameterOptionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """参数选项管理"""
    queryset = ParameterOption.objects.filter(is_deleted=False)
    serializer_class = ParameterOptionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['parameter']


class ConfigRuleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """配置规则管理"""
    queryset = ConfigRule.objects.filter(is_deleted=False)
    serializer_class = ConfigRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'rule_type', 'is_active']


class ConfigBOMRuleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """BOM配置规则管理"""
    queryset = ConfigBOMRule.objects.filter(is_deleted=False)
    serializer_class = ConfigBOMRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'action', 'is_active']


class ProductConfigurationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """产品配置管理"""
    queryset = ProductConfiguration.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'customer', 'status']
    search_fields = ['config_no', 'name']
    ordering_fields = ['created_at', 'total_price']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductConfigurationListSerializer
        return ProductConfigurationSerializer
    
    def perform_create(self, serializer):
        config = serializer.save(created_by=self.request.user)
        
        # 自动计算价格和BOM
        template = config.template
        config_values = config.config_values
        
        # 调用计算逻辑
        total_price = template.base_price or Decimal('0')
        lead_time = template.base_lead_time or 0
        bom_items = []
        
        for param in template.parameters.filter(is_deleted=False):
            value = config_values.get(param.code)
            if value is None:
                continue
            
            if param.param_type == 'SELECT':
                option = param.options.filter(value=value, is_deleted=False).first()
                if option:
                    if param.affects_price:
                        total_price += option.price_adjustment
                        total_price *= option.price_multiplier
                    if param.affects_lead_time:
                        lead_time += option.lead_time_adjustment
                    if option.add_item:
                        bom_items.append({
                            'item_id': option.add_item.id,
                            'item_code': option.add_item.code,
                            'item_name': option.add_item.name,
                            'quantity': float(option.add_quantity)
                        })
        
        config.total_price = total_price
        config.lead_time = lead_time
        config.generated_bom = bom_items
        config.save()
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认配置"""
        config = self.get_object()
        if config.status != 'DRAFT':
            return Response({'error': '只有草稿状态可以确认'}, status=400)
        config.status = 'CONFIRMED'
        config.save()
        return Response(self.get_serializer(config).data)
    
    @action(detail=True, methods=['post'])
    def create_quotation(self, request, pk=None):
        """生成报价单"""
        config = self.get_object()
        
        # 这里可以集成报价单创建逻辑
        return Response({
            'message': '报价单创建功能待集成',
            'config': self.get_serializer(config).data
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """配置统计"""
        qs = self.get_queryset()
        
        by_status = qs.values('status').annotate(count=Count('id'))
        by_template = qs.values('template__name').annotate(count=Count('id'))[:10]
        
        return Response({
            'total': qs.count(),
            'by_status': list(by_status),
            'by_template': list(by_template)
        })
