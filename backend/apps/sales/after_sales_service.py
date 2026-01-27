"""
售后服务增强模块
After Sales Service - 服务合同、预防维护、客户门户
"""
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import serializers
import secrets

from apps.core.models import BaseModel
from django.conf import settings

User = settings.AUTH_USER_MODEL


class ServiceContract(BaseModel):
    """服务合同"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('ACTIVE', '生效中'),
        ('EXPIRED', '已过期'),
        ('TERMINATED', '已终止'),
    ]
    
    CONTRACT_TYPE_CHOICES = [
        ('WARRANTY', '质保服务'),
        ('EXTENDED_WARRANTY', '延保服务'),
        ('MAINTENANCE', '维保合同'),
        ('FULL_SERVICE', '全包服务'),
        ('ON_DEMAND', '按需服务'),
    ]
    
    contract_no = models.CharField('合同编号', max_length=50, unique=True)
    customer = models.ForeignKey('masterdata.Customer', on_delete=models.CASCADE,
                                related_name='service_contracts', verbose_name='客户')
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='service_contracts', verbose_name='项目')
    
    contract_type = models.CharField('合同类型', max_length=20, choices=CONTRACT_TYPE_CHOICES)
    title = models.CharField('合同标题', max_length=200)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # 期限
    start_date = models.DateField('开始日期')
    end_date = models.DateField('结束日期')
    
    # 金额
    contract_amount = models.DecimalField('合同金额', max_digits=14, decimal_places=2, default=0)
    
    # 服务内容
    service_scope = models.TextField('服务范围')
    response_time_hours = models.IntegerField('响应时间(小时)', default=24)
    resolution_time_hours = models.IntegerField('解决时间(小时)', default=72)
    
    # 包含服务
    includes_parts = models.BooleanField('包含备件', default=False)
    includes_travel = models.BooleanField('包含差旅', default=False)
    includes_remote_support = models.BooleanField('包含远程支持', default=True)
    includes_onsite_visits = models.IntegerField('现场服务次数', default=0)
    remaining_visits = models.IntegerField('剩余服务次数', default=0)
    
    # 联系人
    contact_name = models.CharField('联系人', max_length=100, blank=True)
    contact_phone = models.CharField('联系电话', max_length=50, blank=True)
    contact_email = models.EmailField('联系邮箱', blank=True)
    
    # 设备列表
    equipment_list = models.JSONField('设备清单', default=list)
    
    class Meta:
        db_table = 'service_contract'
        verbose_name = '服务合同'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.contract_no} - {self.title}'
    
    @property
    def is_active(self):
        today = timezone.now().date()
        return self.status == 'ACTIVE' and self.start_date <= today <= self.end_date
    
    @property
    def days_until_expiry(self):
        if self.status != 'ACTIVE':
            return 0
        return (self.end_date - timezone.now().date()).days


class PreventiveMaintenance(BaseModel):
    """预防性维护计划"""
    STATUS_CHOICES = [
        ('SCHEDULED', '已计划'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
        ('OVERDUE', '已逾期'),
    ]
    
    FREQUENCY_CHOICES = [
        ('DAILY', '每日'),
        ('WEEKLY', '每周'),
        ('MONTHLY', '每月'),
        ('QUARTERLY', '每季度'),
        ('SEMI_ANNUAL', '半年'),
        ('ANNUAL', '每年'),
    ]
    
    service_contract = models.ForeignKey(ServiceContract, on_delete=models.CASCADE,
                                        related_name='pm_schedules', verbose_name='服务合同')
    
    name = models.CharField('维护名称', max_length=200)
    description = models.TextField('维护描述', blank=True)
    
    # 计划
    frequency = models.CharField('频率', max_length=20, choices=FREQUENCY_CHOICES)
    scheduled_date = models.DateField('计划日期')
    actual_date = models.DateField('实际日期', null=True, blank=True)
    
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # 维护内容
    checklist = models.JSONField('检查项清单', default=list)
    parts_required = models.JSONField('所需备件', default=list)
    
    # 执行
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='pm_assignments', verbose_name='技术人员')
    
    # 结果
    findings = models.TextField('检查发现', blank=True)
    actions_taken = models.TextField('采取措施', blank=True)
    next_action = models.TextField('后续建议', blank=True)
    
    class Meta:
        db_table = 'preventive_maintenance'
        verbose_name = '预防性维护'
        ordering = ['scheduled_date']


class ServiceRequest(BaseModel):
    """服务请求"""
    STATUS_CHOICES = [
        ('NEW', '新建'),
        ('ACKNOWLEDGED', '已确认'),
        ('ASSIGNED', '已派单'),
        ('IN_PROGRESS', '处理中'),
        ('PENDING_PARTS', '等待备件'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
    ]
    
    PRIORITY_CHOICES = [
        ('CRITICAL', '紧急'),
        ('HIGH', '高'),
        ('MEDIUM', '中'),
        ('LOW', '低'),
    ]
    
    REQUEST_TYPE_CHOICES = [
        ('BREAKDOWN', '故障报修'),
        ('CONSULTATION', '技术咨询'),
        ('MODIFICATION', '改造需求'),
        ('SPARE_PARTS', '备件需求'),
        ('TRAINING', '培训需求'),
        ('OTHER', '其他'),
    ]
    
    request_no = models.CharField('请求编号', max_length=50, unique=True)
    service_contract = models.ForeignKey(ServiceContract, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name='service_requests',
                                        verbose_name='服务合同')
    customer = models.ForeignKey('masterdata.Customer', on_delete=models.CASCADE,
                                related_name='service_requests', verbose_name='客户')
    
    request_type = models.CharField('请求类型', max_length=20, choices=REQUEST_TYPE_CHOICES)
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='NEW')
    
    # 请求内容
    subject = models.CharField('主题', max_length=200)
    description = models.TextField('详细描述')
    equipment_info = models.JSONField('设备信息', default=dict)
    
    # 联系人
    contact_name = models.CharField('联系人', max_length=100)
    contact_phone = models.CharField('联系电话', max_length=50)
    contact_email = models.EmailField('联系邮箱', blank=True)
    
    # 时间追踪
    reported_at = models.DateTimeField('报告时间', auto_now_add=True)
    acknowledged_at = models.DateTimeField('确认时间', null=True, blank=True)
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)
    closed_at = models.DateTimeField('关闭时间', null=True, blank=True)
    
    # SLA
    sla_response_deadline = models.DateTimeField('响应截止', null=True, blank=True)
    sla_resolution_deadline = models.DateTimeField('解决截止', null=True, blank=True)
    sla_breached = models.BooleanField('SLA违规', default=False)
    
    # 分配
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='assigned_service_requests', verbose_name='处理人')
    
    # 解决方案
    resolution = models.TextField('解决方案', blank=True)
    root_cause = models.TextField('根本原因', blank=True)
    
    # 评价
    satisfaction_score = models.IntegerField('满意度评分', null=True, blank=True)
    satisfaction_comment = models.TextField('评价内容', blank=True)
    
    class Meta:
        db_table = 'service_request'
        verbose_name = '服务请求'
        ordering = ['-reported_at']


class ServiceActivity(BaseModel):
    """服务活动记录"""
    ACTIVITY_TYPE_CHOICES = [
        ('PHONE_CALL', '电话沟通'),
        ('REMOTE_SESSION', '远程支持'),
        ('ONSITE_VISIT', '现场服务'),
        ('EMAIL', '邮件'),
        ('PARTS_DELIVERY', '备件发送'),
        ('OTHER', '其他'),
    ]
    
    service_request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE,
                                       related_name='activities', verbose_name='服务请求')
    
    activity_type = models.CharField('活动类型', max_length=20, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField('活动描述')
    
    # 时间
    start_time = models.DateTimeField('开始时间')
    end_time = models.DateTimeField('结束时间', null=True, blank=True)
    duration_minutes = models.IntegerField('时长(分钟)', default=0)
    
    # 执行人
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='service_activities', verbose_name='执行人')
    
    # 费用
    is_billable = models.BooleanField('可计费', default=False)
    cost = models.DecimalField('费用', max_digits=14, decimal_places=2, default=0)
    
    # 附件
    attachments = models.JSONField('附件', default=list)
    
    class Meta:
        db_table = 'service_activity'
        verbose_name = '服务活动'
        ordering = ['-start_time']


class CustomerPortalAccount(BaseModel):
    """客户门户账户"""
    customer = models.ForeignKey('masterdata.Customer', on_delete=models.CASCADE,
                                related_name='portal_accounts', verbose_name='客户')
    
    username = models.CharField('用户名', max_length=100, unique=True)
    password_hash = models.CharField('密码', max_length=255)
    email = models.EmailField('邮箱')
    name = models.CharField('姓名', max_length=100)
    mobile = models.CharField('手机', max_length=20, blank=True)
    
    is_active = models.BooleanField('是否激活', default=True)
    is_primary = models.BooleanField('主联系人', default=False)
    last_login = models.DateTimeField('最后登录', null=True, blank=True)
    
    # 权限
    can_submit_requests = models.BooleanField('提交请求', default=True)
    can_view_contracts = models.BooleanField('查看合同', default=True)
    can_view_documents = models.BooleanField('查看文档', default=True)
    can_view_equipment = models.BooleanField('查看设备', default=True)
    
    class Meta:
        db_table = 'customer_portal_account'
        verbose_name = '客户门户账户'
    
    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)
    
    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)


class KnowledgeBaseArticle(BaseModel):
    """知识库文章"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PUBLISHED', '已发布'),
        ('ARCHIVED', '已归档'),
    ]
    
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容')
    
    # 分类
    category = models.CharField('分类', max_length=100)
    tags = models.JSONField('标签', default=list)
    
    # 关联
    related_equipment = models.JSONField('相关设备', default=list)
    related_articles = models.ManyToManyField('self', blank=True, verbose_name='相关文章')
    
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # 可见性
    is_public = models.BooleanField('客户可见', default=True)
    
    # 统计
    view_count = models.IntegerField('浏览次数', default=0)
    helpful_count = models.IntegerField('有帮助次数', default=0)
    
    # 作者
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              related_name='kb_articles', verbose_name='作者')
    
    class Meta:
        db_table = 'knowledge_base_article'
        verbose_name = '知识库文章'
        ordering = ['-created_at']


# ==================== Serializers ====================

class ServiceContractSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    contract_type_display = serializers.CharField(source='get_contract_type_display', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ServiceContract
        fields = '__all__'


class PreventiveMaintenanceSerializer(serializers.ModelSerializer):
    contract_no = serializers.CharField(source='service_contract.contract_no', read_only=True)
    customer_name = serializers.CharField(source='service_contract.customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    
    class Meta:
        model = PreventiveMaintenance
        fields = '__all__'


class ServiceActivitySerializer(serializers.ModelSerializer):
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    
    class Meta:
        model = ServiceActivity
        fields = '__all__'


class ServiceRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    activities = ServiceActivitySerializer(many=True, read_only=True)
    
    class Meta:
        model = ServiceRequest
        fields = '__all__'


class CustomerPortalAccountSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = CustomerPortalAccount
        exclude = ['password_hash']


class KnowledgeBaseArticleSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = KnowledgeBaseArticle
        fields = '__all__'


# ==================== ViewSets ====================

class ServiceContractViewSet(viewsets.ModelViewSet):
    """服务合同管理"""
    queryset = ServiceContract.objects.filter(is_deleted=False)
    serializer_class = ServiceContractSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        customer = self.request.query_params.get('customer')
        status_filter = self.request.query_params.get('status')
        
        if customer:
            qs = qs.filter(customer_id=customer)
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        return qs.select_related('customer', 'project')
    
    def perform_create(self, serializer):
        today = timezone.now()
        prefix = f'SC{today.strftime("%Y%m%d")}'
        last = ServiceContract.objects.filter(contract_no__startswith=prefix).order_by('-contract_no').first()
        seq = int(last.contract_no[-4:]) + 1 if last else 1
        contract_no = f'{prefix}{seq:04d}'
        
        instance = serializer.save(contract_no=contract_no)
        instance.remaining_visits = instance.includes_onsite_visits
        instance.save()
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活合同"""
        contract = self.get_object()
        contract.status = 'ACTIVE'
        contract.save()
        return Response({'message': '合同已激活'})
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """即将到期合同"""
        days = int(request.query_params.get('days', 30))
        threshold = timezone.now().date() + timedelta(days=days)
        
        contracts = self.get_queryset().filter(
            status='ACTIVE',
            end_date__lte=threshold
        )
        
        return Response(ServiceContractSerializer(contracts, many=True).data)
    
    @action(detail=True, methods=['get'])
    def service_history(self, request, pk=None):
        """服务历史"""
        contract = self.get_object()
        requests = contract.service_requests.all().order_by('-reported_at')
        pm_records = contract.pm_schedules.filter(status='COMPLETED').order_by('-actual_date')
        
        return Response({
            'service_requests': ServiceRequestSerializer(requests, many=True).data,
            'pm_records': PreventiveMaintenanceSerializer(pm_records, many=True).data,
        })


class PreventiveMaintenanceViewSet(viewsets.ModelViewSet):
    """预防性维护管理"""
    queryset = PreventiveMaintenance.objects.filter(is_deleted=False)
    serializer_class = PreventiveMaintenanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        contract = self.request.query_params.get('contract')
        status_filter = self.request.query_params.get('status')
        
        if contract:
            qs = qs.filter(service_contract_id=contract)
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        return qs.select_related('service_contract__customer', 'technician')
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始维护"""
        pm = self.get_object()
        pm.status = 'IN_PROGRESS'
        pm.actual_date = timezone.now().date()
        pm.technician = request.user
        pm.save()
        return Response({'message': '维护已开始'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成维护"""
        pm = self.get_object()
        pm.status = 'COMPLETED'
        pm.findings = request.data.get('findings', '')
        pm.actions_taken = request.data.get('actions_taken', '')
        pm.next_action = request.data.get('next_action', '')
        pm.save()
        
        # 创建下一次计划
        if pm.frequency:
            next_date = self._calculate_next_date(pm.scheduled_date, pm.frequency)
            PreventiveMaintenance.objects.create(
                service_contract=pm.service_contract,
                name=pm.name,
                description=pm.description,
                frequency=pm.frequency,
                scheduled_date=next_date,
                checklist=pm.checklist,
                parts_required=pm.parts_required,
                created_by=request.user,
                updated_by=request.user
            )
        
        return Response({'message': '维护已完成'})
    
    def _calculate_next_date(self, current_date, frequency):
        """计算下次维护日期"""
        from dateutil.relativedelta import relativedelta
        
        freq_map = {
            'DAILY': relativedelta(days=1),
            'WEEKLY': relativedelta(weeks=1),
            'MONTHLY': relativedelta(months=1),
            'QUARTERLY': relativedelta(months=3),
            'SEMI_ANNUAL': relativedelta(months=6),
            'ANNUAL': relativedelta(years=1),
        }
        
        return current_date + freq_map.get(frequency, relativedelta(months=1))
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """即将到期的维护"""
        days = int(request.query_params.get('days', 7))
        threshold = timezone.now().date() + timedelta(days=days)
        
        pms = self.get_queryset().filter(
            status='SCHEDULED',
            scheduled_date__lte=threshold
        )
        
        return Response(PreventiveMaintenanceSerializer(pms, many=True).data)


class ServiceRequestViewSet(viewsets.ModelViewSet):
    """服务请求管理"""
    queryset = ServiceRequest.objects.filter(is_deleted=False)
    serializer_class = ServiceRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        customer = self.request.query_params.get('customer')
        status_filter = self.request.query_params.get('status')
        priority = self.request.query_params.get('priority')
        
        if customer:
            qs = qs.filter(customer_id=customer)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if priority:
            qs = qs.filter(priority=priority)
        
        return qs.select_related('customer', 'service_contract', 'assigned_to')
    
    def perform_create(self, serializer):
        today = timezone.now()
        prefix = f'SR{today.strftime("%Y%m%d")}'
        last = ServiceRequest.objects.filter(request_no__startswith=prefix).order_by('-request_no').first()
        seq = int(last.request_no[-4:]) + 1 if last else 1
        request_no = f'{prefix}{seq:04d}'
        
        instance = serializer.save(request_no=request_no)
        
        # 设置SLA
        if instance.service_contract:
            contract = instance.service_contract
            instance.sla_response_deadline = today + timedelta(hours=contract.response_time_hours)
            instance.sla_resolution_deadline = today + timedelta(hours=contract.resolution_time_hours)
            instance.save()
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """确认请求"""
        sr = self.get_object()
        sr.status = 'ACKNOWLEDGED'
        sr.acknowledged_at = timezone.now()
        sr.save()
        return Response({'message': '请求已确认'})
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分配请求"""
        sr = self.get_object()
        sr.assigned_to_id = request.data.get('user_id')
        sr.status = 'ASSIGNED'
        sr.save()
        return Response({'message': '已分配'})
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决请求"""
        sr = self.get_object()
        sr.status = 'RESOLVED'
        sr.resolved_at = timezone.now()
        sr.resolution = request.data.get('resolution', '')
        sr.root_cause = request.data.get('root_cause', '')
        sr.save()
        
        # 检查SLA
        if sr.sla_resolution_deadline and sr.resolved_at > sr.sla_resolution_deadline:
            sr.sla_breached = True
            sr.save()
        
        return Response({'message': '请求已解决'})
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭请求"""
        sr = self.get_object()
        sr.status = 'CLOSED'
        sr.closed_at = timezone.now()
        sr.satisfaction_score = request.data.get('score')
        sr.satisfaction_comment = request.data.get('comment', '')
        sr.save()
        return Response({'message': '请求已关闭'})
    
    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        """添加活动记录"""
        sr = self.get_object()
        
        activity = ServiceActivity.objects.create(
            service_request=sr,
            activity_type=request.data.get('activity_type'),
            description=request.data.get('description'),
            start_time=request.data.get('start_time'),
            end_time=request.data.get('end_time'),
            duration_minutes=request.data.get('duration_minutes', 0),
            performed_by=request.user,
            is_billable=request.data.get('is_billable', False),
            cost=request.data.get('cost', 0),
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response(ServiceActivitySerializer(activity).data)


class KnowledgeBaseArticleViewSet(viewsets.ModelViewSet):
    """知识库文章管理"""
    queryset = KnowledgeBaseArticle.objects.filter(is_deleted=False)
    serializer_class = KnowledgeBaseArticleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        tag = self.request.query_params.get('tag')
        keyword = self.request.query_params.get('keyword')
        
        if category:
            qs = qs.filter(category=category)
        if tag:
            qs = qs.filter(tags__contains=[tag])
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword) |
                Q(content__icontains=keyword)
            )
        
        return qs
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """发布文章"""
        article = self.get_object()
        article.status = 'PUBLISHED'
        article.save()
        return Response({'message': '文章已发布'})
    
    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """标记有帮助"""
        article = self.get_object()
        article.helpful_count += 1
        article.save()
        return Response({'helpful_count': article.helpful_count})
    
    @action(detail=True, methods=['post'])
    def record_view(self, request, pk=None):
        """记录浏览"""
        article = self.get_object()
        article.view_count += 1
        article.save()
        return Response({'view_count': article.view_count})


# ==================== 客户门户API ====================

class CustomerPortalLoginView(APIView):
    """客户门户登录"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        try:
            account = CustomerPortalAccount.objects.get(username=username, is_active=True)
        except CustomerPortalAccount.DoesNotExist:
            return Response({'error': '用户名或密码错误'}, status=401)
        
        if not account.check_password(password):
            return Response({'error': '用户名或密码错误'}, status=401)
        
        account.last_login = timezone.now()
        account.save()
        
        return Response({
            'token': secrets.token_urlsafe(32),
            'customer_id': account.customer_id,
            'customer_name': account.customer.name,
            'name': account.name,
        })


class CustomerPortalDashboardView(APIView):
    """客户门户首页"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, customer_id):
        # 活跃合同
        active_contracts = ServiceContract.objects.filter(
            customer_id=customer_id,
            status='ACTIVE',
            is_deleted=False
        ).count()
        
        # 未解决请求
        open_requests = ServiceRequest.objects.filter(
            customer_id=customer_id,
            status__in=['NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_PARTS'],
            is_deleted=False
        ).count()
        
        # 即将到期维护
        upcoming_pm = PreventiveMaintenance.objects.filter(
            service_contract__customer_id=customer_id,
            status='SCHEDULED',
            scheduled_date__lte=timezone.now().date() + timedelta(days=30),
            is_deleted=False
        ).count()
        
        # 最近请求
        recent_requests = ServiceRequest.objects.filter(
            customer_id=customer_id,
            is_deleted=False
        ).order_by('-reported_at')[:5]
        
        return Response({
            'active_contracts': active_contracts,
            'open_requests': open_requests,
            'upcoming_pm': upcoming_pm,
            'recent_requests': ServiceRequestSerializer(recent_requests, many=True).data,
        })


class CustomerPortalSubmitRequestView(APIView):
    """客户提交服务请求"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, customer_id):
        today = timezone.now()
        prefix = f'SR{today.strftime("%Y%m%d")}'
        last = ServiceRequest.objects.filter(request_no__startswith=prefix).order_by('-request_no').first()
        seq = int(last.request_no[-4:]) + 1 if last else 1
        request_no = f'{prefix}{seq:04d}'
        
        sr = ServiceRequest.objects.create(
            request_no=request_no,
            customer_id=customer_id,
            service_contract_id=request.data.get('contract_id'),
            request_type=request.data.get('request_type'),
            priority=request.data.get('priority', 'MEDIUM'),
            subject=request.data.get('subject'),
            description=request.data.get('description'),
            equipment_info=request.data.get('equipment_info', {}),
            contact_name=request.data.get('contact_name'),
            contact_phone=request.data.get('contact_phone'),
            contact_email=request.data.get('contact_email', ''),
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response({
            'request_no': sr.request_no,
            'message': '服务请求已提交'
        })
