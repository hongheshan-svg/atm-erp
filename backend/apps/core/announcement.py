"""
系统公告管理
System Announcement Management
发布系统公告、通知等
"""

from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class Announcement(BaseModel):
    """
    系统公告
    """

    ANNOUNCEMENT_TYPES = [
        ('NOTICE', '通知公告'),
        ('NEWS', '新闻动态'),
        ('SYSTEM', '系统公告'),
        ('UPDATE', '更新公告'),
        ('MAINTENANCE', '维护通知'),
        ('IMPORTANT', '重要通知'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', '低'),
        ('NORMAL', '普通'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PUBLISHED', '已发布'),
        ('EXPIRED', '已过期'),
        ('WITHDRAWN', '已撤回'),
    ]

    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='内容')
    summary = models.CharField(max_length=500, blank=True, verbose_name='摘要')

    announcement_type = models.CharField(
        max_length=20, choices=ANNOUNCEMENT_TYPES, default='NOTICE', verbose_name='公告类型'
    )
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='NORMAL', verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 发布设置
    publish_time = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')

    # 显示设置
    is_top = models.BooleanField(default=False, verbose_name='置顶')
    is_popup = models.BooleanField(default=False, verbose_name='弹窗显示')

    # 目标受众
    target_all = models.BooleanField(default=True, verbose_name='全员可见')
    target_departments = models.JSONField(default=list, blank=True, verbose_name='目标部门')
    target_roles = models.JSONField(default=list, blank=True, verbose_name='目标角色')

    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    # 统计
    view_count = models.IntegerField(default=0, verbose_name='浏览次数')

    publisher = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_announcements',
        verbose_name='发布人',
    )

    class Meta:
        db_table = 'core_announcement'
        verbose_name = '系统公告'
        verbose_name_plural = verbose_name
        ordering = ['-is_top', '-publish_time', '-created_at']

    def __str__(self):
        return self.title

    @property
    def is_active(self):
        """是否有效"""
        if self.status != 'PUBLISHED':
            return False
        now = timezone.now()
        if self.expire_time and now > self.expire_time:
            return False
        return True


class AnnouncementRead(BaseModel):
    """
    公告阅读记录
    """

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='reads', verbose_name='公告')
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='announcement_reads', verbose_name='用户'
    )
    read_at = models.DateTimeField(auto_now_add=True, verbose_name='阅读时间')

    class Meta:
        db_table = 'core_announcement_read'
        verbose_name = '公告阅读记录'
        verbose_name_plural = verbose_name
        unique_together = ['announcement', 'user']

    def __str__(self):
        return f'{self.user} - {self.announcement.title}'


# =====================
# Serializers
# =====================


class AnnouncementSerializer(serializers.ModelSerializer):
    announcement_type_display = serializers.CharField(source='get_announcement_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    publisher_name = serializers.CharField(source='publisher.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'publisher', 'view_count']

    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return AnnouncementRead.objects.filter(announcement=obj, user=request.user).exists()


class AnnouncementListSerializer(serializers.ModelSerializer):
    announcement_type_display = serializers.CharField(source='get_announcement_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    publisher_name = serializers.CharField(source='publisher.get_full_name', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            'id',
            'title',
            'summary',
            'announcement_type',
            'announcement_type_display',
            'priority',
            'priority_display',
            'status',
            'status_display',
            'is_top',
            'is_popup',
            'publish_time',
            'expire_time',
            'view_count',
            'publisher_name',
            'is_active',
            'is_read',
            'created_at',
        ]

    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return AnnouncementRead.objects.filter(announcement=obj, user=request.user).exists()


class AnnouncementReadSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = AnnouncementRead
        fields = '__all__'


# =====================
# ViewSets
# =====================


class AnnouncementViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """系统公告管理"""

    queryset = Announcement.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['announcement_type', 'status', 'priority', 'is_top']
    search_fields = ['title', 'content', 'summary']
    ordering_fields = ['publish_time', 'created_at', 'view_count']

    def get_serializer_class(self):
        if self.action == 'list':
            return AnnouncementListSerializer
        return AnnouncementSerializer

    @action(detail=False, methods=['get'])
    def published(self, request):
        """获取已发布的公告"""
        now = timezone.now()
        user = request.user

        # 基础查询：已发布且未过期
        queryset = (
            self.get_queryset()
            .filter(status='PUBLISHED')
            .filter(models.Q(expire_time__isnull=True) | models.Q(expire_time__gt=now))
        )

        # 目标受众过滤
        if not user.is_superuser:
            queryset = queryset.filter(
                models.Q(target_all=True)
                | models.Q(target_departments__contains=[user.department_id])
                | models.Q(target_roles__contains=[user.role_id if hasattr(user, 'role_id') else None])
            )

        serializer = AnnouncementListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """获取未读公告"""
        now = timezone.now()
        user = request.user

        # 获取已读公告ID
        read_ids = AnnouncementRead.objects.filter(user=user).values_list('announcement_id', flat=True)

        queryset = (
            self.get_queryset()
            .filter(status='PUBLISHED')
            .filter(models.Q(expire_time__isnull=True) | models.Q(expire_time__gt=now))
            .exclude(id__in=read_ids)
        )

        serializer = AnnouncementListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def popup(self, request):
        """获取需要弹窗显示的公告"""
        now = timezone.now()
        user = request.user

        # 获取已读公告ID
        read_ids = AnnouncementRead.objects.filter(user=user).values_list('announcement_id', flat=True)

        queryset = (
            self.get_queryset()
            .filter(status='PUBLISHED', is_popup=True)
            .filter(models.Q(expire_time__isnull=True) | models.Q(expire_time__gt=now))
            .exclude(id__in=read_ids)
        )

        serializer = AnnouncementListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """发布公告"""
        announcement = self.get_object()

        if announcement.status not in ['DRAFT', 'WITHDRAWN']:
            return Response({'error': '只有草稿或已撤回的公告可以发布'}, status=400)

        announcement.status = 'PUBLISHED'
        announcement.publish_time = timezone.now()
        announcement.publisher = request.user
        announcement.save()

        return Response(self.get_serializer(announcement).data)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """撤回公告"""
        announcement = self.get_object()

        if announcement.status != 'PUBLISHED':
            return Response({'error': '只有已发布的公告可以撤回'}, status=400)

        announcement.status = 'WITHDRAWN'
        announcement.save()

        return Response(self.get_serializer(announcement).data)

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """标记为已读"""
        announcement = self.get_object()

        AnnouncementRead.objects.get_or_create(announcement=announcement, user=request.user)

        # 更新浏览次数
        announcement.view_count += 1
        announcement.save()

        return Response({'success': True})

    @action(detail=True, methods=['get'])
    def read_list(self, request, pk=None):
        """获取阅读记录"""
        announcement = self.get_object()
        reads = announcement.reads.all().select_related('user')
        return Response(AnnouncementReadSerializer(reads, many=True).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """标记所有为已读"""
        now = timezone.now()
        user = request.user

        # 获取未读公告
        read_ids = AnnouncementRead.objects.filter(user=user).values_list('announcement_id', flat=True)

        unread_announcements = (
            self.get_queryset()
            .filter(status='PUBLISHED')
            .filter(models.Q(expire_time__isnull=True) | models.Q(expire_time__gt=now))
            .exclude(id__in=read_ids)
        )

        # 批量创建阅读记录
        reads = [AnnouncementRead(announcement=a, user=user) for a in unread_announcements]
        AnnouncementRead.objects.bulk_create(reads, ignore_conflicts=True)

        return Response({'success': True, 'marked_count': len(reads)})

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """公告统计"""
        from django.db.models import Count, Sum

        qs = self.get_queryset()

        by_type = qs.values('announcement_type').annotate(count=Count('id'))
        by_status = qs.values('status').annotate(count=Count('id'))

        total_views = qs.aggregate(total=Sum('view_count'))['total'] or 0

        return Response(
            {'total': qs.count(), 'total_views': total_views, 'by_type': list(by_type), 'by_status': list(by_status)}
        )
