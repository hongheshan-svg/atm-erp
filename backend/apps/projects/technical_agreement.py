"""
技术协议管理模块 - 针对非标自动化行业
包含：技术协议模板、协议管理、签章确认、变更追踪
"""

from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# =============================================================================
# 模型定义
# =============================================================================


class TechnicalAgreementTemplate(BaseModel):
    """技术协议模板"""

    CATEGORY_CHOICES = [
        ('STANDARD', '标准设备'),
        ('CUSTOM', '非标设备'),
        ('ASSEMBLY', '组装线'),
        ('TESTING', '检测设备'),
        ('OTHER', '其他'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='模板编号')
    name = models.CharField(max_length=200, verbose_name='模板名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='CUSTOM', verbose_name='设备类别')
    version = models.CharField(max_length=20, default='V1.0', verbose_name='版本号')

    # 模板内容
    content = models.TextField(verbose_name='协议内容模板')
    technical_specs = models.JSONField(default=list, blank=True, verbose_name='技术参数模板')
    acceptance_criteria = models.JSONField(default=list, blank=True, verbose_name='验收标准模板')
    delivery_terms = models.TextField(blank=True, verbose_name='交付条款模板')
    warranty_terms = models.TextField(blank=True, verbose_name='质保条款模板')

    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'technical_agreement_template'
        verbose_name = '技术协议模板'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} - {self.name}'


class TechnicalAgreement(BaseModel):
    """技术协议"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('INTERNAL_REVIEW', '内部评审'),
        ('CUSTOMER_REVIEW', '客户评审'),
        ('CUSTOMER_CONFIRMED', '客户确认'),
        ('SIGNED', '已签署'),
        ('EFFECTIVE', '已生效'),
        ('CHANGED', '已变更'),
        ('CANCELLED', '已取消'),
    ]

    agreement_no = models.CharField(max_length=50, unique=True, verbose_name='协议编号')
    name = models.CharField(max_length=200, verbose_name='协议名称')

    # 关联信息
    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='technical_agreements', verbose_name='关联项目'
    )
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.PROTECT, related_name='technical_agreements', verbose_name='客户'
    )
    template = models.ForeignKey(
        TechnicalAgreementTemplate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='使用模板'
    )
    sales_contract = models.ForeignKey(
        'sales.SalesContract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='technical_agreements',
        verbose_name='销售合同',
    )

    # 协议内容
    version = models.CharField(max_length=20, default='V1.0', verbose_name='版本号')
    content = models.TextField(verbose_name='协议内容')
    technical_specs = models.JSONField(default=list, blank=True, verbose_name='技术参数')
    acceptance_criteria = models.JSONField(default=list, blank=True, verbose_name='验收标准')
    delivery_terms = models.TextField(blank=True, verbose_name='交付条款')
    warranty_terms = models.TextField(blank=True, verbose_name='质保条款')
    special_requirements = models.TextField(blank=True, verbose_name='特殊要求')

    # 状态信息
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 签署信息
    our_signer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_agreements',
        verbose_name='我方签署人',
    )
    our_sign_date = models.DateField(null=True, blank=True, verbose_name='我方签署日期')
    customer_signer = models.CharField(max_length=100, blank=True, verbose_name='客户签署人')
    customer_sign_date = models.DateField(null=True, blank=True, verbose_name='客户签署日期')

    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'technical_agreement'
        verbose_name = '技术协议'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.agreement_no} - {self.name}'


class TechnicalAgreementChange(BaseModel):
    """技术协议变更记录"""

    CHANGE_TYPE_CHOICES = [
        ('SPEC_CHANGE', '技术参数变更'),
        ('CRITERIA_CHANGE', '验收标准变更'),
        ('DELIVERY_CHANGE', '交付条款变更'),
        ('WARRANTY_CHANGE', '质保条款变更'),
        ('OTHER', '其他变更'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已驳回'),
        ('IMPLEMENTED', '已实施'),
    ]

    agreement = models.ForeignKey(
        TechnicalAgreement, on_delete=models.CASCADE, related_name='changes', verbose_name='技术协议'
    )
    change_no = models.CharField(max_length=50, verbose_name='变更编号')
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES, verbose_name='变更类型')

    # 变更内容
    old_version = models.CharField(max_length=20, verbose_name='原版本号')
    new_version = models.CharField(max_length=20, verbose_name='新版本号')
    change_reason = models.TextField(verbose_name='变更原因')
    change_content = models.TextField(verbose_name='变更内容')
    impact_analysis = models.TextField(blank=True, verbose_name='影响分析')

    # 审批信息
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='agreement_change_requests',
        verbose_name='申请人',
    )
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agreement_change_approvals',
        verbose_name='审批人',
    )
    approved_date = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    # 客户确认
    customer_confirmed = models.BooleanField(default=False, verbose_name='客户已确认')
    customer_confirm_date = models.DateField(null=True, blank=True, verbose_name='客户确认日期')

    class Meta:
        db_table = 'technical_agreement_change'
        verbose_name = '技术协议变更'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.change_no} - {self.agreement.agreement_no}'


# =============================================================================
# 序列化器
# =============================================================================


class TechnicalAgreementTemplateSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = TechnicalAgreementTemplate
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TechnicalAgreementChangeSerializer(serializers.ModelSerializer):
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)

    class Meta:
        model = TechnicalAgreementChange
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TechnicalAgreementSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    our_signer_name = serializers.CharField(source='our_signer.get_full_name', read_only=True)
    changes = TechnicalAgreementChangeSerializer(many=True, read_only=True)
    change_count = serializers.SerializerMethodField()

    class Meta:
        model = TechnicalAgreement
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_change_count(self, obj):
        return obj.changes.count()


class TechnicalAgreementListSerializer(serializers.ModelSerializer):
    """列表用简化序列化器"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    change_count = serializers.SerializerMethodField()

    class Meta:
        model = TechnicalAgreement
        fields = [
            'id',
            'agreement_no',
            'name',
            'project',
            'project_name',
            'customer',
            'customer_name',
            'version',
            'status',
            'status_display',
            'our_sign_date',
            'customer_sign_date',
            'change_count',
            'created_at',
        ]

    def get_change_count(self, obj):
        return obj.changes.count()


# =============================================================================
# 视图集
# =============================================================================


class TechnicalAgreementTemplateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术协议模板管理"""

    queryset = TechnicalAgreementTemplate.objects.all()
    serializer_class = TechnicalAgreementTemplateSerializer
    filterset_fields = ['category', 'is_active', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'created_at']

    @action(detail=False, methods=['get'])
    def active_templates(self, request):
        """获取所有启用的模板"""
        templates = self.get_queryset().filter(is_active=True, is_deleted=False)
        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)


class TechnicalAgreementViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术协议管理"""

    queryset = TechnicalAgreement.objects.all()
    filterset_fields = ['project', 'customer', 'status', 'is_deleted']
    search_fields = ['agreement_no', 'name']
    ordering_fields = ['agreement_no', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return TechnicalAgreementListSerializer
        return TechnicalAgreementSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related('project', 'customer', 'template', 'our_signer')
            .prefetch_related('changes')
        )

    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交内部评审"""
        agreement = self.get_object()
        if agreement.status != 'DRAFT':
            return Response({'error': '只有草稿状态可以提交评审'}, status=status.HTTP_400_BAD_REQUEST)

        agreement.status = 'INTERNAL_REVIEW'
        agreement.save()
        return Response(TechnicalAgreementSerializer(agreement).data)

    @action(detail=True, methods=['post'])
    def send_to_customer(self, request, pk=None):
        """发送给客户评审"""
        agreement = self.get_object()
        if agreement.status != 'INTERNAL_REVIEW':
            return Response({'error': '只有内部评审通过后才能发送给客户'}, status=status.HTTP_400_BAD_REQUEST)

        agreement.status = 'CUSTOMER_REVIEW'
        agreement.save()
        return Response(TechnicalAgreementSerializer(agreement).data)

    @action(detail=True, methods=['post'])
    def customer_confirm(self, request, pk=None):
        """客户确认"""
        agreement = self.get_object()
        if agreement.status != 'CUSTOMER_REVIEW':
            return Response({'error': '只有客户评审状态才能确认'}, status=status.HTTP_400_BAD_REQUEST)

        agreement.status = 'CUSTOMER_CONFIRMED'
        agreement.customer_signer = request.data.get('customer_signer', '')
        agreement.customer_sign_date = request.data.get('customer_sign_date')
        agreement.save()
        return Response(TechnicalAgreementSerializer(agreement).data)

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """签署协议"""
        agreement = self.get_object()
        if agreement.status != 'CUSTOMER_CONFIRMED':
            return Response({'error': '只有客户确认后才能签署'}, status=status.HTTP_400_BAD_REQUEST)

        agreement.status = 'SIGNED'
        agreement.our_signer = request.user
        agreement.our_sign_date = request.data.get('sign_date')
        agreement.save()
        return Response(TechnicalAgreementSerializer(agreement).data)

    @action(detail=True, methods=['post'])
    def make_effective(self, request, pk=None):
        """使协议生效"""
        agreement = self.get_object()
        if agreement.status != 'SIGNED':
            return Response({'error': '只有已签署的协议才能生效'}, status=status.HTTP_400_BAD_REQUEST)

        agreement.status = 'EFFECTIVE'
        agreement.save()
        return Response(TechnicalAgreementSerializer(agreement).data)

    @action(detail=True, methods=['post'])
    def create_from_template(self, request, pk=None):
        """从模板创建协议内容"""
        agreement = self.get_object()
        template_id = request.data.get('template_id')

        try:
            template = TechnicalAgreementTemplate.objects.get(id=template_id)
            agreement.template = template
            agreement.content = template.content
            agreement.technical_specs = template.technical_specs
            agreement.acceptance_criteria = template.acceptance_criteria
            agreement.delivery_terms = template.delivery_terms
            agreement.warranty_terms = template.warranty_terms
            agreement.save()
            return Response(TechnicalAgreementSerializer(agreement).data)
        except TechnicalAgreementTemplate.DoesNotExist:
            return Response({'error': '模板不存在'}, status=status.HTTP_404_NOT_FOUND)


class TechnicalAgreementChangeViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术协议变更管理"""

    queryset = TechnicalAgreementChange.objects.all()
    serializer_class = TechnicalAgreementChangeSerializer
    filterset_fields = ['agreement', 'change_type', 'status', 'is_deleted']
    search_fields = ['change_no', 'change_reason']
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批变更"""
        change = self.get_object()
        if change.status != 'PENDING':
            return Response({'error': '只有待审批状态才能审批'}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone

        change.status = 'APPROVED'
        change.approved_by = request.user
        change.approved_date = timezone.now()
        change.save()
        return Response(TechnicalAgreementChangeSerializer(change).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """驳回变更"""
        change = self.get_object()
        if change.status != 'PENDING':
            return Response({'error': '只有待审批状态才能驳回'}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone

        change.status = 'REJECTED'
        change.approved_by = request.user
        change.approved_date = timezone.now()
        change.save()
        return Response(TechnicalAgreementChangeSerializer(change).data)

    @action(detail=True, methods=['post'])
    def implement(self, request, pk=None):
        """实施变更"""
        change = self.get_object()
        if change.status != 'APPROVED':
            return Response({'error': '只有已批准的变更才能实施'}, status=status.HTTP_400_BAD_REQUEST)

        # 更新协议版本
        agreement = change.agreement
        agreement.version = change.new_version
        agreement.status = 'CHANGED'
        agreement.save()

        change.status = 'IMPLEMENTED'
        change.save()

        return Response(TechnicalAgreementChangeSerializer(change).data)
