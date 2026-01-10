"""
需求管理模块
Requirements Management
客户需求收集、分解、追溯
"""
from datetime import date
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class RequirementCategory(BaseModel):
    """需求分类"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类编码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级分类'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'plm_requirement_category'
        verbose_name = '需求分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']
    
    def __str__(self):
        return self.name


class Requirement(BaseModel):
    """客户需求"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('REVIEWING', '评审中'),
        ('APPROVED', '已批准'),
        ('IN_PROGRESS', '实施中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('CRITICAL', '紧急'),
    ]
    
    TYPE_CHOICES = [
        ('FUNCTIONAL', '功能需求'),
        ('PERFORMANCE', '性能需求'),
        ('INTERFACE', '接口需求'),
        ('SAFETY', '安全需求'),
        ('QUALITY', '质量需求'),
        ('OTHER', '其他'),
    ]
    
    req_no = models.CharField(max_length=50, unique=True, verbose_name='需求编号')
    title = models.CharField(max_length=200, verbose_name='需求标题')
    
    # 关联
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        verbose_name='客户'
    )
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        verbose_name='商机'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        verbose_name='项目'
    )
    category = models.ForeignKey(
        RequirementCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        verbose_name='需求分类'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级需求'
    )
    
    # 需求详情
    req_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='FUNCTIONAL',
        verbose_name='需求类型'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        verbose_name='优先级'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    description = models.TextField(verbose_name='需求描述')
    acceptance_criteria = models.TextField(blank=True, verbose_name='验收标准')
    assumptions = models.TextField(blank=True, verbose_name='假设条件')
    constraints = models.TextField(blank=True, verbose_name='约束条件')
    
    # 日期
    request_date = models.DateField(default=date.today, verbose_name='提出日期')
    due_date = models.DateField(null=True, blank=True, verbose_name='期望日期')
    completed_date = models.DateField(null=True, blank=True, verbose_name='完成日期')
    
    # 评估
    estimated_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='预估工时'
    )
    estimated_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='预估成本'
    )
    
    # 负责人
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_requirements',
        verbose_name='负责人'
    )
    
    # 版本
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    
    class Meta:
        db_table = 'plm_requirement'
        verbose_name = '客户需求'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.req_no} - {self.title}'
    
    def save(self, *args, **kwargs):
        if not self.req_no:
            from apps.core.utils import generate_code
            self.req_no = generate_code('REQ')
        super().save(*args, **kwargs)


class RequirementChange(BaseModel):
    """需求变更记录"""
    CHANGE_TYPES = [
        ('ADD', '新增'),
        ('MODIFY', '修改'),
        ('DELETE', '删除'),
        ('SCOPE', '范围变更'),
    ]
    
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='changes',
        verbose_name='需求'
    )
    change_type = models.CharField(
        max_length=20,
        choices=CHANGE_TYPES,
        verbose_name='变更类型'
    )
    change_reason = models.TextField(verbose_name='变更原因')
    old_content = models.TextField(blank=True, verbose_name='原内容')
    new_content = models.TextField(blank=True, verbose_name='新内容')
    impact_analysis = models.TextField(blank=True, verbose_name='影响分析')
    
    # 审批
    is_approved = models.BooleanField(default=False, verbose_name='是否批准')
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_req_changes',
        verbose_name='批准人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='批准时间')
    
    class Meta:
        db_table = 'plm_requirement_change'
        verbose_name = '需求变更'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class RequirementTrace(BaseModel):
    """需求追溯"""
    TRACE_TYPES = [
        ('DESIGN', '设计文档'),
        ('BOM', 'BOM'),
        ('DRAWING', '图纸'),
        ('TASK', '任务'),
        ('TEST', '测试用例'),
        ('CODE', '代码'),
    ]
    
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='traces',
        verbose_name='需求'
    )
    trace_type = models.CharField(
        max_length=20,
        choices=TRACE_TYPES,
        verbose_name='追溯类型'
    )
    target_id = models.IntegerField(verbose_name='目标ID')
    target_name = models.CharField(max_length=200, verbose_name='目标名称')
    target_url = models.CharField(max_length=500, blank=True, verbose_name='目标链接')
    description = models.TextField(blank=True, verbose_name='说明')
    
    class Meta:
        db_table = 'plm_requirement_trace'
        verbose_name = '需求追溯'
        verbose_name_plural = verbose_name


# =====================
# Serializers
# =====================

class RequirementCategorySerializer(serializers.ModelSerializer):
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RequirementCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class RequirementChangeSerializer(serializers.ModelSerializer):
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = RequirementChange
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approved_by', 'approved_at']


class RequirementTraceSerializer(serializers.ModelSerializer):
    trace_type_display = serializers.CharField(source='get_trace_type_display', read_only=True)
    
    class Meta:
        model = RequirementTrace
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class RequirementSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    type_display = serializers.CharField(source='get_req_type_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    children_count = serializers.SerializerMethodField()
    traces = RequirementTraceSerializer(many=True, read_only=True)
    changes = RequirementChangeSerializer(many=True, read_only=True)
    
    class Meta:
        model = Requirement
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'req_no']
    
    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class RequirementListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    type_display = serializers.CharField(source='get_req_type_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Requirement
        fields = [
            'id', 'req_no', 'title', 'req_type', 'type_display',
            'priority', 'priority_display', 'status', 'status_display',
            'customer', 'customer_name', 'project', 'project_name',
            'owner', 'owner_name', 'request_date', 'due_date',
            'estimated_hours', 'children_count', 'created_at'
        ]
    
    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


# =====================
# ViewSets
# =====================

class RequirementCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """需求分类管理"""
    queryset = RequirementCategory.objects.filter(is_deleted=False)
    serializer_class = RequirementCategorySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'code']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取树形结构"""
        categories = self.get_queryset().filter(parent__isnull=True)
        
        def build_tree(cat):
            return {
                'id': cat.id,
                'name': cat.name,
                'code': cat.code,
                'children': [build_tree(c) for c in cat.children.filter(is_deleted=False)]
            }
        
        return Response([build_tree(c) for c in categories])


class RequirementViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """需求管理"""
    queryset = Requirement.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'priority', 'req_type', 'customer', 'project', 'owner', 'category']
    search_fields = ['req_no', 'title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RequirementListSerializer
        return RequirementSerializer
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交需求"""
        req = self.get_object()
        if req.status != 'DRAFT':
            return Response({'error': '只有草稿状态可以提交'}, status=400)
        req.status = 'SUBMITTED'
        req.save()
        return Response(self.get_serializer(req).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准需求"""
        req = self.get_object()
        if req.status not in ['SUBMITTED', 'REVIEWING']:
            return Response({'error': '只有已提交或评审中的需求可以批准'}, status=400)
        req.status = 'APPROVED'
        req.save()
        return Response(self.get_serializer(req).data)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始实施"""
        req = self.get_object()
        if req.status != 'APPROVED':
            return Response({'error': '只有已批准的需求可以开始实施'}, status=400)
        req.status = 'IN_PROGRESS'
        req.save()
        return Response(self.get_serializer(req).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成需求"""
        req = self.get_object()
        req.status = 'COMPLETED'
        req.completed_date = date.today()
        req.save()
        return Response(self.get_serializer(req).data)
    
    @action(detail=True, methods=['post'])
    def decompose(self, request, pk=None):
        """分解需求"""
        parent = self.get_object()
        children_data = request.data.get('children', [])
        
        created = []
        for child_data in children_data:
            child = Requirement.objects.create(
                parent=parent,
                customer=parent.customer,
                project=parent.project,
                title=child_data.get('title'),
                description=child_data.get('description', ''),
                req_type=child_data.get('req_type', parent.req_type),
                priority=child_data.get('priority', parent.priority),
                created_by=request.user
            )
            created.append(child)
        
        return Response({
            'success': True,
            'created_count': len(created),
            'children': RequirementListSerializer(created, many=True).data
        })
    
    @action(detail=True, methods=['post'])
    def add_trace(self, request, pk=None):
        """添加追溯"""
        req = self.get_object()
        
        trace = RequirementTrace.objects.create(
            requirement=req,
            trace_type=request.data.get('trace_type'),
            target_id=request.data.get('target_id'),
            target_name=request.data.get('target_name'),
            target_url=request.data.get('target_url', ''),
            description=request.data.get('description', ''),
            created_by=request.user
        )
        
        return Response(RequirementTraceSerializer(trace).data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """需求统计"""
        qs = self.get_queryset()
        
        by_status = qs.values('status').annotate(count=Count('id'))
        by_priority = qs.values('priority').annotate(count=Count('id'))
        by_type = qs.values('req_type').annotate(count=Count('id'))
        
        # 本月新增
        month_start = date.today().replace(day=1)
        new_this_month = qs.filter(created_at__date__gte=month_start).count()
        
        # 待处理
        pending = qs.filter(status__in=['SUBMITTED', 'REVIEWING', 'APPROVED']).count()
        
        return Response({
            'total': qs.count(),
            'new_this_month': new_this_month,
            'pending': pending,
            'by_status': list(by_status),
            'by_priority': list(by_priority),
            'by_type': list(by_type)
        })


class RequirementChangeViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """需求变更管理"""
    queryset = RequirementChange.objects.filter(is_deleted=False)
    serializer_class = RequirementChangeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['requirement', 'change_type', 'is_approved']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准变更"""
        change = self.get_object()
        change.is_approved = True
        change.approved_by = request.user
        change.approved_at = timezone.now()
        change.save()
        return Response(self.get_serializer(change).data)
