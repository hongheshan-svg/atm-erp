"""
报价成本预测优化模块
Quote Prediction - 历史参照、多版本报价、利润预测
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel

User = settings.AUTH_USER_MODEL


class QuoteVersion(BaseModel):
    """报价版本"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('REVIEWING', '评审中'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('SENT', '已发送客户'),
        ('ACCEPTED', '客户接受'),
        ('LOST', '报价失败'),
    ]

    quote_no = models.CharField('报价编号', max_length=50)
    version = models.IntegerField('版本号', default=1)
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.CASCADE, related_name='quote_versions', verbose_name='客户'
    )
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_versions',
        verbose_name='商机',
    )

    title = models.CharField('报价标题', max_length=200)
    description = models.TextField('项目描述', blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # 参照项目
    reference_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referenced_quotes',
        verbose_name='参照项目',
    )
    similarity_score = models.DecimalField('相似度', max_digits=5, decimal_places=2, default=0)

    # 成本估算
    material_cost = models.DecimalField('材料成本', max_digits=14, decimal_places=2, default=0)
    labor_cost = models.DecimalField('人工成本', max_digits=14, decimal_places=2, default=0)
    outsource_cost = models.DecimalField('外协成本', max_digits=14, decimal_places=2, default=0)
    overhead_cost = models.DecimalField('管理费用', max_digits=14, decimal_places=2, default=0)
    other_cost = models.DecimalField('其他成本', max_digits=14, decimal_places=2, default=0)
    contingency = models.DecimalField('风险预留', max_digits=14, decimal_places=2, default=0)

    # 报价金额
    quote_amount = models.DecimalField('报价金额', max_digits=14, decimal_places=2, default=0)
    discount_rate = models.DecimalField('折扣率%', max_digits=5, decimal_places=2, default=0)
    final_amount = models.DecimalField('最终报价', max_digits=14, decimal_places=2, default=0)

    # 利润预测
    expected_profit = models.DecimalField('预期利润', max_digits=14, decimal_places=2, default=0)
    profit_margin = models.DecimalField('利润率%', max_digits=5, decimal_places=2, default=0)

    # 交期
    estimated_days = models.IntegerField('预计工期(天)', default=0)
    delivery_date = models.DateField('预计交付日期', null=True, blank=True)

    # 有效期
    valid_until = models.DateField('有效期至', null=True, blank=True)

    # 创建人
    created_by_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_quotes', verbose_name='创建人'
    )

    class Meta:
        db_table = 'quote_version'
        verbose_name = '报价版本'
        unique_together = ['quote_no', 'version']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.quote_no} V{self.version}'

    @property
    def total_cost(self):
        return (
            self.material_cost
            + self.labor_cost
            + self.outsource_cost
            + self.overhead_cost
            + self.other_cost
            + self.contingency
        )

    def save(self, *args, **kwargs):
        # 计算利润
        self.expected_profit = self.final_amount - self.total_cost
        if self.final_amount > 0:
            self.profit_margin = self.expected_profit / self.final_amount * 100
        super().save(*args, **kwargs)


class QuoteCostItem(BaseModel):
    """报价成本明细"""

    COST_TYPE_CHOICES = [
        ('MATERIAL', '材料'),
        ('LABOR', '人工'),
        ('OUTSOURCE', '外协'),
        ('OVERHEAD', '管理费'),
        ('OTHER', '其他'),
    ]

    quote = models.ForeignKey(QuoteVersion, on_delete=models.CASCADE, related_name='cost_items', verbose_name='报价')
    cost_type = models.CharField('成本类型', max_length=20, choices=COST_TYPE_CHOICES)

    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quote_cost_items',
        verbose_name='物料',
    )
    description = models.CharField('描述', max_length=500)

    quantity = models.DecimalField('数量', max_digits=14, decimal_places=4, default=1)
    unit = models.CharField('单位', max_length=20, blank=True)
    unit_price = models.DecimalField('单价', max_digits=14, decimal_places=2, default=0)
    amount = models.DecimalField('金额', max_digits=14, decimal_places=2, default=0)

    # 来源
    source = models.CharField('来源', max_length=50, blank=True)  # 历史数据、供应商报价、估算等
    confidence = models.IntegerField('置信度%', default=80)

    remarks = models.TextField('备注', blank=True)

    class Meta:
        db_table = 'quote_cost_item'
        verbose_name = '报价成本明细'

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class QuoteComparison(BaseModel):
    """报价对比"""

    name = models.CharField('对比名称', max_length=200)
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.CASCADE, related_name='quote_comparisons', verbose_name='客户'
    )
    quotes = models.ManyToManyField(QuoteVersion, related_name='comparisons', verbose_name='报价版本')

    conclusion = models.TextField('对比结论', blank=True)
    recommended_quote = models.ForeignKey(
        QuoteVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommended_in',
        verbose_name='推荐版本',
    )

    class Meta:
        db_table = 'quote_comparison'
        verbose_name = '报价对比'


class QuoteProjectCostRef(BaseModel):
    """报价参考-项目成本历史（用于参照报价）"""

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='quote_cost_refs', verbose_name='项目'
    )

    # 项目特征
    project_type = models.CharField('项目类型', max_length=100)
    industry = models.CharField('行业', max_length=100, blank=True)
    complexity = models.CharField('复杂度', max_length=20, blank=True)
    keywords = models.JSONField('关键词标签', default=list)

    # 合同信息
    contract_amount = models.DecimalField('合同金额', max_digits=14, decimal_places=2)

    # 实际成本
    actual_material_cost = models.DecimalField('实际材料成本', max_digits=14, decimal_places=2)
    actual_labor_cost = models.DecimalField('实际人工成本', max_digits=14, decimal_places=2)
    actual_outsource_cost = models.DecimalField('实际外协成本', max_digits=14, decimal_places=2)
    actual_other_cost = models.DecimalField('实际其他成本', max_digits=14, decimal_places=2)
    actual_total_cost = models.DecimalField('实际总成本', max_digits=14, decimal_places=2)

    # 利润
    actual_profit = models.DecimalField('实际利润', max_digits=14, decimal_places=2)
    profit_margin = models.DecimalField('利润率%', max_digits=5, decimal_places=2)

    # 工期
    planned_days = models.IntegerField('计划工期')
    actual_days = models.IntegerField('实际工期')

    class Meta:
        db_table = 'quote_project_cost_ref'
        verbose_name = '报价参考成本历史'


# ==================== Services ====================


class QuotePredictionService:
    """报价预测服务"""

    @staticmethod
    def find_similar_projects(keywords, industry=None, limit=10):
        """查找相似项目"""

        # 基于关键词搜索
        qs = QuoteProjectCostRef.objects.filter(is_deleted=False)

        if industry:
            qs = qs.filter(industry=industry)

        similar = []
        for history in qs:
            # 计算相似度
            history_keywords = set(history.keywords or [])
            query_keywords = set(keywords or [])

            if history_keywords and query_keywords:
                intersection = len(history_keywords & query_keywords)
                union = len(history_keywords | query_keywords)
                similarity = intersection / union if union > 0 else 0
            else:
                similarity = 0

            if similarity > 0:
                similar.append(
                    {
                        'project_id': history.project_id,
                        'project_name': history.project.name if history.project else '',
                        'project_type': history.project_type,
                        'similarity': round(similarity * 100, 1),
                        'contract_amount': float(history.contract_amount),
                        'actual_cost': float(history.actual_total_cost),
                        'profit_margin': float(history.profit_margin),
                        'actual_days': history.actual_days,
                    }
                )

        # 按相似度排序
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        return similar[:limit]

    @staticmethod
    def estimate_from_reference(reference_project_id, adjustment_factor=1.0):
        """基于参照项目估算"""
        try:
            history = QuoteProjectCostRef.objects.get(project_id=reference_project_id)
        except QuoteProjectCostRef.DoesNotExist:
            return None

        factor = Decimal(str(adjustment_factor))

        return {
            'material_cost': float(history.actual_material_cost * factor),
            'labor_cost': float(history.actual_labor_cost * factor),
            'outsource_cost': float(history.actual_outsource_cost * factor),
            'other_cost': float(history.actual_other_cost * factor),
            'total_cost': float(history.actual_total_cost * factor),
            'suggested_price': float(history.contract_amount * factor),
            'reference_profit_margin': float(history.profit_margin),
            'estimated_days': int(history.actual_days * float(adjustment_factor)),
        }

    @staticmethod
    def predict_profit(quote_amount, total_cost, historical_margin=None):
        """利润预测"""
        expected_profit = quote_amount - total_cost
        margin = (expected_profit / quote_amount * 100) if quote_amount > 0 else 0

        # 风险评估
        risk_level = 'LOW'
        if margin < 10:
            risk_level = 'HIGH'
        elif margin < 20:
            risk_level = 'MEDIUM'

        return {
            'expected_profit': float(expected_profit),
            'profit_margin': round(float(margin), 2),
            'risk_level': risk_level,
            'recommendation': '利润率较低，建议重新评估成本或调整报价' if margin < 15 else '利润率正常',
        }


# ==================== Serializers ====================


class QuoteCostItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    cost_type_display = serializers.CharField(source='get_cost_type_display', read_only=True)

    class Meta:
        model = QuoteCostItem
        fields = '__all__'


class QuoteVersionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cost_items = QuoteCostItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by_user.get_full_name', read_only=True)

    class Meta:
        model = QuoteVersion
        fields = '__all__'


class QuoteComparisonSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    quotes_detail = QuoteVersionSerializer(source='quotes', many=True, read_only=True)

    class Meta:
        model = QuoteComparison
        fields = '__all__'


class QuoteProjectCostRefSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = QuoteProjectCostRef
        fields = '__all__'


# ==================== ViewSets ====================


class QuoteVersionViewSet(viewsets.ModelViewSet):
    """报价版本管理"""

    queryset = QuoteVersion.objects.filter(is_deleted=False)
    serializer_class = QuoteVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        customer = self.request.query_params.get('customer')
        status_filter = self.request.query_params.get('status')

        if customer:
            qs = qs.filter(customer_id=customer)
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.select_related('customer', 'created_by_user')

    def perform_create(self, serializer):
        # 自动生成报价编号
        today = timezone.now()
        prefix = f'QT{today.strftime("%Y%m%d")}'
        last = QuoteVersion.objects.filter(quote_no__startswith=prefix).order_by('-quote_no').first()
        if last:
            seq = int(last.quote_no[-4:]) + 1
        else:
            seq = 1
        quote_no = f'{prefix}{seq:04d}'

        serializer.save(quote_no=quote_no, created_by_user=self.request.user)

    @action(detail=True, methods=['post'])
    def create_new_version(self, request, pk=None):
        """创建新版本"""
        quote = self.get_object()

        # 获取最新版本号
        max_version = (
            QuoteVersion.objects.filter(quote_no=quote.quote_no).aggregate(max_v=models.Max('version'))['max_v'] or 0
        )

        # 复制创建新版本
        new_quote = QuoteVersion.objects.create(
            quote_no=quote.quote_no,
            version=max_version + 1,
            customer=quote.customer,
            opportunity=quote.opportunity,
            title=quote.title,
            description=quote.description,
            reference_project=quote.reference_project,
            material_cost=quote.material_cost,
            labor_cost=quote.labor_cost,
            outsource_cost=quote.outsource_cost,
            overhead_cost=quote.overhead_cost,
            other_cost=quote.other_cost,
            contingency=quote.contingency,
            quote_amount=quote.quote_amount,
            discount_rate=quote.discount_rate,
            final_amount=quote.final_amount,
            estimated_days=quote.estimated_days,
            created_by_user=request.user,
            created_by=request.user,
            updated_by=request.user,
        )

        # 复制成本明细
        for item in quote.cost_items.all():
            QuoteCostItem.objects.create(
                quote=new_quote,
                cost_type=item.cost_type,
                item=item.item,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                amount=item.amount,
                source=item.source,
                confidence=item.confidence,
                remarks=item.remarks,
                created_by=request.user,
                updated_by=request.user,
            )

        return Response(QuoteVersionSerializer(new_quote).data)

    @action(detail=True, methods=['post'])
    def estimate_from_reference(self, request, pk=None):
        """基于参照项目估算"""
        quote = self.get_object()
        reference_id = request.data.get('reference_project_id')
        adjustment_factor = float(request.data.get('adjustment_factor', 1.0))

        estimate = QuotePredictionService.estimate_from_reference(reference_id, adjustment_factor)

        if not estimate:
            return Response({'error': '参照项目无历史数据'}, status=400)

        return Response(estimate)

    @action(detail=True, methods=['get'])
    def profit_prediction(self, request, pk=None):
        """利润预测"""
        quote = self.get_object()

        prediction = QuotePredictionService.predict_profit(float(quote.final_amount), float(quote.total_cost))

        return Response(prediction)

    @action(detail=False, methods=['post'])
    def find_similar(self, request):
        """查找相似项目"""
        keywords = request.data.get('keywords', [])
        industry = request.data.get('industry')

        similar = QuotePredictionService.find_similar_projects(keywords, industry)

        return Response(similar)


class QuoteCostItemViewSet(viewsets.ModelViewSet):
    """报价成本明细管理"""

    queryset = QuoteCostItem.objects.filter(is_deleted=False)
    serializer_class = QuoteCostItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        quote = self.request.query_params.get('quote')
        if quote:
            qs = qs.filter(quote_id=quote)
        return qs


class QuoteComparisonViewSet(viewsets.ModelViewSet):
    """报价对比管理"""

    queryset = QuoteComparison.objects.filter(is_deleted=False)
    serializer_class = QuoteComparisonSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['get'])
    def compare(self, request, pk=None):
        """执行对比"""
        comparison = self.get_object()
        quotes = comparison.quotes.all()

        if quotes.count() < 2:
            return Response({'error': '至少需要2个报价版本进行对比'}, status=400)

        comparison_data = {
            'quotes': [],
            'metrics': {
                'total_cost': [],
                'final_amount': [],
                'profit_margin': [],
                'estimated_days': [],
            },
        }

        for quote in quotes:
            comparison_data['quotes'].append(
                {
                    'id': quote.id,
                    'quote_no': f'{quote.quote_no} V{quote.version}',
                    'total_cost': float(quote.total_cost),
                    'final_amount': float(quote.final_amount),
                    'profit_margin': float(quote.profit_margin),
                    'estimated_days': quote.estimated_days,
                    'material_cost': float(quote.material_cost),
                    'labor_cost': float(quote.labor_cost),
                    'outsource_cost': float(quote.outsource_cost),
                }
            )

            comparison_data['metrics']['total_cost'].append(float(quote.total_cost))
            comparison_data['metrics']['final_amount'].append(float(quote.final_amount))
            comparison_data['metrics']['profit_margin'].append(float(quote.profit_margin))
            comparison_data['metrics']['estimated_days'].append(quote.estimated_days)

        # 计算差异
        comparison_data['analysis'] = {
            'cost_variance': max(comparison_data['metrics']['total_cost'])
            - min(comparison_data['metrics']['total_cost']),
            'price_variance': max(comparison_data['metrics']['final_amount'])
            - min(comparison_data['metrics']['final_amount']),
            'best_margin_quote': max(comparison_data['quotes'], key=lambda x: x['profit_margin'])['quote_no'],
            'lowest_cost_quote': min(comparison_data['quotes'], key=lambda x: x['total_cost'])['quote_no'],
        }

        return Response(comparison_data)


class QuoteProjectCostRefViewSet(viewsets.ModelViewSet):
    """报价参考成本历史管理"""

    queryset = QuoteProjectCostRef.objects.filter(is_deleted=False)
    serializer_class = QuoteProjectCostRefSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def sync_from_project(self, request):
        """从已完成项目同步成本历史"""
        project_id = request.data.get('project_id')

        from apps.projects.models import Project

        try:
            project = Project.objects.get(pk=project_id, status='COMPLETED')
        except Project.DoesNotExist:
            return Response({'error': '项目不存在或未完成'}, status=400)

        # 获取实际成本
        material_cost = project.get_actual_material_cost() or Decimal('0')
        labor_cost = project.get_actual_labor_cost() or Decimal('0')
        expense_cost = project.get_actual_expense_cost() or Decimal('0')
        total_cost = material_cost + labor_cost + expense_cost

        # 获取合同金额
        from apps.sales.models import SalesOrder

        contract_amount = SalesOrder.objects.filter(project=project, is_deleted=False).aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')

        profit = contract_amount - total_cost
        margin = (profit / contract_amount * 100) if contract_amount > 0 else Decimal('0')

        # 工期
        planned_days = (project.end_date - project.start_date).days if project.end_date and project.start_date else 0
        actual_end = project.actual_end_date or project.end_date
        actual_days = (actual_end - project.start_date).days if actual_end and project.start_date else planned_days

        history, created = QuoteProjectCostRef.objects.update_or_create(
            project=project,
            defaults={
                'project_type': project.project_type if hasattr(project, 'project_type') else '',
                'contract_amount': contract_amount,
                'actual_material_cost': material_cost,
                'actual_labor_cost': labor_cost,
                'actual_outsource_cost': Decimal('0'),
                'actual_other_cost': expense_cost,
                'actual_total_cost': total_cost,
                'actual_profit': profit,
                'profit_margin': margin,
                'planned_days': planned_days,
                'actual_days': actual_days,
                'created_by': request.user,
                'updated_by': request.user,
            },
        )

        return Response(
            {'message': '已同步' if created else '已更新', 'data': QuoteProjectCostRefSerializer(history).data}
        )
