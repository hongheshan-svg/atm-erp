"""
客户跟进记录管理
Customer Follow-up Management
记录客户拜访、电话、邮件等跟进活动
"""

from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class CustomerFollowUp(BaseModel):
    """
    客户跟进记录
    """

    FOLLOW_TYPES = [
        ('VISIT', '客户拜访'),
        ('PHONE', '电话沟通'),
        ('EMAIL', '邮件往来'),
        ('MEETING', '会议洽谈'),
        ('VIDEO', '视频会议'),
        ('WECHAT', '微信沟通'),
        ('RECEPTION', '客户来访'),
        ('EXHIBITION', '展会接洽'),
        ('OTHER', '其他'),
    ]

    RESULT_TYPES = [
        ('POSITIVE', '积极反馈'),
        ('NEUTRAL', '一般'),
        ('NEGATIVE', '消极反馈'),
        ('PENDING', '待跟进'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]

    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.CASCADE, related_name='follow_ups', verbose_name='客户'
    )
    follow_type = models.CharField(max_length=20, choices=FOLLOW_TYPES, default='PHONE', verbose_name='跟进方式')
    follow_date = models.DateField(verbose_name='跟进日期')
    follow_time = models.TimeField(null=True, blank=True, verbose_name='跟进时间')

    # 跟进人员
    follower = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='customer_followups', verbose_name='跟进人'
    )
    participants = models.ManyToManyField(
        'accounts.User', blank=True, related_name='participated_followups', verbose_name='参与人员'
    )

    # 客户方参与人
    customer_contacts = models.CharField(max_length=500, blank=True, verbose_name='客户方参与人')

    # 跟进内容
    subject = models.CharField(max_length=200, verbose_name='跟进主题')
    content = models.TextField(verbose_name='跟进内容')
    result = models.CharField(max_length=20, choices=RESULT_TYPES, default='NEUTRAL', verbose_name='跟进结果')

    # 关联信息
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='follow_ups',
        verbose_name='关联商机',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_followups',
        verbose_name='关联项目',
    )

    # 下次跟进计划
    next_follow_date = models.DateField(null=True, blank=True, verbose_name='下次跟进日期')
    next_follow_plan = models.TextField(blank=True, verbose_name='下次跟进计划')
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='MEDIUM', verbose_name='优先级')

    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件列表')

    # 位置（拜访时）
    location = models.CharField(max_length=500, blank=True, verbose_name='拜访地点')

    class Meta:
        db_table = 'masterdata_customer_followup'
        verbose_name = '客户跟进记录'
        verbose_name_plural = verbose_name
        ordering = ['-follow_date', '-created_at']

    def __str__(self):
        return f'{self.customer.name} - {self.subject}'


class CustomerReminder(BaseModel):
    """
    客户提醒
    """

    REMINDER_TYPES = [
        ('FOLLOW', '跟进提醒'),
        ('BIRTHDAY', '生日提醒'),
        ('CONTRACT', '合同到期'),
        ('PAYMENT', '付款提醒'),
        ('VISIT', '拜访计划'),
        ('CUSTOM', '自定义提醒'),
    ]

    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.CASCADE, related_name='reminders', verbose_name='客户'
    )
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES, default='FOLLOW', verbose_name='提醒类型')
    title = models.CharField(max_length=200, verbose_name='提醒标题')
    content = models.TextField(blank=True, verbose_name='提醒内容')
    remind_date = models.DateField(verbose_name='提醒日期')
    remind_time = models.TimeField(null=True, blank=True, verbose_name='提醒时间')

    # 提醒对象
    remind_user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='customer_reminders', verbose_name='提醒对象'
    )

    # 状态
    is_completed = models.BooleanField(default=False, verbose_name='已完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    is_notified = models.BooleanField(default=False, verbose_name='已通知')
    notified_at = models.DateTimeField(null=True, blank=True, verbose_name='通知时间')

    # 重复设置
    is_recurring = models.BooleanField(default=False, verbose_name='重复提醒')
    recurrence_pattern = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', '每天'),
            ('WEEKLY', '每周'),
            ('MONTHLY', '每月'),
            ('YEARLY', '每年'),
        ],
        blank=True,
        verbose_name='重复模式',
    )

    class Meta:
        db_table = 'masterdata_customer_reminder'
        verbose_name = '客户提醒'
        verbose_name_plural = verbose_name
        ordering = ['remind_date', 'remind_time']

    def __str__(self):
        return f'{self.customer.name} - {self.title}'


class CustomerContact(BaseModel):
    """
    客户联系人
    """

    CONTACT_ROLES = [
        ('DECISION', '决策者'),
        ('TECHNICAL', '技术负责人'),
        ('PURCHASE', '采购负责人'),
        ('FINANCE', '财务负责人'),
        ('PROJECT', '项目负责人'),
        ('OPERATOR', '操作人员'),
        ('OTHER', '其他'),
    ]

    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.CASCADE, related_name='contacts', verbose_name='客户'
    )
    name = models.CharField(max_length=100, verbose_name='姓名')
    title = models.CharField(max_length=100, blank=True, verbose_name='职位')
    department = models.CharField(max_length=100, blank=True, verbose_name='部门')
    role = models.CharField(max_length=20, choices=CONTACT_ROLES, default='OTHER', verbose_name='角色')

    # 联系方式
    mobile = models.CharField(max_length=50, blank=True, verbose_name='手机')
    phone = models.CharField(max_length=50, blank=True, verbose_name='电话')
    email = models.EmailField(blank=True, verbose_name='邮箱')
    wechat = models.CharField(max_length=100, blank=True, verbose_name='微信')
    qq = models.CharField(max_length=50, blank=True, verbose_name='QQ')

    # 个人信息
    birthday = models.DateField(null=True, blank=True, verbose_name='生日')
    hobbies = models.CharField(max_length=500, blank=True, verbose_name='兴趣爱好')
    notes = models.TextField(blank=True, verbose_name='备注')

    # 状态
    is_primary = models.BooleanField(default=False, verbose_name='主联系人')
    is_active = models.BooleanField(default=True, verbose_name='在职')

    class Meta:
        db_table = 'masterdata_customer_contact'
        verbose_name = '客户联系人'
        verbose_name_plural = verbose_name
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f'{self.customer.name} - {self.name}'

    def save(self, *args, **kwargs):
        if self.is_primary:
            CustomerContact.objects.filter(customer=self.customer, is_primary=True).exclude(pk=self.pk).update(
                is_primary=False
            )
        super().save(*args, **kwargs)


# =====================
# Serializers
# =====================


class CustomerFollowUpSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    follower_name = serializers.CharField(source='follower.get_full_name', read_only=True)
    follow_type_display = serializers.CharField(source='get_follow_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = CustomerFollowUp
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CustomerFollowUpListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    follower_name = serializers.CharField(source='follower.get_full_name', read_only=True)
    follow_type_display = serializers.CharField(source='get_follow_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = CustomerFollowUp
        fields = [
            'id',
            'customer',
            'customer_name',
            'follow_type',
            'follow_type_display',
            'follow_date',
            'follower',
            'follower_name',
            'subject',
            'result',
            'result_display',
            'next_follow_date',
            'created_at',
        ]


class CustomerReminderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    remind_user_name = serializers.CharField(source='remind_user.get_full_name', read_only=True)
    reminder_type_display = serializers.CharField(source='get_reminder_type_display', read_only=True)

    class Meta:
        model = CustomerReminder
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CustomerContactSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = CustomerContact
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================


class CustomerFollowUpViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """客户跟进记录管理"""

    queryset = CustomerFollowUp.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'follow_type', 'result', 'follower', 'priority']
    search_fields = ['subject', 'content', 'customer__name']
    ordering_fields = ['follow_date', 'created_at', 'next_follow_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerFollowUpListSerializer
        return CustomerFollowUpSerializer

    def perform_create(self, serializer):
        follower = serializer.validated_data.get('follower') or self.request.user
        serializer.save(follower=follower, created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def follow_types(self, request):
        """获取跟进方式"""
        return Response([{'value': t[0], 'label': t[1]} for t in CustomerFollowUp.FOLLOW_TYPES])

    @action(detail=False, methods=['get'])
    def my_followups(self, request):
        """我的跟进记录"""
        queryset = self.get_queryset().filter(follower=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_followups(self, request):
        """待跟进记录（下次跟进日期已到或已过）"""
        from datetime import date

        queryset = (
            self.get_queryset()
            .filter(follower=request.user, next_follow_date__lte=date.today())
            .exclude(result='POSITIVE')
        )

        return Response(CustomerFollowUpListSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        """获取客户的跟进记录"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': '请提供客户ID'}, status=400)

        queryset = self.get_queryset().filter(customer_id=customer_id)
        return Response(CustomerFollowUpListSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """跟进统计"""
        from datetime import date, timedelta

        from django.db.models import Count
        from django.db.models.functions import TruncMonth

        user = request.user
        qs = self.get_queryset()

        # 可选过滤
        if not request.user.is_superuser:
            qs = qs.filter(follower=user)

        today = date.today()
        this_week_start = today - timedelta(days=today.weekday())
        this_month_start = today.replace(day=1)

        # 本周/本月统计
        this_week = qs.filter(follow_date__gte=this_week_start).count()
        this_month = qs.filter(follow_date__gte=this_month_start).count()

        # 按跟进方式统计
        by_type = qs.values('follow_type').annotate(count=Count('id'))

        # 按结果统计
        by_result = qs.values('result').annotate(count=Count('id'))

        # 按月趋势
        by_month = (
            qs.annotate(month=TruncMonth('follow_date')).values('month').annotate(count=Count('id')).order_by('month')
        )

        # 待跟进数量
        pending = qs.filter(next_follow_date__lte=today).exclude(result='POSITIVE').count()

        return Response(
            {
                'total': qs.count(),
                'this_week': this_week,
                'this_month': this_month,
                'pending': pending,
                'by_type': list(by_type),
                'by_result': list(by_result),
                'by_month': list(by_month),
            }
        )


class CustomerReminderViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """客户提醒管理"""

    queryset = CustomerReminder.objects.filter(is_deleted=False)
    serializer_class = CustomerReminderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'reminder_type', 'is_completed', 'remind_user']
    search_fields = ['title', 'content', 'customer__name']
    ordering_fields = ['remind_date', 'remind_time']

    @action(detail=False, methods=['get'])
    def my_reminders(self, request):
        """我的提醒"""
        queryset = (
            self.get_queryset()
            .filter(remind_user=request.user, is_completed=False)
            .order_by('remind_date', 'remind_time')
        )

        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """今日提醒"""
        from datetime import date

        queryset = self.get_queryset().filter(remind_user=request.user, remind_date=date.today(), is_completed=False)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成提醒"""
        reminder = self.get_object()
        reminder.is_completed = True
        reminder.completed_at = timezone.now()
        reminder.save()
        return Response(self.get_serializer(reminder).data)


class CustomerContactViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """客户联系人管理"""

    queryset = CustomerContact.objects.filter(is_deleted=False)
    serializer_class = CustomerContactSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'role', 'is_primary', 'is_active']
    search_fields = ['name', 'title', 'mobile', 'email', 'customer__name']
    ordering_fields = ['name', 'created_at']

    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        """获取客户的联系人"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': '请提供客户ID'}, status=400)

        queryset = self.get_queryset().filter(customer_id=customer_id)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """设为主联系人"""
        contact = self.get_object()
        contact.is_primary = True
        contact.save()
        return Response(self.get_serializer(contact).data)

    @action(detail=False, methods=['get'])
    def contact_roles(self, request):
        """获取联系人角色"""
        return Response([{'value': r[0], 'label': r[1]} for r in CustomerContact.CONTACT_ROLES])

    @action(detail=False, methods=['get'])
    def upcoming_birthdays(self, request):
        """即将到来的生日"""
        from datetime import date, timedelta

        today = date.today()
        next_30_days = today + timedelta(days=30)

        # 查询未来30天内的生日
        contacts = self.get_queryset().filter(birthday__isnull=False, is_active=True).exclude(birthday=None)

        upcoming = []
        for contact in contacts:
            if contact.birthday:
                this_year_birthday = contact.birthday.replace(year=today.year)
                if this_year_birthday < today:
                    this_year_birthday = this_year_birthday.replace(year=today.year + 1)

                if today <= this_year_birthday <= next_30_days:
                    upcoming.append(
                        {
                            'id': contact.id,
                            'name': contact.name,
                            'customer_name': contact.customer.name,
                            'birthday': this_year_birthday,
                            'days_until': (this_year_birthday - today).days,
                        }
                    )

        upcoming.sort(key=lambda x: x['days_until'])
        return Response(upcoming)
