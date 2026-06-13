"""
供应商评价管理模型
Supplier Evaluation Management Models
"""

from django.db import models

from apps.accounts.models import User
from apps.core.models import BaseModel
from apps.masterdata.models import Supplier


class SupplierEvaluationTemplate(BaseModel):
    """
    供应商评价模板
    """

    name = models.CharField(max_length=100, verbose_name='模板名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    description = models.TextField(blank=True, verbose_name='描述')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        verbose_name = '评价模板'
        verbose_name_plural = '评价模板'
        db_table = 'supplier_evaluation_template'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name


class EvaluationCriteria(BaseModel):
    """
    评价标准/指标
    """

    CATEGORY_CHOICES = [
        ('QUALITY', '质量'),
        ('DELIVERY', '交期'),
        ('PRICE', '价格'),
        ('SERVICE', '服务'),
        ('TECH', '技术能力'),
        ('COOPERATION', '配合度'),
    ]

    template = models.ForeignKey(
        SupplierEvaluationTemplate, on_delete=models.CASCADE, related_name='criteria', verbose_name='评价模板'
    )
    name = models.CharField(max_length=100, verbose_name='指标名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='指标类别')
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name='权重')
    max_score = models.IntegerField(default=100, verbose_name='最高分')
    description = models.TextField(blank=True, verbose_name='评分说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        verbose_name = '评价指标'
        verbose_name_plural = '评价指标'
        db_table = 'evaluation_criteria'
        ordering = ['template', 'sort_order']

    def __str__(self):
        return f'{self.template.name} - {self.name}'


class SupplierEvaluation(BaseModel):
    """
    供应商评价记录
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('APPROVED', '已审批'),
        ('REJECTED', '已驳回'),
    ]

    PERIOD_CHOICES = [
        ('MONTHLY', '月度'),
        ('QUARTERLY', '季度'),
        ('YEARLY', '年度'),
        ('PROJECT', '项目'),
        ('DELIVERY', '到货'),
    ]

    evaluation_no = models.CharField(max_length=50, unique=True, verbose_name='评价编号')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='evaluations', verbose_name='供应商')
    template = models.ForeignKey(
        SupplierEvaluationTemplate, on_delete=models.PROTECT, related_name='evaluations', verbose_name='评价模板'
    )
    period_type = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='QUARTERLY', verbose_name='评价周期')
    evaluation_date = models.DateField(verbose_name='评价日期')
    period_start = models.DateField(verbose_name='评价期间开始')
    period_end = models.DateField(verbose_name='评价期间结束')

    # 评分汇总
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='总分')
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='质量得分')
    delivery_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='交期得分')
    price_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='价格得分')
    service_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='服务得分')

    # 评价等级
    grade = models.CharField(max_length=10, blank=True, verbose_name='评价等级')

    evaluator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_evaluations',
        verbose_name='评价人',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    comments = models.TextField(blank=True, verbose_name='综合评价')
    improvement_suggestions = models.TextField(blank=True, verbose_name='改进建议')

    # 审批信息
    approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_evaluations',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    approval_comments = models.TextField(blank=True, verbose_name='审批意见')

    class Meta:
        verbose_name = '供应商评价'
        verbose_name_plural = '供应商评价'
        db_table = 'supplier_evaluation'
        ordering = ['-evaluation_date']

    def __str__(self):
        return f'{self.evaluation_no} - {self.supplier.name}'

    def save(self, *args, **kwargs):
        if not self.evaluation_no:
            from apps.core.utils import generate_code

            self.evaluation_no = generate_code('SE', rule_type='SUPPLIER_EVALUATION')
        super().save(*args, **kwargs)

    def calculate_scores(self):
        """计算评分"""
        scores = self.score_items.all()
        if not scores:
            return

        category_scores = {}
        category_weights = {}

        for item in scores:
            category = item.criteria.category
            weighted_score = float(item.score) * float(item.criteria.weight)

            if category not in category_scores:
                category_scores[category] = 0
                category_weights[category] = 0

            category_scores[category] += weighted_score
            category_weights[category] += float(item.criteria.weight)

        # 计算各类别平均分
        for category, total in category_scores.items():
            if category_weights[category] > 0:
                avg = total / category_weights[category]
                if category == 'QUALITY':
                    self.quality_score = avg
                elif category == 'DELIVERY':
                    self.delivery_score = avg
                elif category == 'PRICE':
                    self.price_score = avg
                elif category == 'SERVICE':
                    self.service_score = avg

        # 计算总分
        total_weighted = sum(category_scores.values())
        total_weight = sum(category_weights.values())
        if total_weight > 0:
            self.total_score = total_weighted / total_weight

        # 计算等级
        self.grade = self._calculate_grade(self.total_score)
        self.save()

    def _calculate_grade(self, score):
        """根据分数计算等级"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'E'


class EvaluationScoreItem(BaseModel):
    """
    评价得分明细
    """

    evaluation = models.ForeignKey(
        SupplierEvaluation, on_delete=models.CASCADE, related_name='score_items', verbose_name='评价记录'
    )
    criteria = models.ForeignKey(
        EvaluationCriteria, on_delete=models.PROTECT, related_name='score_items', verbose_name='评价指标'
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='得分')
    comments = models.TextField(blank=True, verbose_name='评价说明')

    class Meta:
        verbose_name = '评价得分明细'
        verbose_name_plural = '评价得分明细'
        db_table = 'evaluation_score_item'
        unique_together = ['evaluation', 'criteria']

    def __str__(self):
        return f'{self.evaluation.evaluation_no} - {self.criteria.name}: {self.score}'


class SupplierGradeHistory(BaseModel):
    """
    供应商等级变更历史
    """

    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='grade_history', verbose_name='供应商'
    )
    evaluation = models.ForeignKey(
        SupplierEvaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grade_changes',
        verbose_name='关联评价',
    )
    old_grade = models.CharField(max_length=10, blank=True, verbose_name='原等级')
    new_grade = models.CharField(max_length=10, verbose_name='新等级')
    change_date = models.DateField(verbose_name='变更日期')
    reason = models.TextField(blank=True, verbose_name='变更原因')

    class Meta:
        verbose_name = '供应商等级变更历史'
        verbose_name_plural = '供应商等级变更历史'
        db_table = 'supplier_grade_history'
        ordering = ['-change_date']

    def __str__(self):
        return f'{self.supplier.name}: {self.old_grade} -> {self.new_grade}'


class SupplierBlacklist(BaseModel):
    """
    供应商黑名单
    """

    STATUS_CHOICES = [
        ('ACTIVE', '有效'),
        ('LIFTED', '已解除'),
    ]

    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='blacklist_records', verbose_name='供应商'
    )
    blacklist_date = models.DateField(verbose_name='加入日期')
    reason = models.TextField(verbose_name='加入原因')
    related_evaluation = models.ForeignKey(
        SupplierEvaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blacklist_records',
        verbose_name='关联评价',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', verbose_name='状态')
    lifted_date = models.DateField(null=True, blank=True, verbose_name='解除日期')
    lifted_reason = models.TextField(blank=True, verbose_name='解除原因')
    lifted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lifted_blacklists', verbose_name='解除人'
    )

    class Meta:
        verbose_name = '供应商黑名单'
        verbose_name_plural = '供应商黑名单'
        db_table = 'supplier_blacklist'
        ordering = ['-blacklist_date']

    def __str__(self):
        return f'{self.supplier.name} - {self.get_status_display()}'

    @classmethod
    def is_blacklisted(cls, supplier):
        """供应商当前是否在有效黑名单中（status=ACTIVE）。supplier 可为实例或 id。"""
        if not supplier:
            return False
        supplier_id = getattr(supplier, 'pk', supplier)
        return cls.objects.filter(supplier_id=supplier_id, status='ACTIVE', is_deleted=False).exists()
