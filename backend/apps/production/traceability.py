"""
追溯管理
Traceability Management
批次追溯、条码管理、质量追溯
"""
from datetime import date, datetime
from django.db import models
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class ProductBatch(BaseModel):
    """产品批次"""
    STATUS_CHOICES = [
        ('ACTIVE', '生产中'),
        ('COMPLETED', '已完成'),
        ('HOLD', '暂扣'),
        ('RELEASED', '已放行'),
        ('SCRAPPED', '已报废'),
    ]
    
    batch_no = models.CharField(max_length=50, unique=True, verbose_name='批次号')
    
    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='batches',
        verbose_name='项目'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_batches',
        verbose_name='产品'
    )
    
    # 生产信息
    production_date = models.DateField(default=date.today, verbose_name='生产日期')
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1, verbose_name='数量')
    
    # 来源批次
    source_batches = models.JSONField(default=list, blank=True, verbose_name='来源批次')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name='状态'
    )
    
    # 质量信息
    inspection_result = models.CharField(max_length=20, blank=True, verbose_name='检验结果')
    quality_grade = models.CharField(max_length=20, blank=True, verbose_name='质量等级')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'mes_product_batch'
        verbose_name = '产品批次'
        verbose_name_plural = verbose_name
        ordering = ['-production_date', '-created_at']
    
    def __str__(self):
        return self.batch_no
    
    def save(self, *args, **kwargs):
        if not self.batch_no:
            # 生成批次号: 日期 + 项目编号 + 序号
            prefix = date.today().strftime('%Y%m%d')
            count = ProductBatch.objects.filter(
                batch_no__startswith=prefix
            ).count() + 1
            self.batch_no = f'{prefix}{count:04d}'
        super().save(*args, **kwargs)


class BatchOperation(BaseModel):
    """批次操作记录"""
    OPERATION_TYPES = [
        ('CREATE', '创建'),
        ('PRODUCE', '生产'),
        ('INSPECT', '检验'),
        ('PACK', '包装'),
        ('SHIP', '发货'),
        ('INSTALL', '安装'),
        ('REWORK', '返工'),
        ('SCRAP', '报废'),
    ]
    
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        related_name='operations',
        verbose_name='批次'
    )
    operation_type = models.CharField(
        max_length=20,
        choices=OPERATION_TYPES,
        verbose_name='操作类型'
    )
    
    # 操作详情
    operation_time = models.DateTimeField(default=timezone.now, verbose_name='操作时间')
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='batch_operations',
        verbose_name='操作人'
    )
    
    # 工序/工位
    work_center = models.ForeignKey(
        'production.WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batch_operations',
        verbose_name='工作中心'
    )
    process_name = models.CharField(max_length=100, blank=True, verbose_name='工序名称')
    
    # 结果
    result = models.CharField(max_length=50, blank=True, verbose_name='结果')
    quantity = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='数量')
    
    # 附加数据
    data = models.JSONField(default=dict, blank=True, verbose_name='附加数据')
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'mes_batch_operation'
        verbose_name = '批次操作'
        verbose_name_plural = verbose_name
        ordering = ['-operation_time']


class MaterialTrace(BaseModel):
    """物料追溯"""
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        related_name='material_traces',
        verbose_name='产品批次'
    )
    material_batch = models.CharField(max_length=50, verbose_name='物料批次')
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        related_name='material_traces',
        verbose_name='物料'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='material_traces',
        verbose_name='供应商'
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4, verbose_name='用量')
    use_time = models.DateTimeField(default=timezone.now, verbose_name='使用时间')
    
    class Meta:
        db_table = 'mes_material_trace'
        verbose_name = '物料追溯'
        verbose_name_plural = verbose_name


class QualityRecord(BaseModel):
    """质量记录"""
    RESULT_CHOICES = [
        ('PASS', '合格'),
        ('FAIL', '不合格'),
        ('CONDITIONAL', '有条件放行'),
    ]
    
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        related_name='quality_records',
        verbose_name='批次'
    )
    
    # 检验信息
    inspection_type = models.CharField(max_length=50, verbose_name='检验类型')
    inspection_item = models.CharField(max_length=200, verbose_name='检验项目')
    
    # 标准
    standard_value = models.CharField(max_length=100, blank=True, verbose_name='标准值')
    upper_limit = models.CharField(max_length=50, blank=True, verbose_name='上限')
    lower_limit = models.CharField(max_length=50, blank=True, verbose_name='下限')
    
    # 实测
    actual_value = models.CharField(max_length=100, blank=True, verbose_name='实测值')
    
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='PASS',
        verbose_name='结果'
    )
    
    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='quality_records',
        verbose_name='检验员'
    )
    inspection_time = models.DateTimeField(default=timezone.now, verbose_name='检验时间')
    
    defect_description = models.TextField(blank=True, verbose_name='缺陷描述')
    corrective_action = models.TextField(blank=True, verbose_name='纠正措施')
    
    class Meta:
        db_table = 'mes_quality_record'
        verbose_name = '质量记录'
        verbose_name_plural = verbose_name
        ordering = ['-inspection_time']


# =====================
# Serializers
# =====================

class BatchOperationSerializer(serializers.ModelSerializer):
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    
    class Meta:
        model = BatchOperation
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class MaterialTraceSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
    class Meta:
        model = MaterialTrace
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class QualityRecordSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    
    class Meta:
        model = QualityRecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProductBatchSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    operations = BatchOperationSerializer(many=True, read_only=True)
    material_traces = MaterialTraceSerializer(many=True, read_only=True)
    quality_records = QualityRecordSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductBatch
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'batch_no']


class ProductBatchListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    operation_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductBatch
        fields = [
            'id', 'batch_no', 'project', 'project_name',
            'item', 'item_name', 'production_date', 'quantity',
            'status', 'status_display', 'inspection_result',
            'quality_grade', 'operation_count', 'created_at'
        ]
    
    def get_operation_count(self, obj):
        return obj.operations.count()


# =====================
# ViewSets
# =====================

class ProductBatchViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """产品批次管理"""
    queryset = ProductBatch.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'project', 'item', 'production_date']
    search_fields = ['batch_no', 'project__name', 'item__name']
    ordering_fields = ['production_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductBatchListSerializer
        return ProductBatchSerializer
    
    @action(detail=True, methods=['post'])
    def add_operation(self, request, pk=None):
        """添加操作记录"""
        batch = self.get_object()
        
        operation = BatchOperation.objects.create(
            batch=batch,
            operation_type=request.data.get('operation_type'),
            operator=request.user,
            process_name=request.data.get('process_name', ''),
            result=request.data.get('result', ''),
            quantity=request.data.get('quantity'),
            data=request.data.get('data', {}),
            remarks=request.data.get('remarks', ''),
            created_by=request.user
        )
        
        return Response(BatchOperationSerializer(operation).data)
    
    @action(detail=True, methods=['post'])
    def add_material(self, request, pk=None):
        """添加物料追溯"""
        batch = self.get_object()
        
        trace = MaterialTrace.objects.create(
            batch=batch,
            material_batch=request.data.get('material_batch'),
            item_id=request.data.get('item_id'),
            supplier_id=request.data.get('supplier_id'),
            quantity=request.data.get('quantity'),
            created_by=request.user
        )
        
        return Response(MaterialTraceSerializer(trace).data)
    
    @action(detail=True, methods=['post'])
    def add_quality_record(self, request, pk=None):
        """添加质量记录"""
        batch = self.get_object()
        
        record = QualityRecord.objects.create(
            batch=batch,
            inspection_type=request.data.get('inspection_type'),
            inspection_item=request.data.get('inspection_item'),
            standard_value=request.data.get('standard_value', ''),
            upper_limit=request.data.get('upper_limit', ''),
            lower_limit=request.data.get('lower_limit', ''),
            actual_value=request.data.get('actual_value', ''),
            result=request.data.get('result', 'PASS'),
            inspector=request.user,
            defect_description=request.data.get('defect_description', ''),
            corrective_action=request.data.get('corrective_action', ''),
            created_by=request.user
        )
        
        return Response(QualityRecordSerializer(record).data)
    
    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """放行批次"""
        batch = self.get_object()
        batch.status = 'RELEASED'
        batch.save()
        
        # 记录操作
        BatchOperation.objects.create(
            batch=batch,
            operation_type='INSPECT',
            operator=request.user,
            result='放行',
            remarks='批次已放行',
            created_by=request.user
        )
        
        return Response(self.get_serializer(batch).data)
    
    @action(detail=True, methods=['post'])
    def hold(self, request, pk=None):
        """暂扣批次"""
        batch = self.get_object()
        batch.status = 'HOLD'
        batch.save()
        
        BatchOperation.objects.create(
            batch=batch,
            operation_type='INSPECT',
            operator=request.user,
            result='暂扣',
            remarks=request.data.get('reason', ''),
            created_by=request.user
        )
        
        return Response(self.get_serializer(batch).data)
    
    @action(detail=True, methods=['get'])
    def trace(self, request, pk=None):
        """追溯查询"""
        batch = self.get_object()
        
        # 获取完整追溯链
        trace_data = {
            'batch': ProductBatchListSerializer(batch).data,
            'operations': BatchOperationSerializer(batch.operations.all(), many=True).data,
            'materials': MaterialTraceSerializer(batch.material_traces.all(), many=True).data,
            'quality': QualityRecordSerializer(batch.quality_records.all(), many=True).data,
            'source_batches': batch.source_batches
        }
        
        # 递归获取来源批次信息
        if batch.source_batches:
            source_details = []
            for source_no in batch.source_batches:
                try:
                    source = ProductBatch.objects.get(batch_no=source_no)
                    source_details.append(ProductBatchListSerializer(source).data)
                except ProductBatch.DoesNotExist:
                    source_details.append({'batch_no': source_no, 'error': '未找到'})
            trace_data['source_details'] = source_details
        
        return Response(trace_data)


class TraceSearchView(APIView):
    """追溯搜索API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """搜索追溯信息"""
        query = request.query_params.get('q', '')
        search_type = request.query_params.get('type', 'all')  # batch, material, project
        
        results = {
            'batches': [],
            'materials': [],
            'projects': []
        }
        
        if not query:
            return Response(results)
        
        if search_type in ['all', 'batch']:
            batches = ProductBatch.objects.filter(
                Q(batch_no__icontains=query) | Q(project__name__icontains=query),
                is_deleted=False
            )[:20]
            results['batches'] = ProductBatchListSerializer(batches, many=True).data
        
        if search_type in ['all', 'material']:
            materials = MaterialTrace.objects.filter(
                Q(material_batch__icontains=query) | Q(item__name__icontains=query),
                is_deleted=False
            ).select_related('batch', 'item')[:20]
            results['materials'] = MaterialTraceSerializer(materials, many=True).data
        
        return Response(results)
