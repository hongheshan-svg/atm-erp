"""
编码规则模型
支持自定义各种业务单据的编号规则
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from datetime import datetime


class CodeRule(BaseModel):
    """
    编码规则配置
    支持的占位符：
    - {YYYY}: 4位年份
    - {YY}: 2位年份
    - {MM}: 2位月份
    - {DD}: 2位日期
    - {SEQ}: 序列号（自动递增）
    - {PREFIX}: 前缀
    """
    
    RULE_TYPE_CHOICES = [
        ('PROJECT', '项目编号'),
        ('ITEM', '物料编码'),
        ('PURCHASE_CONTRACT', '采购合同'),
        ('SALES_CONTRACT', '销售合同'),
        ('PURCHASE_REQUEST', '采购申请'),
        ('PURCHASE_ORDER', '采购订单'),
        ('SALES_ORDER', '销售订单'),
        ('SALES_QUOTE', '销售报价'),
        ('DELIVERY_ORDER', '发货单'),
        ('INVOICE', '发票'),
        ('GOODS_RECEIPT', '收货单'),
        ('STOCK_MOVE', '库存移动'),
        ('STOCK_ADJUSTMENT', '库存调整'),
        ('BUG', 'Bug编号'),
        ('PRODUCTION_PLAN', '生产计划'),
        ('DEBUG_RECORD', '调试记录'),
        ('QUALITY_INSPECTION', '质量检验'),
    ]
    
    RESET_MODE_CHOICES = [
        ('NONE', '不重置'),
        ('YEARLY', '每年重置'),
        ('MONTHLY', '每月重置'),
        ('DAILY', '每日重置'),
    ]
    
    rule_type = models.CharField(
        max_length=50,
        choices=RULE_TYPE_CHOICES,
        unique=True,
        verbose_name='规则类型'
    )
    rule_name = models.CharField(max_length=100, verbose_name='规则名称')
    prefix = models.CharField(max_length=20, blank=True, default='', verbose_name='固定前缀')
    date_format = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='日期格式：YYYY-年，YY-年后两位，MM-月，DD-日',
        verbose_name='日期格式'
    )
    seq_length = models.IntegerField(
        default=4,
        help_text='序列号长度（不足补0）',
        verbose_name='序列号长度'
    )
    seq_start = models.IntegerField(
        default=1,
        help_text='序列号起始值',
        verbose_name='序列号起始值'
    )
    current_seq = models.IntegerField(
        default=0,
        help_text='当前序列号',
        verbose_name='当前序列号'
    )
    reset_mode = models.CharField(
        max_length=20,
        choices=RESET_MODE_CHOICES,
        default='YEARLY',
        help_text='序列号重置模式',
        verbose_name='重置模式'
    )
    separator = models.CharField(
        max_length=5,
        blank=True,
        default='',
        help_text='分隔符（如：- 或 _）',
        verbose_name='分隔符'
    )
    example = models.CharField(
        max_length=100,
        blank=True,
        editable=False,
        verbose_name='示例编码'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='说明')
    
    # 最后重置时间（用于判断是否需要重置序列号）
    last_reset_date = models.DateField(null=True, blank=True, verbose_name='最后重置日期')
    
    class Meta:
        db_table = 'code_rule'
        verbose_name = '编码规则'
        verbose_name_plural = verbose_name
        ordering = ['rule_type']
    
    def __str__(self):
        return f"{self.get_rule_type_display()} - {self.rule_name}"
    
    def save(self, *args, **kwargs):
        # 自动生成示例编码
        self.example = self.generate_example()
        super().save(*args, **kwargs)
    
    def generate_example(self):
        """生成示例编码"""
        parts = []
        
        # 前缀
        if self.prefix:
            parts.append(self.prefix)
        
        # 日期部分
        if self.date_format:
            date_str = self._format_date(datetime.now())
            if date_str:
                parts.append(date_str)
        
        # 序列号部分
        seq_str = str(self.seq_start).zfill(self.seq_length)
        parts.append(seq_str)
        
        # 使用分隔符连接
        return self.separator.join(parts) if parts else 'N/A'
    
    def _format_date(self, date):
        """格式化日期"""
        if not self.date_format:
            return ''
        
        format_str = self.date_format
        format_str = format_str.replace('YYYY', date.strftime('%Y'))
        format_str = format_str.replace('YY', date.strftime('%y'))
        format_str = format_str.replace('MM', date.strftime('%m'))
        format_str = format_str.replace('DD', date.strftime('%d'))
        return format_str
    
    def should_reset_sequence(self):
        """判断是否需要重置序列号"""
        if self.reset_mode == 'NONE':
            return False
        
        if not self.last_reset_date:
            return True
        
        today = datetime.now().date()
        
        if self.reset_mode == 'DAILY':
            return self.last_reset_date < today
        elif self.reset_mode == 'MONTHLY':
            return (self.last_reset_date.year < today.year or 
                   self.last_reset_date.month < today.month)
        elif self.reset_mode == 'YEARLY':
            return self.last_reset_date.year < today.year
        
        return False
    
    def generate_code(self):
        """
        生成下一个编码
        线程安全：使用数据库行锁
        """
        from django.db import transaction
        
        with transaction.atomic():
            # 使用行锁获取规则
            rule = CodeRule.objects.select_for_update().get(pk=self.pk)
            
            # 检查是否需要重置序列号
            if rule.should_reset_sequence():
                rule.current_seq = rule.seq_start - 1
                rule.last_reset_date = datetime.now().date()
            
            # 递增序列号
            rule.current_seq += 1
            rule.save()
            
            # 生成编码
            parts = []
            
            # 前缀
            if rule.prefix:
                parts.append(rule.prefix)
            
            # 日期部分
            if rule.date_format:
                date_str = rule._format_date(datetime.now())
                if date_str:
                    parts.append(date_str)
            
            # 序列号部分
            seq_str = str(rule.current_seq).zfill(rule.seq_length)
            parts.append(seq_str)
            
            # 使用分隔符连接
            return rule.separator.join(parts) if parts else f'CODE{rule.current_seq}'


class CodeHistory(models.Model):
    """
    编码生成历史记录
    用于追踪和调试
    """
    rule = models.ForeignKey(
        CodeRule,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='编码规则'
    )
    generated_code = models.CharField(max_length=100, verbose_name='生成的编码')
    sequence_number = models.IntegerField(verbose_name='序列号')
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='生成人'
    )
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name='生成时间')
    business_model = models.CharField(max_length=100, blank=True, verbose_name='业务模型')
    business_id = models.IntegerField(null=True, blank=True, verbose_name='业务ID')
    
    class Meta:
        db_table = 'code_history'
        verbose_name = '编码历史'
        verbose_name_plural = verbose_name
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['rule', '-generated_at']),
            models.Index(fields=['generated_code']),
        ]
    
    def __str__(self):
        return f"{self.generated_code} - {self.generated_at}"

