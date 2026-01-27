"""
智能排产优化模块
Smart Production Scheduling Optimization

功能：
- 多目标优化算法
- 资源冲突检测
- 瓶颈分析
- 排产方案对比
"""
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q, Min, Max
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


# =============================================================================
# 模型定义
# =============================================================================

class SchedulingObjective(BaseModel):
    """排产目标"""
    code = models.CharField(max_length=50, unique=True, verbose_name='目标编码')
    name = models.CharField(max_length=100, verbose_name='目标名称')
    
    objective_type = models.CharField(
        max_length=20,
        choices=[
            ('MINIMIZE', '最小化'),
            ('MAXIMIZE', '最大化'),
            ('TARGET', '目标值'),
        ],
        verbose_name='优化方向'
    )
    
    # 权重（用于多目标优化）
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, verbose_name='权重')
    
    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    class Meta:
        db_table = 'scheduling_objective'
        verbose_name = '排产目标'
        verbose_name_plural = verbose_name
        ordering = ['-weight']
    
    def __str__(self):
        return self.name


class SchedulingConstraint(BaseModel):
    """排产约束"""
    CONSTRAINT_TYPE_CHOICES = [
        ('RESOURCE_CAPACITY', '资源产能'),
        ('WORK_CENTER', '工作中心'),
        ('MATERIAL_AVAILABILITY', '物料可用'),
        ('SEQUENCE', '工序顺序'),
        ('TIME_WINDOW', '时间窗口'),
        ('PRIORITY', '优先级'),
        ('CUSTOM', '自定义'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='约束编码')
    name = models.CharField(max_length=100, verbose_name='约束名称')
    constraint_type = models.CharField(max_length=30, choices=CONSTRAINT_TYPE_CHOICES, verbose_name='约束类型')
    
    # 约束规则
    rule_expression = models.TextField(blank=True, verbose_name='规则表达式')
    parameters = models.JSONField(default=dict, blank=True, verbose_name='参数')
    
    # 优先级（硬约束/软约束）
    is_hard_constraint = models.BooleanField(default=True, verbose_name='硬约束')
    penalty_weight = models.DecimalField(max_digits=10, decimal_places=2, default=100, verbose_name='违反惩罚')
    
    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    class Meta:
        db_table = 'scheduling_constraint'
        verbose_name = '排产约束'
        verbose_name_plural = verbose_name
        ordering = ['constraint_type']
    
    def __str__(self):
        return self.name


class SchedulingScenario(BaseModel):
    """排产场景"""
    name = models.CharField(max_length=200, verbose_name='场景名称')
    
    # 计划范围
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    
    # 优化目标
    objectives = models.ManyToManyField(
        SchedulingObjective,
        related_name='scenarios',
        verbose_name='优化目标'
    )
    
    # 约束条件
    constraints = models.ManyToManyField(
        SchedulingConstraint,
        related_name='scenarios',
        verbose_name='约束条件'
    )
    
    # 包含的生产计划
    production_plans = models.ManyToManyField(
        'production.ProductionPlan',
        blank=True,
        related_name='scheduling_scenarios',
        verbose_name='生产计划'
    )
    
    # 算法参数
    algorithm = models.CharField(
        max_length=30,
        choices=[
            ('GENETIC', '遗传算法'),
            ('SIMULATED_ANNEALING', '模拟退火'),
            ('TABU_SEARCH', '禁忌搜索'),
            ('GRASP', 'GRASP'),
            ('HYBRID', '混合算法'),
            ('SIMPLE', '简单规则'),
        ],
        default='SIMPLE',
        verbose_name='调度算法'
    )
    algorithm_params = models.JSONField(default=dict, blank=True, verbose_name='算法参数')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('RUNNING', '计算中'),
            ('COMPLETED', '已完成'),
            ('FAILED', '失败'),
            ('APPLIED', '已应用'),
        ],
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 计算信息
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    computation_time_seconds = models.IntegerField(default=0, verbose_name='计算耗时(秒)')
    
    # 结果评估
    objective_values = models.JSONField(default=dict, blank=True, verbose_name='目标值')
    constraint_violations = models.JSONField(default=list, blank=True, verbose_name='约束违反')
    total_score = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='综合评分')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'scheduling_scenario'
        verbose_name = '排产场景'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class SchedulingResult(BaseModel):
    """排产结果"""
    scenario = models.ForeignKey(
        SchedulingScenario,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='排产场景'
    )
    
    production_plan = models.ForeignKey(
        'production.ProductionPlan',
        on_delete=models.CASCADE,
        related_name='scheduling_results',
        verbose_name='生产计划'
    )
    
    # 排产信息
    work_center = models.ForeignKey(
        'production.WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='工作中心'
    )
    
    scheduled_start = models.DateTimeField(verbose_name='计划开始时间')
    scheduled_end = models.DateTimeField(verbose_name='计划结束时间')
    
    # 工序信息
    operation_sequence = models.IntegerField(default=1, verbose_name='工序序号')
    operation_name = models.CharField(max_length=200, blank=True, verbose_name='工序名称')
    
    # 资源分配
    assigned_equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='分配设备'
    )
    assigned_operators = models.IntegerField(default=1, verbose_name='分配人员数')
    
    # 优先级
    priority_score = models.IntegerField(default=0, verbose_name='优先级分数')
    
    class Meta:
        db_table = 'scheduling_result'
        verbose_name = '排产结果'
        verbose_name_plural = verbose_name
        ordering = ['scheduled_start', 'priority_score']


class ResourceConflict(BaseModel):
    """资源冲突"""
    scenario = models.ForeignKey(
        SchedulingScenario,
        on_delete=models.CASCADE,
        related_name='conflicts',
        verbose_name='排产场景'
    )
    
    conflict_type = models.CharField(
        max_length=30,
        choices=[
            ('EQUIPMENT_OVERLAP', '设备时间重叠'),
            ('OPERATOR_OVERLAP', '人员时间重叠'),
            ('MATERIAL_SHORTAGE', '物料短缺'),
            ('CAPACITY_EXCEEDED', '产能超限'),
            ('DEADLINE_MISSED', '交期延误'),
        ],
        verbose_name='冲突类型'
    )
    
    # 冲突资源
    resource_type = models.CharField(max_length=50, verbose_name='资源类型')
    resource_id = models.IntegerField(verbose_name='资源ID')
    resource_name = models.CharField(max_length=200, verbose_name='资源名称')
    
    # 冲突时间
    conflict_start = models.DateTimeField(verbose_name='冲突开始')
    conflict_end = models.DateTimeField(verbose_name='冲突结束')
    
    # 涉及订单
    orders_involved = models.JSONField(default=list, verbose_name='涉及订单')
    
    # 严重程度
    severity = models.CharField(
        max_length=20,
        choices=[
            ('LOW', '低'),
            ('MEDIUM', '中'),
            ('HIGH', '高'),
            ('CRITICAL', '严重'),
        ],
        default='MEDIUM',
        verbose_name='严重程度'
    )
    
    # 建议解决方案
    suggested_resolution = models.TextField(blank=True, verbose_name='建议方案')
    
    is_resolved = models.BooleanField(default=False, verbose_name='已解决')
    resolution_notes = models.TextField(blank=True, verbose_name='解决说明')
    
    class Meta:
        db_table = 'scheduling_conflict'
        verbose_name = '资源冲突'
        verbose_name_plural = verbose_name
        ordering = ['-severity', 'conflict_start']


class BottleneckAnalysis(BaseModel):
    """瓶颈分析"""
    scenario = models.ForeignKey(
        SchedulingScenario,
        on_delete=models.CASCADE,
        related_name='bottlenecks',
        verbose_name='排产场景'
    )
    
    analysis_date = models.DateTimeField(auto_now_add=True, verbose_name='分析时间')
    
    # 瓶颈资源
    resource_type = models.CharField(
        max_length=30,
        choices=[
            ('WORK_CENTER', '工作中心'),
            ('EQUIPMENT', '设备'),
            ('OPERATOR', '人员'),
            ('MATERIAL', '物料'),
        ],
        verbose_name='资源类型'
    )
    resource_id = models.IntegerField(verbose_name='资源ID')
    resource_name = models.CharField(max_length=200, verbose_name='资源名称')
    
    # 瓶颈指标
    utilization_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='利用率%')
    waiting_time_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='等待时间(h)')
    queue_length = models.IntegerField(default=0, verbose_name='队列长度')
    
    # 影响
    affected_orders = models.JSONField(default=list, verbose_name='影响订单')
    delay_impact_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='延误影响(h)')
    
    # 建议
    improvement_suggestions = models.JSONField(default=list, verbose_name='改进建议')
    
    class Meta:
        db_table = 'scheduling_bottleneck'
        verbose_name = '瓶颈分析'
        verbose_name_plural = verbose_name
        ordering = ['-utilization_rate']


class SchedulingComparison(BaseModel):
    """排产方案对比"""
    name = models.CharField(max_length=200, verbose_name='对比名称')
    
    scenarios = models.ManyToManyField(
        SchedulingScenario,
        related_name='comparisons',
        verbose_name='对比场景'
    )
    
    # 对比结果
    comparison_metrics = models.JSONField(default=dict, blank=True, verbose_name='对比指标')
    winner_scenario = models.ForeignKey(
        SchedulingScenario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_comparisons',
        verbose_name='最优场景'
    )
    
    analysis_notes = models.TextField(blank=True, verbose_name='分析说明')
    
    class Meta:
        db_table = 'scheduling_comparison'
        verbose_name = '排产对比'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


# =============================================================================
# 序列化器
# =============================================================================

class SchedulingObjectiveSerializer(serializers.ModelSerializer):
    objective_type_display = serializers.CharField(source='get_objective_type_display', read_only=True)
    
    class Meta:
        model = SchedulingObjective
        fields = '__all__'


class SchedulingConstraintSerializer(serializers.ModelSerializer):
    constraint_type_display = serializers.CharField(source='get_constraint_type_display', read_only=True)
    
    class Meta:
        model = SchedulingConstraint
        fields = '__all__'


class SchedulingResultSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='production_order.order_no', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    equipment_name = serializers.CharField(source='assigned_equipment.name', read_only=True)
    
    class Meta:
        model = SchedulingResult
        fields = '__all__'


class ResourceConflictSerializer(serializers.ModelSerializer):
    conflict_type_display = serializers.CharField(source='get_conflict_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = ResourceConflict
        fields = '__all__'


class BottleneckAnalysisSerializer(serializers.ModelSerializer):
    resource_type_display = serializers.CharField(source='get_resource_type_display', read_only=True)
    
    class Meta:
        model = BottleneckAnalysis
        fields = '__all__'


class SchedulingScenarioSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    algorithm_display = serializers.CharField(source='get_algorithm_display', read_only=True)
    objectives_data = SchedulingObjectiveSerializer(source='objectives', many=True, read_only=True)
    constraints_data = SchedulingConstraintSerializer(source='constraints', many=True, read_only=True)
    results = SchedulingResultSerializer(many=True, read_only=True)
    conflicts = ResourceConflictSerializer(many=True, read_only=True)
    
    class Meta:
        model = SchedulingScenario
        fields = '__all__'


class SchedulingScenarioListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    algorithm_display = serializers.CharField(source='get_algorithm_display', read_only=True)
    order_count = serializers.SerializerMethodField()
    conflict_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SchedulingScenario
        fields = [
            'id', 'name', 'start_date', 'end_date', 'algorithm', 'algorithm_display',
            'status', 'status_display', 'total_score', 'computation_time_seconds',
            'order_count', 'conflict_count', 'created_at'
        ]
    
    def get_order_count(self, obj):
        return obj.production_orders.count()
    
    def get_conflict_count(self, obj):
        return obj.conflicts.filter(is_resolved=False).count()


class SchedulingComparisonSerializer(serializers.ModelSerializer):
    scenarios_data = SchedulingScenarioListSerializer(source='scenarios', many=True, read_only=True)
    winner_name = serializers.CharField(source='winner_scenario.name', read_only=True)
    
    class Meta:
        model = SchedulingComparison
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================

class SchedulingObjectiveViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排产目标管理"""
    queryset = SchedulingObjective.objects.filter(is_deleted=False)
    serializer_class = SchedulingObjectiveSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['objective_type', 'is_active']


class SchedulingConstraintViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排产约束管理"""
    queryset = SchedulingConstraint.objects.filter(is_deleted=False)
    serializer_class = SchedulingConstraintSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['constraint_type', 'is_hard_constraint', 'is_active']


class SchedulingScenarioViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排产场景管理"""
    queryset = SchedulingScenario.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'algorithm']
    search_fields = ['name']
    ordering_fields = ['created_at', 'total_score']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SchedulingScenarioListSerializer
        return SchedulingScenarioSerializer
    
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """执行排产计算"""
        scenario = self.get_object()
        scenario.status = 'RUNNING'
        scenario.started_at = timezone.now()
        scenario.save()
        
        # 实际实现中这里会调用排产算法
        # 这里简化为按优先级和交期排序的简单规则
        try:
            results = self._simple_schedule(scenario)
            
            scenario.status = 'COMPLETED'
            scenario.completed_at = timezone.now()
            scenario.computation_time_seconds = int(
                (scenario.completed_at - scenario.started_at).total_seconds()
            )
            
            # 计算目标值
            scenario.objective_values = self._calculate_objectives(scenario)
            
            # 检测冲突
            self._detect_conflicts(scenario)
            
            # 分析瓶颈
            self._analyze_bottlenecks(scenario)
            
            # 计算总分
            scenario.total_score = self._calculate_score(scenario)
            
            scenario.save()
            
        except Exception as e:
            scenario.status = 'FAILED'
            scenario.remarks = str(e)
            scenario.save()
            return Response({'error': str(e)}, status=500)
        
        return Response(SchedulingScenarioSerializer(scenario).data)
    
    def _simple_schedule(self, scenario):
        """简单排产规则"""
        from apps.production.models import ProductionPlan
        
        orders = scenario.production_orders.filter(
            status__in=['PENDING', 'CONFIRMED']
        ).order_by('priority', 'planned_end_date')
        
        current_time = datetime.combine(scenario.start_date, datetime.min.time())
        
        for order in orders:
            # 简单排产：顺序安排
            duration = timedelta(hours=float(order.planned_hours or 8))
            
            SchedulingResult.objects.create(
                scenario=scenario,
                production_order=order,
                work_center=order.work_center,
                scheduled_start=current_time,
                scheduled_end=current_time + duration,
                operation_sequence=1,
                operation_name='生产',
                priority_score=order.priority,
                created_by=self.request.user
            )
            
            current_time += duration + timedelta(hours=1)  # 1小时间隔
        
        return True
    
    def _calculate_objectives(self, scenario):
        """计算目标值"""
        results = scenario.results.all()
        
        objectives = {
            'makespan': 0,  # 完工时间跨度
            'tardiness': 0,  # 延误
            'utilization': 0,  # 利用率
        }
        
        if results.exists():
            earliest = results.aggregate(min=Min('scheduled_start'))['min']
            latest = results.aggregate(max=Max('scheduled_end'))['max']
            if earliest and latest:
                objectives['makespan'] = (latest - earliest).total_seconds() / 3600
        
        return objectives
    
    def _detect_conflicts(self, scenario):
        """检测资源冲突"""
        results = scenario.results.order_by('scheduled_start')
        
        # 简单检测：同一工作中心的时间重叠
        work_center_schedules = {}
        
        for result in results:
            if result.work_center_id:
                wc_id = result.work_center_id
                if wc_id not in work_center_schedules:
                    work_center_schedules[wc_id] = []
                work_center_schedules[wc_id].append(result)
        
        for wc_id, schedules in work_center_schedules.items():
            for i, s1 in enumerate(schedules):
                for s2 in schedules[i+1:]:
                    if s1.scheduled_end > s2.scheduled_start:
                        ResourceConflict.objects.create(
                            scenario=scenario,
                            conflict_type='EQUIPMENT_OVERLAP',
                            resource_type='WorkCenter',
                            resource_id=wc_id,
                            resource_name=s1.work_center.name if s1.work_center else '',
                            conflict_start=s2.scheduled_start,
                            conflict_end=s1.scheduled_end,
                            orders_involved=[
                                s1.production_order.order_no,
                                s2.production_order.order_no
                            ],
                            severity='HIGH',
                            created_by=self.request.user
                        )
    
    def _analyze_bottlenecks(self, scenario):
        """分析瓶颈"""
        # 简化实现：统计各工作中心利用率
        from apps.production.models import WorkCenter
        
        total_hours = (scenario.end_date - scenario.start_date).days * 8
        
        for wc in WorkCenter.objects.filter(is_deleted=False):
            wc_results = scenario.results.filter(work_center=wc)
            if wc_results.exists():
                scheduled_hours = sum([
                    (r.scheduled_end - r.scheduled_start).total_seconds() / 3600
                    for r in wc_results
                ])
                utilization = (scheduled_hours / total_hours * 100) if total_hours > 0 else 0
                
                if utilization > 80:  # 高利用率可能是瓶颈
                    BottleneckAnalysis.objects.create(
                        scenario=scenario,
                        resource_type='WORK_CENTER',
                        resource_id=wc.id,
                        resource_name=wc.name,
                        utilization_rate=min(utilization, 100),
                        queue_length=wc_results.count(),
                        improvement_suggestions=[
                            '考虑增加该工作中心产能',
                            '优化工序安排减少等待',
                            '考虑外协部分任务'
                        ],
                        created_by=self.request.user
                    )
    
    def _calculate_score(self, scenario):
        """计算综合评分"""
        score = 100.0
        
        # 扣除冲突分数
        conflicts = scenario.conflicts.filter(is_resolved=False)
        score -= conflicts.filter(severity='CRITICAL').count() * 20
        score -= conflicts.filter(severity='HIGH').count() * 10
        score -= conflicts.filter(severity='MEDIUM').count() * 5
        score -= conflicts.filter(severity='LOW').count() * 2
        
        return max(score, 0)
    
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """应用排产结果"""
        scenario = self.get_object()
        
        if scenario.status != 'COMPLETED':
            return Response({'error': '只能应用已完成的排产'}, status=400)
        
        # 更新生产订单计划时间
        for result in scenario.results.all():
            order = result.production_order
            order.planned_start_date = result.scheduled_start.date()
            order.planned_end_date = result.scheduled_end.date()
            order.save(update_fields=['planned_start_date', 'planned_end_date'])
        
        scenario.status = 'APPLIED'
        scenario.save()
        
        return Response({
            'message': '排产结果已应用',
            'updated_orders': scenario.results.count()
        })
    
    @action(detail=False, methods=['get'])
    def gantt_data(self, request):
        """甘特图数据"""
        scenario_id = request.query_params.get('scenario_id')
        
        if not scenario_id:
            return Response({'error': '请指定排产场景'}, status=400)
        
        results = SchedulingResult.objects.filter(
            scenario_id=scenario_id
        ).select_related('production_order', 'work_center')
        
        gantt_items = []
        for r in results:
            gantt_items.append({
                'id': r.id,
                'order_no': r.production_order.order_no,
                'order_name': r.production_order.product_name,
                'resource': r.work_center.name if r.work_center else '未分配',
                'start': r.scheduled_start.isoformat(),
                'end': r.scheduled_end.isoformat(),
                'priority': r.priority_score,
            })
        
        return Response(gantt_items)


class ResourceConflictViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """资源冲突管理"""
    queryset = ResourceConflict.objects.filter(is_deleted=False)
    serializer_class = ResourceConflictSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['scenario', 'conflict_type', 'severity', 'is_resolved']
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决冲突"""
        conflict = self.get_object()
        conflict.is_resolved = True
        conflict.resolution_notes = request.data.get('notes', '')
        conflict.save()
        return Response(ResourceConflictSerializer(conflict).data)


class BottleneckAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """瓶颈分析"""
    queryset = BottleneckAnalysis.objects.filter(is_deleted=False)
    serializer_class = BottleneckAnalysisSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['scenario', 'resource_type']


class SchedulingComparisonViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排产对比管理"""
    queryset = SchedulingComparison.objects.filter(is_deleted=False)
    serializer_class = SchedulingComparisonSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """执行对比分析"""
        comparison = self.get_object()
        scenarios = comparison.scenarios.all()
        
        if scenarios.count() < 2:
            return Response({'error': '至少需要2个场景进行对比'}, status=400)
        
        metrics = {
            'scenarios': [],
            'best': {}
        }
        
        for scenario in scenarios:
            scenario_metrics = {
                'id': scenario.id,
                'name': scenario.name,
                'score': float(scenario.total_score),
                'conflicts': scenario.conflicts.filter(is_resolved=False).count(),
                'makespan': scenario.objective_values.get('makespan', 0),
            }
            metrics['scenarios'].append(scenario_metrics)
        
        # 找出最优
        best_scenario = max(metrics['scenarios'], key=lambda x: x['score'])
        metrics['best'] = best_scenario
        
        comparison.comparison_metrics = metrics
        comparison.winner_scenario_id = best_scenario['id']
        comparison.save()
        
        return Response(SchedulingComparisonSerializer(comparison).data)
