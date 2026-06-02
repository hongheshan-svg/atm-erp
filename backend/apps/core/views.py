"""
Core API views for audit logs, notifications and attachments
"""

from django.http import FileResponse
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.permission_mixin import PermissionMixin
from apps.core.permissions import IsSystemAdmin

from .models import Attachment, AuditLog, SystemConfig, SystemNotification
from .serializers import AttachmentSerializer, AttachmentUploadSerializer, SystemConfigSerializer


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'username',
            'action',
            'model_name',
            'object_id',
            'object_repr',
            'changes',
            'ip_address',
            'timestamp',
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemNotification
        fields = ['id', 'type', 'title', 'message', 'is_read', 'created_at', 'read_at']
        read_only_fields = ['id', 'created_at', 'read_at']


class AuditLogViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """Audit log viewing (read-only)"""

    permission_module = 'system'
    permission_resource = 'audit_log'
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by user if specified
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)

        # Filter by model
        model_name = self.request.query_params.get('model_name')
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)

        return queryset.order_by('-timestamp')[:1000]  # Limit to last 1000 entries


class NotificationViewSet(PermissionMixin, viewsets.ModelViewSet):
    """User notification management"""

    permission_module = 'system'
    permission_resource = 'system_notification'
    queryset = SystemNotification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users only see their own notifications
        return self.queryset.filter(user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({'status': 'marked as read'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        self.get_queryset().filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return Response({'status': 'all marked as read'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})


# 附件父对象所属、且「权限模块名与 Django app_label 对齐」的业务模块。仅对这些模块做模块级访问校验，
# 其它（core/accounts/masterdata 等无法可靠映射菜单模块的）一律放行，避免误伤合法下载。
_ATTACHMENT_ENFORCED_MODULES = {'sales', 'purchase', 'inventory', 'finance', 'projects', 'production'}


def _user_can_access_attachment(user, attachment):
    """判断非系统管理员能否访问某附件（retrieve/download/update/destroy）。

    附件按 related_model+related_id 挂在业务对象上、自身无归属。为消除「猜 PK 下载任意附件」的越权，
    在保持系统「菜单级粒度」前提下做模块级校验：上传者本人放行；否则要求用户在父对象所属业务模块
    持有任一菜单权限。无法可靠解析模块时一律放行（fail-open），避免误伤合法跨用户下载。

    注：这是模块级而非对象级授权（与全系统 RBAC 粒度一致）；真正的对象级授权需引入通用「父对象权限」
    模型（更大改造）。batch_delete 走 Attachment.objects.filter(id__in=) 不经此校验，另有越权面，未在此覆盖。
    """
    uploaded_by_id = getattr(attachment, 'uploaded_by_id', None)
    if uploaded_by_id and uploaded_by_id == getattr(user, 'id', None):
        return True

    related_model = (getattr(attachment, 'related_model', '') or '').strip()
    if not related_model:
        return True

    from django.apps import apps as django_apps

    model = next((m for m in django_apps.get_models() if m.__name__ == related_model), None)
    if model is None:
        return True

    module = model._meta.app_label
    if module not in _ATTACHMENT_ENFORCED_MODULES:
        return True

    from apps.core.permission_service import get_user_permissions

    perms = get_user_permissions(user)
    return any(code == module or code.startswith(module + ':') for code in perms)


class AttachmentViewSet(PermissionMixin, viewsets.ModelViewSet):
    """
    附件管理视图集
    支持上传、下载、删除附件
    """

    permission_module = 'system'
    permission_resource = 'attachment'
    skip_data_scope = True  # 附件可见性随父对象，而非 created_by；避免 self 范围误伤共享对象的他人附件
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = super().get_queryset()

        # 按关联对象过滤
        related_model = self.request.query_params.get('related_model')
        related_id = self.request.query_params.get('related_id')

        # 列表操作：非系统管理员必须按具体关联对象(related_model+related_id)查询，否则返回空，
        # 防止越权批量枚举全部附件（审计 IDOR）。retrieve/download 按 id 不受此限。
        if getattr(self, 'action', None) == 'list':
            from apps.core.permissions import _is_system_admin

            if not _is_system_admin(self.request.user) and not (related_model and related_id):
                return queryset.none()

        if related_model:
            queryset = queryset.filter(related_model=related_model)
        if related_id:
            queryset = queryset.filter(related_id=related_id)

        # 按分类过滤
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        return queryset

    def get_object(self):
        # retrieve/download/update/destroy 经此取对象：非管理员需能访问父对象所属模块，
        # 否则任意登录用户可猜 PK 下载/读取任意附件（审计越权收紧）。
        obj = super().get_object()
        from apps.core.permissions import _is_system_admin

        if not _is_system_admin(self.request.user) and not _user_can_access_attachment(self.request.user, obj):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('无权访问该附件')
        return obj

    def get_serializer_class(self):
        if self.action == 'create':
            return AttachmentUploadSerializer
        return AttachmentSerializer

    def create(self, request, *args, **kwargs):
        """上传附件"""
        from django.core.exceptions import ValidationError as DjangoValidationError

        from apps.core.validators import sanitize_filename, validate_uploaded_file

        # 获取上传的文件
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请选择要上传的文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 安全验证
        try:
            validate_uploaded_file(file)
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 清理文件名
        file.name = sanitize_filename(file.name)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save()

        # 返回完整的附件信息
        output_serializer = AttachmentSerializer(attachment, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载附件"""
        attachment = self.get_object()
        try:
            response = FileResponse(attachment.file.open('rb'), as_attachment=True, filename=attachment.original_name)
            return response
        except Exception as e:
            return Response({'error': f'文件下载失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def batch_upload(self, request):
        """批量上传附件"""
        from django.core.exceptions import ValidationError as DjangoValidationError

        from apps.core.validators import sanitize_filename, validate_uploaded_file

        files = request.FILES.getlist('files')
        related_model = request.data.get('related_model')
        related_id = request.data.get('related_id')
        category = request.data.get('category', 'OTHER')

        if not files:
            return Response({'error': '请选择要上传的文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not related_model or not related_id:
            return Response({'error': '请指定关联对象'}, status=status.HTTP_400_BAD_REQUEST)

        # 限制批量上传数量
        if len(files) > 10:
            return Response({'error': '一次最多上传10个文件'}, status=status.HTTP_400_BAD_REQUEST)

        attachments = []
        errors = []

        for file in files:
            try:
                # 安全验证
                validate_uploaded_file(file)
                file.name = sanitize_filename(file.name)

                attachment = Attachment.objects.create(
                    file=file,
                    original_name=file.name,
                    related_model=related_model,
                    related_id=related_id,
                    category=category,
                    uploaded_by=request.user,
                )
                attachments.append(attachment)
            except DjangoValidationError as e:
                errors.append({'filename': file.name, 'error': str(e)})

        serializer = AttachmentSerializer(attachments, many=True, context={'request': request})
        response_data = {
            'success': serializer.data,
            'errors': errors,
            'total': len(files),
            'uploaded': len(attachments),
            'failed': len(errors),
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['delete'])
    def batch_delete(self, request):
        """批量删除附件。

        按 id 批量删除，非系统管理员仅能删除「有权访问其父对象模块」的附件（与 get_object 同口径），
        无权的静默跳过并在 denied 计数中回报，防止任意登录用户按 id 删除他人附件（审计越权收紧）。
        """
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请指定要删除的附件ID'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.core.permissions import _is_system_admin

        attachments = list(Attachment.objects.filter(id__in=ids))
        is_admin = _is_system_admin(request.user)
        allowed = [a for a in attachments if is_admin or _user_can_access_attachment(request.user, a)]
        denied_count = len(attachments) - len(allowed)

        # 删除文件和数据库记录（仅限有权访问的）
        for attachment in allowed:
            attachment.file.delete(save=False)
        allowed_ids = [a.id for a in allowed]
        deleted_count = Attachment.objects.filter(id__in=allowed_ids).delete()[0] if allowed_ids else 0

        result = {'deleted': deleted_count}
        if denied_count:
            result['denied'] = denied_count
        return Response(result)


class NotificationChannelViewSet(viewsets.ViewSet):
    """
    Notification channel management and testing.
    Supports DingTalk (钉钉) and WeChat Work (企业微信).
    """

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get status of all notification channels."""
        from django.conf import settings

        channels = {
            'email': {
                'enabled': bool(getattr(settings, 'EMAIL_HOST', '')),
                'configured': bool(getattr(settings, 'DEFAULT_FROM_EMAIL', '')),
            },
            'dingtalk': {
                'webhook_enabled': bool(getattr(settings, 'DINGTALK_WEBHOOK_URL', '')),
                'app_enabled': bool(getattr(settings, 'DINGTALK_APP_KEY', '')),
                'configured': bool(getattr(settings, 'DINGTALK_WEBHOOK_URL', ''))
                or bool(getattr(settings, 'DINGTALK_APP_KEY', '')),
            },
            'wechat_work': {
                'webhook_enabled': bool(getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', '')),
                'app_enabled': bool(getattr(settings, 'WECHAT_WORK_CORP_ID', '')),
                'configured': bool(getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', ''))
                or bool(getattr(settings, 'WECHAT_WORK_CORP_ID', '')),
            },
        }

        enabled_channels = getattr(settings, 'NOTIFICATION_CHANNELS_ENABLED', ['email'])

        return Response(
            {
                'channels': channels,
                'enabled': enabled_channels,
            }
        )

    @action(detail=False, methods=['post'])
    def test_dingtalk(self, request):
        """Test DingTalk webhook notification."""
        from .notification_channels import send_dingtalk

        title = request.data.get('title', 'ERP系统测试通知')
        content = request.data.get('content', '这是一条测试消息，用于验证钉钉通知配置是否正确。')

        success = send_dingtalk(title, content, msg_type='markdown')

        if success:
            return Response({'status': 'success', 'message': '钉钉通知发送成功'})
        else:
            return Response(
                {'status': 'failed', 'message': '钉钉通知发送失败，请检查配置'}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def test_wechat_work(self, request):
        """Test WeChat Work webhook notification."""
        from .notification_channels import send_wechat_work

        title = request.data.get('title', 'ERP系统测试通知')
        content = request.data.get('content', '这是一条测试消息，用于验证企业微信通知配置是否正确。')

        success = send_wechat_work(title, content, msg_type='markdown')

        if success:
            return Response({'status': 'success', 'message': '企业微信通知发送成功'})
        else:
            return Response(
                {'status': 'failed', 'message': '企业微信通知发送失败，请检查配置'}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        """Broadcast notification to all configured channels."""
        from .notification_channels import broadcast_notification

        title = request.data.get('title')
        content = request.data.get('content')
        channels = request.data.get('channels')  # Optional: list of channel names

        if not title or not content:
            return Response({'error': '请提供通知标题和内容'}, status=status.HTTP_400_BAD_REQUEST)

        results = broadcast_notification(title, content, channels)

        return Response({'status': 'completed', 'results': results})


class SystemConfigViewSet(viewsets.ViewSet):
    """
    系统配置管理 - 单例模式，只有一条记录
    """

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """list 方法允许匿名访问（用于登录页面显示公司信息）"""
        if self.action == 'list':
            return [AllowAny()]
        return super().get_permissions()

    def list(self, request):
        """获取系统配置（公开信息，无需登录）"""
        config = SystemConfig.get_config()
        serializer = SystemConfigSerializer(config)
        return Response(serializer.data)

    def create(self, request):
        """更新系统配置（使用POST代替PUT，因为始终操作同一条记录）"""
        config = SystemConfig.get_config()
        serializer = SystemConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def company_name(self, request):
        """快速获取公司名称（供其他模块调用）"""
        config = SystemConfig.get_config()
        return Response({'company_name': config.company_name, 'company_tax_no': config.company_tax_no})
