"""
Configurable Report Builder System
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel


class ReportTemplate(BaseModel):
    CATEGORY_CHOICES = [
        ('sales', '销售'),
        ('purchase', '采购'),
        ('inventory', '库存'),
        ('production', '生产'),
        ('finance', '财务'),
        ('project', '项目'),
        ('quality', '质量'),
        ('equipment', '设备'),
        ('comprehensive', '综合'),
    ]
    DATA_SOURCE_CHOICES = [
        ('sales_order', '销售订单'),
        ('purchase_order', '采购订单'),
        ('stock', '库存'),
        ('production_order', '生产工单'),
        ('project', '项目'),
        ('inspection', '检验'),
        ('customer', '客户'),
        ('supplier', '供应商'),
        ('material', '物料'),
        ('equipment', '设备'),
        ('financial_voucher', '财务凭证'),
        ('quality_record', '质量记录'),
        ('bom', 'BOM'),
    ]

    name = models.CharField(max_length=200, verbose_name='报表名称')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='分类')
    data_source = models.CharField(max_length=30, choices=DATA_SOURCE_CHOICES, verbose_name='数据源')
    config = models.JSONField(default=dict, verbose_name='配置')
    is_system = models.BooleanField(default=False, verbose_name='系统报表')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_templates_created',
        verbose_name='创建人',
    )

    class Meta:
        db_table = 'reports_report_template'
        ordering = ['category', 'name']
        verbose_name = '报表模板'
        verbose_name_plural = '报表模板'

    def __str__(self):
        return self.name


class ReportExecution(BaseModel):
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]

    template = models.ForeignKey(
        ReportTemplate, on_delete=models.CASCADE, related_name='executions', verbose_name='报表模板'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    parameters = models.JSONField(default=dict, verbose_name='参数')
    result_data = models.JSONField(default=dict, verbose_name='结果数据')
    row_count = models.IntegerField(default=0, verbose_name='行数')
    execution_time = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True, verbose_name='执行时间(秒)'
    )
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='report_executions_created',
        verbose_name='执行人',
    )

    class Meta:
        db_table = 'reports_report_execution'
        ordering = ['-created_at']
        verbose_name = '报表执行记录'
        verbose_name_plural = '报表执行记录'

    def __str__(self):
        return f'{self.template.name} - {self.status}'


class ReportFavorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='report_favorites', verbose_name='用户'
    )
    template = models.ForeignKey(
        ReportTemplate, on_delete=models.CASCADE, related_name='favorites', verbose_name='报表模板'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='收藏时间')

    class Meta:
        db_table = 'reports_report_favorite'
        unique_together = [('user', 'template')]
        verbose_name = '报表收藏'
        verbose_name_plural = '报表收藏'


class ReportQueryService:
    """Service for executing report queries."""

    DATA_SOURCE_MODEL_MAP = {
        'sales_order': 'apps.sales.models.SalesOrder',
        'purchase_order': 'apps.purchase.models.PurchaseOrder',
        'stock': 'apps.inventory.models.Stock',
        'production_order': 'apps.production.models.ProductionOrder',
        'project': 'apps.projects.models.Project',
        'customer': 'apps.masterdata.models.Customer',
        'supplier': 'apps.masterdata.models.Supplier',
        'material': 'apps.masterdata.models.Material',
    }

    @staticmethod
    def execute(template_id, params, user):
        import time

        template = ReportTemplate.objects.get(id=template_id, is_deleted=False)
        execution = ReportExecution.objects.create(
            template=template,
            parameters=params,
            status='running',
            created_by=user,
        )
        start = time.time()
        try:
            model_path = ReportQueryService.DATA_SOURCE_MODEL_MAP.get(template.data_source)
            if not model_path:
                raise ValueError(f'不支持的数据源: {template.data_source}')

            module_path, model_name = model_path.rsplit('.', 1)
            import importlib

            module = importlib.import_module(module_path)
            model_cls = getattr(module, model_name)

            qs = model_cls.objects.filter(is_deleted=False)

            date_from = params.get('date_from')
            date_to = params.get('date_to')
            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)

            limit = min(int(params.get('limit', 1000)), 5000)
            rows = list(qs.values()[:limit])

            elapsed = time.time() - start
            execution.status = 'completed'
            execution.result_data = {'rows': rows}
            execution.row_count = len(rows)
            execution.execution_time = Decimal(str(round(elapsed, 3)))
            execution.save()
        except Exception as e:
            elapsed = time.time() - start
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.execution_time = Decimal(str(round(elapsed, 3)))
            execution.save()
        return execution


# ─── Serializers ────────────────────────────────────────────────


class ReportTemplateSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    data_source_display = serializers.CharField(source='get_data_source_display', read_only=True)

    class Meta:
        model = ReportTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ReportExecutionSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)

    class Meta:
        model = ReportExecution
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ReportFavoriteSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)

    class Meta:
        model = ReportFavorite
        fields = '__all__'


# ─── ViewSets ───────────────────────────────────────────────────


class ReportTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ReportTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ReportTemplate.objects.filter(is_deleted=False)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        params = request.data.get('parameters', {})
        execution = ReportQueryService.execute(pk, params, request.user)
        return Response(ReportExecutionSerializer(execution).data)

    @action(detail=True, methods=['post'])
    def favorite(self, request, pk=None):
        template = self.get_object()
        fav, created = ReportFavorite.objects.get_or_create(user=request.user, template=template)
        if not created:
            fav.delete()
            return Response({'status': 'unfavorited'})
        return Response({'status': 'favorited'})

    @action(detail=False, methods=['get'])
    def my_favorites(self, request):
        favs = ReportFavorite.objects.filter(user=request.user).select_related('template')
        templates = [f.template for f in favs]
        return Response(ReportTemplateSerializer(templates, many=True).data)

    @action(detail=False, methods=['get'])
    def data_source_fields(self, request):
        data_source = request.query_params.get('data_source')
        model_path = ReportQueryService.DATA_SOURCE_MODEL_MAP.get(data_source)
        if not model_path:
            return Response({'error': '不支持的数据源'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            module_path, model_name = model_path.rsplit('.', 1)
            import importlib

            module = importlib.import_module(module_path)
            model_cls = getattr(module, model_name)
            fields = [
                {'name': f.name, 'type': f.get_internal_type(), 'verbose_name': str(f.verbose_name)}
                for f in model_cls._meta.get_fields()
                if hasattr(f, 'get_internal_type')
            ]
            return Response(fields)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReportExecutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ReportExecution.objects.filter(is_deleted=False)
        template_id = self.request.query_params.get('template_id')
        if template_id:
            qs = qs.filter(template_id=template_id)
        return qs
