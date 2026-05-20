"""
项目文档管理
Project Document Management
管理项目相关文档、版本控制、权限控制等
"""
import os

from django.db import models
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class DocumentCategory(BaseModel):
    """
    文档分类
    """
    code = models.CharField(max_length=50, unique=True, verbose_name='分类编码')
    name = models.CharField(max_length=100, verbose_name='分类名称')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级分类'
    )

    # 文件类型限制
    allowed_extensions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='允许的扩展名',
        help_text='如 ["pdf", "docx", "xlsx"]'
    )
    max_file_size = models.IntegerField(default=50, verbose_name='最大文件大小(MB)')

    icon = models.CharField(max_length=50, default='Folder', verbose_name='图标')
    color = models.CharField(max_length=20, default='#409EFF', verbose_name='颜色')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'project_document_category'
        verbose_name = '文档分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class ProjectDocument(BaseModel):
    """
    项目文档
    """
    DOC_TYPES = [
        ('DESIGN', '设计文档'),
        ('TECHNICAL', '技术文档'),
        ('CONTRACT', '合同文档'),
        ('DRAWING', '图纸文件'),
        ('BOM', 'BOM清单'),
        ('MANUAL', '操作手册'),
        ('REPORT', '报告文档'),
        ('IMAGE', '图片'),
        ('VIDEO', '视频'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('REVIEWING', '审核中'),
        ('APPROVED', '已批准'),
        ('RELEASED', '已发布'),
        ('OBSOLETE', '已废弃'),
    ]

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='项目'
    )
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
        verbose_name='分类'
    )

    # 文档信息
    doc_no = models.CharField(max_length=50, verbose_name='文档编号')
    title = models.CharField(max_length=200, verbose_name='文档标题')
    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPES,
        default='OTHER',
        verbose_name='文档类型'
    )

    # 文件信息
    file = models.FileField(upload_to='project_docs/%Y/%m/', verbose_name='文件')
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_size = models.IntegerField(default=0, verbose_name='文件大小(字节)')
    file_ext = models.CharField(max_length=20, blank=True, verbose_name='文件扩展名')
    mime_type = models.CharField(max_length=100, blank=True, verbose_name='MIME类型')
    file_hash = models.CharField(max_length=64, blank=True, verbose_name='文件哈希')

    # 版本
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')
    is_latest = models.BooleanField(default=True, verbose_name='是否最新版')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )

    # 审批
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
        verbose_name='审核人'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_comments = models.TextField(blank=True, verbose_name='审核意见')

    # 标签
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')

    # 统计
    download_count = models.IntegerField(default=0, verbose_name='下载次数')
    view_count = models.IntegerField(default=0, verbose_name='查看次数')

    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'project_document'
        verbose_name = '项目文档'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        unique_together = ['project', 'doc_no', 'version']

    def __str__(self):
        return f'{self.doc_no} - {self.title}'

    def save(self, *args, **kwargs):
        if self.file:
            self.file_name = os.path.basename(self.file.name)
            self.file_ext = os.path.splitext(self.file_name)[1].lower().lstrip('.')
            if hasattr(self.file, 'size'):
                self.file_size = self.file.size
        super().save(*args, **kwargs)


class DocumentVersion(BaseModel):
    """
    文档版本历史
    """
    document = models.ForeignKey(
        ProjectDocument,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='文档'
    )

    version = models.CharField(max_length=20, verbose_name='版本号')
    file = models.FileField(upload_to='project_docs/versions/%Y/%m/', verbose_name='文件')
    file_size = models.IntegerField(default=0, verbose_name='文件大小')

    change_log = models.TextField(blank=True, verbose_name='变更说明')

    class Meta:
        db_table = 'project_document_version'
        verbose_name = '文档版本'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        unique_together = ['document', 'version']

    def __str__(self):
        return f'{self.document.title} - v{self.version}'


class DocumentShare(BaseModel):
    """
    文档分享
    """
    document = models.ForeignKey(
        ProjectDocument,
        on_delete=models.CASCADE,
        related_name='shares',
        verbose_name='文档'
    )

    share_code = models.CharField(max_length=32, unique=True, verbose_name='分享码')
    password = models.CharField(max_length=20, blank=True, verbose_name='访问密码')

    expire_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    max_downloads = models.IntegerField(default=0, verbose_name='最大下载次数')
    download_count = models.IntegerField(default=0, verbose_name='已下载次数')

    is_active = models.BooleanField(default=True, verbose_name='是否有效')

    class Meta:
        db_table = 'project_document_share'
        verbose_name = '文档分享'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document.title} - {self.share_code}'


# =====================
# Serializers
# =====================

class DocumentCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False)
        return DocumentCategorySerializer(children, many=True).data

    def get_document_count(self, obj):
        return obj.documents.filter(is_deleted=False).count()


class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = DocumentVersion
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProjectDocumentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    versions = DocumentVersionSerializer(many=True, read_only=True)
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDocument
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'file_name', 'file_size', 'file_ext',
                          'file_hash', 'download_count', 'view_count', 'reviewer', 'reviewed_at']

    def get_file_size_display(self, obj):
        if obj.file_size < 1024:
            return f'{obj.file_size} B'
        elif obj.file_size < 1024 * 1024:
            return f'{obj.file_size / 1024:.1f} KB'
        else:
            return f'{obj.file_size / 1024 / 1024:.1f} MB'


class ProjectDocumentListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDocument
        fields = [
            'id', 'project', 'project_name', 'category', 'category_name',
            'doc_no', 'title', 'doc_type', 'doc_type_display',
            'file_name', 'file_ext', 'file_size', 'file_size_display',
            'version', 'status', 'status_display', 'tags',
            'download_count', 'view_count', 'created_by_name', 'created_at'
        ]

    def get_file_size_display(self, obj):
        if obj.file_size < 1024:
            return f'{obj.file_size} B'
        elif obj.file_size < 1024 * 1024:
            return f'{obj.file_size / 1024:.1f} KB'
        else:
            return f'{obj.file_size / 1024 / 1024:.1f} MB'


class DocumentShareSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentShare
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'share_code', 'download_count']

    def get_share_url(self, obj):
        return f'/api/projects/documents/share/{obj.share_code}/'


# =====================
# ViewSets
# =====================

class DocumentCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """文档分类管理"""
    queryset = DocumentCategory.objects.filter(is_deleted=False)
    serializer_class = DocumentCategorySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['code', 'name']

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取分类树"""
        roots = self.get_queryset().filter(parent__isnull=True)
        return Response(self.get_serializer(roots, many=True).data)

    @action(detail=False, methods=['post'])
    def init_categories(self, request):
        """初始化默认分类"""
        categories = [
            ('DESIGN', '设计文档', ['pdf', 'docx', 'pptx']),
            ('DRAWING', '图纸文件', ['dwg', 'dxf', 'pdf', 'step', 'stp', 'igs']),
            ('BOM', 'BOM文档', ['xlsx', 'csv']),
            ('CONTRACT', '合同文档', ['pdf', 'docx']),
            ('MANUAL', '操作手册', ['pdf', 'docx']),
            ('REPORT', '报告文档', ['pdf', 'docx', 'xlsx']),
            ('IMAGE', '图片文件', ['jpg', 'jpeg', 'png', 'gif', 'bmp']),
            ('VIDEO', '视频文件', ['mp4', 'avi', 'mov']),
        ]

        created = 0
        for i, (code, name, exts) in enumerate(categories):
            _, c = DocumentCategory.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'allowed_extensions': exts,
                    'sort_order': i * 10,
                    'created_by': request.user
                }
            )
            if c:
                created += 1

        return Response({'success': True, 'created': created})


class ProjectDocumentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目文档管理"""
    queryset = ProjectDocument.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'category', 'doc_type', 'status']
    search_fields = ['doc_no', 'title', 'description']
    ordering_fields = ['created_at', 'title', 'file_size']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectDocumentListSerializer
        return ProjectDocumentSerializer

    def perform_create(self, serializer):
        # 生成文档编号
        from apps.core.utils import generate_code
        doc_no = generate_code('DOC')
        serializer.save(doc_no=doc_no, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def upload_new_version(self, request, pk=None):
        """上传新版本"""
        document = self.get_object()
        new_file = request.FILES.get('file')
        change_log = request.data.get('change_log', '')

        if not new_file:
            return Response({'error': '请上传文件'}, status=400)

        # 保存旧版本
        DocumentVersion.objects.create(
            document=document,
            version=document.version,
            file=document.file,
            file_size=document.file_size,
            change_log=change_log,
            created_by=request.user
        )

        # 更新文档
        old_version = document.version
        version_parts = old_version.split('.')
        version_parts[-1] = str(int(version_parts[-1]) + 1)
        new_version = '.'.join(version_parts)

        document.file = new_file
        document.version = new_version
        document.save()

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交审核"""
        document = self.get_object()

        if document.status not in ['DRAFT']:
            return Response({'error': '只有草稿状态可以提交审核'}, status=400)

        document.status = 'REVIEWING'
        document.save()

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过"""
        from django.utils import timezone

        document = self.get_object()

        if document.status != 'REVIEWING':
            return Response({'error': '只有审核中的文档可以审批'}, status=400)

        document.status = 'APPROVED'
        document.reviewer = request.user
        document.reviewed_at = timezone.now()
        document.review_comments = request.data.get('comments', '')
        document.save()

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审核拒绝"""
        from django.utils import timezone

        document = self.get_object()

        if document.status != 'REVIEWING':
            return Response({'error': '只有审核中的文档可以拒绝'}, status=400)

        document.status = 'DRAFT'
        document.reviewer = request.user
        document.reviewed_at = timezone.now()
        document.review_comments = request.data.get('comments', '')
        document.save()

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """发布"""
        document = self.get_object()

        if document.status != 'APPROVED':
            return Response({'error': '只有已批准的文档可以发布'}, status=400)

        document.status = 'RELEASED'
        document.save()

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载文档"""
        from django.http import FileResponse

        document = self.get_object()
        document.download_count += 1
        document.save()

        response = FileResponse(document.file.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
        return response

    @action(detail=True, methods=['post'])
    def create_share(self, request, pk=None):
        """创建分享链接"""
        import secrets

        document = self.get_object()

        share = DocumentShare.objects.create(
            document=document,
            share_code=secrets.token_urlsafe(16),
            password=request.data.get('password', ''),
            expire_at=request.data.get('expire_at'),
            max_downloads=request.data.get('max_downloads', 0),
            created_by=request.user
        )

        return Response(DocumentShareSerializer(share).data)

    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """按项目获取文档"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response({'error': '请提供项目ID'}, status=400)

        documents = self.get_queryset().filter(project_id=project_id)
        return Response(ProjectDocumentListSerializer(documents, many=True).data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """最近文档"""
        limit = int(request.query_params.get('limit', 20))
        documents = self.get_queryset().order_by('-created_at')[:limit]
        return Response(ProjectDocumentListSerializer(documents, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """文档统计"""
        from django.db.models import Count, Sum

        qs = self.get_queryset()

        by_type = qs.values('doc_type').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        )

        by_status = qs.values('status').annotate(count=Count('id'))

        total_size = qs.aggregate(total=Sum('file_size'))['total'] or 0

        return Response({
            'total_documents': qs.count(),
            'total_size': total_size,
            'total_size_display': f'{total_size / 1024 / 1024:.1f} MB' if total_size > 0 else '0 MB',
            'by_type': list(by_type),
            'by_status': list(by_status)
        })


class DocumentShareViewSet(viewsets.ReadOnlyModelViewSet):
    """文档分享管理"""
    queryset = DocumentShare.objects.filter(is_deleted=False)
    serializer_class = DocumentShareSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='access/(?P<share_code>[^/.]+)')
    def access(self, request, share_code=None):
        """访问分享链接"""
        from django.http import FileResponse
        from django.utils import timezone

        try:
            share = DocumentShare.objects.get(share_code=share_code, is_active=True)
        except DocumentShare.DoesNotExist:
            return Response({'error': '分享链接不存在或已失效'}, status=404)

        # 检查过期
        if share.expire_at and share.expire_at < timezone.now():
            return Response({'error': '分享链接已过期'}, status=400)

        # 检查下载次数
        if share.max_downloads > 0 and share.download_count >= share.max_downloads:
            return Response({'error': '下载次数已达上限'}, status=400)

        # 检查密码
        if share.password:
            password = request.query_params.get('password')
            if password != share.password:
                return Response({'error': '密码错误', 'need_password': True}, status=403)

        # 更新下载次数
        share.download_count += 1
        share.save()

        # 返回文件
        document = share.document
        response = FileResponse(document.file.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
        return response
