"""
设备台账管理模型
Equipment Ledger Management Models

用于追踪非标自动化设备的完整生命周期：
- 设备基本信息
- 出厂记录
- 现场安装记录
- 客户验收记录
- 质保信息
- 维护保养记录
"""

from django.db import models

from apps.core.models import BaseModel


class Equipment(BaseModel):
    """
    设备台账 - 已交付设备的主记录
    """

    STATUS_CHOICES = [
        ('PRODUCING', '生产中'),
        ('TESTING', '厂内调试'),
        ('READY', '待发货'),
        ('SHIPPING', '运输中'),
        ('INSTALLING', '现场安装'),
        ('COMMISSIONING', '现场调试'),
        ('ACCEPTED', '已验收'),
        ('WARRANTY', '质保期'),
        ('POST_WARRANTY', '质保后'),
        ('SCRAPPED', '已报废'),
    ]

    # 设备标识
    equipment_no = models.CharField(max_length=50, unique=True, verbose_name='设备编号')
    name = models.CharField(max_length=200, verbose_name='设备名称')
    model = models.CharField(max_length=100, blank=True, verbose_name='设备型号')
    serial_no = models.CharField(max_length=100, blank=True, verbose_name='出厂序列号')

    # 关联信息
    project = models.ForeignKey(
        'Project', on_delete=models.PROTECT, related_name='equipment_list', verbose_name='所属项目'
    )
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.PROTECT, related_name='equipment_list', verbose_name='客户'
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_list',
        verbose_name='销售订单',
    )

    # 设备规格
    specifications = models.JSONField(default=dict, blank=True, verbose_name='技术规格')
    main_components = models.TextField(blank=True, verbose_name='主要部件清单')
    software_version = models.CharField(max_length=50, blank=True, verbose_name='软件版本')
    plc_program = models.CharField(max_length=100, blank=True, verbose_name='PLC程序版本')

    # 状态和日期
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRODUCING', verbose_name='设备状态')
    production_date = models.DateField(null=True, blank=True, verbose_name='生产完成日期')
    shipping_date = models.DateField(null=True, blank=True, verbose_name='发货日期')
    installation_date = models.DateField(null=True, blank=True, verbose_name='安装完成日期')
    acceptance_date = models.DateField(null=True, blank=True, verbose_name='验收日期')

    # 质保信息
    warranty_months = models.IntegerField(default=12, verbose_name='质保期（月）')
    warranty_start_date = models.DateField(null=True, blank=True, verbose_name='质保开始日期')
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='质保结束日期')
    extended_warranty = models.BooleanField(default=False, verbose_name='延保')
    extended_warranty_months = models.IntegerField(default=0, verbose_name='延保月数')

    # 安装地点
    installation_address = models.TextField(blank=True, verbose_name='安装地址')
    installation_contact = models.CharField(max_length=50, blank=True, verbose_name='现场联系人')
    installation_phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')

    # 技术资料
    user_manual = models.FileField(upload_to='equipment/manuals/', blank=True, verbose_name='用户手册')
    electrical_diagram = models.FileField(upload_to='equipment/diagrams/', blank=True, verbose_name='电气图纸')
    mechanical_diagram = models.FileField(upload_to='equipment/diagrams/', blank=True, verbose_name='机械图纸')
    software_backup = models.FileField(upload_to='equipment/software/', blank=True, verbose_name='程序备份')

    # 备注
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'equipment'
        verbose_name = '设备台账'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.equipment_no} - {self.name}'

    def save(self, *args, **kwargs):
        # 自动生成设备编号
        if not self.equipment_no:
            from apps.core.code_rule_models import CodeRule

            self.equipment_no = CodeRule.generate_code('EQUIPMENT')

        # 计算质保结束日期
        if self.warranty_start_date and not self.warranty_end_date:
            from dateutil.relativedelta import relativedelta

            total_months = self.warranty_months + (self.extended_warranty_months if self.extended_warranty else 0)
            self.warranty_end_date = self.warranty_start_date + relativedelta(months=total_months)

        super().save(*args, **kwargs)

    @property
    def is_in_warranty(self):
        """判断是否在质保期内"""
        if not self.warranty_end_date:
            return False
        from django.utils import timezone

        return timezone.now().date() <= self.warranty_end_date


class EquipmentShipment(BaseModel):
    """
    设备发货记录
    """

    SHIPMENT_STATUS = [
        ('PREPARING', '准备中'),
        ('PACKED', '已打包'),
        ('SHIPPED', '已发货'),
        ('IN_TRANSIT', '运输中'),
        ('DELIVERED', '已送达'),
    ]

    shipment_no = models.CharField(max_length=50, unique=True, verbose_name='发货单号')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='shipments', verbose_name='设备')

    # 发货信息
    shipment_date = models.DateField(verbose_name='发货日期')
    expected_arrival = models.DateField(null=True, blank=True, verbose_name='预计到达日期')
    actual_arrival = models.DateField(null=True, blank=True, verbose_name='实际到达日期')
    status = models.CharField(max_length=20, choices=SHIPMENT_STATUS, default='PREPARING', verbose_name='发货状态')

    # 物流信息
    logistics_company = models.CharField(max_length=100, blank=True, verbose_name='物流公司')
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name='物流单号')
    logistics_contact = models.CharField(max_length=50, blank=True, verbose_name='物流联系人')
    logistics_phone = models.CharField(max_length=20, blank=True, verbose_name='物流电话')

    # 包装信息
    package_count = models.IntegerField(default=1, verbose_name='包装件数')
    package_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='总重量(kg)')
    package_volume = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name='总体积(m³)')
    package_list = models.TextField(blank=True, verbose_name='装箱清单')

    # 收货信息
    receiver_name = models.CharField(max_length=50, blank=True, verbose_name='收货人')
    receiver_phone = models.CharField(max_length=20, blank=True, verbose_name='收货电话')
    receiver_address = models.TextField(blank=True, verbose_name='收货地址')

    # 随机文件
    documents_included = models.TextField(blank=True, verbose_name='随机文件清单')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'equipment_shipment'
        verbose_name = '设备发货记录'
        verbose_name_plural = verbose_name
        ordering = ['-shipment_date']

    def __str__(self):
        return f'{self.shipment_no} - {self.equipment.name}'


class EquipmentInstallation(BaseModel):
    """
    现场安装记录
    """

    INSTALL_STATUS = [
        ('PLANNED', '计划中'),
        ('PREPARING', '准备中'),
        ('ONGOING', '安装中'),
        ('DEBUGGING', '调试中'),
        ('COMPLETED', '已完成'),
        ('PAUSED', '暂停'),
    ]

    installation_no = models.CharField(max_length=50, unique=True, verbose_name='安装单号')
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name='installations', verbose_name='设备'
    )

    # 安装计划
    planned_start = models.DateField(verbose_name='计划开始日期')
    planned_end = models.DateField(verbose_name='计划完成日期')
    actual_start = models.DateField(null=True, blank=True, verbose_name='实际开始日期')
    actual_end = models.DateField(null=True, blank=True, verbose_name='实际完成日期')
    status = models.CharField(max_length=20, choices=INSTALL_STATUS, default='PLANNED', verbose_name='安装状态')

    # 安装团队
    team_leader = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='led_installations',
        verbose_name='安装负责人',
    )
    team_members = models.ManyToManyField(
        'accounts.User', blank=True, related_name='participated_installations', verbose_name='安装团队成员'
    )

    # 安装内容
    installation_scope = models.TextField(blank=True, verbose_name='安装范围')
    installation_requirements = models.TextField(blank=True, verbose_name='安装要求')
    site_preparation = models.TextField(blank=True, verbose_name='现场准备要求')

    # 安装进度
    progress = models.IntegerField(default=0, verbose_name='安装进度%')

    # 问题记录
    issues = models.TextField(blank=True, verbose_name='问题记录')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'equipment_installation'
        verbose_name = '现场安装记录'
        verbose_name_plural = verbose_name
        ordering = ['-planned_start']

    def __str__(self):
        return f'{self.installation_no} - {self.equipment.name}'


class InstallationLog(BaseModel):
    """
    安装日志 - 每天的安装工作记录
    """

    installation = models.ForeignKey(
        EquipmentInstallation, on_delete=models.CASCADE, related_name='daily_logs', verbose_name='安装记录'
    )

    log_date = models.DateField(verbose_name='日期')
    work_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0, verbose_name='工作时长(h)')

    # 工作内容
    work_content = models.TextField(verbose_name='工作内容')
    work_result = models.TextField(blank=True, verbose_name='工作成果')

    # 问题和处理
    issues_found = models.TextField(blank=True, verbose_name='发现问题')
    solutions = models.TextField(blank=True, verbose_name='解决方案')

    # 明日计划
    next_plan = models.TextField(blank=True, verbose_name='明日计划')

    # 附件
    photos = models.JSONField(default=list, blank=True, verbose_name='现场照片')

    # 记录人
    recorded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, verbose_name='记录人')

    class Meta:
        db_table = 'installation_log'
        verbose_name = '安装日志'
        verbose_name_plural = verbose_name
        ordering = ['-log_date']
        unique_together = ['installation', 'log_date']

    def __str__(self):
        return f'{self.installation.installation_no} - {self.log_date}'


class EquipmentAcceptance(BaseModel):
    """
    设备验收记录
    """

    ACCEPTANCE_STATUS = [
        ('PENDING', '待验收'),
        ('TESTING', '测试中'),
        ('PASSED', '验收通过'),
        ('CONDITIONAL', '有条件通过'),
        ('FAILED', '验收不通过'),
    ]

    acceptance_no = models.CharField(max_length=50, unique=True, verbose_name='验收单号')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='acceptances', verbose_name='设备')

    # 验收信息
    acceptance_date = models.DateField(verbose_name='验收日期')
    status = models.CharField(max_length=20, choices=ACCEPTANCE_STATUS, default='PENDING', verbose_name='验收状态')

    # 验收人员
    our_representative = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='accepted_equipments',
        verbose_name='我方代表',
    )
    customer_representative = models.CharField(max_length=50, blank=True, verbose_name='客户代表')
    customer_signature = models.FileField(upload_to='acceptance/signatures/', blank=True, verbose_name='客户签字')

    # 验收内容
    test_items = models.JSONField(default=list, blank=True, verbose_name='测试项目')
    test_results = models.JSONField(default=list, blank=True, verbose_name='测试结果')
    performance_data = models.JSONField(default=dict, blank=True, verbose_name='性能数据')

    # 验收结论
    conclusion = models.TextField(blank=True, verbose_name='验收结论')
    issues_found = models.TextField(blank=True, verbose_name='遗留问题')
    rectification_plan = models.TextField(blank=True, verbose_name='整改计划')

    # 验收报告
    acceptance_report = models.FileField(upload_to='acceptance/reports/', blank=True, verbose_name='验收报告')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'equipment_acceptance'
        verbose_name = '设备验收记录'
        verbose_name_plural = verbose_name
        ordering = ['-acceptance_date']

    def __str__(self):
        return f'{self.acceptance_no} - {self.equipment.name}'


class MaintenanceSchedule(BaseModel):
    """
    设备保养计划
    """

    MAINTENANCE_TYPE = [
        ('DAILY', '日常保养'),
        ('WEEKLY', '周保养'),
        ('MONTHLY', '月保养'),
        ('QUARTERLY', '季度保养'),
        ('YEARLY', '年度保养'),
        ('SPECIAL', '特殊保养'),
    ]

    MAINTENANCE_STATUS = [
        ('PLANNED', '计划中'),
        ('OVERDUE', '已逾期'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='maintenance_schedules', verbose_name='设备'
    )

    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE, verbose_name='保养类型')
    scheduled_date = models.DateField(verbose_name='计划日期')
    completed_date = models.DateField(null=True, blank=True, verbose_name='完成日期')
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS, default='PLANNED', verbose_name='状态')

    # 保养内容
    maintenance_items = models.JSONField(default=list, blank=True, verbose_name='保养项目')
    maintenance_result = models.TextField(blank=True, verbose_name='保养结果')

    # 执行人
    performed_by = models.CharField(max_length=50, blank=True, verbose_name='执行人')

    # 费用
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='保养费用')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'maintenance_schedule'
        verbose_name = '设备保养计划'
        verbose_name_plural = verbose_name
        ordering = ['scheduled_date']

    def __str__(self):
        return f'{self.equipment.equipment_no} - {self.get_maintenance_type_display()} - {self.scheduled_date}'


class TrainingRecord(BaseModel):
    """
    客户培训记录
    """

    TRAINING_TYPE = [
        ('OPERATION', '操作培训'),
        ('MAINTENANCE', '保养培训'),
        ('SAFETY', '安全培训'),
        ('PROGRAMMING', '编程培训'),
        ('TROUBLESHOOTING', '故障处理培训'),
    ]

    training_no = models.CharField(max_length=50, unique=True, verbose_name='培训单号')
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name='training_records', verbose_name='设备'
    )

    # 培训信息
    training_type = models.CharField(max_length=20, choices=TRAINING_TYPE, verbose_name='培训类型')
    training_date = models.DateField(verbose_name='培训日期')
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, verbose_name='培训时长(h)')

    # 培训内容
    training_content = models.TextField(verbose_name='培训内容')
    training_materials = models.FileField(upload_to='training/materials/', blank=True, verbose_name='培训资料')

    # 培训师
    trainer = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='conducted_trainings', verbose_name='培训师'
    )

    # 受训人员
    trainees = models.JSONField(default=list, blank=True, verbose_name='受训人员')
    trainee_count = models.IntegerField(default=0, verbose_name='受训人数')

    # 培训效果
    assessment = models.TextField(blank=True, verbose_name='培训考核')
    feedback = models.TextField(blank=True, verbose_name='培训反馈')

    # 签到表
    attendance_sheet = models.FileField(upload_to='training/attendance/', blank=True, verbose_name='签到表')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'training_record'
        verbose_name = '客户培训记录'
        verbose_name_plural = verbose_name
        ordering = ['-training_date']

    def __str__(self):
        return f'{self.training_no} - {self.equipment.name}'
