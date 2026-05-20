"""
序列号与批次追溯增强模块 - 针对非标自动化行业
包含：SN管理、全流程追溯、追溯码生成、追溯查询
"""
from django.db import models
from django.db.models import Q
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin


# =============================================================================
# 模型定义
# =============================================================================

class SerialNumber(BaseModel):
    """序列号管理"""
    STATUS_CHOICES = [
        ('GENERATED', '已生成'),
        ('ASSIGNED', '已分配'),
        ('IN_PRODUCTION', '生产中'),
        ('COMPLETED', '已完工'),
        ('DELIVERED', '已发货'),
        ('INSTALLED', '已安装'),
        ('RETURNED', '已退回'),
        ('SCRAPPED', '已报废'),
    ]
    
    # 序列号信息
    serial_number = models.CharField(max_length=100, unique=True, verbose_name='序列号')
    batch_no = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    
    # 关联信息
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='serial_numbers',
        verbose_name='物料'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serial_numbers',
        verbose_name='项目'
    )
    production_plan = models.ForeignKey(
        'production.ProductionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serial_numbers',
        verbose_name='生产计划'
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serial_numbers',
        verbose_name='销售订单'
    )
    delivery_order = models.ForeignKey(
        'sales.DeliveryOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serial_numbers',
        verbose_name='发货单'
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serial_numbers',
        verbose_name='客户'
    )
    
    # 生产信息
    production_date = models.DateField(null=True, blank=True, verbose_name='生产日期')
    production_line = models.CharField(max_length=100, blank=True, verbose_name='生产线')
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produced_sns',
        verbose_name='操作员'
    )
    
    # 质量信息
    inspection_result = models.CharField(max_length=20, blank=True, verbose_name='检验结果')
    inspection_date = models.DateField(null=True, blank=True, verbose_name='检验日期')
    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspected_sns',
        verbose_name='检验员'
    )
    
    # 发货信息
    delivery_date = models.DateField(null=True, blank=True, verbose_name='发货日期')
    installation_date = models.DateField(null=True, blank=True, verbose_name='安装日期')
    
    # 质保信息
    warranty_start_date = models.DateField(null=True, blank=True, verbose_name='质保开始日期')
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='质保结束日期')
    
    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GENERATED', verbose_name='状态')
    
    # 附加信息
    attributes = models.JSONField(default=dict, blank=True, verbose_name='附加属性')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'serial_number'
        verbose_name = '序列号'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.serial_number


class SNTraceRecord(BaseModel):
    """序列号追溯记录"""
    OPERATION_CHOICES = [
        ('GENERATE', '生成'),
        ('ASSIGN', '分配'),
        ('PRODUCTION_START', '开始生产'),
        ('PRODUCTION_COMPLETE', '完成生产'),
        ('PROCESS_COMPLETE', '工序完成'),
        ('INSPECTION', '质量检验'),
        ('REWORK', '返工'),
        ('PACKAGING', '包装'),
        ('DELIVERY', '发货'),
        ('INSTALLATION', '安装'),
        ('MAINTENANCE', '维护'),
        ('RETURN', '退货'),
        ('SCRAP', '报废'),
        ('TRANSFER', '转移'),
        ('OTHER', '其他'),
    ]
    
    serial_number = models.ForeignKey(
        SerialNumber,
        on_delete=models.CASCADE,
        related_name='trace_records',
        verbose_name='序列号'
    )
    
    operation = models.CharField(max_length=30, choices=OPERATION_CHOICES, verbose_name='操作类型')
    operation_time = models.DateTimeField(verbose_name='操作时间')
    
    # 操作详情
    description = models.TextField(verbose_name='操作描述')
    location = models.CharField(max_length=200, blank=True, verbose_name='操作地点')
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sn_operations',
        verbose_name='操作人'
    )
    
    # 关联单据
    related_doc_type = models.CharField(max_length=50, blank=True, verbose_name='关联单据类型')
    related_doc_no = models.CharField(max_length=100, blank=True, verbose_name='关联单据号')
    related_doc_id = models.IntegerField(null=True, blank=True, verbose_name='关联单据ID')
    
    # 工序信息（如果是工序相关操作）
    process_name = models.CharField(max_length=100, blank=True, verbose_name='工序名称')
    process_result = models.CharField(max_length=50, blank=True, verbose_name='工序结果')
    
    # 质量数据
    quality_data = models.JSONField(default=dict, blank=True, verbose_name='质量数据')
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'sn_trace_record'
        verbose_name = '序列号追溯记录'
        verbose_name_plural = verbose_name
        ordering = ['-operation_time']
    
    def __str__(self):
        return f"{self.serial_number.serial_number} - {self.get_operation_display()}"


class ComponentBinding(BaseModel):
    """组件绑定（设备与关键部件的SN绑定）"""
    parent_sn = models.ForeignKey(
        SerialNumber,
        on_delete=models.CASCADE,
        related_name='child_bindings',
        verbose_name='父序列号'
    )
    child_sn = models.ForeignKey(
        SerialNumber,
        on_delete=models.CASCADE,
        related_name='parent_bindings',
        verbose_name='子序列号'
    )
    
    binding_time = models.DateTimeField(verbose_name='绑定时间')
    position = models.CharField(max_length=100, blank=True, verbose_name='安装位置')
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='component_bindings',
        verbose_name='操作人'
    )
    
    # 解绑信息
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    unbinding_time = models.DateTimeField(null=True, blank=True, verbose_name='解绑时间')
    unbinding_reason = models.TextField(blank=True, verbose_name='解绑原因')
    
    class Meta:
        db_table = 'component_binding'
        verbose_name = '组件绑定'
        verbose_name_plural = verbose_name
        ordering = ['-binding_time']
    
    def __str__(self):
        return f"{self.parent_sn.serial_number} -> {self.child_sn.serial_number}"


class SNRule(BaseModel):
    """序列号规则"""
    code = models.CharField(max_length=50, unique=True, verbose_name='规则编号')
    name = models.CharField(max_length=200, verbose_name='规则名称')
    
    # 适用范围
    item_category = models.ForeignKey(
        'masterdata.ItemCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='物料分类'
    )
    
    # 规则配置
    prefix = models.CharField(max_length=20, blank=True, verbose_name='前缀')
    suffix = models.CharField(max_length=20, blank=True, verbose_name='后缀')
    date_format = models.CharField(max_length=20, default='YYMMDD', verbose_name='日期格式')
    sequence_length = models.IntegerField(default=4, verbose_name='流水号位数')
    separator = models.CharField(max_length=5, default='-', verbose_name='分隔符')
    
    # 格式示例: {prefix}{separator}{date}{separator}{sequence}{suffix}
    # 例如: ATM-240121-0001
    
    # 当前序列
    current_sequence = models.IntegerField(default=0, verbose_name='当前序列')
    last_date = models.CharField(max_length=20, blank=True, verbose_name='最后日期')
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'sn_rule'
        verbose_name = '序列号规则'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def generate_sn(self):
        """生成序列号（使用 select_for_update 防止并发重复）"""
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            rule = SNRule.objects.select_for_update().get(pk=self.pk)

            current_date = datetime.now().strftime(
                rule.date_format.replace('YY', '%y').replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d')
            )

            if current_date != rule.last_date:
                rule.current_sequence = 0
                rule.last_date = current_date

            rule.current_sequence += 1
            sequence_str = str(rule.current_sequence).zfill(rule.sequence_length)

            parts = []
            if rule.prefix:
                parts.append(rule.prefix)
            parts.append(current_date)
            parts.append(sequence_str)

            sn = rule.separator.join(parts)
            if rule.suffix:
                sn += rule.suffix

            rule.save(update_fields=['current_sequence', 'last_date'])

        # Sync self with the updated rule state
        self.current_sequence = rule.current_sequence
        self.last_date = rule.last_date
        return sn


# =============================================================================
# 序列化器
# =============================================================================

class SNTraceRecordSerializer(serializers.ModelSerializer):
    operation_display = serializers.CharField(source='get_operation_display', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)
    
    class Meta:
        model = SNTraceRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class ComponentBindingSerializer(serializers.ModelSerializer):
    parent_sn_no = serializers.CharField(source='parent_sn.serial_number', read_only=True)
    child_sn_no = serializers.CharField(source='child_sn.serial_number', read_only=True)
    child_item_name = serializers.CharField(source='child_sn.item.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)
    
    class Meta:
        model = ComponentBinding
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class SerialNumberSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    trace_records = SNTraceRecordSerializer(many=True, read_only=True)
    child_components = serializers.SerializerMethodField()
    
    class Meta:
        model = SerialNumber
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_child_components(self, obj):
        bindings = obj.child_bindings.filter(is_active=True)
        return ComponentBindingSerializer(bindings, many=True).data


class SerialNumberListSerializer(serializers.ModelSerializer):
    """列表用简化序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_sku = serializers.CharField(source='item.sku', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = SerialNumber
        fields = [
            'id', 'serial_number', 'batch_no', 'item', 'item_name', 'item_sku',
            'project', 'project_code', 'customer', 'customer_name',
            'production_date', 'status', 'status_display', 'created_at'
        ]


class SNRuleSerializer(serializers.ModelSerializer):
    example_sn = serializers.SerializerMethodField()
    
    class Meta:
        model = SNRule
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'current_sequence', 'last_date']
    
    def get_example_sn(self, obj):
        """生成示例序列号"""
        from datetime import datetime
        current_date = datetime.now().strftime(obj.date_format.replace('YY', '%y').replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d'))
        sequence_str = '0001'
        
        parts = []
        if obj.prefix:
            parts.append(obj.prefix)
        parts.append(current_date)
        parts.append(sequence_str)
        
        sn = obj.separator.join(parts)
        if obj.suffix:
            sn += obj.suffix
        
        return sn


# =============================================================================
# 视图集
# =============================================================================

class SNRuleViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """序列号规则管理"""
    queryset = SNRule.objects.all()
    serializer_class = SNRuleSerializer
    filterset_fields = ['item_category', 'is_active', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'created_at']


class SerialNumberViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """序列号管理"""
    queryset = SerialNumber.objects.all()
    filterset_fields = ['item', 'project', 'customer', 'status', 'is_deleted']
    search_fields = ['serial_number', 'batch_no']
    ordering_fields = ['serial_number', 'production_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SerialNumberListSerializer
        return SerialNumberSerializer
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'item', 'project', 'customer', 'operator', 'inspector'
        )
    
    @action(detail=False, methods=['post'])
    def generate_batch(self, request):
        """批量生成序列号"""
        rule_id = request.data.get('rule_id')
        quantity = int(request.data.get('quantity', 1))
        item_id = request.data.get('item_id')
        project_id = request.data.get('project_id')
        batch_no = request.data.get('batch_no', '')
        
        if quantity > 100:
            return Response({'error': '单次生成不能超过100个'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            rule = SNRule.objects.get(id=rule_id)
        except SNRule.DoesNotExist:
            return Response({'error': '规则不存在'}, status=status.HTTP_404_NOT_FOUND)
        
        from django.utils import timezone
        from django.db import transaction
        generated_sns = []

        with transaction.atomic():
            for _ in range(quantity):
                sn = rule.generate_sn()
                serial_number = SerialNumber.objects.create(
                    serial_number=sn,
                    batch_no=batch_no,
                    item_id=item_id,
                    project_id=project_id,
                    status='GENERATED'
                )

                SNTraceRecord.objects.create(
                    serial_number=serial_number,
                    operation='GENERATE',
                    operation_time=timezone.now(),
                    description=f'使用规则 {rule.code} 生成序列号',
                    operator=request.user
                )

                generated_sns.append(serial_number)
        
        return Response({
            'message': f'成功生成 {quantity} 个序列号',
            'serial_numbers': SerialNumberListSerializer(generated_sns, many=True).data
        })
    
    @action(detail=True, methods=['get'])
    def full_trace(self, request, pk=None):
        """获取完整追溯信息"""
        sn = self.get_object()
        
        # 获取追溯记录
        trace_records = sn.trace_records.all().order_by('operation_time')
        
        # 获取组件绑定
        child_bindings = sn.child_bindings.filter(is_active=True)
        parent_bindings = sn.parent_bindings.filter(is_active=True)
        
        # 构建追溯树
        trace_data = {
            'serial_number': SerialNumberSerializer(sn).data,
            'timeline': SNTraceRecordSerializer(trace_records, many=True).data,
            'components': {
                'children': ComponentBindingSerializer(child_bindings, many=True).data,
                'parents': ComponentBindingSerializer(parent_bindings, many=True).data,
            },
            'quality_summary': self._get_quality_summary(sn),
        }
        
        return Response(trace_data)
    
    def _get_quality_summary(self, sn):
        """获取质量汇总"""
        inspection_records = sn.trace_records.filter(operation='INSPECTION')
        return {
            'inspection_count': inspection_records.count(),
            'pass_count': inspection_records.filter(process_result='PASS').count(),
            'fail_count': inspection_records.filter(process_result='FAIL').count(),
        }
    
    @action(detail=True, methods=['post'])
    def add_trace(self, request, pk=None):
        """添加追溯记录"""
        sn = self.get_object()

        from django.utils import timezone
        from django.db import transaction

        with transaction.atomic():
            record = SNTraceRecord.objects.create(
                serial_number=sn,
                operation=request.data.get('operation'),
                operation_time=timezone.now(),
                description=request.data.get('description', ''),
                location=request.data.get('location', ''),
                operator=request.user,
                related_doc_type=request.data.get('related_doc_type', ''),
                related_doc_no=request.data.get('related_doc_no', ''),
                related_doc_id=request.data.get('related_doc_id'),
                process_name=request.data.get('process_name', ''),
                process_result=request.data.get('process_result', ''),
                quality_data=request.data.get('quality_data', {}),
            )

            status_map = {
                'ASSIGN': 'ASSIGNED',
                'PRODUCTION_START': 'IN_PRODUCTION',
                'PRODUCTION_COMPLETE': 'COMPLETED',
                'DELIVERY': 'DELIVERED',
                'INSTALLATION': 'INSTALLED',
                'RETURN': 'RETURNED',
                'SCRAP': 'SCRAPPED',
            }
            operation = request.data.get('operation')
            if operation in status_map:
                sn.status = status_map[operation]
                sn.save(update_fields=['status'])

        return Response(SNTraceRecordSerializer(record).data)
    
    @action(detail=True, methods=['post'])
    def bind_component(self, request, pk=None):
        """绑定子组件"""
        parent_sn = self.get_object()
        child_sn_id = request.data.get('child_sn_id')
        position = request.data.get('position', '')

        try:
            child_sn = SerialNumber.objects.get(id=child_sn_id)
        except SerialNumber.DoesNotExist:
            return Response({'error': '子序列号不存在'}, status=status.HTTP_404_NOT_FOUND)

        from django.utils import timezone
        from django.db import transaction

        with transaction.atomic():
            binding = ComponentBinding.objects.create(
                parent_sn=parent_sn,
                child_sn=child_sn,
                binding_time=timezone.now(),
                position=position,
                operator=request.user
            )

            for sn, desc in [(parent_sn, f'绑定子组件: {child_sn.serial_number}'),
                             (child_sn, f'绑定到父组件: {parent_sn.serial_number}')]:
                SNTraceRecord.objects.create(
                    serial_number=sn,
                    operation='OTHER',
                    operation_time=timezone.now(),
                    description=desc,
                    operator=request.user
                )

        return Response(ComponentBindingSerializer(binding).data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """搜索序列号（支持模糊搜索）"""
        query = request.query_params.get('q', '')
        if len(query) < 3:
            return Response({'error': '搜索关键词至少3个字符'}, status=status.HTTP_400_BAD_REQUEST)
        
        sns = self.get_queryset().filter(
            Q(serial_number__icontains=query) |
            Q(batch_no__icontains=query) |
            Q(item__name__icontains=query) |
            Q(item__sku__icontains=query)
        )[:50]
        
        return Response(SerialNumberListSerializer(sns, many=True).data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """序列号统计"""
        queryset = self.get_queryset().filter(is_deleted=False)
        
        stats = {
            'total': queryset.count(),
            'by_status': {},
        }
        
        for status_code, status_name in SerialNumber.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            stats['by_status'][status_code] = {'name': status_name, 'count': count}
        
        return Response(stats)


class SNTraceRecordViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """序列号追溯记录管理"""
    queryset = SNTraceRecord.objects.all()
    serializer_class = SNTraceRecordSerializer
    filterset_fields = ['serial_number', 'operation', 'operator', 'is_deleted']
    search_fields = ['description', 'related_doc_no']
    ordering_fields = ['operation_time', 'created_at']


class ComponentBindingViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """组件绑定管理"""
    queryset = ComponentBinding.objects.all()
    serializer_class = ComponentBindingSerializer
    filterset_fields = ['parent_sn', 'child_sn', 'is_active', 'is_deleted']
    ordering_fields = ['binding_time', 'created_at']
    
    @action(detail=True, methods=['post'])
    def unbind(self, request, pk=None):
        """解绑组件"""
        binding = self.get_object()

        from django.utils import timezone
        from django.db import transaction

        with transaction.atomic():
            binding.is_active = False
            binding.unbinding_time = timezone.now()
            binding.unbinding_reason = request.data.get('reason', '')
            binding.save(update_fields=['is_active', 'unbinding_time', 'unbinding_reason'])

            for sn, desc in [(binding.parent_sn, f'解绑子组件: {binding.child_sn.serial_number}'),
                             (binding.child_sn, f'从父组件解绑: {binding.parent_sn.serial_number}')]:
                SNTraceRecord.objects.create(
                    serial_number=sn,
                    operation='OTHER',
                    operation_time=timezone.now(),
                    description=desc,
                    operator=request.user
                )

        return Response(ComponentBindingSerializer(binding).data)
