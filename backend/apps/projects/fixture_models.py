"""
工装夹具管理模型
Fixture & Tooling Management Models

非标自动化行业需要管理各种工装夹具：
- 检测工装
- 装配夹具
- 焊接工装
- 测试治具
- 通用工具
"""
from django.db import models

from apps.core.models import BaseModel


class FixtureCategory(BaseModel):
    """
    工装分类
    """
    code = models.CharField(max_length=20, unique=True, verbose_name='分类编码')
    name = models.CharField(max_length=50, verbose_name='分类名称')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级分类'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'fixture_category'
        verbose_name = '工装分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Fixture(BaseModel):
    """
    工装夹具台账
    """
    STATUS_CHOICES = [
        ('IN_USE', '使用中'),
        ('IDLE', '闲置'),
        ('REPAIR', '维修中'),
        ('SCRAPED', '已报废'),
        ('LENT', '外借'),
    ]

    OWNERSHIP_CHOICES = [
        ('SELF', '自有'),
        ('CUSTOMER', '客户'),
        ('BORROWED', '借用'),
    ]

    # 基本信息
    fixture_no = models.CharField(max_length=50, unique=True, verbose_name='工装编号')
    name = models.CharField(max_length=200, verbose_name='工装名称')
    category = models.ForeignKey(
        FixtureCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixtures',
        verbose_name='工装分类'
    )
    model = models.CharField(max_length=100, blank=True, verbose_name='规格型号')

    # 关联信息
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixtures',
        verbose_name='关联项目'
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixtures',
        verbose_name='配套设备'
    )

    # 状态信息
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_USE', verbose_name='状态')
    ownership = models.CharField(max_length=20, choices=OWNERSHIP_CHOICES, default='SELF', verbose_name='所有权')

    # 存放位置
    location = models.CharField(max_length=100, blank=True, verbose_name='存放位置')
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='存放仓库'
    )

    # 责任人
    custodian = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custodial_fixtures',
        verbose_name='保管人'
    )

    # 资产信息
    purchase_date = models.DateField(null=True, blank=True, verbose_name='购置/制作日期')
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='成本价值')
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='供应商/制作方'
    )

    # 技术参数
    specifications = models.JSONField(default=dict, blank=True, verbose_name='技术规格')
    drawing_no = models.CharField(max_length=100, blank=True, verbose_name='图纸编号')
    drawing_file = models.FileField(upload_to='fixtures/drawings/', blank=True, verbose_name='图纸文件')

    # 校验信息（针对检测工装）
    needs_calibration = models.BooleanField(default=False, verbose_name='需要校验')
    calibration_cycle = models.IntegerField(default=12, verbose_name='校验周期(月)')
    last_calibration = models.DateField(null=True, blank=True, verbose_name='上次校验日期')
    next_calibration = models.DateField(null=True, blank=True, verbose_name='下次校验日期')
    calibration_org = models.CharField(max_length=100, blank=True, verbose_name='校验机构')

    # 使用次数/寿命
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    max_usage = models.IntegerField(default=0, verbose_name='最大使用次数(0=无限)')

    # 照片和备注
    photo = models.ImageField(upload_to='fixtures/photos/', blank=True, verbose_name='照片')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fixture'
        verbose_name = '工装夹具'
        verbose_name_plural = verbose_name
        ordering = ['fixture_no']

    def __str__(self):
        return f"{self.fixture_no} - {self.name}"

    def save(self, *args, **kwargs):
        # 自动生成工装编号
        if not self.fixture_no:
            from apps.core.models import CodeRule
            self.fixture_no = CodeRule.generate_code('FIXTURE')

        # 计算下次校验日期
        if self.needs_calibration and self.last_calibration and not self.next_calibration:
            from dateutil.relativedelta import relativedelta
            self.next_calibration = self.last_calibration + relativedelta(months=self.calibration_cycle)

        super().save(*args, **kwargs)

    @property
    def is_calibration_due(self):
        """判断是否需要校验"""
        if not self.needs_calibration or not self.next_calibration:
            return False
        from django.utils import timezone
        return timezone.now().date() >= self.next_calibration


class FixtureUsageRecord(BaseModel):
    """
    工装使用记录
    """
    fixture = models.ForeignKey(
        Fixture,
        on_delete=models.CASCADE,
        related_name='usage_records',
        verbose_name='工装'
    )

    # 使用信息
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixture_usages',
        verbose_name='使用项目'
    )
    used_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='fixture_usages',
        verbose_name='使用人'
    )

    # 时间
    checkout_time = models.DateTimeField(verbose_name='领用时间')
    return_time = models.DateTimeField(null=True, blank=True, verbose_name='归还时间')
    expected_return = models.DateTimeField(null=True, blank=True, verbose_name='预计归还时间')

    # 使用情况
    purpose = models.CharField(max_length=200, blank=True, verbose_name='使用用途')
    condition_before = models.CharField(max_length=50, default='良好', verbose_name='领用前状态')
    condition_after = models.CharField(max_length=50, blank=True, verbose_name='归还时状态')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fixture_usage_record'
        verbose_name = '工装使用记录'
        verbose_name_plural = verbose_name
        ordering = ['-checkout_time']

    def __str__(self):
        return f"{self.fixture.fixture_no} - {self.checkout_time.date()}"

    def save(self, *args, **kwargs):
        # 更新工装使用次数
        if not self.pk:  # 新记录
            self.fixture.usage_count += 1
            self.fixture.save(update_fields=['usage_count'])
        super().save(*args, **kwargs)


class FixtureCalibration(BaseModel):
    """
    工装校验记录
    """
    RESULT_CHOICES = [
        ('PASS', '合格'),
        ('FAIL', '不合格'),
        ('ADJUSTED', '调整后合格'),
    ]

    fixture = models.ForeignKey(
        Fixture,
        on_delete=models.CASCADE,
        related_name='calibration_records',
        verbose_name='工装'
    )

    # 校验信息
    calibration_date = models.DateField(verbose_name='校验日期')
    calibration_org = models.CharField(max_length=100, verbose_name='校验机构')
    certificate_no = models.CharField(max_length=100, blank=True, verbose_name='证书编号')

    # 校验结果
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='PASS', verbose_name='校验结果')
    deviation = models.TextField(blank=True, verbose_name='偏差说明')

    # 费用
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='校验费用')

    # 证书
    certificate_file = models.FileField(upload_to='fixtures/certificates/', blank=True, verbose_name='证书文件')

    # 有效期
    valid_until = models.DateField(verbose_name='有效期至')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fixture_calibration'
        verbose_name = '工装校验记录'
        verbose_name_plural = verbose_name
        ordering = ['-calibration_date']

    def __str__(self):
        return f"{self.fixture.fixture_no} - {self.calibration_date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # 更新工装的校验信息
        self.fixture.last_calibration = self.calibration_date
        self.fixture.next_calibration = self.valid_until
        self.fixture.calibration_org = self.calibration_org
        self.fixture.save(update_fields=['last_calibration', 'next_calibration', 'calibration_org'])


class FixtureMaintenance(BaseModel):
    """
    工装维护记录
    """
    MAINTENANCE_TYPE = [
        ('REPAIR', '维修'),
        ('OVERHAUL', '保养'),
        ('UPGRADE', '升级改造'),
        ('CLEAN', '清洁'),
    ]

    fixture = models.ForeignKey(
        Fixture,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name='工装'
    )

    # 维护信息
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE, verbose_name='维护类型')
    maintenance_date = models.DateField(verbose_name='维护日期')

    # 问题描述
    problem_description = models.TextField(blank=True, verbose_name='问题描述')
    repair_content = models.TextField(verbose_name='维护内容')

    # 更换配件
    parts_replaced = models.JSONField(default=list, blank=True, verbose_name='更换配件')

    # 费用
    parts_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='配件费用')
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='人工费用')
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='总费用')

    # 执行人
    performed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='fixture_maintenances',
        verbose_name='执行人'
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fixture_maintenance'
        verbose_name = '工装维护记录'
        verbose_name_plural = verbose_name
        ordering = ['-maintenance_date']

    def __str__(self):
        return f"{self.fixture.fixture_no} - {self.get_maintenance_type_display()} - {self.maintenance_date}"

    def save(self, *args, **kwargs):
        # 计算总费用
        self.total_cost = self.parts_cost + self.labor_cost
        super().save(*args, **kwargs)
