"""
现场服务派工管理模块
Field Service Dispatch Management

功能：
- 技术人员技能矩阵
- 现场服务派工单
- 服务人员日程排期
- 现场打卡和日志
- 差旅费用关联
"""

from datetime import date

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# =============================================================================
# 模型定义
# =============================================================================


class SkillCategory(BaseModel):
    """技能类别"""

    code = models.CharField(max_length=50, unique=True, verbose_name='类别编码')
    name = models.CharField(max_length=100, verbose_name='类别名称')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'field_skill_category'
        verbose_name = '技能类别'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name


class Skill(BaseModel):
    """技能定义"""

    category = models.ForeignKey(
        SkillCategory, on_delete=models.CASCADE, related_name='skills', verbose_name='技能类别'
    )
    code = models.CharField(max_length=50, unique=True, verbose_name='技能编码')
    name = models.CharField(max_length=100, verbose_name='技能名称')
    description = models.TextField(blank=True, verbose_name='描述')

    # 技能等级定义
    level_definitions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='等级定义',
        help_text='[{"level": 1, "name": "初级", "description": "..."}]',
    )

    is_required_for_dispatch = models.BooleanField(default=False, verbose_name='派工必需')

    class Meta:
        db_table = 'field_skill'
        verbose_name = '技能'
        verbose_name_plural = verbose_name
        ordering = ['category', 'code']

    def __str__(self):
        return f'{self.category.name} - {self.name}'


class TechnicianSkill(BaseModel):
    """技术人员技能"""

    LEVEL_CHOICES = [
        (1, '初级'),
        (2, '中级'),
        (3, '高级'),
        (4, '专家'),
        (5, '大师'),
    ]

    technician = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='technician_skills', verbose_name='技术人员'
    )
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='technician_skills', verbose_name='技能')

    level = models.IntegerField(choices=LEVEL_CHOICES, default=1, verbose_name='技能等级')
    certified = models.BooleanField(default=False, verbose_name='已认证')
    certified_date = models.DateField(null=True, blank=True, verbose_name='认证日期')
    certificate_no = models.CharField(max_length=100, blank=True, verbose_name='证书编号')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='有效期至')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'field_technician_skill'
        verbose_name = '技术人员技能'
        verbose_name_plural = verbose_name
        unique_together = ['technician', 'skill']
        ordering = ['technician', 'skill']

    def __str__(self):
        return f'{self.technician.get_full_name()} - {self.skill.name} (L{self.level})'


class TechnicianProfile(BaseModel):
    """技术人员档案"""

    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='technician_profile', verbose_name='用户'
    )

    # 基本信息
    employee_type = models.CharField(
        max_length=20,
        choices=[
            ('INTERNAL', '内部员工'),
            ('CONTRACT', '外包人员'),
            ('PARTNER', '合作伙伴'),
        ],
        default='INTERNAL',
        verbose_name='人员类型',
    )

    # 专业领域
    specialties = models.JSONField(default=list, blank=True, verbose_name='专业领域')

    # 资质证书
    certificates = models.JSONField(default=list, blank=True, verbose_name='资质证书')

    # 可出差区域
    service_regions = models.JSONField(default=list, blank=True, verbose_name='服务区域')

    # 日费率
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='日费率')
    overtime_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='加班费率')

    # 状态
    availability_status = models.CharField(
        max_length=20,
        choices=[
            ('AVAILABLE', '可派工'),
            ('BUSY', '忙碌'),
            ('ON_LEAVE', '请假'),
            ('TRAINING', '培训中'),
            ('UNAVAILABLE', '不可用'),
        ],
        default='AVAILABLE',
        verbose_name='可用状态',
    )

    # 统计
    total_service_days = models.IntegerField(default=0, verbose_name='累计服务天数')
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, verbose_name='平均评分')

    class Meta:
        db_table = 'field_technician_profile'
        verbose_name = '技术人员档案'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.user.get_full_name()} - 技术人员'


class ServiceOrder(BaseModel):
    """现场服务派工单"""

    SERVICE_TYPE_CHOICES = [
        ('INSTALLATION', '安装'),
        ('DEBUGGING', '调试'),
        ('TRAINING', '培训'),
        ('MAINTENANCE', '维护'),
        ('REPAIR', '维修'),
        ('UPGRADE', '升级'),
        ('INSPECTION', '巡检'),
        ('ACCEPTANCE', '验收'),
        ('OTHER', '其他'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('NORMAL', '普通'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待派工'),
        ('ASSIGNED', '已派工'),
        ('CONFIRMED', '已确认'),
        ('IN_TRANSIT', '前往中'),
        ('ON_SITE', '现场中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    # 基本信息
    order_no = models.CharField(max_length=50, unique=True, verbose_name='服务单号')
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, verbose_name='服务类型')
    title = models.CharField(max_length=200, verbose_name='服务标题')
    description = models.TextField(blank=True, verbose_name='服务描述')

    # 关联信息
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.PROTECT, related_name='service_orders', verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_orders',
        verbose_name='关联项目',
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_orders',
        verbose_name='关联设备',
    )

    # 服务地点
    service_address = models.TextField(verbose_name='服务地址')
    contact_name = models.CharField(max_length=50, verbose_name='联系人')
    contact_phone = models.CharField(max_length=20, verbose_name='联系电话')
    contact_email = models.EmailField(blank=True, verbose_name='联系邮箱')

    # 服务时间
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL', verbose_name='优先级')
    requested_date = models.DateField(verbose_name='期望日期', null=True, blank=True)
    planned_start_date = models.DateField(null=True, blank=True, verbose_name='计划开始')
    planned_end_date = models.DateField(null=True, blank=True, verbose_name='计划结束')
    actual_start_date = models.DateField(null=True, blank=True, verbose_name='实际开始')
    actual_end_date = models.DateField(null=True, blank=True, verbose_name='实际结束')

    # 技能要求
    required_skills = models.ManyToManyField(Skill, blank=True, related_name='service_orders', verbose_name='所需技能')
    min_skill_level = models.IntegerField(default=1, verbose_name='最低技能等级')

    # 人员估计
    estimated_technicians = models.IntegerField(default=1, verbose_name='预计人数')
    estimated_days = models.DecimalField(max_digits=5, decimal_places=1, default=1, verbose_name='预计天数')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 费用
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='预计费用')
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='实际费用')
    is_chargeable = models.BooleanField(default=True, verbose_name='是否收费')

    # 评价
    customer_rating = models.IntegerField(null=True, blank=True, verbose_name='客户评分(1-5)')
    customer_feedback = models.TextField(blank=True, verbose_name='客户反馈')

    # 结果
    result_summary = models.TextField(blank=True, verbose_name='结果摘要')
    follow_up_needed = models.BooleanField(default=False, verbose_name='需要跟进')
    follow_up_notes = models.TextField(blank=True, verbose_name='跟进事项')

    class Meta:
        db_table = 'field_service_order'
        verbose_name = '现场服务单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_no} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.order_no:
            from apps.core.models import CodeRule

            self.order_no = CodeRule.generate_code('SERVICE')
        super().save(*args, **kwargs)


class ServiceDispatch(BaseModel):
    """服务派工记录"""

    STATUS_CHOICES = [
        ('PENDING', '待确认'),
        ('CONFIRMED', '已确认'),
        ('REJECTED', '已拒绝'),
        ('COMPLETED', '已完成'),
    ]

    service_order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name='dispatches', verbose_name='服务单'
    )

    technician = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT, related_name='service_dispatches', verbose_name='技术人员'
    )

    # 派工信息
    role = models.CharField(
        max_length=20,
        choices=[
            ('LEADER', '负责人'),
            ('MEMBER', '成员'),
            ('SUPPORT', '支持'),
        ],
        default='MEMBER',
        verbose_name='角色',
    )

    dispatch_date = models.DateField(auto_now_add=True, verbose_name='派工日期')
    planned_start = models.DateField(verbose_name='计划开始')
    planned_end = models.DateField(verbose_name='计划结束')
    actual_start = models.DateField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateField(null=True, blank=True, verbose_name='实际结束')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    reject_reason = models.CharField(max_length=500, blank=True, verbose_name='拒绝原因')

    # 工作量
    planned_days = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='计划天数')
    actual_days = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='实际天数')
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='加班小时')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'field_service_dispatch'
        verbose_name = '服务派工'
        verbose_name_plural = verbose_name
        unique_together = ['service_order', 'technician']
        ordering = ['-dispatch_date']

    def __str__(self):
        return f'{self.service_order.order_no} - {self.technician.get_full_name()}'


class ServiceCheckIn(BaseModel):
    """现场打卡记录"""

    CHECK_TYPE_CHOICES = [
        ('ARRIVAL', '到达'),
        ('DEPARTURE', '离开'),
        ('BREAK_START', '休息开始'),
        ('BREAK_END', '休息结束'),
    ]

    dispatch = models.ForeignKey(
        ServiceDispatch, on_delete=models.CASCADE, related_name='check_ins', verbose_name='派工记录'
    )

    check_type = models.CharField(max_length=20, choices=CHECK_TYPE_CHOICES, verbose_name='打卡类型')
    check_time = models.DateTimeField(verbose_name='打卡时间')

    # 位置信息
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='纬度')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='经度')
    address = models.CharField(max_length=300, blank=True, verbose_name='地址')

    # 照片
    photo = models.ImageField(upload_to='service/checkins/', blank=True, verbose_name='现场照片')

    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'field_service_checkin'
        verbose_name = '现场打卡'
        verbose_name_plural = verbose_name
        ordering = ['-check_time']

    def __str__(self):
        return f'{self.dispatch.technician.get_full_name()} - {self.get_check_type_display()}'


class ServiceLog(BaseModel):
    """服务日志"""

    dispatch = models.ForeignKey(
        ServiceDispatch, on_delete=models.CASCADE, related_name='logs', verbose_name='派工记录'
    )

    log_date = models.DateField(verbose_name='日期')
    work_hours = models.DecimalField(max_digits=4, decimal_places=1, default=8, verbose_name='工作时长')
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0, verbose_name='加班时长')

    # 工作内容
    work_content = models.TextField(verbose_name='工作内容')
    work_result = models.TextField(blank=True, verbose_name='工作成果')

    # 问题和处理
    issues_found = models.TextField(blank=True, verbose_name='发现问题')
    solutions = models.TextField(blank=True, verbose_name='解决方案')
    pending_issues = models.TextField(blank=True, verbose_name='遗留问题')

    # 明日计划
    next_plan = models.TextField(blank=True, verbose_name='明日计划')

    # 附件
    photos = models.JSONField(default=list, blank=True, verbose_name='现场照片')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    # 客户签字
    customer_signature = models.ImageField(upload_to='service/signatures/', blank=True, verbose_name='客户签字')
    customer_name = models.CharField(max_length=50, blank=True, verbose_name='签字人')

    class Meta:
        db_table = 'field_service_log'
        verbose_name = '服务日志'
        verbose_name_plural = verbose_name
        unique_together = ['dispatch', 'log_date']
        ordering = ['-log_date']

    def __str__(self):
        return f'{self.dispatch.service_order.order_no} - {self.log_date}'


class ServiceExpense(BaseModel):
    """服务费用"""

    EXPENSE_TYPE_CHOICES = [
        ('TRAVEL', '差旅费'),
        ('ACCOMMODATION', '住宿费'),
        ('MEAL', '餐费'),
        ('TRANSPORT', '交通费'),
        ('MATERIAL', '材料费'),
        ('TOOL', '工具费'),
        ('OTHER', '其他'),
    ]

    service_order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name='expenses', verbose_name='服务单'
    )
    dispatch = models.ForeignKey(
        ServiceDispatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='派工记录',
    )

    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES, verbose_name='费用类型')
    description = models.CharField(max_length=500, verbose_name='费用说明')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='金额')
    expense_date = models.DateField(verbose_name='费用日期')

    # 发票信息
    invoice_no = models.CharField(max_length=100, blank=True, verbose_name='发票号')
    invoice_image = models.ImageField(upload_to='service/invoices/', blank=True, verbose_name='发票照片')

    # 审批
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待审批'),
            ('APPROVED', '已批准'),
            ('REJECTED', '已拒绝'),
        ],
        default='PENDING',
        verbose_name='状态',
    )
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_service_expenses',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'field_service_expense'
        verbose_name = '服务费用'
        verbose_name_plural = verbose_name
        ordering = ['-expense_date']

    def __str__(self):
        return f'{self.service_order.order_no} - {self.get_expense_type_display()} ¥{self.amount}'


class TechnicianSchedule(BaseModel):
    """技术人员日程"""

    SCHEDULE_TYPE_CHOICES = [
        ('SERVICE', '现场服务'),
        ('TRAINING', '培训'),
        ('MEETING', '会议'),
        ('LEAVE', '请假'),
        ('OTHER', '其他'),
    ]

    technician = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='technician_schedules', verbose_name='技术人员'
    )

    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, verbose_name='日程类型')
    title = models.CharField(max_length=200, verbose_name='标题')

    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    all_day = models.BooleanField(default=True, verbose_name='全天')
    start_time = models.TimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.TimeField(null=True, blank=True, verbose_name='结束时间')

    # 关联
    service_order = models.ForeignKey(
        ServiceOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedules', verbose_name='服务单'
    )

    location = models.CharField(max_length=300, blank=True, verbose_name='地点')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'field_technician_schedule'
        verbose_name = '技术人员日程'
        verbose_name_plural = verbose_name
        ordering = ['start_date', 'start_time']

    def __str__(self):
        return f'{self.technician.get_full_name()} - {self.title}'


# =============================================================================
# 序列化器
# =============================================================================


class SkillCategorySerializer(serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()

    class Meta:
        model = SkillCategory
        fields = '__all__'

    def get_skills(self, obj):
        skills = obj.skills.filter(is_deleted=False)
        return SkillSerializer(skills, many=True).data


class SkillSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Skill
        fields = '__all__'


class TechnicianSkillSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_category = serializers.CharField(source='skill.category.name', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)

    class Meta:
        model = TechnicianSkill
        fields = '__all__'


class TechnicianProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    employee_type_display = serializers.CharField(source='get_employee_type_display', read_only=True)
    availability_status_display = serializers.CharField(source='get_availability_status_display', read_only=True)
    skills = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianProfile
        fields = '__all__'

    def get_skills(self, obj):
        skills = TechnicianSkill.objects.filter(technician=obj.user, is_deleted=False)
        return TechnicianSkillSerializer(skills, many=True).data


class ServiceDispatchSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ServiceDispatch
        fields = '__all__'


class ServiceCheckInSerializer(serializers.ModelSerializer):
    check_type_display = serializers.CharField(source='get_check_type_display', read_only=True)
    technician_name = serializers.CharField(source='dispatch.technician.get_full_name', read_only=True)

    class Meta:
        model = ServiceCheckIn
        fields = '__all__'


class ServiceLogSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source='dispatch.technician.get_full_name', read_only=True)
    service_order_no = serializers.CharField(source='dispatch.service_order.order_no', read_only=True)

    class Meta:
        model = ServiceLog
        fields = '__all__'


class ServiceExpenseSerializer(serializers.ModelSerializer):
    expense_type_display = serializers.CharField(source='get_expense_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    service_order_no = serializers.CharField(source='service_order.order_no', read_only=True)

    class Meta:
        model = ServiceExpense
        fields = '__all__'


class ServiceOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    dispatches = ServiceDispatchSerializer(many=True, read_only=True)
    expenses_total = serializers.SerializerMethodField()

    class Meta:
        model = ServiceOrder
        fields = '__all__'

    def get_expenses_total(self, obj):
        return obj.expenses.filter(status='APPROVED', is_deleted=False).aggregate(total=Sum('amount'))['total'] or 0


class ServiceOrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    technician_count = serializers.SerializerMethodField()

    class Meta:
        model = ServiceOrder
        fields = [
            'id',
            'order_no',
            'title',
            'service_type',
            'service_type_display',
            'customer',
            'customer_name',
            'service_address',
            'contact_name',
            'priority',
            'priority_display',
            'requested_date',
            'planned_start_date',
            'status',
            'status_display',
            'technician_count',
            'created_at',
        ]

    def get_technician_count(self, obj):
        return obj.dispatches.filter(status__in=['CONFIRMED', 'COMPLETED']).count()


class TechnicianScheduleSerializer(serializers.ModelSerializer):
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    schedule_type_display = serializers.CharField(source='get_schedule_type_display', read_only=True)
    service_order_no = serializers.CharField(source='service_order.order_no', read_only=True)

    class Meta:
        model = TechnicianSchedule
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================


class SkillCategoryViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技能类别管理"""

    permission_module = 'projects'
    permission_resource = 'skill_category'
    queryset = SkillCategory.objects.filter(is_deleted=False)
    serializer_class = SkillCategorySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['code', 'name']


class SkillViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技能管理"""

    permission_module = 'projects'
    permission_resource = 'skill'
    queryset = Skill.objects.filter(is_deleted=False)
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_required_for_dispatch']
    search_fields = ['code', 'name']


class TechnicianProfileViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术人员档案管理"""

    permission_module = 'projects'
    permission_resource = 'technician_profile'
    queryset = TechnicianProfile.objects.filter(is_deleted=False)
    serializer_class = TechnicianProfileSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['employee_type', 'availability_status']
    search_fields = ['user__first_name', 'user__last_name', 'user__username']

    @action(detail=False, methods=['get'])
    def skill_matrix(self, request):
        """技能矩阵"""
        profiles = self.get_queryset().filter(availability_status__in=['AVAILABLE', 'BUSY'])
        skills = Skill.objects.filter(is_deleted=False)

        matrix = []
        for profile in profiles:
            tech_skills = TechnicianSkill.objects.filter(technician=profile.user, is_deleted=False)
            skill_map = {ts.skill_id: ts.level for ts in tech_skills}

            row = {
                'technician_id': profile.user_id,
                'technician_name': profile.user.get_full_name(),
                'availability': profile.availability_status,
                'skills': {s.id: skill_map.get(s.id, 0) for s in skills},
            }
            matrix.append(row)

        return Response({'skills': SkillSerializer(skills, many=True).data, 'matrix': matrix})

    @action(detail=False, methods=['get'])
    def available_technicians(self, request):
        """可用技术人员"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        skill_ids = request.query_params.getlist('skill_ids')

        profiles = self.get_queryset().filter(availability_status='AVAILABLE')

        # 按技能筛选
        if skill_ids:
            profiles = profiles.filter(
                user__technician_skills__skill_id__in=skill_ids, user__technician_skills__is_deleted=False
            ).distinct()

        # 按日期排除已有安排的人员
        if start_date and end_date:
            busy_technicians = TechnicianSchedule.objects.filter(
                start_date__lte=end_date, end_date__gte=start_date, is_deleted=False
            ).values_list('technician_id', flat=True)

            profiles = profiles.exclude(user_id__in=busy_technicians)

        return Response(TechnicianProfileSerializer(profiles, many=True).data)


class TechnicianSkillViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术人员技能管理"""

    permission_module = 'projects'
    permission_resource = 'technician_skill'
    queryset = TechnicianSkill.objects.filter(is_deleted=False)
    serializer_class = TechnicianSkillSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['technician', 'skill', 'level', 'certified']


class ServiceOrderViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """现场服务单管理"""

    permission_module = 'projects'
    permission_resource = 'service_order'
    queryset = ServiceOrder.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'service_type', 'customer', 'priority']
    search_fields = ['order_no', 'title', 'customer__name']
    ordering_fields = ['created_at', 'requested_date', 'priority']

    def get_serializer_class(self):
        if self.action == 'list':
            return ServiceOrderListSerializer
        return ServiceOrderSerializer

    @action(detail=True, methods=['post'])
    def dispatch(self, request, pk=None):
        """派工"""
        order = self.get_object()
        technician_id = request.data.get('technician_id')
        role = request.data.get('role', 'MEMBER')
        planned_start = request.data.get('planned_start')
        planned_end = request.data.get('planned_end')

        if not technician_id:
            return Response({'error': '请选择技术人员'}, status=400)

        from apps.accounts.models import User

        try:
            technician = User.objects.get(id=technician_id)
        except User.DoesNotExist:
            return Response({'error': '技术人员不存在'}, status=404)

        # 创建派工记录
        dispatch, created = ServiceDispatch.objects.get_or_create(
            service_order=order,
            technician=technician,
            defaults={
                'role': role,
                'planned_start': planned_start or order.planned_start_date,
                'planned_end': planned_end or order.planned_end_date,
                'created_by': request.user,
            },
        )

        if not created:
            return Response({'error': '该技术人员已派工'}, status=400)

        # 创建日程
        TechnicianSchedule.objects.create(
            technician=technician,
            schedule_type='SERVICE',
            title=f'[服务] {order.title}',
            start_date=dispatch.planned_start,
            end_date=dispatch.planned_end,
            service_order=order,
            location=order.service_address,
            created_by=request.user,
        )

        # 更新订单状态
        if order.status == 'PENDING':
            order.status = 'ASSIGNED'
            order.save()

        return Response({'message': '派工成功', 'dispatch': ServiceDispatchSerializer(dispatch).data})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成服务"""
        order = self.get_object()

        order.status = 'COMPLETED'
        order.actual_end_date = date.today()
        order.result_summary = request.data.get('result_summary', '')
        order.follow_up_needed = request.data.get('follow_up_needed', False)
        order.follow_up_notes = request.data.get('follow_up_notes', '')

        # 计算实际费用
        order.actual_cost = (
            order.expenses.filter(status='APPROVED', is_deleted=False).aggregate(total=Sum('amount'))['total'] or 0
        )

        order.save()

        # 更新派工记录
        order.dispatches.filter(status='CONFIRMED').update(status='COMPLETED', actual_end=date.today())

        return Response(ServiceOrderSerializer(order).data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """服务看板"""
        today = date.today()

        # 各状态统计
        status_stats = self.get_queryset().values('status').annotate(count=Count('id'))

        # 本月服务
        month_start = today.replace(day=1)
        month_orders = self.get_queryset().filter(created_at__gte=month_start)

        # 紧急服务
        urgent = self.get_queryset().filter(priority='URGENT', status__in=['PENDING', 'ASSIGNED', 'CONFIRMED']).count()

        # 今日现场
        on_site_today = ServiceDispatch.objects.filter(
            planned_start__lte=today, planned_end__gte=today, status__in=['CONFIRMED', 'COMPLETED']
        ).count()

        return Response(
            {
                'status_stats': list(status_stats),
                'month_total': month_orders.count(),
                'month_completed': month_orders.filter(status='COMPLETED').count(),
                'urgent_count': urgent,
                'on_site_today': on_site_today,
            }
        )


class ServiceDispatchViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """服务派工管理"""

    permission_module = 'projects'
    permission_resource = 'service_dispatch'
    queryset = ServiceDispatch.objects.filter(is_deleted=False)
    serializer_class = ServiceDispatchSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['service_order', 'technician', 'status', 'role']

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认派工"""
        dispatch = self.get_object()
        dispatch.status = 'CONFIRMED'
        dispatch.save()

        # 更新订单状态
        order = dispatch.service_order
        if order.status == 'ASSIGNED':
            order.status = 'CONFIRMED'
            order.save()

        return Response(ServiceDispatchSerializer(dispatch).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝派工"""
        dispatch = self.get_object()
        dispatch.status = 'REJECTED'
        dispatch.reject_reason = request.data.get('reason', '')
        dispatch.save()

        # 删除日程
        TechnicianSchedule.objects.filter(technician=dispatch.technician, service_order=dispatch.service_order).delete()

        return Response(ServiceDispatchSerializer(dispatch).data)

    @action(detail=False, methods=['get'])
    def my_dispatches(self, request):
        """我的派工"""
        dispatches = self.get_queryset().filter(technician=request.user).order_by('-planned_start')

        return Response(ServiceDispatchSerializer(dispatches, many=True).data)


class ServiceCheckInViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """现场打卡管理"""

    permission_module = 'projects'
    permission_resource = 'service_check_in'
    queryset = ServiceCheckIn.objects.filter(is_deleted=False)
    serializer_class = ServiceCheckInSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dispatch', 'check_type']

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)

        # 更新派工状态
        dispatch = instance.dispatch
        if instance.check_type == 'ARRIVAL' and dispatch.actual_start is None:
            dispatch.actual_start = instance.check_time.date()
            dispatch.service_order.actual_start_date = instance.check_time.date()
            dispatch.service_order.status = 'ON_SITE'
            dispatch.service_order.save()

        dispatch.save()


class ServiceLogViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """服务日志管理"""

    permission_module = 'projects'
    permission_resource = 'service_log'
    queryset = ServiceLog.objects.filter(is_deleted=False)
    serializer_class = ServiceLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dispatch', 'log_date']


class ServiceExpenseViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """服务费用管理"""

    permission_module = 'projects'
    permission_resource = 'service_expense'
    queryset = ServiceExpense.objects.filter(is_deleted=False)
    serializer_class = ServiceExpenseSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['service_order', 'dispatch', 'expense_type', 'status']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批费用"""
        expense = self.get_object()
        expense.status = 'APPROVED'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save()

        # 更新服务单实际费用
        order = expense.service_order
        order.actual_cost = (
            order.expenses.filter(status='APPROVED', is_deleted=False).aggregate(total=Sum('amount'))['total'] or 0
        )
        order.save()

        return Response(ServiceExpenseSerializer(expense).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝费用"""
        expense = self.get_object()
        expense.status = 'REJECTED'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.remarks = request.data.get('reason', '')
        expense.save()
        return Response(ServiceExpenseSerializer(expense).data)


class TechnicianScheduleViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术人员日程管理"""

    permission_module = 'projects'
    permission_resource = 'technician_schedule'
    queryset = TechnicianSchedule.objects.filter(is_deleted=False)
    serializer_class = TechnicianScheduleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['technician', 'schedule_type', 'service_order']

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """日历视图"""
        technician_id = request.query_params.get('technician_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        queryset = self.get_queryset()

        if technician_id:
            queryset = queryset.filter(technician_id=technician_id)

        if start_date:
            queryset = queryset.filter(end_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(start_date__lte=end_date)

        return Response(TechnicianScheduleSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def my_schedule(self, request):
        """我的日程"""
        schedules = (
            self.get_queryset().filter(technician=request.user, end_date__gte=date.today()).order_by('start_date')
        )

        return Response(TechnicianScheduleSerializer(schedules, many=True).data)
