"""
Core API views for audit logs, notifications and attachments
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.utils import timezone
from django.http import FileResponse
from .models import AuditLog, SystemNotification, Attachment
from rest_framework import serializers
from .serializers import AttachmentSerializer, AttachmentUploadSerializer


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'username', 'action', 'model_name', 'object_id', 
                  'object_repr', 'changes', 'ip_address', 'timestamp']
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemNotification
        fields = ['id', 'type', 'title', 'message', 'is_read', 'created_at', 'read_at']
        read_only_fields = ['id', 'created_at', 'read_at']


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log viewing (read-only)"""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    
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


class NotificationViewSet(viewsets.ModelViewSet):
    """User notification management"""
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
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'status': 'all marked as read'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})


class AttachmentViewSet(viewsets.ModelViewSet):
    """
    附件管理视图集
    支持上传、下载、删除附件
    """
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 按关联对象过滤
        related_model = self.request.query_params.get('related_model')
        related_id = self.request.query_params.get('related_id')
        
        if related_model:
            queryset = queryset.filter(related_model=related_model)
        if related_id:
            queryset = queryset.filter(related_id=related_id)
        
        # 按分类过滤
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AttachmentUploadSerializer
        return AttachmentSerializer
    
    def create(self, request, *args, **kwargs):
        """上传附件"""
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
            response = FileResponse(
                attachment.file.open('rb'),
                as_attachment=True,
                filename=attachment.original_name
            )
            return response
        except Exception as e:
            return Response(
                {'error': f'文件下载失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def batch_upload(self, request):
        """批量上传附件"""
        files = request.FILES.getlist('files')
        related_model = request.data.get('related_model')
        related_id = request.data.get('related_id')
        category = request.data.get('category', 'OTHER')
        
        if not files:
            return Response(
                {'error': '请选择要上传的文件'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not related_model or not related_id:
            return Response(
                {'error': '请指定关联对象'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attachments = []
        for file in files:
            attachment = Attachment.objects.create(
                file=file,
                original_name=file.name,
                related_model=related_model,
                related_id=related_id,
                category=category,
                uploaded_by=request.user
            )
            attachments.append(attachment)
        
        serializer = AttachmentSerializer(attachments, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['delete'])
    def batch_delete(self, request):
        """批量删除附件"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response(
                {'error': '请指定要删除的附件ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 删除文件和数据库记录
        attachments = Attachment.objects.filter(id__in=ids)
        for attachment in attachments:
            attachment.file.delete(save=False)
        deleted_count = attachments.delete()[0]
        
        return Response({'deleted': deleted_count})


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
                'configured': bool(getattr(settings, 'DINGTALK_WEBHOOK_URL', '')) or bool(getattr(settings, 'DINGTALK_APP_KEY', '')),
            },
            'wechat_work': {
                'webhook_enabled': bool(getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', '')),
                'app_enabled': bool(getattr(settings, 'WECHAT_WORK_CORP_ID', '')),
                'configured': bool(getattr(settings, 'WECHAT_WORK_WEBHOOK_URL', '')) or bool(getattr(settings, 'WECHAT_WORK_CORP_ID', '')),
            },
        }
        
        enabled_channels = getattr(settings, 'NOTIFICATION_CHANNELS_ENABLED', ['email'])
        
        return Response({
            'channels': channels,
            'enabled': enabled_channels,
        })
    
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
                {'status': 'failed', 'message': '钉钉通知发送失败，请检查配置'},
                status=status.HTTP_400_BAD_REQUEST
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
                {'status': 'failed', 'message': '企业微信通知发送失败，请检查配置'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        """Broadcast notification to all configured channels."""
        from .notification_channels import broadcast_notification
        
        title = request.data.get('title')
        content = request.data.get('content')
        channels = request.data.get('channels')  # Optional: list of channel names
        
        if not title or not content:
            return Response(
                {'error': '请提供通知标题和内容'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = broadcast_notification(title, content, channels)
        
        return Response({
            'status': 'completed',
            'results': results
        })

