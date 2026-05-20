"""
方案设计管理模块
Technical Proposal Management
PLM核心功能
"""

from datetime import date

from django.db import models
from django.db.models import Count
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class ProposalCategory(BaseModel):
    """方案分类"""

    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类编码')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name='上级分类'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'plm_proposal_category'
        verbose_name = '方案分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name


class TechnicalProposal(BaseModel):
    """技术方案"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('REVIEWING', '评审中'),
        ('REVISION', '需修改'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('ARCHIVED', '已归档'),
    ]

    TYPE_CHOICES = [
        ('SCHEME', '整体方案'),
        ('MECHANICAL', '机械方案'),
        ('ELECTRICAL', '电气方案'),
        ('SOFTWARE', '软件方案'),
        ('INTEGRATION', '集成方案'),
    ]

    proposal_no = models.CharField(max_length=50, unique=True, verbose_name='方案编号')
    title = models.CharField(max_length=200, verbose_name='方案名称')

    # 关联
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
        verbose_name='客户',
    )
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
        verbose_name='商机',
    )
    requirement = models.ForeignKey(
        'projects.Requirement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
        verbose_name='需求',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
        verbose_name='项目',
    )
    category = models.ForeignKey(
        ProposalCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposals',
        verbose_name='方案分类',
    )

    # 类型和状态
    proposal_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SCHEME', verbose_name='方案类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 版本管理
    version = models.CharField(max_length=20, default='V1.0', verbose_name='版本号')
    parent_version = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_versions', verbose_name='上一版本'
    )

    # 内容
    summary = models.TextField(blank=True, verbose_name='方案概述')
    technical_requirements = models.TextField(blank=True, verbose_name='技术要求')
    solution_description = models.TextField(blank=True, verbose_name='方案描述')
    key_technologies = models.TextField(blank=True, verbose_name='关键技术')
    risk_analysis = models.TextField(blank=True, verbose_name='风险分析')
    implementation_plan = models.TextField(blank=True, verbose_name='实施计划')

    # 评估
    estimated_cost = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name='预估成本'
    )
    estimated_days = models.IntegerField(null=True, blank=True, verbose_name='预估工期(天)')

    # 负责人
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authored_proposals',
        verbose_name='编制人',
    )
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewing_proposals',
        verbose_name='评审人',
    )

    # 日期
    submit_date = models.DateField(null=True, blank=True, verbose_name='提交日期')
    review_date = models.DateField(null=True, blank=True, verbose_name='评审日期')
    approve_date = models.DateField(null=True, blank=True, verbose_name='批准日期')

    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')

    class Meta:
        db_table = 'plm_technical_proposal'
        verbose_name = '技术方案'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.proposal_no} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.proposal_no:
            from apps.core.utils import generate_code

            self.proposal_no = generate_code('FA')  # 方案
        super().save(*args, **kwargs)


class ProposalReview(BaseModel):
    """方案评审"""

    RESULT_CHOICES = [
        ('PENDING', '待评审'),
        ('APPROVED', '通过'),
        ('CONDITIONAL', '有条件通过'),
        ('REVISION', '需修改'),
        ('REJECTED', '拒绝'),
    ]

    proposal = models.ForeignKey(
        TechnicalProposal, on_delete=models.CASCADE, related_name='reviews', verbose_name='方案'
    )

    # 评审信息
    review_date = models.DateField(default=date.today, verbose_name='评审日期')
    review_type = models.CharField(max_length=50, default='技术评审', verbose_name='评审类型')

    # 评审人
    reviewers = models.ManyToManyField(
        'accounts.User',
        through='ProposalReviewItem',
        through_fields=('review', 'reviewer'),
        related_name='proposal_reviews',
        verbose_name='评审人',
    )

    # 评审结论
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='PENDING', verbose_name='评审结论')
    conclusion = models.TextField(blank=True, verbose_name='评审结论说明')
    issues = models.TextField(blank=True, verbose_name='遗留问题')
    action_items = models.JSONField(default=list, blank=True, verbose_name='待办事项')

    meeting_minutes = models.TextField(blank=True, verbose_name='会议纪要')

    class Meta:
        db_table = 'plm_proposal_review'
        verbose_name = '方案评审'
        verbose_name_plural = verbose_name
        ordering = ['-review_date']


class ProposalReviewItem(BaseModel):
    """评审意见"""

    review = models.ForeignKey(
        ProposalReview, on_delete=models.CASCADE, related_name='review_items', verbose_name='评审'
    )
    reviewer = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='proposal_review_items', verbose_name='评审人'
    )

    # 评分
    score = models.IntegerField(default=0, verbose_name='评分(1-10)')

    # 意见
    opinion = models.TextField(blank=True, verbose_name='评审意见')
    suggestions = models.TextField(blank=True, verbose_name='改进建议')

    # 结论
    is_approved = models.BooleanField(default=False, verbose_name='是否同意')

    class Meta:
        db_table = 'plm_proposal_review_item'
        verbose_name = '评审意见'
        verbose_name_plural = verbose_name
        unique_together = ['review', 'reviewer']


class ProposalDocument(BaseModel):
    """方案文档"""

    DOC_TYPES = [
        ('MAIN', '主方案文档'),
        ('ATTACHMENT', '附件'),
        ('DRAWING', '图纸'),
        ('CALCULATION', '计算书'),
        ('BOM', 'BOM清单'),
        ('OTHER', '其他'),
    ]

    proposal = models.ForeignKey(
        TechnicalProposal, on_delete=models.CASCADE, related_name='documents', verbose_name='方案'
    )

    doc_type = models.CharField(max_length=20, choices=DOC_TYPES, default='ATTACHMENT', verbose_name='文档类型')
    name = models.CharField(max_length=200, verbose_name='文档名称')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_size = models.IntegerField(default=0, verbose_name='文件大小(bytes)')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'plm_proposal_document'
        verbose_name = '方案文档'
        verbose_name_plural = verbose_name


# =====================
# Serializers
# =====================


class ProposalCategorySerializer(serializers.ModelSerializer):
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = ProposalCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class ProposalDocumentSerializer(serializers.ModelSerializer):
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)

    class Meta:
        model = ProposalDocument
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProposalReviewItemSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)

    class Meta:
        model = ProposalReviewItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProposalReviewSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    review_items = ProposalReviewItemSerializer(many=True, read_only=True)

    class Meta:
        model = ProposalReview
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class TechnicalProposalSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_proposal_type_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    requirement_title = serializers.CharField(source='requirement.title', read_only=True)
    documents = ProposalDocumentSerializer(many=True, read_only=True)
    reviews = ProposalReviewSerializer(many=True, read_only=True)

    class Meta:
        model = TechnicalProposal
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'proposal_no']


class TechnicalProposalListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_proposal_type_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = TechnicalProposal
        fields = [
            'id',
            'proposal_no',
            'title',
            'proposal_type',
            'type_display',
            'status',
            'status_display',
            'version',
            'customer',
            'customer_name',
            'project',
            'project_name',
            'author',
            'author_name',
            'estimated_cost',
            'estimated_days',
            'submit_date',
            'created_at',
        ]


# =====================
# ViewSets
# =====================


class ProposalCategoryViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """方案分类管理"""

    queryset = ProposalCategory.objects.filter(is_deleted=False)
    serializer_class = ProposalCategorySerializer
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
                'children': [build_tree(c) for c in cat.children.filter(is_deleted=False)],
            }

        return Response([build_tree(c) for c in categories])


class TechnicalProposalViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术方案管理"""

    queryset = TechnicalProposal.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'proposal_type', 'customer', 'project', 'author', 'category']
    search_fields = ['proposal_no', 'title', 'summary']
    ordering_fields = ['created_at', 'submit_date', 'version']

    def get_serializer_class(self):
        if self.action == 'list':
            return TechnicalProposalListSerializer
        return TechnicalProposalSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交方案"""
        proposal = self.get_object()
        if proposal.status != 'DRAFT':
            return Response({'error': '只有草稿状态可以提交'}, status=400)
        proposal.status = 'SUBMITTED'
        proposal.submit_date = date.today()
        proposal.save()
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=['post'])
    def start_review(self, request, pk=None):
        """开始评审"""
        proposal = self.get_object()
        if proposal.status != 'SUBMITTED':
            return Response({'error': '只有已提交的方案可以评审'}, status=400)
        proposal.status = 'REVIEWING'
        proposal.review_date = date.today()
        proposal.save()

        # 创建评审记录
        review = ProposalReview.objects.create(
            proposal=proposal, review_type=request.data.get('review_type', '技术评审'), created_by=request.user
        )

        return Response(
            {'proposal': self.get_serializer(proposal).data, 'review': ProposalReviewSerializer(review).data}
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准方案"""
        proposal = self.get_object()
        if proposal.status != 'REVIEWING':
            return Response({'error': '只有评审中的方案可以批准'}, status=400)
        proposal.status = 'APPROVED'
        proposal.approve_date = date.today()
        proposal.save()
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝方案"""
        proposal = self.get_object()
        proposal.status = 'REJECTED'
        proposal.save()
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=['post'])
    def request_revision(self, request, pk=None):
        """要求修改"""
        proposal = self.get_object()
        proposal.status = 'REVISION'
        proposal.save()
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=['post'])
    def create_new_version(self, request, pk=None):
        """创建新版本"""
        original = self.get_object()

        # 计算新版本号
        version_parts = original.version.replace('V', '').split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        new_version = f'V{major}.{minor + 1}'

        # 创建新版本
        new_proposal = TechnicalProposal.objects.create(
            title=original.title,
            customer=original.customer,
            opportunity=original.opportunity,
            requirement=original.requirement,
            project=original.project,
            category=original.category,
            proposal_type=original.proposal_type,
            version=new_version,
            parent_version=original,
            summary=original.summary,
            technical_requirements=original.technical_requirements,
            solution_description=original.solution_description,
            key_technologies=original.key_technologies,
            risk_analysis=original.risk_analysis,
            implementation_plan=original.implementation_plan,
            estimated_cost=original.estimated_cost,
            estimated_days=original.estimated_days,
            author=request.user,
            created_by=request.user,
        )

        return Response(self.get_serializer(new_proposal).data)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """归档方案"""
        proposal = self.get_object()
        proposal.status = 'ARCHIVED'
        proposal.save()
        return Response(self.get_serializer(proposal).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """方案统计"""
        qs = self.get_queryset()

        by_status = qs.values('status').annotate(count=Count('id'))
        by_type = qs.values('proposal_type').annotate(count=Count('id'))

        # 本月新增
        month_start = date.today().replace(day=1)
        new_this_month = qs.filter(created_at__date__gte=month_start).count()

        # 待评审
        pending_review = qs.filter(status__in=['SUBMITTED', 'REVIEWING']).count()

        return Response(
            {
                'total': qs.count(),
                'new_this_month': new_this_month,
                'pending_review': pending_review,
                'by_status': list(by_status),
                'by_type': list(by_type),
            }
        )


class ProposalReviewViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """方案评审管理"""

    queryset = ProposalReview.objects.filter(is_deleted=False)
    serializer_class = ProposalReviewSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['proposal', 'result']

    @action(detail=True, methods=['post'])
    def add_review_item(self, request, pk=None):
        """添加评审意见"""
        review = self.get_object()

        item = ProposalReviewItem.objects.create(
            review=review,
            reviewer=request.user,
            score=request.data.get('score', 0),
            opinion=request.data.get('opinion', ''),
            suggestions=request.data.get('suggestions', ''),
            is_approved=request.data.get('is_approved', False),
            created_by=request.user,
        )

        return Response(ProposalReviewItemSerializer(item).data)

    @action(detail=True, methods=['post'])
    def conclude(self, request, pk=None):
        """评审结论"""
        review = self.get_object()

        review.result = request.data.get('result', 'APPROVED')
        review.conclusion = request.data.get('conclusion', '')
        review.issues = request.data.get('issues', '')
        review.action_items = request.data.get('action_items', [])
        review.meeting_minutes = request.data.get('meeting_minutes', '')
        review.save()

        # 更新方案状态
        proposal = review.proposal
        if review.result == 'APPROVED':
            proposal.status = 'APPROVED'
            proposal.approve_date = date.today()
        elif review.result in ['REVISION', 'CONDITIONAL']:
            proposal.status = 'REVISION'
        elif review.result == 'REJECTED':
            proposal.status = 'REJECTED'
        proposal.save()

        return Response(self.get_serializer(review).data)


class ProposalDocumentViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """方案文档管理"""

    queryset = ProposalDocument.objects.filter(is_deleted=False)
    serializer_class = ProposalDocumentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['proposal', 'doc_type']
