"""
即时通讯模块
Instant Messaging with Group Chat and File Sharing

非标自动化行业建议：
- 可创建项目专属群组，方便项目团队沟通
- 文件共享可用于分享技术资料、图纸等
- 建议与项目协作配合使用
"""
from datetime import datetime
from django.db import models
from django.conf import settings
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class IMConversation(BaseModel):
    """IM会话/聊天室"""
    TYPE_CHOICES = [
        ('PRIVATE', '私聊'),
        ('GROUP', '群聊'),
    ]
    
    name = models.CharField(max_length=100, blank=True, verbose_name='会话名称')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='PRIVATE', verbose_name='会话类型')
    avatar = models.ImageField(upload_to='im/avatars/', blank=True, null=True, verbose_name='群头像')
    description = models.TextField(blank=True, verbose_name='群描述')
    
    # 群组设置
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_im_conversations',
        verbose_name='群主'
    )
    max_members = models.IntegerField(default=500, verbose_name='最大成员数')
    is_muted = models.BooleanField(default=False, verbose_name='全员禁言')
    
    # 最后消息信息（用于排序和预览）
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='最后消息时间')
    last_message_content = models.CharField(max_length=200, blank=True, verbose_name='最后消息内容')
    
    class Meta:
        db_table = 'oa_im_conversation'
        verbose_name = 'IM会话'
        verbose_name_plural = verbose_name
        ordering = ['-last_message_at', '-created_at']
    
    def __str__(self):
        return self.name or f'IM会话{self.id}'
    
    def update_last_message(self, message):
        """更新最后消息"""
        self.last_message_at = message.created_at
        if message.message_type == 'TEXT':
            self.last_message_content = message.content[:100]
        elif message.message_type == 'IMAGE':
            self.last_message_content = '[图片]'
        elif message.message_type == 'FILE':
            self.last_message_content = f'[文件] {message.file_name}'
        else:
            self.last_message_content = '[消息]'
        self.save(update_fields=['last_message_at', 'last_message_content'])


class IMConversationMember(BaseModel):
    """IM会话成员"""
    ROLE_CHOICES = [
        ('OWNER', '群主'),
        ('ADMIN', '管理员'),
        ('MEMBER', '成员'),
    ]
    
    conversation = models.ForeignKey(
        IMConversation,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name='会话'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='im_conversation_memberships',
        verbose_name='用户'
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER', verbose_name='角色')
    nickname = models.CharField(max_length=50, blank=True, verbose_name='群昵称')
    is_muted = models.BooleanField(default=False, verbose_name='消息免打扰')
    is_pinned = models.BooleanField(default=False, verbose_name='置顶')
    
    # 已读状态
    last_read_at = models.DateTimeField(null=True, blank=True, verbose_name='最后已读时间')
    last_read_message_id = models.BigIntegerField(null=True, blank=True, verbose_name='最后已读消息ID')
    
    # 加入信息
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_members',
        verbose_name='邀请人'
    )
    
    class Meta:
        db_table = 'oa_im_conversation_member'
        verbose_name = 'IM会话成员'
        verbose_name_plural = verbose_name
        unique_together = ['conversation', 'user']
    
    def __str__(self):
        return f'{self.user.username} in {self.conversation}'
    
    def get_unread_count(self):
        """获取未读消息数"""
        if not self.last_read_at:
            return self.conversation.messages.count()
        return self.conversation.messages.filter(created_at__gt=self.last_read_at).count()


class IMMessage(BaseModel):
    """IM消息"""
    TYPE_CHOICES = [
        ('TEXT', '文本'),
        ('IMAGE', '图片'),
        ('FILE', '文件'),
        ('AUDIO', '语音'),
        ('VIDEO', '视频'),
        ('SYSTEM', '系统消息'),
    ]
    
    conversation = models.ForeignKey(
        IMConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='会话'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='im_sent_messages',
        verbose_name='发送者'
    )
    
    # 消息内容
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='TEXT', verbose_name='消息类型')
    content = models.TextField(blank=True, verbose_name='消息内容')
    
    # 文件相关
    file = models.FileField(upload_to='im/files/%Y/%m/', blank=True, null=True, verbose_name='文件')
    file_name = models.CharField(max_length=255, blank=True, verbose_name='文件名')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小')
    file_type = models.CharField(max_length=100, blank=True, verbose_name='文件MIME类型')
    
    # @提及
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='im_mentioned_in_messages',
        verbose_name='@提及的用户'
    )
    is_mention_all = models.BooleanField(default=False, verbose_name='@所有人')
    
    # 引用回复
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='回复的消息'
    )
    
    # 消息状态
    is_recalled = models.BooleanField(default=False, verbose_name='已撤回')
    recalled_at = models.DateTimeField(null=True, blank=True, verbose_name='撤回时间')
    
    class Meta:
        db_table = 'oa_im_message'
        verbose_name = 'IM消息'
        verbose_name_plural = verbose_name
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        return f'{self.sender}: {self.content[:50] if self.content else self.message_type}'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 更新会话的最后消息
        if not self.is_recalled:
            self.conversation.update_last_message(self)


class IMMessageRead(models.Model):
    """IM消息已读记录"""
    message = models.ForeignKey(
        IMMessage,
        on_delete=models.CASCADE,
        related_name='read_records',
        verbose_name='消息'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='im_read_messages',
        verbose_name='用户'
    )
    read_at = models.DateTimeField(auto_now_add=True, verbose_name='已读时间')
    
    class Meta:
        db_table = 'oa_im_message_read'
        verbose_name = 'IM消息已读记录'
        verbose_name_plural = verbose_name
        unique_together = ['message', 'user']


# ============ Serializers ============

class IMConversationMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    avatar = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = IMConversationMember
        fields = ['id', 'user', 'username', 'full_name', 'avatar', 'role', 
                  'nickname', 'is_muted', 'is_pinned', 'joined_at', 'unread_count']
    
    def get_avatar(self, obj):
        return None  # 可扩展用户头像
    
    def get_unread_count(self, obj):
        return obj.get_unread_count()


class IMMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    sender_full_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    reply_to_content = serializers.SerializerMethodField()
    
    class Meta:
        model = IMMessage
        fields = ['id', 'conversation', 'sender', 'sender_name', 'sender_full_name',
                  'message_type', 'content', 'file', 'file_url', 'file_name', 'file_size',
                  'file_type', 'is_mention_all', 'reply_to', 'reply_to_content',
                  'is_recalled', 'created_at']
        read_only_fields = ['sender', 'file_size', 'file_type', 'is_recalled']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None
    
    def get_reply_to_content(self, obj):
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'sender': obj.reply_to.sender.username if obj.reply_to.sender else None,
                'content': obj.reply_to.content[:100] if obj.reply_to.content else '[文件]'
            }
        return None


class IMConversationSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = IMConversation
        fields = ['id', 'name', 'type', 'avatar', 'description', 'owner',
                  'members_count', 'last_message', 'unread_count', 'last_message_at',
                  'created_at']
        read_only_fields = ['owner', 'last_message_at']
    
    def get_members_count(self, obj):
        return obj.members.count()
    
    def get_last_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        if msg:
            return {
                'content': obj.last_message_content,
                'sender': msg.sender.username if msg.sender else None,
                'created_at': msg.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            member = obj.members.filter(user=request.user).first()
            if member:
                return member.get_unread_count()
        return 0


class IMConversationDetailSerializer(IMConversationSerializer):
    members = IMConversationMemberSerializer(many=True, read_only=True)
    
    class Meta(IMConversationSerializer.Meta):
        fields = IMConversationSerializer.Meta.fields + ['members']


# ============ ViewSets ============

class IMConversationViewSet(viewsets.ModelViewSet):
    """IM会话管理"""
    serializer_class = IMConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return IMConversation.objects.filter(
            members__user=self.request.user,
            is_deleted=False
        ).distinct()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return IMConversationDetailSerializer
        return IMConversationSerializer
    
    def perform_create(self, serializer):
        conversation = serializer.save(owner=self.request.user)
        # 创建者自动成为群主
        IMConversationMember.objects.create(
            conversation=conversation,
            user=self.request.user,
            role='OWNER',
            created_by=self.request.user
        )
    
    @action(detail=False, methods=['post'])
    def create_private(self, request):
        """创建私聊会话"""
        target_user_id = request.data.get('user_id')
        if not target_user_id:
            return Response({'error': '请指定聊天对象'}, status=400)
        
        from apps.accounts.models import User
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=404)
        
        # 检查是否已存在私聊
        existing = IMConversation.objects.filter(
            type='PRIVATE',
            members__user=request.user
        ).filter(
            members__user=target_user
        ).first()
        
        if existing:
            return Response(IMConversationSerializer(existing, context={'request': request}).data)
        
        # 创建新私聊
        conversation = IMConversation.objects.create(
            type='PRIVATE',
            name=f'{request.user.username}-{target_user.username}',
            created_by=request.user
        )
        IMConversationMember.objects.create(
            conversation=conversation,
            user=request.user,
            created_by=request.user
        )
        IMConversationMember.objects.create(
            conversation=conversation,
            user=target_user,
            created_by=request.user
        )
        
        return Response(IMConversationSerializer(conversation, context={'request': request}).data)
    
    @action(detail=False, methods=['post'])
    def create_group(self, request):
        """创建群聊"""
        name = request.data.get('name')
        member_ids = request.data.get('members', [])
        
        if not name:
            return Response({'error': '请输入群名称'}, status=400)
        
        conversation = IMConversation.objects.create(
            type='GROUP',
            name=name,
            description=request.data.get('description', ''),
            owner=request.user,
            created_by=request.user
        )
        
        # 添加群主
        IMConversationMember.objects.create(
            conversation=conversation,
            user=request.user,
            role='OWNER',
            created_by=request.user
        )
        
        # 添加其他成员
        from apps.accounts.models import User
        for user_id in member_ids:
            try:
                user = User.objects.get(id=user_id)
                if user != request.user:
                    IMConversationMember.objects.create(
                        conversation=conversation,
                        user=user,
                        invited_by=request.user,
                        created_by=request.user
                    )
            except User.DoesNotExist:
                pass
        
        # 发送系统消息
        IMMessage.objects.create(
            conversation=conversation,
            message_type='SYSTEM',
            content=f'{request.user.get_full_name() or request.user.username} 创建了群聊',
            created_by=request.user
        )
        
        return Response(IMConversationDetailSerializer(conversation, context={'request': request}).data)
    
    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """添加群成员"""
        conversation = self.get_object()
        if conversation.type != 'GROUP':
            return Response({'error': '只有群聊才能添加成员'}, status=400)
        
        member_ids = request.data.get('members', [])
        added = []
        
        from apps.accounts.models import User
        for user_id in member_ids:
            try:
                user = User.objects.get(id=user_id)
                if not conversation.members.filter(user=user).exists():
                    IMConversationMember.objects.create(
                        conversation=conversation,
                        user=user,
                        invited_by=request.user,
                        created_by=request.user
                    )
                    added.append(user.username)
            except User.DoesNotExist:
                pass
        
        if added:
            IMMessage.objects.create(
                conversation=conversation,
                message_type='SYSTEM',
                content=f'{request.user.username} 邀请了 {", ".join(added)} 加入群聊',
                created_by=request.user
            )
        
        return Response({'added': added})
    
    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """退出群聊"""
        conversation = self.get_object()
        if conversation.type != 'GROUP':
            return Response({'error': '只有群聊才能退出'}, status=400)
        
        member = conversation.members.filter(user=request.user).first()
        if member:
            if member.role == 'OWNER':
                # 群主需要先转让
                return Response({'error': '请先转让群主身份'}, status=400)
            member.delete()
            
            IMMessage.objects.create(
                conversation=conversation,
                message_type='SYSTEM',
                content=f'{request.user.username} 退出了群聊',
                created_by=request.user
            )
        
        return Response({'message': '已退出群聊'})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """标记会话已读"""
        conversation = self.get_object()
        member = conversation.members.filter(user=request.user).first()
        if member:
            from django.utils import timezone
            last_msg = conversation.messages.order_by('-id').first()
            member.last_read_at = timezone.now()
            if last_msg:
                member.last_read_message_id = last_msg.id
            member.save()
        return Response({'message': '已标记已读'})


class IMMessageViewSet(viewsets.ModelViewSet):
    """IM消息管理"""
    serializer_class = IMMessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        conversation_id = self.request.query_params.get('conversation')
        qs = IMMessage.objects.filter(
            conversation__members__user=self.request.user,
            is_deleted=False
        ).distinct()
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        return qs.select_related('sender', 'reply_to')
    
    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        
        message = serializer.save(
            sender=self.request.user,
            created_by=self.request.user
        )
        
        if file:
            message.file = file
            message.file_name = file.name
            message.file_size = file.size
            message.file_type = file.content_type
            
            # 根据文件类型设置消息类型
            if file.content_type.startswith('image/'):
                message.message_type = 'IMAGE'
            else:
                message.message_type = 'FILE'
            message.save()
    
    @action(detail=True, methods=['post'])
    def recall(self, request, pk=None):
        """撤回消息"""
        message = self.get_object()
        
        if message.sender != request.user:
            return Response({'error': '只能撤回自己的消息'}, status=403)
        
        from django.utils import timezone
        from datetime import timedelta
        
        if timezone.now() - message.created_at > timedelta(minutes=2):
            return Response({'error': '超过2分钟的消息无法撤回'}, status=400)
        
        message.is_recalled = True
        message.recalled_at = timezone.now()
        message.save()
        
        return Response({'message': '消息已撤回'})
    
    @action(detail=False, methods=['post'])
    def send_file(self, request):
        """发送文件消息"""
        conversation_id = request.data.get('conversation')
        file = request.FILES.get('file')
        
        if not conversation_id or not file:
            return Response({'error': '请提供会话ID和文件'}, status=400)
        
        try:
            conversation = IMConversation.objects.get(id=conversation_id)
        except IMConversation.DoesNotExist:
            return Response({'error': '会话不存在'}, status=404)
        
        # 检查权限
        if not conversation.members.filter(user=request.user).exists():
            return Response({'error': '无权访问此会话'}, status=403)
        
        # 确定消息类型
        if file.content_type.startswith('image/'):
            msg_type = 'IMAGE'
        elif file.content_type.startswith('video/'):
            msg_type = 'VIDEO'
        elif file.content_type.startswith('audio/'):
            msg_type = 'AUDIO'
        else:
            msg_type = 'FILE'
        
        message = IMMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            message_type=msg_type,
            file=file,
            file_name=file.name,
            file_size=file.size,
            file_type=file.content_type,
            created_by=request.user
        )
        
        return Response(IMMessageSerializer(message, context={'request': request}).data)
