"""
技术文档协同模块
Document Collaboration - 在线批注、发放控制、移动查看
"""
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import serializers

from apps.core.models import BaseModel
from django.conf import settings

User = settings.AUTH_USER_MODEL


class TechDocumentCategory(BaseModel):
    """技术文档分类"""
    code = models.CharField('分类代码', max_length=50, unique=True)
    name = models.CharField('分类名称', max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='children', verbose_name='上级分类')
    description = models.TextField('描述', blank=True)
    sort_order = models.IntegerField('排序', default=0)
    
    # 控制规则
    requires_approval = models.BooleanField('需要审批', default=False)
    retention_days = models.IntegerField('保留天数', default=0)  # 0表示永久
    
    class Meta:
        db_table = 'tech_document_category'
        verbose_name = '技术文档分类'
        ordering = ['sort_order', 'code']


class TechnicalDocument(BaseModel):
    """技术文档"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('REVIEWING', '评审中'),
        ('APPROVED', '已批准'),
        ('RELEASED', '已发布'),
        ('OBSOLETE', '已作废'),
    ]
    
    CONTROL_LEVEL_CHOICES = [
        ('UNCONTROLLED', '非受控'),
        ('CONTROLLED', '受控'),
        ('CONFIDENTIAL', '机密'),
    ]
    
    doc_no = models.CharField('文档编号', max_length=50, unique=True)
    title = models.CharField('文档标题', max_length=200)
    category = models.ForeignKey(TechDocumentCategory, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='documents', verbose_name='文档分类')
    
    # 关联
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='tech_documents', verbose_name='项目')
    
    # 版本
    version = models.CharField('版本号', max_length=20, default='A')
    revision = models.IntegerField('修订号', default=0)
    
    # 状态
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    control_level = models.CharField('受控级别', max_length=20, choices=CONTROL_LEVEL_CHOICES, default='CONTROLLED')
    
    # 文件
    file_path = models.CharField('文件路径', max_length=500)
    file_name = models.CharField('文件名', max_length=200)
    file_size = models.BigIntegerField('文件大小', default=0)
    file_type = models.CharField('文件类型', max_length=50, blank=True)
    
    # 摘要
    description = models.TextField('文档描述', blank=True)
    keywords = models.JSONField('关键词', default=list)
    
    # 作者
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              related_name='authored_docs', verbose_name='作者')
    
    # 审批
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_docs', verbose_name='批准人')
    approved_at = models.DateTimeField('批准时间', null=True, blank=True)
    
    # 发布
    released_at = models.DateTimeField('发布时间', null=True, blank=True)
    effective_date = models.DateField('生效日期', null=True, blank=True)
    
    class Meta:
        db_table = 'technical_document'
        verbose_name = '技术文档'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.doc_no} - {self.title}'


class TechDocumentVersion(BaseModel):
    """技术文档版本历史"""
    document = models.ForeignKey(TechnicalDocument, on_delete=models.CASCADE,
                                related_name='versions', verbose_name='文档')
    version = models.CharField('版本号', max_length=20)
    revision = models.IntegerField('修订号')
    
    file_path = models.CharField('文件路径', max_length=500)
    change_description = models.TextField('变更说明')
    
    created_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                       related_name='tech_doc_versions', verbose_name='创建人')
    
    class Meta:
        db_table = 'tech_document_version'
        verbose_name = '技术文档版本'
        ordering = ['-created_at']


class DocumentAnnotation(BaseModel):
    """文档批注"""
    ANNOTATION_TYPE_CHOICES = [
        ('COMMENT', '评论'),
        ('QUESTION', '问题'),
        ('SUGGESTION', '建议'),
        ('APPROVAL', '审批意见'),
        ('HIGHLIGHT', '高亮'),
    ]
    
    document = models.ForeignKey(TechnicalDocument, on_delete=models.CASCADE,
                                related_name='annotations', verbose_name='文档')
    
    annotation_type = models.CharField('批注类型', max_length=20, choices=ANNOTATION_TYPE_CHOICES)
    content = models.TextField('批注内容')
    
    # 位置（用于PDF等）
    page_number = models.IntegerField('页码', null=True, blank=True)
    position_x = models.FloatField('X坐标', null=True, blank=True)
    position_y = models.FloatField('Y坐标', null=True, blank=True)
    
    # 创建人
    annotated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='doc_annotations', verbose_name='批注人')
    
    # 回复
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                              related_name='replies', verbose_name='父批注')
    
    # 状态
    resolved = models.BooleanField('已解决', default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='resolved_annotations', verbose_name='解决人')
    
    class Meta:
        db_table = 'document_annotation'
        verbose_name = '文档批注'
        ordering = ['-created_at']


class DocumentDistribution(BaseModel):
    """文档发放记录"""
    document = models.ForeignKey(TechnicalDocument, on_delete=models.CASCADE,
                                related_name='distributions', verbose_name='文档')
    
    # 接收方
    recipient_type = models.CharField('接收方类型', max_length=20,
                                     choices=[('USER', '用户'), ('DEPARTMENT', '部门'), 
                                             ('EXTERNAL', '外部'), ('SUPPLIER', '供应商')])
    recipient_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='received_docs', verbose_name='接收用户')
    recipient_name = models.CharField('接收方名称', max_length=100, blank=True)
    recipient_email = models.EmailField('接收邮箱', blank=True)
    
    # 发放信息
    distribution_no = models.CharField('发放编号', max_length=50)
    purpose = models.CharField('发放目的', max_length=200, blank=True)
    copy_count = models.IntegerField('份数', default=1)
    
    # 状态
    distributed_at = models.DateTimeField('发放时间', auto_now_add=True)
    distributed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                      related_name='distributed_docs', verbose_name='发放人')
    
    # 确认
    confirmed = models.BooleanField('已确认接收', default=False)
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    
    # 回收
    recalled = models.BooleanField('已回收', default=False)
    recalled_at = models.DateTimeField('回收时间', null=True, blank=True)
    
    class Meta:
        db_table = 'document_distribution'
        verbose_name = '文档发放'
        ordering = ['-distributed_at']


class DocumentAccessLog(BaseModel):
    """文档访问日志"""
    document = models.ForeignKey(TechnicalDocument, on_delete=models.CASCADE,
                                related_name='access_logs', verbose_name='文档')
    
    ACCESS_TYPE_CHOICES = [
        ('VIEW', '查看'),
        ('DOWNLOAD', '下载'),
        ('PRINT', '打印'),
        ('SHARE', '分享'),
    ]
    
    access_type = models.CharField('访问类型', max_length=20, choices=ACCESS_TYPE_CHOICES)
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='doc_access_logs', verbose_name='访问人')
    accessed_at = models.DateTimeField('访问时间', auto_now_add=True)
    
    # 设备信息
    device_type = models.CharField('设备类型', max_length=50, blank=True)
    ip_address = models.GenericIPAddressField('IP地址', null=True, blank=True)
    user_agent = models.CharField('用户代理', max_length=500, blank=True)
    
    class Meta:
        db_table = 'document_access_log'
        verbose_name = '文档访问日志'
        ordering = ['-accessed_at']


class DocumentReview(BaseModel):
    """文档评审"""
    document = models.ForeignKey(TechnicalDocument, on_delete=models.CASCADE,
                                related_name='reviews', verbose_name='文档')
    
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='doc_reviews', verbose_name='评审人')
    
    DECISION_CHOICES = [
        ('PENDING', '待评审'),
        ('APPROVED', '同意'),
        ('REJECTED', '拒绝'),
        ('REVISION_REQUIRED', '需修改'),
    ]
    
    decision = models.CharField('评审决定', max_length=20, choices=DECISION_CHOICES, default='PENDING')
    comments = models.TextField('评审意见', blank=True)
    review_date = models.DateTimeField('评审时间', null=True, blank=True)
    
    class Meta:
        db_table = 'document_review'
        verbose_name = '文档评审'


# ==================== Serializers ====================

class TechDocumentCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = TechDocumentCategory
        fields = '__all__'
    
    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False)
        return TechDocumentCategorySerializer(children, many=True).data


class DocumentAnnotationSerializer(serializers.ModelSerializer):
    annotated_by_name = serializers.CharField(source='annotated_by.get_full_name', read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentAnnotation
        fields = '__all__'
    
    def get_replies(self, obj):
        replies = obj.replies.filter(is_deleted=False)
        return DocumentAnnotationSerializer(replies, many=True).data


class TechDocumentVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by_user.get_full_name', read_only=True)
    
    class Meta:
        model = TechDocumentVersion
        fields = '__all__'


class DocumentDistributionSerializer(serializers.ModelSerializer):
    recipient_user_name = serializers.CharField(source='recipient_user.get_full_name', read_only=True)
    distributed_by_name = serializers.CharField(source='distributed_by.get_full_name', read_only=True)
    
    class Meta:
        model = DocumentDistribution
        fields = '__all__'


class TechnicalDocumentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    control_level_display = serializers.CharField(source='get_control_level_display', read_only=True)
    
    class Meta:
        model = TechnicalDocument
        fields = '__all__'


class TechnicalDocumentDetailSerializer(TechnicalDocumentSerializer):
    annotations = DocumentAnnotationSerializer(many=True, read_only=True)
    versions = TechDocumentVersionSerializer(many=True, read_only=True)
    distributions = DocumentDistributionSerializer(many=True, read_only=True)


# ==================== ViewSets ====================

class TechDocumentCategoryViewSet(viewsets.ModelViewSet):
    """技术文档分类管理"""
    queryset = TechDocumentCategory.objects.filter(is_deleted=False)
    serializer_class = TechDocumentCategorySerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取分类树"""
        roots = self.get_queryset().filter(parent__isnull=True)
        return Response(TechDocumentCategorySerializer(roots, many=True).data)


class TechnicalDocumentViewSet(viewsets.ModelViewSet):
    """技术文档管理"""
    queryset = TechnicalDocument.objects.filter(is_deleted=False)
    serializer_class = TechnicalDocumentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TechnicalDocumentDetailSerializer
        return TechnicalDocumentSerializer
    
    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        project = self.request.query_params.get('project')
        status_filter = self.request.query_params.get('status')
        keyword = self.request.query_params.get('keyword')
        
        if category:
            qs = qs.filter(category_id=category)
        if project:
            qs = qs.filter(project_id=project)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword) |
                Q(doc_no__icontains=keyword) |
                Q(keywords__contains=[keyword])
            )
        
        return qs.select_related('category', 'project', 'author')
    
    def perform_create(self, serializer):
        # 自动生成编号
        today = timezone.now()
        prefix = f'DOC{today.strftime("%Y%m%d")}'
        last = TechnicalDocument.objects.filter(doc_no__startswith=prefix).order_by('-doc_no').first()
        if last:
            seq = int(last.doc_no[-4:]) + 1
        else:
            seq = 1
        doc_no = f'{prefix}{seq:04d}'
        
        serializer.save(doc_no=doc_no, author=self.request.user)
    
    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交评审"""
        doc = self.get_object()
        reviewers = request.data.get('reviewers', [])
        
        doc.status = 'REVIEWING'
        doc.save()
        
        # 创建评审任务
        for reviewer_id in reviewers:
            DocumentReview.objects.create(
                document=doc,
                reviewer_id=reviewer_id,
                created_by=request.user,
                updated_by=request.user
            )
        
        return Response({'message': '已提交评审'})
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准文档"""
        doc = self.get_object()
        
        doc.status = 'APPROVED'
        doc.approved_by = request.user
        doc.approved_at = timezone.now()
        doc.save()
        
        return Response({'message': '文档已批准'})
    
    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """发布文档"""
        doc = self.get_object()
        
        if doc.status != 'APPROVED':
            return Response({'error': '只有已批准的文档可以发布'}, status=400)
        
        doc.status = 'RELEASED'
        doc.released_at = timezone.now()
        doc.effective_date = request.data.get('effective_date', timezone.now().date())
        doc.save()
        
        return Response({'message': '文档已发布'})
    
    @action(detail=True, methods=['post'])
    def new_revision(self, request, pk=None):
        """创建新修订版"""
        doc = self.get_object()
        
        # 保存当前版本
        TechDocumentVersion.objects.create(
            document=doc,
            version=doc.version,
            revision=doc.revision,
            file_path=doc.file_path,
            change_description=request.data.get('change_description', ''),
            created_by_user=request.user,
            created_by=request.user,
            updated_by=request.user
        )
        
        # 更新修订号
        doc.revision += 1
        doc.status = 'DRAFT'
        doc.file_path = request.data.get('file_path', doc.file_path)
        doc.save()
        
        return Response({'message': f'新修订版 {doc.version}.{doc.revision} 已创建'})
    
    @action(detail=True, methods=['post'])
    def distribute(self, request, pk=None):
        """发放文档"""
        doc = self.get_object()
        
        if doc.status != 'RELEASED':
            return Response({'error': '只有已发布的文档可以发放'}, status=400)
        
        # 生成发放编号
        dist_no = f'DIST{timezone.now().strftime("%Y%m%d%H%M%S")}'
        
        distribution = DocumentDistribution.objects.create(
            document=doc,
            distribution_no=dist_no,
            recipient_type=request.data.get('recipient_type'),
            recipient_user_id=request.data.get('recipient_user'),
            recipient_name=request.data.get('recipient_name', ''),
            recipient_email=request.data.get('recipient_email', ''),
            purpose=request.data.get('purpose', ''),
            copy_count=request.data.get('copy_count', 1),
            distributed_by=request.user,
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response(DocumentDistributionSerializer(distribution).data)
    
    @action(detail=True, methods=['get'])
    def access_log(self, request, pk=None):
        """获取访问日志"""
        doc = self.get_object()
        logs = doc.access_logs.all()[:100]
        
        return Response([{
            'access_type': log.access_type,
            'accessed_by': log.accessed_by.get_full_name() if log.accessed_by else '',
            'accessed_at': log.accessed_at,
            'device_type': log.device_type,
        } for log in logs])
    
    @action(detail=True, methods=['post'])
    def log_access(self, request, pk=None):
        """记录访问"""
        doc = self.get_object()
        
        DocumentAccessLog.objects.create(
            document=doc,
            access_type=request.data.get('access_type', 'VIEW'),
            accessed_by=request.user,
            device_type=request.data.get('device_type', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response({'message': '已记录'})


class DocumentAnnotationViewSet(viewsets.ModelViewSet):
    """文档批注管理"""
    queryset = DocumentAnnotation.objects.filter(is_deleted=False)
    serializer_class = DocumentAnnotationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document, parent__isnull=True)
        return qs
    
    def perform_create(self, serializer):
        serializer.save(annotated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决批注"""
        annotation = self.get_object()
        annotation.resolved = True
        annotation.resolved_by = request.user
        annotation.save()
        return Response({'message': '批注已解决'})


class DocumentReviewViewSet(viewsets.ModelViewSet):
    """文档评审管理"""
    queryset = DocumentReview.objects.filter(is_deleted=False)
    serializer_class = serializers.ModelSerializer
    permission_classes = [IsAuthenticated]
    
    class Meta:
        model = DocumentReview
        fields = '__all__'
    
    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交评审意见"""
        review = self.get_object()
        
        review.decision = request.data.get('decision')
        review.comments = request.data.get('comments', '')
        review.review_date = timezone.now()
        review.save()
        
        # 检查所有评审是否完成
        doc = review.document
        pending = doc.reviews.filter(decision='PENDING').count()
        rejected = doc.reviews.filter(decision='REJECTED').count()
        
        if pending == 0:
            if rejected > 0:
                doc.status = 'DRAFT'  # 有拒绝，退回
            else:
                doc.status = 'APPROVED'
                doc.approved_at = timezone.now()
            doc.save()
        
        return Response({'message': '评审意见已提交'})
