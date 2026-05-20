"""
设计变更管理增强模块
ECN Enhanced Management - 变更影响分析、成本估算、审批流程
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

User = settings.AUTH_USER_MODEL


class ECNChangeRequest(BaseModel):
    """设计变更申请"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('REVIEWING', '评审中'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('IMPLEMENTING', '实施中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]

    CHANGE_TYPE_CHOICES = [
        ('DESIGN', '设计变更'),
        ('MATERIAL', '材料变更'),
        ('PROCESS', '工艺变更'),
        ('SPEC', '规格变更'),
        ('SUPPLIER', '供应商变更'),
        ('OTHER', '其他'),
    ]

    ecn_no = models.CharField('变更编号', max_length=50, unique=True)
    title = models.CharField('变更标题', max_length=200)
    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='ecn_requests', verbose_name='关联项目'
    )
    change_type = models.CharField('变更类型', max_length=20, choices=CHANGE_TYPE_CHOICES)
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # 变更原因
    reason = models.TextField('变更原因')
    customer_request = models.BooleanField('客户要求', default=False)
    customer_confirmation_required = models.BooleanField('需客户确认', default=True)

    # 变更描述
    current_state = models.TextField('当前状态描述')
    proposed_change = models.TextField('变更方案描述')

    # 影响分析
    impact_bom = models.BooleanField('影响BOM', default=False)
    impact_procurement = models.BooleanField('影响采购', default=False)
    impact_production = models.BooleanField('影响生产', default=False)
    impact_quality = models.BooleanField('影响质量', default=False)
    impact_delivery = models.BooleanField('影响交期', default=False)
    impact_cost = models.BooleanField('影响成本', default=False)
    impact_analysis = models.TextField('影响分析详情', blank=True)

    # 成本估算
    estimated_material_cost = models.DecimalField('预估材料成本变化', max_digits=14, decimal_places=2, default=0)
    estimated_labor_cost = models.DecimalField('预估人工成本变化', max_digits=14, decimal_places=2, default=0)
    estimated_outsource_cost = models.DecimalField('预估外协成本变化', max_digits=14, decimal_places=2, default=0)
    estimated_other_cost = models.DecimalField('预估其他成本变化', max_digits=14, decimal_places=2, default=0)
    cost_remarks = models.TextField('成本说明', blank=True)

    # 交期影响
    original_delivery_date = models.DateField('原交期', null=True, blank=True)
    new_delivery_date = models.DateField('新交期', null=True, blank=True)
    delivery_delay_days = models.IntegerField('延期天数', default=0)

    # 申请人信息
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='ecn_requests', verbose_name='申请人'
    )
    requested_date = models.DateTimeField('申请时间', auto_now_add=True)

    # 客户确认
    customer_confirmed = models.BooleanField('客户已确认', default=False)
    customer_confirmed_by = models.CharField('客户确认人', max_length=100, blank=True)
    customer_confirmed_date = models.DateTimeField('客户确认时间', null=True, blank=True)
    customer_remarks = models.TextField('客户意见', blank=True)

    class Meta:
        db_table = 'ecn_change_request'
        verbose_name = '设计变更申请'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.ecn_no} - {self.title}'

    @property
    def total_estimated_cost(self):
        return (
            self.estimated_material_cost
            + self.estimated_labor_cost
            + self.estimated_outsource_cost
            + self.estimated_other_cost
        )

    def save(self, *args, **kwargs):
        if not self.ecn_no:
            # 自动生成编号
            today = timezone.now()
            prefix = f'ECN{today.strftime("%Y%m%d")}'
            last = ECNChangeRequest.objects.filter(ecn_no__startswith=prefix).order_by('-ecn_no').first()
            if last:
                seq = int(last.ecn_no[-4:]) + 1
            else:
                seq = 1
            self.ecn_no = f'{prefix}{seq:04d}'
        super().save(*args, **kwargs)


class ECNAffectedItem(BaseModel):
    """变更影响的物料/BOM项"""

    ecn = models.ForeignKey(
        ECNChangeRequest, on_delete=models.CASCADE, related_name='affected_items', verbose_name='变更申请'
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.CASCADE, related_name='ecn_affected', verbose_name='物料'
    )
    bom_item = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecn_affected',
        verbose_name='BOM项',
    )

    CHANGE_ACTION_CHOICES = [
        ('ADD', '新增'),
        ('MODIFY', '修改'),
        ('REPLACE', '替换'),
        ('DELETE', '删除'),
    ]

    change_action = models.CharField('变更动作', max_length=20, choices=CHANGE_ACTION_CHOICES)
    original_spec = models.TextField('原规格/参数', blank=True)
    new_spec = models.TextField('新规格/参数', blank=True)
    original_qty = models.DecimalField('原数量', max_digits=14, decimal_places=4, default=0)
    new_qty = models.DecimalField('新数量', max_digits=14, decimal_places=4, default=0)
    replace_item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecn_replace_to',
        verbose_name='替换物料',
    )
    cost_impact = models.DecimalField('成本影响', max_digits=14, decimal_places=2, default=0)
    remarks = models.TextField('备注', blank=True)

    class Meta:
        db_table = 'ecn_affected_item'
        verbose_name = '变更影响物料'


class ECNReviewRecord(BaseModel):
    """变更评审记录"""

    ecn = models.ForeignKey(
        ECNChangeRequest, on_delete=models.CASCADE, related_name='review_records', verbose_name='变更申请'
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='ecn_reviews', verbose_name='评审人'
    )
    review_role = models.CharField('评审角色', max_length=50)  # 设计、采购、生产、质量等

    DECISION_CHOICES = [
        ('PENDING', '待评审'),
        ('APPROVED', '同意'),
        ('REJECTED', '拒绝'),
        ('CONDITIONALLY_APPROVED', '有条件同意'),
    ]

    decision = models.CharField('评审决定', max_length=30, choices=DECISION_CHOICES, default='PENDING')
    comments = models.TextField('评审意见', blank=True)
    conditions = models.TextField('附加条件', blank=True)
    review_date = models.DateTimeField('评审时间', null=True, blank=True)

    class Meta:
        db_table = 'ecn_review_record'
        verbose_name = '变更评审记录'


class ECNImplementation(BaseModel):
    """变更实施记录"""

    ecn = models.ForeignKey(
        ECNChangeRequest, on_delete=models.CASCADE, related_name='implementations', verbose_name='变更申请'
    )

    IMPL_TYPE_CHOICES = [
        ('BOM_UPDATE', 'BOM更新'),
        ('DRAWING_UPDATE', '图纸更新'),
        ('PROCESS_UPDATE', '工艺更新'),
        ('PROCUREMENT', '采购调整'),
        ('INVENTORY', '库存处理'),
        ('PRODUCTION', '生产调整'),
        ('OTHER', '其他'),
    ]

    impl_type = models.CharField('实施类型', max_length=30, choices=IMPL_TYPE_CHOICES)
    description = models.TextField('实施内容')
    responsible = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='ecn_implementations', verbose_name='负责人'
    )
    planned_date = models.DateField('计划完成日期')
    actual_date = models.DateField('实际完成日期', null=True, blank=True)
    status = models.CharField(
        '状态',
        max_length=20,
        default='PENDING',
        choices=[('PENDING', '待实施'), ('IN_PROGRESS', '进行中'), ('COMPLETED', '已完成'), ('CANCELLED', '已取消')],
    )
    result = models.TextField('实施结果', blank=True)

    class Meta:
        db_table = 'ecn_implementation'
        verbose_name = '变更实施记录'


# ==================== Serializers ====================


class ECNAffectedItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_code = serializers.CharField(source='item.sku', read_only=True)
    replace_item_name = serializers.CharField(source='replace_item.name', read_only=True)

    class Meta:
        model = ECNAffectedItem
        fields = '__all__'


class ECNReviewRecordSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)

    class Meta:
        model = ECNReviewRecord
        fields = '__all__'


class ECNImplementationSerializer(serializers.ModelSerializer):
    responsible_name = serializers.CharField(source='responsible.get_full_name', read_only=True)

    class Meta:
        model = ECNImplementation
        fields = '__all__'


class ECNChangeRequestSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    total_estimated_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    affected_items = ECNAffectedItemSerializer(many=True, read_only=True)
    review_records = ECNReviewRecordSerializer(many=True, read_only=True)
    implementations = ECNImplementationSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = ECNChangeRequest
        fields = '__all__'


# ==================== ViewSets ====================


class ECNChangeRequestViewSet(PermissionMixin, viewsets.ModelViewSet):
    """设计变更申请管理"""

    queryset = ECNChangeRequest.objects.filter(is_deleted=False)
    serializer_class = ECNChangeRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get('project')
        status_filter = self.request.query_params.get('status')
        change_type = self.request.query_params.get('change_type')

        if project:
            qs = qs.filter(project_id=project)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if change_type:
            qs = qs.filter(change_type=change_type)

        return qs.select_related('project', 'requested_by')

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交评审"""
        ecn = self.get_object()
        if ecn.status != 'DRAFT':
            return Response({'error': '只有草稿状态可以提交'}, status=400)

        ecn.status = 'SUBMITTED'
        ecn.save()

        # 创建评审记录
        review_roles = ['设计', '采购', '生产', '质量']
        for role in review_roles:
            ECNReviewRecord.objects.create(ecn=ecn, review_role=role, created_by=request.user, updated_by=request.user)

        return Response({'message': '已提交评审'})

    @action(detail=True, methods=['post'])
    def analyze_impact(self, request, pk=None):
        """分析变更影响"""
        ecn = self.get_object()

        # 分析BOM影响
        from apps.production.models import ProductionPlan
        from apps.purchase.models import PurchaseOrderLine

        affected_items = ecn.affected_items.all()
        item_ids = [ai.item_id for ai in affected_items]

        # 采购影响
        pending_po = PurchaseOrderLine.objects.filter(
            item_id__in=item_ids, order__project=ecn.project, order__status__in=['DRAFT', 'PENDING', 'APPROVED']
        ).select_related('order')

        # 生产影响
        production_impact = ProductionPlan.objects.filter(
            project=ecn.project, status__in=['DRAFT', 'CONFIRMED', 'IN_PROGRESS']
        ).count()

        # 成本影响汇总
        total_cost_impact = affected_items.aggregate(total=Sum('cost_impact'))['total'] or Decimal('0')

        impact_summary = {
            'affected_items_count': affected_items.count(),
            'pending_purchase_orders': pending_po.values('order__order_no').distinct().count(),
            'pending_purchase_lines': pending_po.count(),
            'affected_production_plans': production_impact,
            'total_cost_impact': float(total_cost_impact),
            'recommendations': [],
        }

        # 生成建议
        if pending_po.exists():
            impact_summary['recommendations'].append('建议暂停相关采购订单，等待变更确认')
        if production_impact > 0:
            impact_summary['recommendations'].append('建议评估生产计划调整方案')
        if total_cost_impact > 0:
            impact_summary['recommendations'].append('变更将增加成本，建议与客户沟通费用承担')
        elif total_cost_impact < 0:
            impact_summary['recommendations'].append('变更可降低成本')

        # 更新ECN记录
        ecn.impact_procurement = pending_po.exists()
        ecn.impact_production = production_impact > 0
        ecn.impact_cost = total_cost_impact != 0
        ecn.impact_analysis = str(impact_summary)
        ecn.save()

        return Response(impact_summary)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准变更"""
        ecn = self.get_object()

        # 检查所有评审是否完成
        pending_reviews = ecn.review_records.filter(decision='PENDING').count()
        if pending_reviews > 0:
            return Response({'error': f'还有{pending_reviews}个评审未完成'}, status=400)

        # 检查是否有拒绝
        rejected = ecn.review_records.filter(decision='REJECTED').exists()
        if rejected:
            return Response({'error': '存在拒绝意见，无法批准'}, status=400)

        ecn.status = 'APPROVED'
        ecn.save()

        return Response({'message': '变更已批准'})

    @action(detail=True, methods=['post'])
    def customer_confirm(self, request, pk=None):
        """客户确认"""
        ecn = self.get_object()

        ecn.customer_confirmed = True
        ecn.customer_confirmed_by = request.data.get('confirmed_by', '')
        ecn.customer_confirmed_date = timezone.now()
        ecn.customer_remarks = request.data.get('remarks', '')
        ecn.save()

        return Response({'message': '客户已确认'})

    @action(detail=True, methods=['post'])
    def start_implementation(self, request, pk=None):
        """开始实施"""
        ecn = self.get_object()

        if ecn.status != 'APPROVED':
            return Response({'error': '只有已批准的变更可以开始实施'}, status=400)

        if ecn.customer_confirmation_required and not ecn.customer_confirmed:
            return Response({'error': '需要客户确认后才能实施'}, status=400)

        ecn.status = 'IMPLEMENTING'
        ecn.save()

        return Response({'message': '已开始实施'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成变更"""
        ecn = self.get_object()

        # 检查实施项是否全部完成
        pending_impl = ecn.implementations.exclude(status='COMPLETED').count()
        if pending_impl > 0:
            return Response({'error': f'还有{pending_impl}个实施项未完成'}, status=400)

        ecn.status = 'COMPLETED'
        ecn.save()

        return Response({'message': '变更已完成'})

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """变更统计"""
        project_id = request.query_params.get('project')

        qs = self.get_queryset()
        if project_id:
            qs = qs.filter(project_id=project_id)

        stats = {
            'total': qs.count(),
            'by_status': {},
            'by_type': {},
            'cost_impact': {
                'total_increase': 0,
                'total_decrease': 0,
            },
            'avg_processing_days': 0,
        }

        # 按状态统计
        status_counts = qs.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats['by_status'][item['status']] = item['count']

        # 按类型统计
        type_counts = qs.values('change_type').annotate(count=Count('id'))
        for item in type_counts:
            stats['by_type'][item['change_type']] = item['count']

        # 成本影响
        cost_agg = qs.aggregate(
            material=Sum('estimated_material_cost'),
            labor=Sum('estimated_labor_cost'),
            outsource=Sum('estimated_outsource_cost'),
            other=Sum('estimated_other_cost'),
        )
        total_cost = sum(v or 0 for v in cost_agg.values())
        if total_cost > 0:
            stats['cost_impact']['total_increase'] = float(total_cost)
        else:
            stats['cost_impact']['total_decrease'] = float(abs(total_cost))

        return Response(stats)


class ECNAffectedItemViewSet(PermissionMixin, viewsets.ModelViewSet):
    """变更影响物料管理"""

    queryset = ECNAffectedItem.objects.filter(is_deleted=False)
    serializer_class = ECNAffectedItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        ecn = self.request.query_params.get('ecn')
        if ecn:
            qs = qs.filter(ecn_id=ecn)
        return qs


class ECNReviewRecordViewSet(PermissionMixin, viewsets.ModelViewSet):
    """变更评审记录管理"""

    queryset = ECNReviewRecord.objects.filter(is_deleted=False)
    serializer_class = ECNReviewRecordSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """提交评审意见"""
        record = self.get_object()

        record.reviewer = request.user
        record.decision = request.data.get('decision')
        record.comments = request.data.get('comments', '')
        record.conditions = request.data.get('conditions', '')
        record.review_date = timezone.now()
        record.save()

        # 检查是否所有评审完成
        ecn = record.ecn
        pending = ecn.review_records.filter(decision='PENDING').count()
        if pending == 0:
            ecn.status = 'REVIEWING'  # 所有人已评审，等待最终决定
            ecn.save()

        return Response({'message': '评审意见已提交'})


class ECNImplementationViewSet(PermissionMixin, viewsets.ModelViewSet):
    """变更实施记录管理"""

    queryset = ECNImplementation.objects.filter(is_deleted=False)
    serializer_class = ECNImplementationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成实施项"""
        impl = self.get_object()

        impl.status = 'COMPLETED'
        impl.actual_date = timezone.now().date()
        impl.result = request.data.get('result', '')
        impl.save()

        return Response({'message': '实施项已完成'})
