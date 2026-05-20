"""
电子签章模块
Electronic Signature
电子签章、合同签署、签章管理等
支持后续集成第三方服务（法大大、e签宝、DocuSign等）
"""
import hashlib
from datetime import date

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


class SignatureSeal(BaseModel):
    """电子印章"""
    SEAL_TYPE_CHOICES = [
        ('COMPANY', '公章'),
        ('CONTRACT', '合同章'),
        ('FINANCE', '财务章'),
        ('INVOICE', '发票章'),
        ('PERSONAL', '个人章'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待审核'),
        ('ACTIVE', '已启用'),
        ('DISABLED', '已停用'),
        ('EXPIRED', '已过期'),
    ]

    name = models.CharField(max_length=100, verbose_name='印章名称')
    seal_type = models.CharField(
        max_length=20,
        choices=SEAL_TYPE_CHOICES,
        default='COMPANY',
        verbose_name='印章类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )

    # 印章图片
    seal_image = models.CharField(max_length=500, blank=True, verbose_name='印章图片路径')

    # 所有者
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_seals',
        verbose_name='所有者'
    )

    # 授权用户
    authorized_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='authorized_seals',
        verbose_name='授权用户'
    )

    # 有效期
    valid_from = models.DateField(null=True, blank=True, verbose_name='生效日期')
    valid_to = models.DateField(null=True, blank=True, verbose_name='失效日期')

    # 使用统计
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='最后使用时间')

    # 第三方集成
    external_seal_id = models.CharField(max_length=100, blank=True, verbose_name='第三方印章ID')
    provider = models.CharField(max_length=50, blank=True, verbose_name='服务商')

    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'oa_signature_seal'
        verbose_name = '电子印章'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_seal_type_display()})"

    @property
    def is_valid(self):
        """检查印章是否有效"""
        if self.status != 'ACTIVE':
            return False
        today = date.today()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_to and today > self.valid_to:
            return False
        return True


class SignatureDocument(BaseModel):
    """签署文档"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待签署'),
        ('SIGNING', '签署中'),
        ('COMPLETED', '已完成'),
        ('REJECTED', '已拒绝'),
        ('EXPIRED', '已过期'),
        ('CANCELLED', '已取消'),
    ]

    DOC_TYPE_CHOICES = [
        ('CONTRACT', '合同'),
        ('AGREEMENT', '协议'),
        ('QUOTATION', '报价单'),
        ('INVOICE', '发票'),
        ('REPORT', '报告'),
        ('OTHER', '其他'),
    ]

    doc_no = models.CharField(max_length=50, unique=True, verbose_name='文档编号')
    title = models.CharField(max_length=200, verbose_name='文档标题')
    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        default='CONTRACT',
        verbose_name='文档类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )

    # 文件信息
    original_file = models.CharField(max_length=500, blank=True, verbose_name='原始文件路径')
    signed_file = models.CharField(max_length=500, blank=True, verbose_name='签署后文件路径')
    file_hash = models.CharField(max_length=64, blank=True, verbose_name='文件哈希')

    # 来源关联
    source_type = models.CharField(max_length=50, blank=True, verbose_name='来源类型')
    source_id = models.IntegerField(null=True, blank=True, verbose_name='来源ID')

    # 发起人
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_documents',
        verbose_name='发起人'
    )

    # 时间
    initiated_at = models.DateTimeField(null=True, blank=True, verbose_name='发起时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    expire_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')

    # 第三方集成
    external_doc_id = models.CharField(max_length=100, blank=True, verbose_name='第三方文档ID')
    external_url = models.CharField(max_length=500, blank=True, verbose_name='第三方签署链接')
    provider = models.CharField(max_length=50, blank=True, verbose_name='服务商')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'oa_signature_document'
        verbose_name = '签署文档'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.doc_no} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.doc_no:
            from apps.core.utils import generate_code
            self.doc_no = generate_code('SIG')
        super().save(*args, **kwargs)

    def calculate_file_hash(self, file_path):
        """计算文件哈希"""
        import os
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                self.file_hash = hashlib.sha256(f.read()).hexdigest()
            self.save(update_fields=['file_hash'])
        return self.file_hash


class SignatureParticipant(BaseModel):
    """签署参与者"""
    ROLE_CHOICES = [
        ('SIGNER', '签署人'),
        ('APPROVER', '审批人'),
        ('VIEWER', '抄送人'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待签署'),
        ('SIGNED', '已签署'),
        ('REJECTED', '已拒绝'),
        ('EXPIRED', '已过期'),
    ]

    document = models.ForeignKey(
        SignatureDocument,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name='文档'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signature_participations',
        verbose_name='用户'
    )

    # 外部签署人信息
    external_name = models.CharField(max_length=100, blank=True, verbose_name='姓名')
    external_phone = models.CharField(max_length=50, blank=True, verbose_name='手机号')
    external_email = models.EmailField(blank=True, verbose_name='邮箱')
    external_company = models.CharField(max_length=200, blank=True, verbose_name='公司')

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='SIGNER',
        verbose_name='角色'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )

    # 签署顺序
    sign_order = models.IntegerField(default=1, verbose_name='签署顺序')

    # 使用的印章
    seal = models.ForeignKey(
        SignatureSeal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signatures',
        verbose_name='印章'
    )

    # 签署信息
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name='签署时间')
    sign_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='签署IP')
    sign_location = models.CharField(max_length=200, blank=True, verbose_name='签署位置')

    # 拒绝原因
    reject_reason = models.TextField(blank=True, verbose_name='拒绝原因')

    # 第三方集成
    external_participant_id = models.CharField(max_length=100, blank=True, verbose_name='第三方参与者ID')
    sign_url = models.CharField(max_length=500, blank=True, verbose_name='签署链接')

    class Meta:
        db_table = 'oa_signature_participant'
        verbose_name = '签署参与者'
        verbose_name_plural = verbose_name
        ordering = ['document', 'sign_order']

    def __str__(self):
        name = self.user.get_full_name() if self.user else self.external_name
        return f"{self.document.doc_no} - {name}"


class SignatureLog(BaseModel):
    """签署日志"""
    ACTION_CHOICES = [
        ('CREATE', '创建文档'),
        ('SEND', '发送签署'),
        ('VIEW', '查看文档'),
        ('SIGN', '签署'),
        ('REJECT', '拒绝'),
        ('CANCEL', '取消'),
        ('DOWNLOAD', '下载'),
        ('VERIFY', '验证'),
    ]

    document = models.ForeignKey(
        SignatureDocument,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='文档'
    )
    participant = models.ForeignKey(
        SignatureParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name='参与者'
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作')

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='signature_logs',
        verbose_name='操作人'
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='浏览器标识')

    details = models.JSONField(default=dict, blank=True, verbose_name='详情')

    class Meta:
        db_table = 'oa_signature_log'
        verbose_name = '签署日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


# =====================
# Serializers
# =====================

class SignatureSealSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_seal_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = SignatureSeal
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'usage_count', 'last_used_at']


class SignatureParticipantSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    user_name = serializers.SerializerMethodField()
    seal_name = serializers.CharField(source='seal.name', read_only=True)

    class Meta:
        model = SignatureParticipant
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'signed_at', 'sign_ip']

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.external_name


class SignatureLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = SignatureLog
        fields = '__all__'


class SignatureDocumentSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    initiator_name = serializers.CharField(source='initiator.get_full_name', read_only=True)
    participants = SignatureParticipantSerializer(many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()
    signed_count = serializers.SerializerMethodField()

    class Meta:
        model = SignatureDocument
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'doc_no', 'file_hash']

    def get_participant_count(self, obj):
        return obj.participants.filter(role='SIGNER').count()

    def get_signed_count(self, obj):
        return obj.participants.filter(role='SIGNER', status='SIGNED').count()


# =====================
# ViewSets
# =====================

class SignatureSealViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """电子印章管理"""
    queryset = SignatureSeal.objects.filter(is_deleted=False)
    serializer_class = SignatureSealSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['seal_type', 'status', 'owner']
    search_fields = ['name']

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """启用印章"""
        seal = self.get_object()
        seal.status = 'ACTIVE'
        seal.save()
        return Response(self.get_serializer(seal).data)

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """停用印章"""
        seal = self.get_object()
        seal.status = 'DISABLED'
        seal.save()
        return Response(self.get_serializer(seal).data)

    @action(detail=True, methods=['post'])
    def authorize(self, request, pk=None):
        """授权用户"""
        seal = self.get_object()
        user_ids = request.data.get('user_ids', [])
        seal.authorized_users.set(user_ids)
        return Response(self.get_serializer(seal).data)


class SignatureDocumentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """签署文档管理"""
    queryset = SignatureDocument.objects.filter(is_deleted=False)
    serializer_class = SignatureDocumentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['doc_type', 'status', 'initiator']
    search_fields = ['doc_no', 'title']
    ordering_fields = ['created_at', 'initiated_at']

    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """添加参与者"""
        document = self.get_object()

        participant = SignatureParticipant.objects.create(
            document=document,
            user_id=request.data.get('user_id'),
            external_name=request.data.get('external_name', ''),
            external_phone=request.data.get('external_phone', ''),
            external_email=request.data.get('external_email', ''),
            external_company=request.data.get('external_company', ''),
            role=request.data.get('role', 'SIGNER'),
            sign_order=request.data.get('sign_order', 1),
            created_by=request.user
        )

        return Response(SignatureParticipantSerializer(participant).data)

    @action(detail=True, methods=['post'])
    def send_for_signing(self, request, pk=None):
        """发送签署"""
        document = self.get_object()

        if document.status not in ['DRAFT', 'PENDING']:
            return Response({'error': '当前状态无法发送签署'}, status=400)

        if not document.participants.filter(role='SIGNER').exists():
            return Response({'error': '请先添加签署人'}, status=400)

        document.status = 'PENDING'
        document.initiated_at = timezone.now()
        document.save()

        # 记录日志
        SignatureLog.objects.create(
            document=document,
            action='SEND',
            operator=request.user,
            created_by=request.user
        )

        # TODO: 集成第三方服务发送签署请求
        # 这里是模拟实现，实际需要调用第三方API

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """签署文档（模拟签署）"""
        document = self.get_object()
        seal_id = request.data.get('seal_id')

        # 获取当前用户的参与记录
        participant = document.participants.filter(
            user=request.user,
            role='SIGNER',
            status='PENDING'
        ).first()

        if not participant:
            return Response({'error': '您不是此文档的待签署人'}, status=400)

        # 检查印章权限
        if seal_id:
            seal = SignatureSeal.objects.filter(id=seal_id, status='ACTIVE').first()
            if not seal:
                return Response({'error': '印章不可用'}, status=400)

            if seal.owner != request.user and request.user not in seal.authorized_users.all():
                return Response({'error': '您没有使用此印章的权限'}, status=403)

            participant.seal = seal
            seal.usage_count += 1
            seal.last_used_at = timezone.now()
            seal.save()

        # 更新签署状态
        participant.status = 'SIGNED'
        participant.signed_at = timezone.now()
        participant.sign_ip = request.META.get('REMOTE_ADDR')
        participant.save()

        # 记录日志
        SignatureLog.objects.create(
            document=document,
            participant=participant,
            action='SIGN',
            operator=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            created_by=request.user
        )

        # 检查是否所有人都已签署
        pending_signers = document.participants.filter(role='SIGNER', status='PENDING').count()
        if pending_signers == 0:
            document.status = 'COMPLETED'
            document.completed_at = timezone.now()
            document.save()
        else:
            document.status = 'SIGNING'
            document.save()

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝签署"""
        document = self.get_object()
        reason = request.data.get('reason', '')

        participant = document.participants.filter(
            user=request.user,
            role='SIGNER',
            status='PENDING'
        ).first()

        if not participant:
            return Response({'error': '您不是此文档的待签署人'}, status=400)

        participant.status = 'REJECTED'
        participant.reject_reason = reason
        participant.save()

        document.status = 'REJECTED'
        document.save()

        # 记录日志
        SignatureLog.objects.create(
            document=document,
            participant=participant,
            action='REJECT',
            operator=request.user,
            details={'reason': reason},
            created_by=request.user
        )

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消签署"""
        document = self.get_object()

        if document.status == 'COMPLETED':
            return Response({'error': '已完成的文档无法取消'}, status=400)

        if document.initiator != request.user:
            return Response({'error': '只有发起人可以取消'}, status=403)

        document.status = 'CANCELLED'
        document.save()

        SignatureLog.objects.create(
            document=document,
            action='CANCEL',
            operator=request.user,
            created_by=request.user
        )

        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """获取签署日志"""
        document = self.get_object()
        logs = document.logs.all()
        return Response(SignatureLogSerializer(logs, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """签署统计"""
        qs = self.get_queryset()

        total = qs.count()
        by_status = qs.values('status').annotate(count=Count('id'))

        # 本月统计
        month_start = date.today().replace(day=1)
        this_month = qs.filter(created_at__date__gte=month_start).count()
        completed_this_month = qs.filter(
            status='COMPLETED',
            completed_at__date__gte=month_start
        ).count()

        # 待签署
        pending = qs.filter(status__in=['PENDING', 'SIGNING']).count()

        return Response({
            'total': total,
            'this_month': this_month,
            'completed_this_month': completed_this_month,
            'pending': pending,
            'by_status': list(by_status)
        })


class SignatureLogViewSet(viewsets.ReadOnlyModelViewSet):
    """签署日志查看"""
    queryset = SignatureLog.objects.all()
    serializer_class = SignatureLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['document', 'action', 'operator']
    ordering_fields = ['created_at']
