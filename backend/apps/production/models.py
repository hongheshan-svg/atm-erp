"""
生产管理模块模型
用于非标自动化设备的生产过程管理
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class ProductionProcess(BaseModel):
    """
    生产工序模型 - 定义项目/产品的生产工序流程
    """
    PROCESS_TYPE_CHOICES = [
        ('MACHINING', '机加工'),
        ('WELDING', '焊接'),
        ('ASSEMBLY', '装配'),
        ('WIRING', '布线'),
        ('PROGRAMMING', '编程调试'),
        ('TESTING', '测试'),
        ('PAINTING', '喷涂'),
        ('PACKAGING', '包装'),
        ('OTHER', '其他'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='production_processes',
        verbose_name='所属项目'
    )
    process_no = models.CharField(max_length=50, verbose_name='工序编号')
    name = models.CharField(max_length=200, verbose_name='工序名称')
    process_type = models.CharField(
        max_length=20,
        choices=PROCESS_TYPE_CHOICES,
        default='ASSEMBLY',
        verbose_name='工序类型'
    )
    sequence = models.IntegerField(default=1, verbose_name='工序顺序')
    
    # 工时信息
    planned_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='计划工时(小时)'
    )
    actual_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='实际工时(小时)'
    )
    
    # 负责人
    assignee = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_processes',
        verbose_name='负责人'
    )
    
    # 工作中心（工位/设备）
    work_center = models.CharField(max_length=100, blank=True, verbose_name='工作中心')
    
    # 工序说明
    description = models.TextField(blank=True, verbose_name='工序说明')
    work_instruction = models.TextField(blank=True, verbose_name='作业指导书')
    quality_requirements = models.TextField(blank=True, verbose_name='质量要求')
    
    # 所需物料（外键到ProjectBOM）
    bom_items = models.ManyToManyField(
        'projects.ProjectBOM',
        blank=True,
        related_name='processes',
        verbose_name='所需物料'
    )
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_process'
        verbose_name = '生产工序'
        verbose_name_plural = verbose_name
        ordering = ['project', 'sequence']
        unique_together = [['project', 'process_no']]
    
    def __str__(self):
        return f"{self.project.code} - {self.process_no} - {self.name}"


class ProductionPlan(BaseModel):
    """
    生产计划模型 - 项目级别的生产排程
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('IN_PROGRESS', '生产中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='production_plans',
        verbose_name='所属项目'
    )
    plan_no = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    title = models.CharField(max_length=200, verbose_name='计划名称')
    
    # 时间安排
    planned_start = models.DateField(verbose_name='计划开始日期')
    planned_end = models.DateField(verbose_name='计划完成日期')
    actual_start = models.DateField(null=True, blank=True, verbose_name='实际开始日期')
    actual_end = models.DateField(null=True, blank=True, verbose_name='实际完成日期')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 进度
    progress_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='完成进度(%)'
    )
    
    # 责任人
    planner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planned_productions',
        verbose_name='计划员'
    )
    production_manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_productions',
        verbose_name='生产负责人'
    )
    
    # 说明
    description = models.TextField(blank=True, verbose_name='计划说明')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_plan'
        verbose_name = '生产计划'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.plan_no} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.plan_no:
            from apps.core.utils import generate_code
            self.plan_no = generate_code('PP', rule_type='PRODUCTION_PLAN')
        super().save(*args, **kwargs)


class ProductionPlanProcess(BaseModel):
    """
    生产计划工序 - 计划中每个工序的详细安排
    """
    STATUS_CHOICES = [
        ('PENDING', '待开始'),
        ('IN_PROGRESS', '进行中'),
        ('PAUSED', '暂停'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    plan = models.ForeignKey(
        ProductionPlan,
        on_delete=models.CASCADE,
        related_name='plan_processes',
        verbose_name='生产计划'
    )
    process = models.ForeignKey(
        ProductionProcess,
        on_delete=models.CASCADE,
        related_name='plan_processes',
        verbose_name='工序'
    )
    
    # 时间安排
    planned_start = models.DateTimeField(verbose_name='计划开始时间')
    planned_end = models.DateTimeField(verbose_name='计划结束时间')
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始时间')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束时间')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 进度
    progress_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='完成进度(%)'
    )
    
    # 工时
    planned_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='计划工时'
    )
    actual_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='实际工时'
    )
    
    # 负责人
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operated_processes',
        verbose_name='操作员'
    )
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_plan_process'
        verbose_name = '生产计划工序'
        verbose_name_plural = verbose_name
        ordering = ['plan', 'process__sequence']
    
    def __str__(self):
        return f"{self.plan.plan_no} - {self.process.name}"


class ProductionLog(BaseModel):
    """
    生产日志 - 记录每日生产情况
    """
    plan_process = models.ForeignKey(
        ProductionPlanProcess,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='计划工序'
    )
    log_date = models.DateField(verbose_name='日期')
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='production_logs',
        verbose_name='操作员'
    )
    
    # 工时
    work_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='工时(小时)'
    )
    
    # 内容
    work_content = models.TextField(verbose_name='工作内容')
    progress_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='完成进度(%)'
    )
    
    # 问题记录
    issues = models.TextField(blank=True, verbose_name='问题记录')
    solutions = models.TextField(blank=True, verbose_name='解决措施')
    
    class Meta:
        db_table = 'production_log'
        verbose_name = '生产日志'
        verbose_name_plural = verbose_name
        ordering = ['-log_date', '-created_at']
    
    def __str__(self):
        return f"{self.plan_process.plan.plan_no} - {self.log_date}"


class DebugRecord(BaseModel):
    """
    调试记录 - 非标自动化设备的调试过程记录
    """
    STATUS_CHOICES = [
        ('PENDING', '待调试'),
        ('IN_PROGRESS', '调试中'),
        ('DEBUGGING', '问题处理中'),
        ('COMPLETED', '调试完成'),
        ('FAILED', '调试失败'),
    ]
    
    RESULT_CHOICES = [
        ('PASS', '通过'),
        ('FAIL', '不通过'),
        ('CONDITIONAL', '有条件通过'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='debug_records',
        verbose_name='所属项目'
    )
    record_no = models.CharField(max_length=50, unique=True, verbose_name='调试单号')
    title = models.CharField(max_length=200, verbose_name='调试项目')
    
    # 调试类型
    DEBUG_TYPE_CHOICES = [
        ('MECHANICAL', '机械调试'),
        ('ELECTRICAL', '电气调试'),
        ('PNEUMATIC', '气动调试'),
        ('PLC', 'PLC程序调试'),
        ('HMI', '人机界面调试'),
        ('VISION', '视觉系统调试'),
        ('ROBOT', '机器人调试'),
        ('MOTION', '运动控制调试'),
        ('INTEGRATION', '整机联调'),
        ('FAT', '出厂验收'),
        ('SAT', '现场验收'),
        ('OTHER', '其他'),
    ]
    debug_type = models.CharField(
        max_length=20,
        choices=DEBUG_TYPE_CHOICES,
        default='INTEGRATION',
        verbose_name='调试类型'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        blank=True,
        verbose_name='调试结果'
    )
    
    # 时间
    planned_date = models.DateField(null=True, blank=True, verbose_name='计划日期')
    debug_date = models.DateField(null=True, blank=True, verbose_name='调试日期')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    # 人员
    debugger = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='debug_records',
        verbose_name='调试人员'
    )
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_debug_records',
        verbose_name='审核人'
    )
    
    # 内容
    debug_content = models.TextField(verbose_name='调试内容')
    test_conditions = models.TextField(blank=True, verbose_name='测试条件')
    expected_result = models.TextField(blank=True, verbose_name='预期结果')
    actual_result = models.TextField(blank=True, verbose_name='实际结果')
    
    # 问题和解决
    issues_found = models.TextField(blank=True, verbose_name='发现问题')
    solutions = models.TextField(blank=True, verbose_name='解决措施')
    remaining_issues = models.TextField(blank=True, verbose_name='遗留问题')
    
    # 附件路径（多个用逗号分隔）
    attachments = models.TextField(blank=True, verbose_name='附件路径')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_debug_record'
        verbose_name = '调试记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.record_no} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.record_no:
            from apps.core.utils import generate_code
            self.record_no = generate_code('DBG', rule_type='DEBUG_RECORD')
        super().save(*args, **kwargs)


class DebugCheckItem(BaseModel):
    """
    调试检查项 - 调试过程中的具体检查点
    """
    RESULT_CHOICES = [
        ('PASS', '通过'),
        ('FAIL', '不通过'),
        ('NA', '不适用'),
        ('PENDING', '待检查'),
    ]
    
    debug_record = models.ForeignKey(
        DebugRecord,
        on_delete=models.CASCADE,
        related_name='check_items',
        verbose_name='调试记录'
    )
    sequence = models.IntegerField(default=1, verbose_name='序号')
    item_name = models.CharField(max_length=200, verbose_name='检查项')
    standard = models.TextField(blank=True, verbose_name='标准/要求')
    method = models.TextField(blank=True, verbose_name='检查方法')
    
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='PENDING',
        verbose_name='结果'
    )
    actual_value = models.CharField(max_length=200, blank=True, verbose_name='实测值')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_debug_check_item'
        verbose_name = '调试检查项'
        verbose_name_plural = verbose_name
        ordering = ['debug_record', 'sequence']
    
    def __str__(self):
        return f"{self.debug_record.record_no} - {self.item_name}"


class QualityInspection(BaseModel):
    """
    质量检验记录 - 生产过程中的质量检验
    """
    INSPECTION_TYPE_CHOICES = [
        ('INCOMING', '来料检验'),
        ('FIRST_PIECE', '首件检验'),
        ('PROCESS', '过程检验'),
        ('FINAL', '成品检验'),
        ('OUTGOING', '出货检验'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待检验'),
        ('IN_PROGRESS', '检验中'),
        ('COMPLETED', '已完成'),
    ]
    
    RESULT_CHOICES = [
        ('PASS', '合格'),
        ('FAIL', '不合格'),
        ('CONDITIONAL', '让步接收'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='quality_inspections',
        verbose_name='所属项目'
    )
    inspection_no = models.CharField(max_length=50, unique=True, verbose_name='检验单号')
    inspection_type = models.CharField(
        max_length=20,
        choices=INSPECTION_TYPE_CHOICES,
        default='PROCESS',
        verbose_name='检验类型'
    )
    title = models.CharField(max_length=200, verbose_name='检验名称')
    
    # 关联对象
    production_plan = models.ForeignKey(
        ProductionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspections',
        verbose_name='生产计划'
    )
    process = models.ForeignKey(
        ProductionProcess,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspections',
        verbose_name='工序'
    )
    goods_receipt = models.ForeignKey(
        'purchase.GoodsReceipt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quality_inspections',
        verbose_name='收货单'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        blank=True,
        verbose_name='检验结果'
    )
    
    # 时间
    planned_date = models.DateField(null=True, blank=True, verbose_name='计划检验日期')
    inspection_date = models.DateField(null=True, blank=True, verbose_name='检验日期')
    
    # 人员
    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='production_inspections',
        verbose_name='检验员'
    )
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_inspections',
        verbose_name='审核人'
    )
    
    # 检验依据
    inspection_standard = models.TextField(blank=True, verbose_name='检验依据/标准')
    sampling_method = models.CharField(max_length=200, blank=True, verbose_name='抽样方法')
    sample_qty = models.IntegerField(default=1, verbose_name='检验数量')
    pass_qty = models.IntegerField(default=0, verbose_name='合格数量')
    fail_qty = models.IntegerField(default=0, verbose_name='不合格数量')
    
    # 结论
    conclusion = models.TextField(blank=True, verbose_name='检验结论')
    treatment = models.TextField(blank=True, verbose_name='处理意见')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_quality_inspection'
        verbose_name = '质量检验'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.inspection_no} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.inspection_no:
            from apps.core.utils import generate_code
            self.inspection_no = generate_code('QI', rule_type='QUALITY_INSPECTION')
        super().save(*args, **kwargs)


class InspectionItem(BaseModel):
    """
    检验项目 - 质量检验的具体检查项
    """
    RESULT_CHOICES = [
        ('PASS', '合格'),
        ('FAIL', '不合格'),
        ('NA', '不适用'),
        ('PENDING', '待检'),
    ]
    
    inspection = models.ForeignKey(
        QualityInspection,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='检验记录'
    )
    sequence = models.IntegerField(default=1, verbose_name='序号')
    item_name = models.CharField(max_length=200, verbose_name='检验项目')
    standard = models.TextField(blank=True, verbose_name='标准要求')
    method = models.CharField(max_length=200, blank=True, verbose_name='检验方法')
    
    # 测量值
    nominal_value = models.CharField(max_length=100, blank=True, verbose_name='标准值')
    tolerance_upper = models.CharField(max_length=50, blank=True, verbose_name='上公差')
    tolerance_lower = models.CharField(max_length=50, blank=True, verbose_name='下公差')
    actual_value = models.CharField(max_length=100, blank=True, verbose_name='实测值')
    
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='PENDING',
        verbose_name='结果'
    )
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_inspection_item'
        verbose_name = '检验项目'
        verbose_name_plural = verbose_name
        ordering = ['inspection', 'sequence']
    
    def __str__(self):
        return f"{self.inspection.inspection_no} - {self.item_name}"

