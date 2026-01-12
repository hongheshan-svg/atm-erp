"""
微信营销模块
WeChat Marketing
微信公众号消息、模板消息、小程序消息等
支持后续集成微信公众平台API
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


class WeChatOfficialAccount(BaseModel):
    """微信公众号配置"""
    ACCOUNT_TYPE_CHOICES = [
        ('SERVICE', '服务号'),
        ('SUBSCRIPTION', '订阅号'),
        ('MINI_PROGRAM', '小程序'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='公众号名称')
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default='SERVICE',
        verbose_name='账号类型'
    )
    
    # 配置信息
    app_id = models.CharField(max_length=100, verbose_name='AppID')
    app_secret = models.CharField(max_length=100, verbose_name='AppSecret')
    token = models.CharField(max_length=100, blank=True, verbose_name='Token')
    encoding_aes_key = models.CharField(max_length=100, blank=True, verbose_name='EncodingAESKey')
    
    # 认证信息
    is_verified = models.BooleanField(default=False, verbose_name='是否认证')
    
    # AccessToken缓存
    access_token = models.TextField(blank=True, verbose_name='AccessToken')
    token_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Token过期时间')
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'sales_wechat_official_account'
        verbose_name = '微信公众号'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return self.name


class WeChatFollower(BaseModel):
    """微信关注者"""
    account = models.ForeignKey(
        WeChatOfficialAccount,
        on_delete=models.CASCADE,
        related_name='followers',
        verbose_name='公众号'
    )
    
    openid = models.CharField(max_length=100, verbose_name='OpenID')
    unionid = models.CharField(max_length=100, blank=True, verbose_name='UnionID')
    
    # 用户信息
    nickname = models.CharField(max_length=100, blank=True, verbose_name='昵称')
    avatar = models.CharField(max_length=500, blank=True, verbose_name='头像')
    gender = models.IntegerField(default=0, verbose_name='性别')  # 0未知 1男 2女
    language = models.CharField(max_length=20, blank=True, verbose_name='语言')
    country = models.CharField(max_length=50, blank=True, verbose_name='国家')
    province = models.CharField(max_length=50, blank=True, verbose_name='省份')
    city = models.CharField(max_length=50, blank=True, verbose_name='城市')
    
    # 关注信息
    is_subscribed = models.BooleanField(default=True, verbose_name='是否关注')
    subscribe_time = models.DateTimeField(null=True, blank=True, verbose_name='关注时间')
    subscribe_scene = models.CharField(max_length=50, blank=True, verbose_name='关注场景')
    
    # 关联系统用户/客户
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wechat_followers',
        verbose_name='系统用户'
    )
    customer_id = models.IntegerField(null=True, blank=True, verbose_name='客户ID')
    
    # 标签
    tag_ids = models.JSONField(default=list, blank=True, verbose_name='微信标签ID')
    
    # 备注
    remark = models.CharField(max_length=100, blank=True, verbose_name='备注名')
    
    class Meta:
        db_table = 'sales_wechat_follower'
        verbose_name = '微信关注者'
        verbose_name_plural = verbose_name
        unique_together = ['account', 'openid']
    
    def __str__(self):
        return f"{self.nickname or self.openid}"


class WeChatTemplate(BaseModel):
    """微信消息模板"""
    STATUS_CHOICES = [
        ('ACTIVE', '已启用'),
        ('INACTIVE', '未启用'),
    ]
    
    account = models.ForeignKey(
        WeChatOfficialAccount,
        on_delete=models.CASCADE,
        related_name='templates',
        verbose_name='公众号'
    )
    
    template_id = models.CharField(max_length=100, verbose_name='模板ID')
    name = models.CharField(max_length=100, verbose_name='模板名称')
    title = models.CharField(max_length=200, verbose_name='模板标题')
    content = models.TextField(verbose_name='模板内容')
    example = models.TextField(blank=True, verbose_name='示例')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name='状态'
    )
    
    # 使用统计
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    
    class Meta:
        db_table = 'sales_wechat_template'
        verbose_name = '微信消息模板'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return self.name


class WeChatCampaign(BaseModel):
    """微信营销活动"""
    TYPE_CHOICES = [
        ('TEMPLATE', '模板消息'),
        ('MASS', '群发消息'),
        ('CUSTOM', '客服消息'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SCHEDULED', '已排期'),
        ('SENDING', '发送中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='活动名称')
    campaign_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='TEMPLATE',
        verbose_name='活动类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    account = models.ForeignKey(
        WeChatOfficialAccount,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='公众号'
    )
    
    # 消息模板（模板消息用）
    template = models.ForeignKey(
        WeChatTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
        verbose_name='消息模板'
    )
    
    # 消息内容（群发/客服消息用）
    content = models.TextField(blank=True, verbose_name='消息内容')
    
    # 目标受众
    target_type = models.CharField(max_length=50, default='ALL', verbose_name='目标类型')
    target_filter = models.JSONField(default=dict, blank=True, verbose_name='目标筛选条件')
    
    # 发送计划
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name='计划发送时间')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    # 统计
    total_count = models.IntegerField(default=0, verbose_name='目标数')
    sent_count = models.IntegerField(default=0, verbose_name='发送数')
    success_count = models.IntegerField(default=0, verbose_name='成功数')
    fail_count = models.IntegerField(default=0, verbose_name='失败数')
    read_count = models.IntegerField(default=0, verbose_name='阅读数')
    click_count = models.IntegerField(default=0, verbose_name='点击数')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_wechat_campaign'
        verbose_name = '微信营销活动'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class WeChatMessageLog(BaseModel):
    """微信消息发送日志"""
    TYPE_CHOICES = [
        ('TEMPLATE', '模板消息'),
        ('MASS', '群发消息'),
        ('CUSTOM', '客服消息'),
    ]
    
    account = models.ForeignKey(
        WeChatOfficialAccount,
        on_delete=models.CASCADE,
        related_name='message_logs',
        verbose_name='公众号'
    )
    campaign = models.ForeignKey(
        WeChatCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_logs',
        verbose_name='活动'
    )
    
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='消息类型')
    
    # 接收者
    openid = models.CharField(max_length=100, verbose_name='OpenID')
    follower = models.ForeignKey(
        WeChatFollower,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_logs',
        verbose_name='关注者'
    )
    
    # 消息内容
    template_id = models.CharField(max_length=100, blank=True, verbose_name='模板ID')
    content = models.TextField(blank=True, verbose_name='消息内容')
    data = models.JSONField(default=dict, blank=True, verbose_name='模板数据')
    url = models.CharField(max_length=500, blank=True, verbose_name='跳转链接')
    
    # 发送信息
    sent_at = models.DateTimeField(default=timezone.now, verbose_name='发送时间')
    msg_id = models.CharField(max_length=100, blank=True, verbose_name='消息ID')
    
    # 状态
    is_success = models.BooleanField(default=False, verbose_name='是否成功')
    error_code = models.CharField(max_length=50, blank=True, verbose_name='错误码')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    # 用户行为
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='阅读时间')
    is_clicked = models.BooleanField(default=False, verbose_name='是否点击')
    clicked_at = models.DateTimeField(null=True, blank=True, verbose_name='点击时间')
    
    class Meta:
        db_table = 'sales_wechat_message_log'
        verbose_name = '微信消息日志'
        verbose_name_plural = verbose_name
        ordering = ['-sent_at']


# =====================
# WeChat Service (模拟)
# =====================

class WeChatService:
    """微信服务（模拟实现）"""
    
    def __init__(self, account):
        self.account = account
    
    def get_access_token(self):
        """获取AccessToken"""
        # 检查缓存
        if self.account.access_token and self.account.token_expires_at:
            if self.account.token_expires_at > timezone.now():
                return self.account.access_token
        
        # 模拟获取新Token
        # 实际: requests.get(f'https://api.weixin.qq.com/cgi-bin/token?...')
        import uuid
        new_token = str(uuid.uuid4())
        
        self.account.access_token = new_token
        self.account.token_expires_at = timezone.now() + timedelta(hours=2)
        self.account.save()
        
        return new_token
    
    def send_template_message(self, openid, template_id, data, url=''):
        """发送模板消息"""
        # 模拟发送
        import random
        success = random.random() > 0.05
        
        if success:
            import uuid
            return {
                'success': True,
                'msg_id': str(uuid.uuid4()),
                'error_code': 0,
                'error_message': ''
            }
        else:
            return {
                'success': False,
                'msg_id': '',
                'error_code': 40003,
                'error_message': '模拟发送失败'
            }
    
    def sync_followers(self):
        """同步关注者列表"""
        # 模拟同步
        return {'count': 0}


# =====================
# Serializers
# =====================

class WeChatOfficialAccountSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    follower_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WeChatOfficialAccount
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'access_token', 'token_expires_at']
        extra_kwargs = {
            'app_secret': {'write_only': True},
        }
    
    def get_follower_count(self, obj):
        return obj.followers.filter(is_subscribed=True).count()


class WeChatFollowerSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    
    class Meta:
        model = WeChatFollower
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class WeChatTemplateSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WeChatTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'usage_count']


class WeChatCampaignSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    
    class Meta:
        model = WeChatCampaign
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'started_at', 'completed_at',
                           'sent_count', 'success_count', 'fail_count', 'read_count', 'click_count']


class WeChatMessageLogSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    follower_name = serializers.CharField(source='follower.nickname', read_only=True)
    
    class Meta:
        model = WeChatMessageLog
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================

class WeChatOfficialAccountViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """微信公众号管理"""
    queryset = WeChatOfficialAccount.objects.filter(is_deleted=False)
    serializer_class = WeChatOfficialAccountSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account_type', 'is_active', 'is_verified']
    search_fields = ['name']
    
    @action(detail=True, methods=['post'])
    def refresh_token(self, request, pk=None):
        """刷新AccessToken"""
        account = self.get_object()
        service = WeChatService(account)
        token = service.get_access_token()
        return Response({'access_token': token[:10] + '...'})
    
    @action(detail=True, methods=['post'])
    def sync_followers(self, request, pk=None):
        """同步关注者"""
        account = self.get_object()
        service = WeChatService(account)
        result = service.sync_followers()
        return Response(result)


class WeChatFollowerViewSet(viewsets.ModelViewSet):
    """微信关注者管理"""
    queryset = WeChatFollower.objects.filter(is_deleted=False)
    serializer_class = WeChatFollowerSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account', 'is_subscribed']
    search_fields = ['openid', 'nickname', 'remark']
    
    @action(detail=True, methods=['post'])
    def bind_customer(self, request, pk=None):
        """绑定客户"""
        follower = self.get_object()
        customer_id = request.data.get('customer_id')
        follower.customer_id = customer_id
        follower.save()
        return Response(self.get_serializer(follower).data)


class WeChatTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """微信消息模板管理"""
    queryset = WeChatTemplate.objects.filter(is_deleted=False)
    serializer_class = WeChatTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account', 'status']
    search_fields = ['name', 'title']


class WeChatCampaignViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """微信营销活动管理"""
    queryset = WeChatCampaign.objects.filter(is_deleted=False)
    serializer_class = WeChatCampaignSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account', 'campaign_type', 'status']
    search_fields = ['name']
    
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """发送营销消息"""
        campaign = self.get_object()
        
        if campaign.status not in ['DRAFT', 'SCHEDULED']:
            return Response({'error': '当前状态无法发送'}, status=400)
        
        campaign.status = 'SENDING'
        campaign.started_at = timezone.now()
        campaign.save()
        
        # 获取目标用户
        followers = campaign.account.followers.filter(is_subscribed=True)
        if campaign.target_filter:
            # 应用筛选条件
            pass
        
        service = WeChatService(campaign.account)
        success = 0
        fail = 0
        
        for follower in followers[:100]:  # 限制数量
            if campaign.campaign_type == 'TEMPLATE' and campaign.template:
                result = service.send_template_message(
                    follower.openid,
                    campaign.template.template_id,
                    {}  # 模板数据
                )
            else:
                result = {'success': True, 'msg_id': ''}
            
            # 记录日志
            WeChatMessageLog.objects.create(
                account=campaign.account,
                campaign=campaign,
                message_type=campaign.campaign_type,
                openid=follower.openid,
                follower=follower,
                template_id=campaign.template.template_id if campaign.template else '',
                content=campaign.content,
                msg_id=result.get('msg_id', ''),
                is_success=result['success'],
                error_code=str(result.get('error_code', '')),
                error_message=result.get('error_message', ''),
                created_by=request.user
            )
            
            if result['success']:
                success += 1
            else:
                fail += 1
        
        campaign.sent_count = success + fail
        campaign.success_count = success
        campaign.fail_count = fail
        campaign.status = 'COMPLETED'
        campaign.completed_at = timezone.now()
        campaign.save()
        
        return Response(self.get_serializer(campaign).data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """统计数据"""
        qs = self.get_queryset()
        
        return Response({
            'total_campaigns': qs.count(),
            'total_sent': qs.aggregate(total=models.Sum('sent_count'))['total'] or 0,
            'total_success': qs.aggregate(total=models.Sum('success_count'))['total'] or 0,
            'total_read': qs.aggregate(total=models.Sum('read_count'))['total'] or 0,
            'total_click': qs.aggregate(total=models.Sum('click_count'))['total'] or 0,
        })


class WeChatMessageLogViewSet(viewsets.ReadOnlyModelViewSet):
    """微信消息日志"""
    queryset = WeChatMessageLog.objects.all()
    serializer_class = WeChatMessageLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account', 'campaign', 'message_type', 'is_success']
    search_fields = ['openid']
    ordering_fields = ['sent_at']
