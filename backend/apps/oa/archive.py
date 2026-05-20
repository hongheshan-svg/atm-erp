"""
电子档案管理模块
Electronic Archive Management
文档归档、档案分类、借阅管理等

非标自动化行业扩展建议：
- 档案分类可增加：项目技术资料、工程图纸、验收文档、培训资料
- 可关联项目：在档案中增加project字段关联到具体项目
- 建议与项目文档管理(projects.documents)配合使用
- 长期归档的技术资料（如设备手册、认证文件）适合放在此模块
"""

from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class ArchiveCategory(BaseModel):
    """档案分类"""

    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类编码')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name='上级分类'
    )
    retention_years = models.IntegerField(default=10, verbose_name='保存年限')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    icon = models.CharField(max_length=50, default='Folder', verbose_name='图标')

    class Meta:
        db_table = 'oa_archive_category'
        verbose_name = '档案分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Archive(BaseModel):
    """电子档案"""

    STATUS_CHOICES = [
        ('PENDING', '待归档'),
        ('ARCHIVED', '已归档'),
        ('BORROWED', '借阅中'),
        ('EXPIRED', '已过期'),
        ('DESTROYED', '已销毁'),
    ]

    SECURITY_LEVEL_CHOICES = [
        ('PUBLIC', '公开'),
        ('INTERNAL', '内部'),
        ('CONFIDENTIAL', '机密'),
        ('SECRET', '绝密'),
    ]

    archive_no = models.CharField(max_length=50, unique=True, verbose_name='档案编号')
    title = models.CharField(max_length=200, verbose_name='档案标题')

    category = models.ForeignKey(
        ArchiveCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='archives',
        verbose_name='档案分类',
    )

    # 档案信息
    file_path = models.CharField(max_length=500, blank=True, verbose_name='文件路径')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    file_type = models.CharField(max_length=50, blank=True, verbose_name='文件类型')
    page_count = models.IntegerField(default=1, verbose_name='页数')

    # 来源信息
    source_type = models.CharField(max_length=50, blank=True, verbose_name='来源类型')
    source_id = models.IntegerField(null=True, blank=True, verbose_name='来源ID')
    source_ref = models.CharField(max_length=100, blank=True, verbose_name='来源引用')

    # 档案属性
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    security_level = models.CharField(
        max_length=20, choices=SECURITY_LEVEL_CHOICES, default='INTERNAL', verbose_name='密级'
    )

    # 日期
    archive_date = models.DateField(null=True, blank=True, verbose_name='归档日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='到期日期')

    # 存储位置
    storage_location = models.CharField(max_length=200, blank=True, verbose_name='存储位置')
    cabinet_no = models.CharField(max_length=50, blank=True, verbose_name='柜号')
    shelf_no = models.CharField(max_length=50, blank=True, verbose_name='架号')
    box_no = models.CharField(max_length=50, blank=True, verbose_name='盒号')

    # 责任人
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custodian_archives',
        verbose_name='保管人',
    )

    keywords = models.JSONField(default=list, blank=True, verbose_name='关键词')
    abstract = models.TextField(blank=True, verbose_name='摘要')
    notes = models.TextField(blank=True, verbose_name='备注')

    # 借阅统计
    borrow_count = models.IntegerField(default=0, verbose_name='借阅次数')
    view_count = models.IntegerField(default=0, verbose_name='浏览次数')

    class Meta:
        db_table = 'oa_archive'
        verbose_name = '电子档案'
        verbose_name_plural = verbose_name
        ordering = ['-archive_date', '-created_at']

    def __str__(self):
        return f'{self.archive_no} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.archive_no:
            from apps.core.utils import generate_code

            self.archive_no = generate_code('ARC')

        # 计算到期日期
        if self.archive_date and self.category and not self.expiry_date:
            self.expiry_date = self.archive_date.replace(year=self.archive_date.year + self.category.retention_years)

        super().save(*args, **kwargs)


class ArchiveBorrow(BaseModel):
    """档案借阅记录"""

    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('BORROWED', '借阅中'),
        ('RETURNED', '已归还'),
        ('OVERDUE', '逾期'),
    ]

    archive = models.ForeignKey(Archive, on_delete=models.CASCADE, related_name='borrows', verbose_name='档案')
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='archive_borrows', verbose_name='借阅人'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # 借阅信息
    purpose = models.TextField(verbose_name='借阅目的')
    borrow_date = models.DateField(null=True, blank=True, verbose_name='借阅日期')
    due_date = models.DateField(null=True, blank=True, verbose_name='应还日期')
    return_date = models.DateField(null=True, blank=True, verbose_name='归还日期')

    # 审批
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_archive_borrows',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    reject_reason = models.TextField(blank=True, verbose_name='拒绝原因')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'oa_archive_borrow'
        verbose_name = '档案借阅'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.archive.archive_no} - {self.borrower.username}'


class ArchiveTransfer(BaseModel):
    """档案移交记录"""

    STATUS_CHOICES = [
        ('PENDING', '待确认'),
        ('CONFIRMED', '已确认'),
        ('REJECTED', '已拒绝'),
    ]

    archive = models.ForeignKey(Archive, on_delete=models.CASCADE, related_name='transfers', verbose_name='档案')
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='archive_transfers_out', verbose_name='移交人'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='archive_transfers_in', verbose_name='接收人'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    transfer_date = models.DateField(default=date.today, verbose_name='移交日期')
    confirm_date = models.DateField(null=True, blank=True, verbose_name='确认日期')
    reason = models.TextField(blank=True, verbose_name='移交原因')

    class Meta:
        db_table = 'oa_archive_transfer'
        verbose_name = '档案移交'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class ArchiveDestruction(BaseModel):
    """档案销毁记录"""

    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('DESTROYED', '已销毁'),
    ]

    archives = models.ManyToManyField(Archive, related_name='destructions', verbose_name='档案')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    reason = models.TextField(verbose_name='销毁原因')
    destruction_date = models.DateField(null=True, blank=True, verbose_name='销毁日期')
    destruction_method = models.CharField(max_length=100, blank=True, verbose_name='销毁方式')

    # 审批
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_archive_destructions',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    # 见证人
    witness = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='witnessed_archive_destructions',
        verbose_name='见证人',
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'oa_archive_destruction'
        verbose_name = '档案销毁'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


# =====================
# Serializers
# =====================


class ArchiveCategorySerializer(serializers.ModelSerializer):
    children_count = serializers.SerializerMethodField()
    archive_count = serializers.SerializerMethodField()

    class Meta:
        model = ArchiveCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()

    def get_archive_count(self, obj):
        return obj.archives.filter(is_deleted=False).count()


class ArchiveSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    security_display = serializers.CharField(source='get_security_level_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    custodian_name = serializers.CharField(source='custodian.get_full_name', read_only=True)

    class Meta:
        model = Archive
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'archive_no', 'borrow_count', 'view_count']


class ArchiveListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    security_display = serializers.CharField(source='get_security_level_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Archive
        fields = [
            'id',
            'archive_no',
            'title',
            'category',
            'category_name',
            'status',
            'status_display',
            'security_level',
            'security_display',
            'archive_date',
            'expiry_date',
            'borrow_count',
            'view_count',
            'created_at',
        ]


class ArchiveBorrowSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    archive_title = serializers.CharField(source='archive.title', read_only=True)
    archive_no = serializers.CharField(source='archive.archive_no', read_only=True)
    borrower_name = serializers.CharField(source='borrower.get_full_name', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)

    class Meta:
        model = ArchiveBorrow
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approver', 'approved_at']


class ArchiveTransferSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    archive_title = serializers.CharField(source='archive.title', read_only=True)
    from_user_name = serializers.CharField(source='from_user.get_full_name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.get_full_name', read_only=True)

    class Meta:
        model = ArchiveTransfer
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ArchiveDestructionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    archive_count = serializers.SerializerMethodField()
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    witness_name = serializers.CharField(source='witness.get_full_name', read_only=True)

    class Meta:
        model = ArchiveDestruction
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approver', 'approved_at']

    def get_archive_count(self, obj):
        return obj.archives.count()


# =====================
# ViewSets
# =====================


class ArchiveCategoryViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """档案分类管理"""

    queryset = ArchiveCategory.objects.filter(is_deleted=False)
    serializer_class = ArchiveCategorySerializer
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
                'retention_years': cat.retention_years,
                'children': [build_tree(c) for c in cat.children.filter(is_deleted=False)],
            }

        return Response([build_tree(c) for c in categories])


class ArchiveViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """电子档案管理"""

    queryset = Archive.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'status', 'security_level', 'custodian']
    search_fields = ['archive_no', 'title', 'abstract']
    ordering_fields = ['archive_date', 'created_at', 'borrow_count']

    def get_serializer_class(self):
        if self.action == 'list':
            return ArchiveListSerializer
        return ArchiveSerializer

    def retrieve(self, request, *args, **kwargs):
        """获取档案详情时增加浏览次数"""
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """归档"""
        archive = self.get_object()
        if archive.status != 'PENDING':
            return Response({'error': '只有待归档状态可以归档'}, status=400)

        archive.status = 'ARCHIVED'
        archive.archive_date = date.today()
        archive.save()

        return Response(self.get_serializer(archive).data)

    @action(detail=False, methods=['get'])
    def expiring(self, request):
        """获取即将到期的档案"""
        days = int(request.query_params.get('days', 90))
        threshold = date.today() + timedelta(days=days)

        archives = self.get_queryset().filter(status='ARCHIVED', expiry_date__lte=threshold).order_by('expiry_date')

        return Response(ArchiveListSerializer(archives, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """档案统计"""
        qs = self.get_queryset()

        total = qs.count()
        by_status = qs.values('status').annotate(count=Count('id'))
        by_security = qs.values('security_level').annotate(count=Count('id'))
        by_category = (
            qs.filter(category__isnull=False)
            .values('category__id', 'category__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # 即将到期
        expiring = qs.filter(status='ARCHIVED', expiry_date__lte=date.today() + timedelta(days=90)).count()

        # 本月归档
        month_start = date.today().replace(day=1)
        this_month = qs.filter(archive_date__gte=month_start).count()

        return Response(
            {
                'total': total,
                'this_month': this_month,
                'expiring_soon': expiring,
                'by_status': list(by_status),
                'by_security': list(by_security),
                'by_category': list(by_category),
            }
        )


class ArchiveBorrowViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """档案借阅管理"""

    queryset = ArchiveBorrow.objects.filter(is_deleted=False)
    serializer_class = ArchiveBorrowSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['archive', 'borrower', 'status']

    def perform_create(self, serializer):
        serializer.save(borrower=self.request.user, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批借阅"""
        borrow = self.get_object()
        if borrow.status != 'PENDING':
            return Response({'error': '只有待审批状态可以审批'}, status=400)

        borrow.status = 'APPROVED'
        borrow.approver = request.user
        borrow.approved_at = timezone.now()
        borrow.save()

        return Response(self.get_serializer(borrow).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝借阅"""
        borrow = self.get_object()
        if borrow.status != 'PENDING':
            return Response({'error': '只有待审批状态可以拒绝'}, status=400)

        borrow.status = 'REJECTED'
        borrow.approver = request.user
        borrow.approved_at = timezone.now()
        borrow.reject_reason = request.data.get('reason', '')
        borrow.save()

        return Response(self.get_serializer(borrow).data)

    @action(detail=True, methods=['post'])
    def borrow(self, request, pk=None):
        """确认借出"""
        borrow = self.get_object()
        if borrow.status != 'APPROVED':
            return Response({'error': '只有已批准状态可以借出'}, status=400)

        borrow.status = 'BORROWED'
        borrow.borrow_date = date.today()
        borrow.due_date = request.data.get('due_date', date.today() + timedelta(days=30))
        borrow.save()

        # 更新档案状态
        borrow.archive.status = 'BORROWED'
        borrow.archive.borrow_count += 1
        borrow.archive.save()

        return Response(self.get_serializer(borrow).data)

    @action(detail=True, methods=['post'])
    def return_archive(self, request, pk=None):
        """归还档案"""
        borrow = self.get_object()
        if borrow.status not in ['BORROWED', 'OVERDUE']:
            return Response({'error': '只有借阅中或逾期状态可以归还'}, status=400)

        borrow.status = 'RETURNED'
        borrow.return_date = date.today()
        borrow.save()

        # 更新档案状态
        borrow.archive.status = 'ARCHIVED'
        borrow.archive.save()

        return Response(self.get_serializer(borrow).data)


class ArchiveTransferViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """档案移交管理"""

    queryset = ArchiveTransfer.objects.filter(is_deleted=False)
    serializer_class = ArchiveTransferSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['archive', 'from_user', 'to_user', 'status']

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认接收"""
        transfer = self.get_object()
        if transfer.status != 'PENDING':
            return Response({'error': '只有待确认状态可以确认'}, status=400)

        if request.user != transfer.to_user:
            return Response({'error': '只有接收人可以确认'}, status=403)

        transfer.status = 'CONFIRMED'
        transfer.confirm_date = date.today()
        transfer.save()

        # 更新档案保管人
        transfer.archive.custodian = transfer.to_user
        transfer.archive.save()

        return Response(self.get_serializer(transfer).data)


class ArchiveDestructionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """档案销毁管理"""

    queryset = ArchiveDestruction.objects.filter(is_deleted=False)
    serializer_class = ArchiveDestructionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批销毁"""
        destruction = self.get_object()
        if destruction.status != 'PENDING':
            return Response({'error': '只有待审批状态可以审批'}, status=400)

        destruction.status = 'APPROVED'
        destruction.approver = request.user
        destruction.approved_at = timezone.now()
        destruction.save()

        return Response(self.get_serializer(destruction).data)

    @action(detail=True, methods=['post'])
    def execute_destruction(self, request, pk=None):
        """执行销毁"""
        destruction = self.get_object()
        if destruction.status != 'APPROVED':
            return Response({'error': '只有已批准状态可以销毁'}, status=400)

        destruction.status = 'DESTROYED'
        destruction.destruction_date = date.today()
        destruction.destruction_method = request.data.get('method', '')
        destruction.witness_id = request.data.get('witness_id')
        destruction.save()

        # 更新档案状态
        destruction.archives.update(status='DESTROYED')

        return Response(self.get_serializer(destruction).data)
