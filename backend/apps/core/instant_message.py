"""
即时通讯
Instant Messaging
站内消息、群组聊天、文件共享
"""

from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class Conversation(BaseModel):
    """会话"""

    TYPE_CHOICES = [
        ('PRIVATE', '私聊'),
        ('GROUP', '群组'),
        ('PROJECT', '项目群'),
        ('DEPARTMENT', '部门群'),
    ]

    name = models.CharField(max_length=100, blank=True, verbose_name='会话名称')
    conversation_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='PRIVATE', verbose_name='会话类型'
    )

    # 群组设置
    avatar = models.CharField(max_length=500, blank=True, verbose_name='头像')
    description = models.TextField(blank=True, verbose_name='描述')

    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='关联项目',
    )
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='关联部门',
    )

    # 成员
    members = models.ManyToManyField(
        'accounts.User',
        through='ConversationMember',
        through_fields=('conversation', 'user'),
        related_name='im_conversations',
        verbose_name='成员',
    )

    # 创建者
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_conversations',
        verbose_name='创建者',
    )

    # 最后消息时间（用于排序）
    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='最后消息时间')

    class Meta:
        db_table = 'im_conversation'
        verbose_name = '会话'
        verbose_name_plural = verbose_name
        ordering = ['-last_message_at']

    def __str__(self):
        return self.name or f'会话{self.id}'


class ConversationMember(BaseModel):
    """会话成员"""

    ROLE_CHOICES = [
        ('OWNER', '群主'),
        ('ADMIN', '管理员'),
        ('MEMBER', '成员'),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='conversation_members', verbose_name='会话'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='conversation_memberships', verbose_name='用户'
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER', verbose_name='角色')

    # 设置
    is_pinned = models.BooleanField(default=False, verbose_name='置顶')
    is_muted = models.BooleanField(default=False, verbose_name='免打扰')
    nickname = models.CharField(max_length=50, blank=True, verbose_name='群昵称')

    # 已读位置
    last_read_at = models.DateTimeField(null=True, blank=True, verbose_name='最后阅读时间')
    last_read_message = models.ForeignKey(
        'Message', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='最后阅读消息'
    )

    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')

    class Meta:
        db_table = 'im_conversation_member'
        verbose_name = '会话成员'
        verbose_name_plural = verbose_name
        unique_together = ['conversation', 'user']


class Message(BaseModel):
    """消息"""

    TYPE_CHOICES = [
        ('TEXT', '文本'),
        ('IMAGE', '图片'),
        ('FILE', '文件'),
        ('AUDIO', '语音'),
        ('VIDEO', '视频'),
        ('LINK', '链接'),
        ('SYSTEM', '系统消息'),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages', verbose_name='会话'
    )

    sender = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='sent_messages', verbose_name='发送者'
    )

    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='TEXT', verbose_name='消息类型')

    content = models.TextField(verbose_name='内容')

    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    # 引用
    reply_to = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies', verbose_name='回复消息'
    )

    # @提及
    mentions = models.ManyToManyField(
        'accounts.User', blank=True, related_name='mentioned_messages', verbose_name='提及用户'
    )

    # 状态
    is_recalled = models.BooleanField(default=False, verbose_name='已撤回')
    recalled_at = models.DateTimeField(null=True, blank=True, verbose_name='撤回时间')

    class Meta:
        db_table = 'im_message'
        verbose_name = '消息'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender} - {self.content[:20]}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 更新会话最后消息时间
        if self.conversation:
            self.conversation.last_message_at = self.created_at
            self.conversation.save(update_fields=['last_message_at'])


class MessageRead(BaseModel):
    """消息已读状态"""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reads', verbose_name='消息')
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='message_reads', verbose_name='用户'
    )
    read_at = models.DateTimeField(auto_now_add=True, verbose_name='阅读时间')

    class Meta:
        db_table = 'im_message_read'
        verbose_name = '消息已读'
        verbose_name_plural = verbose_name
        unique_together = ['message', 'user']


# =====================
# Serializers
# =====================


class MessageSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_avatar = serializers.SerializerMethodField()
    reply_content = serializers.SerializerMethodField()
    mention_names = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'is_recalled', 'recalled_at']

    def get_sender_avatar(self, obj):
        if obj.sender and hasattr(obj.sender, 'avatar'):
            return obj.sender.avatar
        return None

    def get_reply_content(self, obj):
        if obj.reply_to:
            return obj.reply_to.content[:50]
        return None

    def get_mention_names(self, obj):
        return [u.get_full_name() or u.username for u in obj.mentions.all()]


class ConversationMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = ConversationMember
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'joined_at']


class ConversationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_conversation_type_display', read_only=True)
    member_count = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    conversation_members = ConversationMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'last_message_at']

    def get_member_count(self, obj):
        return obj.members.count()

    def get_unread_count(self, obj):
        user = self.context.get('request')
        if user and hasattr(user, 'user'):
            user = user.user
            membership = obj.conversation_members.filter(user=user).first()
            if membership and membership.last_read_at:
                return (
                    obj.messages.filter(created_at__gt=membership.last_read_at, is_recalled=False)
                    .exclude(sender=user)
                    .count()
                )
        return 0

    def get_last_message(self, obj):
        last_msg = obj.messages.filter(is_recalled=False).order_by('-created_at').first()
        if last_msg:
            return {
                'content': last_msg.content[:50],
                'sender': last_msg.sender.get_full_name() if last_msg.sender else None,
                'time': last_msg.created_at.isoformat(),
            }
        return None


class ConversationListSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_conversation_type_display', read_only=True)
    member_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'name',
            'conversation_type',
            'type_display',
            'avatar',
            'member_count',
            'last_message',
            'last_message_at',
        ]

    def get_member_count(self, obj):
        return obj.members.count()

    def get_last_message(self, obj):
        last_msg = obj.messages.filter(is_recalled=False).order_by('-created_at').first()
        if last_msg:
            return {'content': last_msg.content[:30], 'time': last_msg.created_at.isoformat()}
        return None


# =====================
# ViewSets
# =====================


class ConversationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """会话管理"""

    queryset = Conversation.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conversation_type', 'project', 'department']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer

    def get_queryset(self):
        # 只返回用户参与的会话
        return super().get_queryset().filter(members=self.request.user).distinct()

    @action(detail=False, methods=['post'])
    def create_private(self, request):
        """创建私聊"""
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': '请指定用户'}, status=400)

        from apps.accounts.models import User

        try:
            other_user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=404)

        current_user = request.user

        # 检查是否已存在私聊
        existing = (
            Conversation.objects.filter(conversation_type='PRIVATE', is_deleted=False)
            .filter(members=current_user)
            .filter(members=other_user)
        )

        if existing.exists():
            return Response(ConversationSerializer(existing.first(), context={'request': request}).data)

        # 创建新私聊
        conv = Conversation.objects.create(
            name=f'{current_user.get_full_name()},{other_user.get_full_name()}',
            conversation_type='PRIVATE',
            owner=current_user,
            created_by=current_user,
        )

        ConversationMember.objects.create(conversation=conv, user=current_user, role='OWNER', created_by=current_user)
        ConversationMember.objects.create(conversation=conv, user=other_user, role='MEMBER', created_by=current_user)

        return Response(ConversationSerializer(conv, context={'request': request}).data)

    @action(detail=False, methods=['post'])
    def create_group(self, request):
        """创建群组"""
        name = request.data.get('name')
        member_ids = request.data.get('member_ids', [])

        if not name:
            return Response({'error': '请提供群组名称'}, status=400)

        current_user = request.user

        conv = Conversation.objects.create(
            name=name, conversation_type='GROUP', owner=current_user, created_by=current_user
        )

        # 添加创建者
        ConversationMember.objects.create(conversation=conv, user=current_user, role='OWNER', created_by=current_user)

        # 添加其他成员
        from apps.accounts.models import User

        for uid in member_ids:
            try:
                user = User.objects.get(id=uid, is_active=True)
                ConversationMember.objects.create(conversation=conv, user=user, role='MEMBER', created_by=current_user)
            except User.DoesNotExist:
                pass

        return Response(ConversationSerializer(conv, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def add_members(self, request, pk=None):
        """添加成员"""
        conv = self.get_object()
        member_ids = request.data.get('member_ids', [])

        from apps.accounts.models import User

        added = []
        for uid in member_ids:
            try:
                user = User.objects.get(id=uid, is_active=True)
                if not conv.members.filter(id=uid).exists():
                    ConversationMember.objects.create(
                        conversation=conv, user=user, role='MEMBER', created_by=request.user
                    )
                    added.append(uid)
            except User.DoesNotExist:
                pass

        return Response({'added': added})

    @action(detail=True, methods=['post'])
    def leave(self, request, pk=None):
        """离开群组"""
        conv = self.get_object()
        membership = conv.conversation_members.filter(user=request.user).first()

        if membership:
            membership.delete()

        return Response({'success': True})


class MessageViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """消息管理"""

    queryset = Message.objects.filter(is_deleted=False)
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conversation', 'message_type']
    ordering = ['-created_at']

    def get_queryset(self):
        # 只返回用户参与的会话中的消息
        user_conversations = Conversation.objects.filter(members=self.request.user, is_deleted=False)
        return super().get_queryset().filter(conversation__in=user_conversations)

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def recall(self, request, pk=None):
        """撤回消息"""
        msg = self.get_object()

        # 只能撤回自己的消息
        if msg.sender != request.user:
            return Response({'error': '只能撤回自己的消息'}, status=403)

        # 检查时间限制（2分钟）
        time_limit = timezone.now() - timezone.timedelta(minutes=2)
        if msg.created_at < time_limit:
            return Response({'error': '消息已超过撤回时限'}, status=400)

        msg.is_recalled = True
        msg.recalled_at = timezone.now()
        msg.save()

        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def mark_read(self, request):
        """标记已读"""
        conversation_id = request.data.get('conversation_id')
        message_id = request.data.get('message_id')

        if not conversation_id:
            return Response({'error': '请指定会话'}, status=400)

        try:
            conv = Conversation.objects.get(id=conversation_id, is_deleted=False)
            membership = conv.conversation_members.filter(user=request.user).first()

            if membership:
                membership.last_read_at = timezone.now()
                if message_id:
                    try:
                        msg = Message.objects.get(id=message_id)
                        membership.last_read_message = msg
                    except Message.DoesNotExist:
                        pass
                membership.save()

            return Response({'success': True})
        except Conversation.DoesNotExist:
            return Response({'error': '会话不存在'}, status=404)


class ConversationMemberViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """会话成员管理"""

    queryset = ConversationMember.objects.filter(is_deleted=False)
    serializer_class = ConversationMemberSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conversation', 'role']
