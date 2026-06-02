"""
日程管理和会议管理
Schedule and Meeting Management
OA协同办公模块
"""

from datetime import date, timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class Schedule(BaseModel):
    """日程安排"""

    TYPE_CHOICES = [
        ('MEETING', '会议'),
        ('TASK', '任务'),
        ('REMINDER', '提醒'),
        ('VISIT', '拜访'),
        ('CALL', '电话'),
        ('OTHER', '其他'),
    ]

    REPEAT_CHOICES = [
        ('NONE', '不重复'),
        ('DAILY', '每天'),
        ('WEEKLY', '每周'),
        ('MONTHLY', '每月'),
        ('YEARLY', '每年'),
    ]

    title = models.CharField(max_length=200, verbose_name='标题')
    schedule_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='TASK', verbose_name='日程类型')

    # 时间
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    all_day = models.BooleanField(default=False, verbose_name='全天')

    # 重复
    repeat_type = models.CharField(max_length=20, choices=REPEAT_CHOICES, default='NONE', verbose_name='重复类型')
    repeat_end_date = models.DateField(null=True, blank=True, verbose_name='重复结束日期')

    # 关联
    owner = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='schedules', verbose_name='所有者'
    )
    participants = models.ManyToManyField(
        'accounts.User', blank=True, related_name='participated_schedules', verbose_name='参与人'
    )

    # 关联业务
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules',
        verbose_name='关联项目',
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules',
        verbose_name='关联客户',
    )

    # 详情
    location = models.CharField(max_length=200, blank=True, verbose_name='地点')
    description = models.TextField(blank=True, verbose_name='描述')

    # 提醒
    reminder_minutes = models.IntegerField(default=15, verbose_name='提前提醒(分钟)')
    is_reminded = models.BooleanField(default=False, verbose_name='已提醒')

    # 颜色
    color = models.CharField(max_length=20, default='#409EFF', verbose_name='颜色')

    # 是否公开
    is_public = models.BooleanField(default=False, verbose_name='公开日程')

    class Meta:
        db_table = 'oa_schedule'
        verbose_name = '日程'
        verbose_name_plural = verbose_name
        ordering = ['start_time']

    def __str__(self):
        return f'{self.title} ({self.start_time.strftime("%Y-%m-%d %H:%M")})'


class Meeting(BaseModel):
    """会议管理"""

    STATUS_CHOICES = [
        ('SCHEDULED', '已安排'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    TYPE_CHOICES = [
        ('REGULAR', '例会'),
        ('PROJECT', '项目会议'),
        ('REVIEW', '评审会议'),
        ('TRAINING', '培训'),
        ('CUSTOMER', '客户会议'),
        ('OTHER', '其他'),
    ]

    meeting_no = models.CharField(max_length=50, unique=True, verbose_name='会议编号')
    title = models.CharField(max_length=200, verbose_name='会议主题')
    meeting_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='REGULAR', verbose_name='会议类型')

    # 时间地点
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    location = models.CharField(max_length=200, blank=True, verbose_name='会议地点')
    meeting_room = models.ForeignKey(
        'MeetingRoom', on_delete=models.SET_NULL, null=True, blank=True, related_name='meetings', verbose_name='会议室'
    )
    is_online = models.BooleanField(default=False, verbose_name='线上会议')
    meeting_link = models.CharField(max_length=500, blank=True, verbose_name='会议链接')

    # 人员
    organizer = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='organized_meetings', verbose_name='组织者'
    )
    participants = models.ManyToManyField(
        'accounts.User',
        through='MeetingParticipant',
        through_fields=('meeting', 'user'),
        related_name='meetings',
        verbose_name='参会人员',
    )

    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meetings',
        verbose_name='关联项目',
    )

    # 内容
    agenda = models.TextField(blank=True, verbose_name='会议议程')
    minutes = models.TextField(blank=True, verbose_name='会议纪要')
    decisions = models.TextField(blank=True, verbose_name='会议决议')
    action_items = models.JSONField(default=list, blank=True, verbose_name='待办事项')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED', verbose_name='状态')

    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    class Meta:
        db_table = 'oa_meeting'
        verbose_name = '会议'
        verbose_name_plural = verbose_name
        ordering = ['-start_time']

    def __str__(self):
        return f'{self.meeting_no} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.meeting_no:
            from apps.core.utils import generate_code

            self.meeting_no = generate_code('MTG')
        super().save(*args, **kwargs)


class MeetingRoom(BaseModel):
    """会议室"""

    name = models.CharField(max_length=100, verbose_name='会议室名称')
    location = models.CharField(max_length=200, blank=True, verbose_name='位置')
    capacity = models.IntegerField(default=10, verbose_name='容纳人数')
    equipment = models.JSONField(default=list, blank=True, verbose_name='设备设施')
    is_available = models.BooleanField(default=True, verbose_name='可用')

    class Meta:
        db_table = 'oa_meeting_room'
        verbose_name = '会议室'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


class MeetingParticipant(BaseModel):
    """会议参与者"""

    RESPONSE_CHOICES = [
        ('PENDING', '待确认'),
        ('ACCEPTED', '已接受'),
        ('DECLINED', '已拒绝'),
        ('TENTATIVE', '暂定'),
    ]

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name='meeting_participants', verbose_name='会议'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='meeting_participations', verbose_name='参会人'
    )
    response = models.CharField(max_length=20, choices=RESPONSE_CHOICES, default='PENDING', verbose_name='回复状态')
    is_required = models.BooleanField(default=True, verbose_name='必须参加')
    attended = models.BooleanField(default=False, verbose_name='实际出席')

    class Meta:
        db_table = 'oa_meeting_participant'
        verbose_name = '会议参与者'
        verbose_name_plural = verbose_name
        unique_together = ['meeting', 'user']


# =====================
# Serializers
# =====================


class ScheduleSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_schedule_type_display', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    participant_names = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_participant_names(self, obj):
        return [u.get_full_name() for u in obj.participants.all()]


class ScheduleListSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_schedule_type_display', read_only=True)

    class Meta:
        model = Schedule
        fields = [
            'id',
            'title',
            'schedule_type',
            'type_display',
            'start_time',
            'end_time',
            'all_day',
            'location',
            'color',
            'is_public',
        ]


class MeetingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingRoom
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class MeetingParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    response_display = serializers.CharField(source='get_response_display', read_only=True)

    class Meta:
        model = MeetingParticipant
        fields = '__all__'


class MeetingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_meeting_type_display', read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    room_name = serializers.CharField(source='meeting_room.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    meeting_participants = MeetingParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Meeting
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'meeting_no']


class MeetingListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_meeting_type_display', read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    room_name = serializers.CharField(source='meeting_room.name', read_only=True)
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            'id',
            'meeting_no',
            'title',
            'meeting_type',
            'type_display',
            'start_time',
            'end_time',
            'location',
            'is_online',
            'status',
            'status_display',
            'organizer_name',
            'room_name',
            'participant_count',
        ]

    def get_participant_count(self, obj):
        return obj.meeting_participants.count()


# =====================
# ViewSets
# =====================


class ScheduleViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """日程管理"""

    permission_module = 'system'
    permission_resource = 'schedule'
    allow_authenticated_read = True
    skip_data_scope = True  # 可见性由 get_queryset 的 owner|public|participant 控制（审计 H13）
    queryset = Schedule.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['schedule_type', 'owner', 'project', 'customer']
    search_fields = ['title', 'description']

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleListSerializer
        return ScheduleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # 只能看自己的日程或公开日程或被邀请的日程
        return qs.filter(Q(owner=user) | Q(is_public=True) | Q(participants=user)).distinct()

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """日历视图数据"""
        start = request.query_params.get('start')
        end = request.query_params.get('end')

        qs = self.get_queryset()

        if start:
            qs = qs.filter(end_time__gte=start)
        if end:
            qs = qs.filter(start_time__lte=end)

        events = []
        for schedule in qs:
            events.append(
                {
                    'id': schedule.id,
                    'title': schedule.title,
                    'start': schedule.start_time.isoformat(),
                    'end': schedule.end_time.isoformat(),
                    'allDay': schedule.all_day,
                    'color': schedule.color,
                    'type': schedule.schedule_type,
                    'location': schedule.location,
                }
            )

        return Response(events)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """今日日程"""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        schedules = self.get_queryset().filter(start_time__date__lte=today, end_time__date__gte=today)

        return Response(ScheduleListSerializer(schedules, many=True).data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """即将到来的日程"""
        now = timezone.now()
        week_later = now + timedelta(days=7)

        schedules = (
            self.get_queryset().filter(start_time__gte=now, start_time__lte=week_later).order_by('start_time')[:20]
        )

        return Response(ScheduleListSerializer(schedules, many=True).data)


class MeetingRoomViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """会议室管理"""

    permission_module = 'system'
    permission_resource = 'meeting_room'
    allow_authenticated_read = True
    skip_data_scope = True  # 会议室为共享资源，全员可见（审计 H13）
    queryset = MeetingRoom.objects.filter(is_deleted=False)
    serializer_class = MeetingRoomSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_available']
    search_fields = ['name', 'location']

    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """查询会议室可用时段"""
        room = self.get_object()
        date_str = request.query_params.get('date', date.today().isoformat())
        query_date = date.fromisoformat(date_str)

        # 获取该日期的所有预订
        meetings = Meeting.objects.filter(
            meeting_room=room, start_time__date=query_date, status__in=['SCHEDULED', 'IN_PROGRESS'], is_deleted=False
        ).order_by('start_time')

        booked_slots = [
            {'start': m.start_time.strftime('%H:%M'), 'end': m.end_time.strftime('%H:%M'), 'title': m.title}
            for m in meetings
        ]

        return Response({'room': room.name, 'date': date_str, 'booked_slots': booked_slots})


class MeetingViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """会议管理"""

    permission_module = 'system'
    permission_resource = 'meeting'
    allow_authenticated_read = True
    skip_data_scope = True  # 会议为协同数据；个人视图见 my_meetings 动作（审计 H13）
    queryset = Meeting.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'organizer', 'project', 'meeting_room']
    search_fields = ['meeting_no', 'title']
    ordering_fields = ['start_time', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return MeetingListSerializer
        return MeetingSerializer

    def perform_create(self, serializer):
        meeting = serializer.save(organizer=self.request.user, created_by=self.request.user)
        # 添加参与者
        participant_ids = self.request.data.get('participant_ids', [])
        for uid in participant_ids:
            MeetingParticipant.objects.create(meeting=meeting, user_id=uid, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """回复会议邀请"""
        meeting = self.get_object()
        response = request.data.get('response', 'ACCEPTED')

        participant, _ = MeetingParticipant.objects.get_or_create(
            meeting=meeting, user=request.user, defaults={'created_by': request.user}
        )
        participant.response = response
        participant.save()

        return Response({'success': True, 'response': response})

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始会议"""
        meeting = self.get_object()
        meeting.status = 'IN_PROGRESS'
        meeting.save()
        return Response(self.get_serializer(meeting).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成会议"""
        meeting = self.get_object()
        meeting.status = 'COMPLETED'
        meeting.minutes = request.data.get('minutes', meeting.minutes)
        meeting.decisions = request.data.get('decisions', meeting.decisions)
        meeting.action_items = request.data.get('action_items', meeting.action_items)
        meeting.save()
        return Response(self.get_serializer(meeting).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消会议"""
        meeting = self.get_object()
        meeting.status = 'CANCELLED'
        meeting.save()
        return Response(self.get_serializer(meeting).data)

    @action(detail=False, methods=['get'])
    def my_meetings(self, request):
        """我的会议"""
        user = request.user
        meetings = (
            self.get_queryset()
            .filter(Q(organizer=user) | Q(meeting_participants__user=user))
            .distinct()
            .order_by('-start_time')
        )

        return Response(MeetingListSerializer(meetings, many=True).data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """今日会议"""
        today = date.today()
        meetings = (
            self.get_queryset()
            .filter(start_time__date=today, status__in=['SCHEDULED', 'IN_PROGRESS'])
            .order_by('start_time')
        )

        return Response(MeetingListSerializer(meetings, many=True).data)
