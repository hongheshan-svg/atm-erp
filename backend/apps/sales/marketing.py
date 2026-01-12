"""
营销自动化模块
Marketing Automation
邮件营销、营销活动、营销模板等
"""
from datetime import date, datetime, timedelta
from django.db import models
from django.db.models import Count, Sum, Avg, Q
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class MarketingEmailTemplate(BaseModel):
    """营销邮件模板"""
    TYPE_CHOICES = [
        ('MARKETING', '营销推广'),
        ('NOTIFICATION', '通知提醒'),
        ('FOLLOW_UP', '跟进提醒'),
        ('WELCOME', '欢迎邮件'),
        ('BIRTHDAY', '生日祝福'),
        ('FESTIVAL', '节日祝福'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='模板名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    template_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='MARKETING',
        verbose_name='模板类型'
    )
    
    subject = models.CharField(max_length=200, verbose_name='邮件主题')
    content_html = models.TextField(verbose_name='HTML内容')
    content_text = models.TextField(blank=True, verbose_name='纯文本内容')
    
    # 变量说明
    variables = models.JSONField(
        default=list,
        blank=True,
        verbose_name='变量列表',
        help_text='如 ["customer_name", "company_name"]'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'crm_marketing_email_template'
        verbose_name = '营销邮件模板'
        verbose_name_plural = verbose_name
        ordering = ['template_type', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def render(self, context):
        """渲染模板"""
        subject = self.subject
        content = self.content_html
        
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            subject = subject.replace(placeholder, str(value))
            content = content.replace(placeholder, str(value))
        
        return subject, content


class MarketingCampaign(BaseModel):
    """营销活动"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SCHEDULED', '已计划'),
        ('RUNNING', '进行中'),
        ('PAUSED', '已暂停'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    CHANNEL_CHOICES = [
        ('EMAIL', '邮件'),
        ('SMS', '短信'),
        ('WECHAT', '微信'),
        ('MIXED', '多渠道'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='活动名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='活动编码')
    
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='EMAIL',
        verbose_name='渠道'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 邮件模板
    email_template = models.ForeignKey(
        MarketingEmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
        verbose_name='邮件模板'
    )
    
    # 目标受众
    target_segment_name = models.CharField(max_length=100, blank=True, verbose_name='目标客群名称')
    target_criteria = models.JSONField(default=dict, blank=True, verbose_name='目标条件')
    target_count = models.IntegerField(default=0, verbose_name='目标数量')
    
    # 时间
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    
    # 负责人
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marketing_campaigns',
        verbose_name='负责人'
    )
    
    # 预算
    budget = models.DecimalField(
        max_digits=18, decimal_places=2,
        null=True, blank=True,
        verbose_name='预算'
    )
    actual_cost = models.DecimalField(
        max_digits=18, decimal_places=2,
        default=0,
        verbose_name='实际成本'
    )
    
    # 统计
    sent_count = models.IntegerField(default=0, verbose_name='发送数')
    delivered_count = models.IntegerField(default=0, verbose_name='送达数')
    opened_count = models.IntegerField(default=0, verbose_name='打开数')
    clicked_count = models.IntegerField(default=0, verbose_name='点击数')
    converted_count = models.IntegerField(default=0, verbose_name='转化数')
    unsubscribed_count = models.IntegerField(default=0, verbose_name='退订数')
    
    description = models.TextField(blank=True, verbose_name='描述')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'crm_marketing_campaign'
        verbose_name = '营销活动'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def open_rate(self):
        """打开率"""
        if self.delivered_count > 0:
            return round(self.opened_count / self.delivered_count * 100, 2)
        return 0
    
    @property
    def click_rate(self):
        """点击率"""
        if self.opened_count > 0:
            return round(self.clicked_count / self.opened_count * 100, 2)
        return 0
    
    @property
    def conversion_rate(self):
        """转化率"""
        if self.clicked_count > 0:
            return round(self.converted_count / self.clicked_count * 100, 2)
        return 0


class CampaignRecipient(BaseModel):
    """活动接收者"""
    STATUS_CHOICES = [
        ('PENDING', '待发送'),
        ('SENT', '已发送'),
        ('DELIVERED', '已送达'),
        ('OPENED', '已打开'),
        ('CLICKED', '已点击'),
        ('CONVERTED', '已转化'),
        ('FAILED', '发送失败'),
        ('UNSUBSCRIBED', '已退订'),
    ]
    
    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name='活动'
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.CASCADE,
        related_name='campaign_recipients',
        verbose_name='客户'
    )
    # 联系人信息直接存储（避免外键依赖问题）
    contact_name = models.CharField(max_length=100, blank=True, verbose_name='联系人姓名')
    
    email = models.EmailField(blank=True, verbose_name='邮箱')
    phone = models.CharField(max_length=50, blank=True, verbose_name='手机号')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='送达时间')
    opened_at = models.DateTimeField(null=True, blank=True, verbose_name='打开时间')
    clicked_at = models.DateTimeField(null=True, blank=True, verbose_name='点击时间')
    converted_at = models.DateTimeField(null=True, blank=True, verbose_name='转化时间')
    
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    class Meta:
        db_table = 'crm_campaign_recipient'
        verbose_name = '活动接收者'
        verbose_name_plural = verbose_name
        unique_together = ('campaign', 'customer')
    
    def __str__(self):
        return f"{self.campaign.code} - {self.customer.name}"


class EmailSendLog(BaseModel):
    """邮件发送日志"""
    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='send_logs',
        verbose_name='活动'
    )
    recipient = models.ForeignKey(
        CampaignRecipient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='send_logs',
        verbose_name='接收者'
    )
    
    to_email = models.EmailField(verbose_name='收件邮箱')
    subject = models.CharField(max_length=200, verbose_name='主题')
    
    is_success = models.BooleanField(default=False, verbose_name='是否成功')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='发送时间')
    
    class Meta:
        db_table = 'crm_email_send_log'
        verbose_name = '邮件发送日志'
        verbose_name_plural = verbose_name
        ordering = ['-sent_at']


# =====================
# Serializers
# =====================

class MarketingEmailTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    usage_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MarketingEmailTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_usage_count(self, obj):
        return obj.campaigns.count()


class MarketingCampaignSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    template_name = serializers.CharField(source='email_template.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    open_rate = serializers.FloatField(read_only=True)
    click_rate = serializers.FloatField(read_only=True)
    conversion_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        model = MarketingCampaign
        fields = '__all__'
        read_only_fields = [
            'created_by', 'updated_by', 'sent_count', 'delivered_count',
            'opened_count', 'clicked_count', 'converted_count', 'unsubscribed_count'
        ]


class CampaignRecipientSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = CampaignRecipient
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class EmailSendLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSendLog
        fields = '__all__'


# =====================
# ViewSets
# =====================

class MarketingEmailTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """营销邮件模板管理"""
    queryset = MarketingEmailTemplate.objects.filter(is_deleted=False)
    serializer_class = MarketingEmailTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template_type', 'is_active']
    search_fields = ['name', 'code', 'subject']
    
    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """预览模板"""
        template = self.get_object()
        context = request.data.get('context', {})
        
        subject, content = template.render(context)
        
        return Response({
            'subject': subject,
            'content': content
        })
    
    @action(detail=True, methods=['post'])
    def send_test(self, request, pk=None):
        """发送测试邮件"""
        template = self.get_object()
        to_email = request.data.get('to_email')
        context = request.data.get('context', {})
        
        if not to_email:
            return Response({'error': '请提供收件邮箱'}, status=400)
        
        subject, content = template.render(context)
        
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=template.content_text or content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email]
            )
            msg.attach_alternative(content, "text/html")
            msg.send()
            
            EmailSendLog.objects.create(
                to_email=to_email,
                subject=subject,
                is_success=True,
                created_by=request.user
            )
            
            return Response({'success': True, 'message': '测试邮件已发送'})
        except Exception as e:
            EmailSendLog.objects.create(
                to_email=to_email,
                subject=subject,
                is_success=False,
                error_message=str(e),
                created_by=request.user
            )
            return Response({'error': str(e)}, status=500)


class MarketingCampaignViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """营销活动管理"""
    queryset = MarketingCampaign.objects.filter(is_deleted=False)
    serializer_class = MarketingCampaignSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['channel', 'status', 'owner']
    search_fields = ['name', 'code']
    ordering_fields = ['start_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def add_recipients(self, request, pk=None):
        """添加接收者"""
        campaign = self.get_object()
        customer_ids = request.data.get('customer_ids', [])
        
        from apps.masterdata.models import Customer
        customers = Customer.objects.filter(id__in=customer_ids)
        
        created = 0
        for customer in customers:
            # 获取客户邮箱
            email = getattr(customer, 'email', '') or ''
            
            if email:
                _, is_created = CampaignRecipient.objects.get_or_create(
                    campaign=campaign,
                    customer=customer,
                    defaults={
                        'email': email,
                        'created_by': request.user
                    }
                )
                if is_created:
                    created += 1
        
        campaign.target_count = campaign.recipients.count()
        campaign.save()
        
        return Response({
            'success': True,
            'created': created,
            'total': campaign.target_count
        })
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """启动活动"""
        campaign = self.get_object()
        if campaign.status not in ['DRAFT', 'SCHEDULED', 'PAUSED']:
            return Response({'error': '当前状态无法启动'}, status=400)
        
        campaign.status = 'RUNNING'
        if not campaign.start_date:
            campaign.start_date = timezone.now()
        campaign.save()
        
        return Response(self.get_serializer(campaign).data)
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """暂停活动"""
        campaign = self.get_object()
        if campaign.status != 'RUNNING':
            return Response({'error': '只有进行中的活动可以暂停'}, status=400)
        
        campaign.status = 'PAUSED'
        campaign.save()
        
        return Response(self.get_serializer(campaign).data)
    
    @action(detail=True, methods=['post'])
    def send_emails(self, request, pk=None):
        """发送邮件"""
        campaign = self.get_object()
        if campaign.status != 'RUNNING':
            return Response({'error': '只有进行中的活动可以发送邮件'}, status=400)
        
        if not campaign.email_template:
            return Response({'error': '请先设置邮件模板'}, status=400)
        
        recipients = campaign.recipients.filter(status='PENDING')
        success_count = 0
        fail_count = 0
        
        for recipient in recipients:
            if not recipient.email:
                continue
            
            context = {
                'customer_name': recipient.customer.name,
                'contact_name': recipient.contact_name or '',
                'company_name': getattr(settings, 'COMPANY_NAME', '公司'),
            }
            
            subject, content = campaign.email_template.render(context)
            
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=campaign.email_template.content_text or content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient.email]
                )
                msg.attach_alternative(content, "text/html")
                msg.send()
                
                recipient.status = 'SENT'
                recipient.sent_at = timezone.now()
                recipient.save()
                
                EmailSendLog.objects.create(
                    campaign=campaign,
                    recipient=recipient,
                    to_email=recipient.email,
                    subject=subject,
                    is_success=True,
                    created_by=request.user
                )
                
                success_count += 1
            except Exception as e:
                recipient.status = 'FAILED'
                recipient.error_message = str(e)
                recipient.save()
                
                EmailSendLog.objects.create(
                    campaign=campaign,
                    recipient=recipient,
                    to_email=recipient.email,
                    subject=subject,
                    is_success=False,
                    error_message=str(e),
                    created_by=request.user
                )
                
                fail_count += 1
        
        # 更新统计
        campaign.sent_count = campaign.recipients.filter(status__in=['SENT', 'DELIVERED', 'OPENED', 'CLICKED', 'CONVERTED']).count()
        campaign.save()
        
        return Response({
            'success': success_count,
            'failed': fail_count,
            'total_sent': campaign.sent_count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """营销统计"""
        qs = self.get_queryset()
        
        total = qs.count()
        by_status = qs.values('status').annotate(count=Count('id'))
        by_channel = qs.values('channel').annotate(count=Count('id'))
        
        # 汇总统计
        totals = qs.aggregate(
            total_sent=Sum('sent_count'),
            total_opened=Sum('opened_count'),
            total_clicked=Sum('clicked_count'),
            total_converted=Sum('converted_count')
        )
        
        # 本月活动
        month_start = date.today().replace(day=1)
        this_month = qs.filter(created_at__date__gte=month_start).count()
        
        return Response({
            'total': total,
            'this_month': this_month,
            'by_status': list(by_status),
            'by_channel': list(by_channel),
            'totals': {
                'sent': totals['total_sent'] or 0,
                'opened': totals['total_opened'] or 0,
                'clicked': totals['total_clicked'] or 0,
                'converted': totals['total_converted'] or 0
            }
        })


class CampaignRecipientViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """活动接收者管理"""
    queryset = CampaignRecipient.objects.filter(is_deleted=False)
    serializer_class = CampaignRecipientSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['campaign', 'customer', 'status']


class EmailSendLogViewSet(viewsets.ReadOnlyModelViewSet):
    """邮件发送日志"""
    queryset = EmailSendLog.objects.all()
    serializer_class = EmailSendLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['campaign', 'is_success']
    ordering_fields = ['sent_at']
