"""
短信营销模块
SMS Marketing
短信模板管理、短信发送、发送日志等
支持后续集成第三方服务（阿里云短信、腾讯云短信等）
"""
from datetime import date, datetime, timedelta
from django.db import models
from django.db.models import Count, Q
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class SMSTemplate(BaseModel):
    """短信模板"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '审核中'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已拒绝'),
    ]
    
    TYPE_CHOICES = [
        ('MARKETING', '营销短信'),
        ('NOTIFICATION', '通知短信'),
        ('VERIFICATION', '验证码'),
    ]
    
    template_code = models.CharField(max_length=50, unique=True, verbose_name='模板编号')
    name = models.CharField(max_length=100, verbose_name='模板名称')
    template_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='MARKETING',
        verbose_name='模板类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    content = models.TextField(verbose_name='模板内容')
    
    # 参数信息
    params = models.JSONField(default=list, blank=True, verbose_name='模板参数')
    
    # 第三方审核信息
    external_template_id = models.CharField(max_length=100, blank=True, verbose_name='第三方模板ID')
    provider = models.CharField(max_length=50, blank=True, verbose_name='服务商')
    audit_remarks = models.TextField(blank=True, verbose_name='审核备注')
    
    # 使用统计
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    success_count = models.IntegerField(default=0, verbose_name='成功次数')
    
    description = models.TextField(blank=True, verbose_name='描述')
    
    class Meta:
        db_table = 'sales_sms_template'
        verbose_name = '短信模板'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.template_code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.template_code:
            from apps.core.utils import generate_code
            self.template_code = generate_code('SMS')
        super().save(*args, **kwargs)


class SMSCampaign(BaseModel):
    """短信营销活动"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SCHEDULED', '已排期'),
        ('SENDING', '发送中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='活动名称')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='短信模板'
    )
    
    # 发送参数
    template_params = models.JSONField(default=dict, blank=True, verbose_name='模板参数值')
    
    # 目标受众
    target_type = models.CharField(max_length=50, default='MANUAL', verbose_name='目标类型')
    target_filter = models.JSONField(default=dict, blank=True, verbose_name='目标筛选条件')
    
    # 发送计划
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='计划发送时间')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始发送时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    # 统计
    total_count = models.IntegerField(default=0, verbose_name='总数')
    sent_count = models.IntegerField(default=0, verbose_name='已发送')
    success_count = models.IntegerField(default=0, verbose_name='成功数')
    fail_count = models.IntegerField(default=0, verbose_name='失败数')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_sms_campaign'
        verbose_name = '短信营销活动'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def success_rate(self):
        if self.sent_count > 0:
            return round(self.success_count / self.sent_count * 100, 2)
        return 0


class SMSRecipient(BaseModel):
    """短信接收人"""
    STATUS_CHOICES = [
        ('PENDING', '待发送'),
        ('SENDING', '发送中'),
        ('SUCCESS', '发送成功'),
        ('FAILED', '发送失败'),
    ]
    
    campaign = models.ForeignKey(
        SMSCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name='营销活动'
    )
    
    phone = models.CharField(max_length=20, verbose_name='手机号')
    name = models.CharField(max_length=100, blank=True, verbose_name='姓名')
    
    # 关联信息
    customer_id = models.IntegerField(null=True, blank=True, verbose_name='客户ID')
    contact_id = models.IntegerField(null=True, blank=True, verbose_name='联系人ID')
    
    # 个性化参数
    params = models.JSONField(default=dict, blank=True, verbose_name='个性化参数')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 发送信息
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    external_msg_id = models.CharField(max_length=100, blank=True, verbose_name='第三方消息ID')
    
    # 结果信息
    error_code = models.CharField(max_length=50, blank=True, verbose_name='错误码')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    class Meta:
        db_table = 'sales_sms_recipient'
        verbose_name = '短信接收人'
        verbose_name_plural = verbose_name
        ordering = ['campaign', 'id']
    
    def __str__(self):
        return f"{self.campaign.name} - {self.phone}"


class SMSSendLog(BaseModel):
    """短信发送日志"""
    phone = models.CharField(max_length=20, verbose_name='手机号')
    content = models.TextField(verbose_name='短信内容')
    
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='send_logs',
        verbose_name='模板'
    )
    campaign = models.ForeignKey(
        SMSCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='send_logs',
        verbose_name='活动'
    )
    
    # 发送信息
    send_type = models.CharField(max_length=20, default='MANUAL', verbose_name='发送类型')
    sent_at = models.DateTimeField(default=timezone.now, verbose_name='发送时间')
    
    # 第三方信息
    external_msg_id = models.CharField(max_length=100, blank=True, verbose_name='第三方消息ID')
    provider = models.CharField(max_length=50, blank=True, verbose_name='服务商')
    
    # 状态
    is_success = models.BooleanField(default=False, verbose_name='是否成功')
    error_code = models.CharField(max_length=50, blank=True, verbose_name='错误码')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    # 计费
    fee_count = models.IntegerField(default=1, verbose_name='计费条数')
    
    class Meta:
        db_table = 'sales_sms_send_log'
        verbose_name = '短信发送日志'
        verbose_name_plural = verbose_name
        ordering = ['-sent_at']


# =====================
# SMS Service (模拟)
# =====================

class SMSService:
    """短信服务（模拟实现，可替换为真实服务商）"""
    
    @staticmethod
    def send_sms(phone, content, template_id=None):
        """
        发送短信
        实际使用时替换为真实服务商API
        
        Returns:
            dict: {
                'success': bool,
                'msg_id': str,
                'error_code': str,
                'error_message': str
            }
        """
        import uuid
        
        # 模拟发送（实际替换为第三方API调用）
        # 示例: 阿里云短信
        # from aliyunsdkcore.client import AcsClient
        # from aliyunsdkdysmsapi.request.v20170525 import SendSmsRequest
        
        # 模拟成功率95%
        import random
        success = random.random() > 0.05
        
        if success:
            return {
                'success': True,
                'msg_id': str(uuid.uuid4()),
                'error_code': '',
                'error_message': ''
            }
        else:
            return {
                'success': False,
                'msg_id': '',
                'error_code': 'MOCK_ERROR',
                'error_message': '模拟发送失败'
            }
    
    @staticmethod
    def query_send_status(msg_id):
        """查询发送状态"""
        # 模拟查询
        return {
            'status': 'DELIVERED',
            'receive_time': timezone.now().isoformat()
        }


# =====================
# Serializers
# =====================

class SMSTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = SMSTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'template_code', 'usage_count', 'success_count']


class SMSRecipientSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = SMSRecipient
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'status', 'sent_at', 'external_msg_id']


class SMSCampaignSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    recipients = SMSRecipientSerializer(many=True, read_only=True)
    
    class Meta:
        model = SMSCampaign
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'started_at', 'completed_at',
                           'sent_count', 'success_count', 'fail_count']


class SMSSendLogSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    
    class Meta:
        model = SMSSendLog
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================

class SMSTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """短信模板管理"""
    queryset = SMSTemplate.objects.filter(is_deleted=False)
    serializer_class = SMSTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template_type', 'status']
    search_fields = ['template_code', 'name', 'content']
    
    @action(detail=True, methods=['post'])
    def submit_audit(self, request, pk=None):
        """提交审核"""
        template = self.get_object()
        if template.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的模板'}, status=400)
        
        template.status = 'PENDING'
        template.save()
        
        # TODO: 调用第三方API提交模板审核
        
        return Response(self.get_serializer(template).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过（管理员操作）"""
        template = self.get_object()
        template.status = 'APPROVED'
        template.save()
        return Response(self.get_serializer(template).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审核拒绝"""
        template = self.get_object()
        template.status = 'REJECTED'
        template.audit_remarks = request.data.get('remarks', '')
        template.save()
        return Response(self.get_serializer(template).data)


class SMSCampaignViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """短信营销活动管理"""
    queryset = SMSCampaign.objects.filter(is_deleted=False)
    serializer_class = SMSCampaignSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'template']
    search_fields = ['name']
    
    @action(detail=True, methods=['post'])
    def add_recipients(self, request, pk=None):
        """添加接收人"""
        campaign = self.get_object()
        
        if campaign.status not in ['DRAFT']:
            return Response({'error': '只能在草稿状态添加接收人'}, status=400)
        
        recipients = request.data.get('recipients', [])
        created = []
        
        for r in recipients:
            recipient = SMSRecipient.objects.create(
                campaign=campaign,
                phone=r.get('phone'),
                name=r.get('name', ''),
                customer_id=r.get('customer_id'),
                contact_id=r.get('contact_id'),
                params=r.get('params', {}),
                created_by=request.user
            )
            created.append(recipient)
        
        campaign.total_count = campaign.recipients.count()
        campaign.save()
        
        return Response({
            'message': f'成功添加 {len(created)} 个接收人',
            'total_count': campaign.total_count
        })
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """排期发送"""
        campaign = self.get_object()
        scheduled_at = request.data.get('scheduled_at')
        
        if not scheduled_at:
            return Response({'error': '请指定发送时间'}, status=400)
        
        if campaign.total_count == 0:
            return Response({'error': '请先添加接收人'}, status=400)
        
        campaign.status = 'SCHEDULED'
        campaign.scheduled_at = scheduled_at
        campaign.save()
        
        return Response(self.get_serializer(campaign).data)
    
    @action(detail=True, methods=['post'])
    def send_now(self, request, pk=None):
        """立即发送"""
        campaign = self.get_object()
        
        if campaign.status not in ['DRAFT', 'SCHEDULED']:
            return Response({'error': '当前状态无法发送'}, status=400)
        
        if campaign.total_count == 0:
            return Response({'error': '没有接收人'}, status=400)
        
        campaign.status = 'SENDING'
        campaign.started_at = timezone.now()
        campaign.save()
        
        # 发送短信
        sms_service = SMSService()
        success = 0
        fail = 0
        
        for recipient in campaign.recipients.filter(status='PENDING'):
            # 构建短信内容
            content = campaign.template.content
            params = {**campaign.template_params, **recipient.params}
            for key, value in params.items():
                content = content.replace(f'{{{key}}}', str(value))
            
            # 发送
            result = sms_service.send_sms(recipient.phone, content)
            
            recipient.sent_at = timezone.now()
            recipient.external_msg_id = result.get('msg_id', '')
            
            if result['success']:
                recipient.status = 'SUCCESS'
                success += 1
            else:
                recipient.status = 'FAILED'
                recipient.error_code = result.get('error_code', '')
                recipient.error_message = result.get('error_message', '')
                fail += 1
            
            recipient.save()
            
            # 记录日志
            SMSSendLog.objects.create(
                phone=recipient.phone,
                content=content,
                template=campaign.template,
                campaign=campaign,
                send_type='CAMPAIGN',
                external_msg_id=result.get('msg_id', ''),
                is_success=result['success'],
                error_code=result.get('error_code', ''),
                error_message=result.get('error_message', ''),
                created_by=request.user
            )
        
        campaign.sent_count = success + fail
        campaign.success_count = success
        campaign.fail_count = fail
        campaign.status = 'COMPLETED'
        campaign.completed_at = timezone.now()
        campaign.save()
        
        # 更新模板统计
        campaign.template.usage_count += campaign.sent_count
        campaign.template.success_count += success
        campaign.template.save()
        
        return Response(self.get_serializer(campaign).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消活动"""
        campaign = self.get_object()
        
        if campaign.status in ['COMPLETED', 'SENDING']:
            return Response({'error': '无法取消已完成或正在发送的活动'}, status=400)
        
        campaign.status = 'CANCELLED'
        campaign.save()
        return Response(self.get_serializer(campaign).data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """统计数据"""
        qs = self.get_queryset()
        
        # 总数
        total_campaigns = qs.count()
        total_sent = qs.aggregate(total=models.Sum('sent_count'))['total'] or 0
        total_success = qs.aggregate(total=models.Sum('success_count'))['total'] or 0
        
        # 本月
        month_start = date.today().replace(day=1)
        this_month = qs.filter(created_at__date__gte=month_start).count()
        
        # 成功率
        success_rate = round(total_success / total_sent * 100, 2) if total_sent > 0 else 0
        
        return Response({
            'total_campaigns': total_campaigns,
            'total_sent': total_sent,
            'total_success': total_success,
            'success_rate': success_rate,
            'this_month': this_month
        })


class SMSSendLogViewSet(viewsets.ReadOnlyModelViewSet):
    """短信发送日志"""
    queryset = SMSSendLog.objects.all()
    serializer_class = SMSSendLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_success', 'template', 'campaign', 'send_type']
    search_fields = ['phone', 'content']
    ordering_fields = ['sent_at']
