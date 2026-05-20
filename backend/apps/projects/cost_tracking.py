"""
项目成本实时核算看板
Real-time Project Cost Tracking Dashboard

功能：
- 预算vs实际对比
- 成本预警（超支提醒）
- 各阶段成本分布
- 成本趋势分析
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# =============================================================================
# 模型定义
# =============================================================================


class ProjectBudget(BaseModel):
    """项目预算"""

    project = models.OneToOneField(
        'projects.Project', on_delete=models.CASCADE, related_name='budget', verbose_name='项目'
    )

    # 预算明细
    material_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='材料预算')
    labor_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='人工预算')
    outsource_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='外协预算')
    equipment_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='设备预算')
    travel_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='差旅预算')
    management_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='管理费预算')
    other_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='其他预算')
    contingency_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='应急预算')

    total_budget = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='总预算')

    # 预警阈值
    warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80, verbose_name='预警阈值%')
    critical_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=95, verbose_name='严重阈值%')

    # 审批
    approved = models.BooleanField(default=False, verbose_name='已审批')
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_project_budgets',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'project_budget'
        verbose_name = '项目预算'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.project.project_no} - 预算'

    def save(self, *args, **kwargs):
        # 计算总预算
        self.total_budget = (
            self.material_budget
            + self.labor_budget
            + self.outsource_budget
            + self.equipment_budget
            + self.travel_budget
            + self.management_budget
            + self.other_budget
            + self.contingency_budget
        )
        super().save(*args, **kwargs)


class ProjectCostRecord(BaseModel):
    """项目成本记录"""

    COST_TYPE_CHOICES = [
        ('MATERIAL', '材料'),
        ('LABOR', '人工'),
        ('OUTSOURCE', '外协'),
        ('EQUIPMENT', '设备'),
        ('TRAVEL', '差旅'),
        ('MANAGEMENT', '管理费'),
        ('OTHER', '其他'),
    ]

    SOURCE_TYPE_CHOICES = [
        ('PURCHASE', '采购单'),
        ('TIMESHEET', '工时单'),
        ('OUTSOURCE', '外协单'),
        ('EXPENSE', '费用报销'),
        ('INVENTORY', '库存领用'),
        ('MANUAL', '手工录入'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='cost_records', verbose_name='项目'
    )

    cost_type = models.CharField(max_length=20, choices=COST_TYPE_CHOICES, verbose_name='成本类型')
    source_type = models.CharField(
        max_length=20, choices=SOURCE_TYPE_CHOICES, default='MANUAL', verbose_name='来源类型'
    )

    # 来源单据
    source_doc_type = models.CharField(max_length=50, blank=True, verbose_name='单据类型')
    source_doc_no = models.CharField(max_length=50, blank=True, verbose_name='单据编号')
    source_doc_id = models.IntegerField(null=True, blank=True, verbose_name='单据ID')

    # 成本信息
    description = models.CharField(max_length=500, verbose_name='成本说明')
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='金额')
    cost_date = models.DateField(verbose_name='成本日期')

    # 项目阶段
    project_phase = models.CharField(
        max_length=20,
        choices=[
            ('DESIGN', '设计阶段'),
            ('PROCUREMENT', '采购阶段'),
            ('PRODUCTION', '生产阶段'),
            ('ASSEMBLY', '装配阶段'),
            ('TESTING', '测试阶段'),
            ('INSTALLATION', '安装调试'),
            ('ACCEPTANCE', '验收阶段'),
            ('WARRANTY', '质保期'),
        ],
        default='PRODUCTION',
        verbose_name='项目阶段',
    )

    # 责任部门
    department = models.ForeignKey(
        'accounts.Department', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='责任部门'
    )

    is_verified = models.BooleanField(default=False, verbose_name='已核实')
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_costs',
        verbose_name='核实人',
    )

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'project_cost_record'
        verbose_name = '项目成本记录'
        verbose_name_plural = verbose_name
        ordering = ['-cost_date']
        indexes = [
            models.Index(fields=['project', 'cost_type']),
            models.Index(fields=['project', 'cost_date']),
        ]

    def __str__(self):
        return f'{self.project.project_no} - {self.get_cost_type_display()} - ¥{self.amount}'


class ProjectCostSnapshot(BaseModel):
    """项目成本快照（定期汇总）"""

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='cost_snapshots', verbose_name='项目'
    )

    snapshot_date = models.DateField(verbose_name='快照日期')
    snapshot_type = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', '日快照'),
            ('WEEKLY', '周快照'),
            ('MONTHLY', '月快照'),
        ],
        default='DAILY',
        verbose_name='快照类型',
    )

    # 累计成本
    material_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='材料成本')
    labor_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='人工成本')
    outsource_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='外协成本')
    equipment_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='设备成本')
    travel_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='差旅成本')
    management_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='管理费')
    other_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='其他成本')

    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='总成本')

    # 预算对比
    budget_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='预算总额')
    budget_used_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='预算使用率%')

    # 项目进度
    project_progress = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='项目进度%')

    # 成本绩效
    cpi = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='成本绩效指数')

    class Meta:
        db_table = 'project_cost_snapshot'
        verbose_name = '项目成本快照'
        verbose_name_plural = verbose_name
        unique_together = ['project', 'snapshot_date', 'snapshot_type']
        ordering = ['-snapshot_date']


class CostAlert(BaseModel):
    """成本预警"""

    ALERT_TYPE_CHOICES = [
        ('BUDGET_WARNING', '预算预警'),
        ('BUDGET_CRITICAL', '预算严重超支'),
        ('BUDGET_EXCEEDED', '预算超支'),
        ('ABNORMAL_COST', '异常成本'),
        ('PHASE_EXCEEDED', '阶段超支'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='cost_alerts', verbose_name='项目'
    )

    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, verbose_name='预警类型')
    alert_date = models.DateTimeField(auto_now_add=True, verbose_name='预警时间')

    cost_type = models.CharField(
        max_length=20, choices=ProjectCostRecord.COST_TYPE_CHOICES, blank=True, verbose_name='成本类型'
    )

    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='预算金额')
    actual_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='实际金额')
    variance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='偏差率%')

    message = models.TextField(verbose_name='预警消息')

    is_resolved = models.BooleanField(default=False, verbose_name='已处理')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_cost_alerts',
        verbose_name='处理人',
    )
    resolution = models.TextField(blank=True, verbose_name='处理说明')

    class Meta:
        db_table = 'project_cost_alert'
        verbose_name = '成本预警'
        verbose_name_plural = verbose_name
        ordering = ['-alert_date']


# =============================================================================
# 序列化器
# =============================================================================


class ProjectBudgetSerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)

    class Meta:
        model = ProjectBudget
        fields = '__all__'
        read_only_fields = ['total_budget']


class ProjectCostRecordSerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    cost_type_display = serializers.CharField(source='get_cost_type_display', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    project_phase_display = serializers.CharField(source='get_project_phase_display', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = ProjectCostRecord
        fields = '__all__'


class ProjectCostSnapshotSerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)

    class Meta:
        model = ProjectCostSnapshot
        fields = '__all__'


class CostAlertSerializer(serializers.ModelSerializer):
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)

    class Meta:
        model = CostAlert
        fields = '__all__'


# =============================================================================
# 视图集和API
# =============================================================================


class ProjectBudgetViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目预算管理"""

    queryset = ProjectBudget.objects.filter(is_deleted=False)
    serializer_class = ProjectBudgetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'approved']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批预算"""
        budget = self.get_object()
        budget.approved = True
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save()
        return Response(ProjectBudgetSerializer(budget).data)


class ProjectCostRecordViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目成本记录"""

    queryset = ProjectCostRecord.objects.filter(is_deleted=False)
    serializer_class = ProjectCostRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'cost_type', 'source_type', 'project_phase', 'is_verified']
    ordering_fields = ['cost_date', 'amount']
    search_fields = ['description', 'source_doc_no']

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """核实成本"""
        record = self.get_object()
        record.is_verified = True
        record.verified_by = request.user
        record.save()
        return Response(ProjectCostRecordSerializer(record).data)


class CostAlertViewSet(PermissionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """成本预警管理"""

    queryset = CostAlert.objects.filter(is_deleted=False)
    serializer_class = CostAlertSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'alert_type', 'is_resolved']

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """处理预警"""
        alert = self.get_object()
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.resolution = request.data.get('resolution', '')
        alert.save()
        return Response(CostAlertSerializer(alert).data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """待处理预警"""
        alerts = self.get_queryset().filter(is_resolved=False)
        return Response(CostAlertSerializer(alerts, many=True).data)


class ProjectCostDashboardView(APIView):
    """项目成本看板API - 非标自动化行业成本分析"""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        from apps.projects.models import Project

        try:
            project = Project.objects.select_related('sales_order', 'customer').get(id=project_id, is_deleted=False)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=404)

        # 获取预算
        try:
            budget = project.budget
            budget_data = ProjectBudgetSerializer(budget).data
        except ProjectBudget.DoesNotExist:
            budget_data = None

        # 计算实际成本
        cost_records = ProjectCostRecord.objects.filter(project=project, is_deleted=False)

        actual_costs = cost_records.values('cost_type').annotate(total=Sum('amount'))
        actual_by_type = {c['cost_type']: float(c['total']) for c in actual_costs}

        total_actual = cost_records.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # ==================== 收入计算 ====================
        # 从销售订单获取合同金额
        revenue = Decimal('0')
        if project.sales_order:
            revenue = project.sales_order.total_with_tax or Decimal('0')

        # ==================== 成本构成分析 ====================
        # 直接成本（材料+人工+外协）
        direct_cost = Decimal('0')
        direct_cost += Decimal(str(actual_by_type.get('MATERIAL', 0)))
        direct_cost += Decimal(str(actual_by_type.get('LABOR', 0)))
        direct_cost += Decimal(str(actual_by_type.get('OUTSOURCE', 0)))

        # 间接成本（设备+差旅+管理+其他）
        indirect_cost = Decimal('0')
        indirect_cost += Decimal(str(actual_by_type.get('EQUIPMENT', 0)))
        indirect_cost += Decimal(str(actual_by_type.get('TRAVEL', 0)))
        indirect_cost += Decimal(str(actual_by_type.get('MANAGEMENT', 0)))
        indirect_cost += Decimal(str(actual_by_type.get('OTHER', 0)))

        # ==================== 利润计算 ====================
        # 毛利润 = 收入 - 直接成本
        gross_profit = revenue - direct_cost
        # 毛利率
        gross_margin = round(float(gross_profit) / float(revenue) * 100, 2) if revenue > 0 else 0

        # 净利润 = 收入 - 总成本
        net_profit = revenue - total_actual
        # 净利率
        net_margin = round(float(net_profit) / float(revenue) * 100, 2) if revenue > 0 else 0

        # ==================== 成本构成明细 ====================
        cost_breakdown = {
            'material': {
                'name': '材料成本',
                'amount': float(actual_by_type.get('MATERIAL', 0)),
                'category': 'direct',
                'budget': float(budget_data.get('material_budget', 0)) if budget_data else 0,
            },
            'labor': {
                'name': '人工成本',
                'amount': float(actual_by_type.get('LABOR', 0)),
                'category': 'direct',
                'budget': float(budget_data.get('labor_budget', 0)) if budget_data else 0,
            },
            'outsource': {
                'name': '外协成本',
                'amount': float(actual_by_type.get('OUTSOURCE', 0)),
                'category': 'direct',
                'budget': float(budget_data.get('outsource_budget', 0)) if budget_data else 0,
            },
            'equipment': {
                'name': '设备费用',
                'amount': float(actual_by_type.get('EQUIPMENT', 0)),
                'category': 'indirect',
                'budget': float(budget_data.get('equipment_budget', 0)) if budget_data else 0,
            },
            'travel': {
                'name': '差旅费用',
                'amount': float(actual_by_type.get('TRAVEL', 0)),
                'category': 'indirect',
                'budget': float(budget_data.get('travel_budget', 0)) if budget_data else 0,
            },
            'management': {
                'name': '管理费用',
                'amount': float(actual_by_type.get('MANAGEMENT', 0)),
                'category': 'indirect',
                'budget': float(budget_data.get('management_budget', 0)) if budget_data else 0,
            },
            'other': {
                'name': '其他费用',
                'amount': float(actual_by_type.get('OTHER', 0)),
                'category': 'indirect',
                'budget': float(budget_data.get('other_budget', 0)) if budget_data else 0,
            },
        }

        # 计算各项成本占比
        for key, item in cost_breakdown.items():
            item['percentage'] = round(item['amount'] / float(total_actual) * 100, 1) if total_actual > 0 else 0
            item['variance'] = item['budget'] - item['amount']
            item['usage_rate'] = round(item['amount'] / item['budget'] * 100, 1) if item['budget'] > 0 else 0

        # 预算vs实际对比
        budget_comparison = []
        if budget_data:
            type_mapping = {
                'MATERIAL': 'material_budget',
                'LABOR': 'labor_budget',
                'OUTSOURCE': 'outsource_budget',
                'EQUIPMENT': 'equipment_budget',
                'TRAVEL': 'travel_budget',
                'MANAGEMENT': 'management_budget',
                'OTHER': 'other_budget',
            }

            for cost_type, budget_field in type_mapping.items():
                budget_val = float(budget_data.get(budget_field, 0))
                actual_val = actual_by_type.get(cost_type, 0)

                budget_comparison.append(
                    {
                        'cost_type': cost_type,
                        'cost_type_display': dict(ProjectCostRecord.COST_TYPE_CHOICES).get(cost_type),
                        'budget': budget_val,
                        'actual': actual_val,
                        'variance': budget_val - actual_val,
                        'usage_rate': round(actual_val / budget_val * 100, 2) if budget_val > 0 else 0,
                    }
                )

        # 按阶段成本
        phase_costs = cost_records.values('project_phase').annotate(total=Sum('amount')).order_by('project_phase')

        # 成本趋势（按月）
        cost_trend = (
            cost_records.annotate(month=TruncMonth('cost_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )

        # 计算预算使用率
        budget_total = float(budget_data.get('total_budget', 0)) if budget_data else 0
        budget_used_rate = round(float(total_actual) / budget_total * 100, 2) if budget_total > 0 else 0

        # 预警状态
        warning_status = 'normal'
        if budget_data:
            if budget_used_rate >= float(budget_data.get('critical_threshold', 95)):
                warning_status = 'critical'
            elif budget_used_rate >= float(budget_data.get('warning_threshold', 80)):
                warning_status = 'warning'

        # 利润预警
        profit_warning = 'normal'
        if net_margin < 0:
            profit_warning = 'critical'  # 亏损
        elif net_margin < 10:
            profit_warning = 'warning'  # 利润率低于10%

        # 最近成本记录
        recent_costs = cost_records.order_by('-cost_date')[:10]

        # 未处理预警
        pending_alerts = CostAlert.objects.filter(project=project, is_resolved=False).count()

        return Response(
            {
                'project': {
                    'id': project.id,
                    'project_no': project.project_no,
                    'name': project.name,
                    'customer_name': project.customer.name if project.customer else None,
                    'status': project.status,
                    'sales_order_no': project.sales_order.order_no if project.sales_order else None,
                },
                # 收入与利润
                'revenue': float(revenue),
                'gross_profit': float(gross_profit),
                'gross_margin': gross_margin,
                'net_profit': float(net_profit),
                'net_margin': net_margin,
                'profit_warning': profit_warning,
                # 成本构成
                'direct_cost': float(direct_cost),
                'indirect_cost': float(indirect_cost),
                'cost_breakdown': cost_breakdown,
                # 预算相关
                'budget': budget_data,
                'actual_total': float(total_actual),
                'budget_total': budget_total,
                'budget_used_rate': budget_used_rate,
                'warning_status': warning_status,
                'budget_comparison': budget_comparison,
                # 其他
                'phase_costs': list(phase_costs),
                'cost_trend': list(cost_trend),
                'recent_costs': ProjectCostRecordSerializer(recent_costs, many=True).data,
                'pending_alerts': pending_alerts,
            }
        )


class CostOverviewDashboardView(APIView):
    """成本总览看板API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.projects.models import Project

        # 筛选条件
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        department_id = request.query_params.get('department_id')

        # 活跃项目
        active_projects = Project.objects.filter(
            status__in=['IN_PROGRESS', 'DEBUGGING', 'INSTALLATION'], is_deleted=False
        )

        # 项目成本汇总
        project_summaries = []
        for project in active_projects:
            cost_records = ProjectCostRecord.objects.filter(project=project, is_deleted=False)

            if start_date:
                cost_records = cost_records.filter(cost_date__gte=start_date)
            if end_date:
                cost_records = cost_records.filter(cost_date__lte=end_date)

            total_cost = cost_records.aggregate(total=Sum('amount'))['total'] or 0

            try:
                budget = project.budget
                budget_total = float(budget.total_budget)
                usage_rate = round(float(total_cost) / budget_total * 100, 2) if budget_total > 0 else 0
            except ProjectBudget.DoesNotExist:
                budget_total = 0
                usage_rate = 0

            project_summaries.append(
                {
                    'project_id': project.id,
                    'project_no': project.project_no,
                    'project_name': project.name,
                    'total_cost': float(total_cost),
                    'budget_total': budget_total,
                    'usage_rate': usage_rate,
                    'status': project.status,
                }
            )

        # 按使用率排序（超支的排前面）
        project_summaries.sort(key=lambda x: x['usage_rate'], reverse=True)

        # 总体统计
        all_costs = ProjectCostRecord.objects.filter(is_deleted=False)
        if start_date:
            all_costs = all_costs.filter(cost_date__gte=start_date)
        if end_date:
            all_costs = all_costs.filter(cost_date__lte=end_date)

        # 按类型汇总
        by_type = all_costs.values('cost_type').annotate(total=Sum('amount'), count=Count('id'))

        # 按部门汇总
        by_department = (
            all_costs.exclude(department__isnull=True)
            .values('department__name')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )

        # 本月vs上月
        today = date.today()
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        this_month_total = (
            all_costs.filter(cost_date__gte=this_month_start).aggregate(total=Sum('amount'))['total'] or 0
        )

        last_month_total = (
            ProjectCostRecord.objects.filter(
                cost_date__gte=last_month_start, cost_date__lte=last_month_end, is_deleted=False
            ).aggregate(total=Sum('amount'))['total']
            or 0
        )

        month_change = 0
        if last_month_total > 0:
            month_change = round((float(this_month_total) - float(last_month_total)) / float(last_month_total) * 100, 2)

        # 预警统计
        alert_stats = CostAlert.objects.filter(is_deleted=False).values('is_resolved').annotate(count=Count('id'))

        return Response(
            {
                'project_summaries': project_summaries[:20],  # 前20个项目
                'total_projects': len(project_summaries),
                'over_budget_count': len([p for p in project_summaries if p['usage_rate'] > 100]),
                'warning_count': len([p for p in project_summaries if 80 <= p['usage_rate'] <= 100]),
                'by_type': list(by_type),
                'by_department': list(by_department)[:10],
                'this_month_total': float(this_month_total),
                'last_month_total': float(last_month_total),
                'month_change': month_change,
                'alert_stats': list(alert_stats),
            }
        )


# =============================================================================
# 辅助函数
# =============================================================================


def create_cost_snapshot(project_id, snapshot_type='DAILY'):
    """创建成本快照"""
    from apps.projects.models import Project

    project = Project.objects.get(id=project_id)
    today = date.today()

    cost_records = ProjectCostRecord.objects.filter(project=project, is_deleted=False)

    # 按类型汇总
    costs_by_type = cost_records.values('cost_type').annotate(total=Sum('amount'))
    type_totals = {c['cost_type']: c['total'] for c in costs_by_type}

    total = sum(type_totals.values())

    # 获取预算
    try:
        budget = project.budget
        budget_total = budget.total_budget
        usage_rate = float(total) / float(budget_total) * 100 if budget_total > 0 else 0
    except ProjectBudget.DoesNotExist:
        budget_total = 0
        usage_rate = 0

    snapshot, created = ProjectCostSnapshot.objects.update_or_create(
        project=project,
        snapshot_date=today,
        snapshot_type=snapshot_type,
        defaults={
            'material_cost': type_totals.get('MATERIAL', 0),
            'labor_cost': type_totals.get('LABOR', 0),
            'outsource_cost': type_totals.get('OUTSOURCE', 0),
            'equipment_cost': type_totals.get('EQUIPMENT', 0),
            'travel_cost': type_totals.get('TRAVEL', 0),
            'management_cost': type_totals.get('MANAGEMENT', 0),
            'other_cost': type_totals.get('OTHER', 0),
            'total_cost': total,
            'budget_total': budget_total,
            'budget_used_rate': usage_rate,
        },
    )

    return snapshot


def check_cost_alerts(project_id):
    """检查成本预警"""
    from apps.projects.models import Project

    project = Project.objects.get(id=project_id)

    try:
        budget = project.budget
    except ProjectBudget.DoesNotExist:
        return []

    cost_records = ProjectCostRecord.objects.filter(project=project, is_deleted=False)

    total_actual = cost_records.aggregate(total=Sum('amount'))['total'] or 0
    usage_rate = float(total_actual) / float(budget.total_budget) * 100 if budget.total_budget > 0 else 0

    alerts = []

    # 检查总预算
    if usage_rate >= 100:
        alert, created = CostAlert.objects.get_or_create(
            project=project,
            alert_type='BUDGET_EXCEEDED',
            is_resolved=False,
            defaults={
                'budget_amount': budget.total_budget,
                'actual_amount': total_actual,
                'variance_rate': usage_rate - 100,
                'message': f'项目 [{project.project_no}] 预算已超支！预算: ¥{budget.total_budget}，实际: ¥{total_actual}',
            },
        )
        if created:
            alerts.append(alert)

    elif usage_rate >= float(budget.critical_threshold):
        alert, created = CostAlert.objects.get_or_create(
            project=project,
            alert_type='BUDGET_CRITICAL',
            is_resolved=False,
            defaults={
                'budget_amount': budget.total_budget,
                'actual_amount': total_actual,
                'variance_rate': usage_rate,
                'message': f'项目 [{project.project_no}] 预算使用率已达 {usage_rate:.1f}%，接近超支！',
            },
        )
        if created:
            alerts.append(alert)

    elif usage_rate >= float(budget.warning_threshold):
        alert, created = CostAlert.objects.get_or_create(
            project=project,
            alert_type='BUDGET_WARNING',
            is_resolved=False,
            defaults={
                'budget_amount': budget.total_budget,
                'actual_amount': total_actual,
                'variance_rate': usage_rate,
                'message': f'项目 [{project.project_no}] 预算使用率已达 {usage_rate:.1f}%，请注意控制成本。',
            },
        )
        if created:
            alerts.append(alert)

    return alerts
