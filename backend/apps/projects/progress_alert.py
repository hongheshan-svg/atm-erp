"""
项目进度预警
Project Progress Alert
监控项目进度，自动预警延期风险
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class ProjectAlertRule(BaseModel):
    """
    项目预警规则
    """

    ALERT_TYPES = [
        ('PROGRESS', '进度预警'),
        ('BUDGET', '预算预警'),
        ('TIMELINE', '时间预警'),
        ('TASK', '任务预警'),
        ('RESOURCE', '资源预警'),
    ]

    SEVERITY_LEVELS = [
        ('INFO', '提示'),
        ('WARNING', '警告'),
        ('CRITICAL', '严重'),
    ]

    name = models.CharField(max_length=100, verbose_name='规则名称')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, verbose_name='预警类型')
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='WARNING', verbose_name='严重程度')

    # 规则条件
    condition = models.JSONField(
        default=dict, verbose_name='条件配置', help_text='{"field": "progress_gap", "operator": ">", "value": 10}'
    )

    # 通知设置
    notify_roles = models.JSONField(default=list, blank=True, verbose_name='通知角色')
    notify_users = models.JSONField(default=list, blank=True, verbose_name='通知用户')
    notify_pm = models.BooleanField(default=True, verbose_name='通知项目经理')

    is_active = models.BooleanField(default=True, verbose_name='启用')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'project_alert_rule'
        verbose_name = '预警规则'
        verbose_name_plural = verbose_name
        ordering = ['alert_type', 'severity']

    def __str__(self):
        return self.name


class ProjectAlert(BaseModel):
    """
    项目预警记录
    """

    STATUS_CHOICES = [
        ('ACTIVE', '活跃'),
        ('ACKNOWLEDGED', '已确认'),
        ('RESOLVED', '已解决'),
        ('IGNORED', '已忽略'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='alerts', verbose_name='项目'
    )
    rule = models.ForeignKey(
        ProjectAlertRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts',
        verbose_name='预警规则',
    )

    alert_type = models.CharField(max_length=20, verbose_name='预警类型')
    severity = models.CharField(max_length=20, verbose_name='严重程度')
    title = models.CharField(max_length=200, verbose_name='预警标题')
    description = models.TextField(verbose_name='预警描述')

    # 预警数据
    alert_data = models.JSONField(default=dict, blank=True, verbose_name='预警数据')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', verbose_name='状态')

    # 处理
    acknowledged_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts',
        verbose_name='确认人',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    resolution = models.TextField(blank=True, verbose_name='解决方案')

    class Meta:
        db_table = 'project_alert'
        verbose_name = '项目预警'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.name} - {self.title}'


class AlertService:
    """预警服务"""

    @staticmethod
    def check_project_alerts(project=None):
        """检查项目预警"""
        from apps.projects.models import Project, ProjectTask

        alerts_created = []

        # 获取需要检查的项目
        if project:
            projects = [project]
        else:
            projects = Project.objects.filter(status__in=['PLANNING', 'IN_PROGRESS'], is_deleted=False)

        for proj in projects:
            # 1. 进度预警：实际进度落后计划进度
            expected_progress = AlertService._calculate_expected_progress(proj)
            actual_progress = AlertService._calculate_actual_progress(proj)
            progress_gap = expected_progress - actual_progress

            if progress_gap > 10:  # 落后超过10%
                alert = AlertService._create_alert(
                    project=proj,
                    alert_type='PROGRESS',
                    severity='WARNING' if progress_gap <= 20 else 'CRITICAL',
                    title=f'项目进度落后 {progress_gap:.1f}%',
                    description=f'项目 {proj.name} 计划进度 {expected_progress:.1f}%，实际进度 {actual_progress:.1f}%，落后 {progress_gap:.1f}%',
                    alert_data={
                        'expected_progress': expected_progress,
                        'actual_progress': actual_progress,
                        'gap': progress_gap,
                    },
                )
                if alert:
                    alerts_created.append(alert)

            # 2. 时间预警：距离截止日期不足
            if proj.end_date:
                days_remaining = (proj.end_date - date.today()).days
                remaining_work = 100 - actual_progress

                if days_remaining > 0 and remaining_work > 0:
                    # 按当前进度预估能否按时完成
                    if proj.start_date:
                        elapsed_days = (date.today() - proj.start_date).days
                        if elapsed_days > 0:
                            daily_progress = actual_progress / elapsed_days
                            if daily_progress > 0:
                                days_needed = remaining_work / daily_progress
                                if days_needed > days_remaining:
                                    alert = AlertService._create_alert(
                                        project=proj,
                                        alert_type='TIMELINE',
                                        severity='WARNING' if days_remaining > 7 else 'CRITICAL',
                                        title=f'项目可能延期 {int(days_needed - days_remaining)} 天',
                                        description=f'项目 {proj.name} 按当前进度预计需要 {int(days_needed)} 天完成，但仅剩 {days_remaining} 天',
                                        alert_data={
                                            'days_remaining': days_remaining,
                                            'days_needed': days_needed,
                                            'daily_progress': daily_progress,
                                        },
                                    )
                                    if alert:
                                        alerts_created.append(alert)

                # 即将到期预警
                if 0 < days_remaining <= 7 and actual_progress < 90:
                    alert = AlertService._create_alert(
                        project=proj,
                        alert_type='TIMELINE',
                        severity='CRITICAL',
                        title=f'项目即将到期，仅剩 {days_remaining} 天',
                        description=f'项目 {proj.name} 将在 {days_remaining} 天后到期，当前进度仅 {actual_progress}%',
                        alert_data={'days_remaining': days_remaining, 'progress': actual_progress},
                    )
                    if alert:
                        alerts_created.append(alert)

            # 3. 任务预警：逾期任务
            overdue_tasks = ProjectTask.objects.filter(
                project=proj, status__in=['PENDING', 'IN_PROGRESS'], end_date__lt=date.today(), is_deleted=False
            ).count()

            if overdue_tasks > 0:
                alert = AlertService._create_alert(
                    project=proj,
                    alert_type='TASK',
                    severity='WARNING' if overdue_tasks < 5 else 'CRITICAL',
                    title=f'{overdue_tasks} 个任务已逾期',
                    description=f'项目 {proj.name} 有 {overdue_tasks} 个任务已超过截止日期',
                    alert_data={'overdue_count': overdue_tasks},
                )
                if alert:
                    alerts_created.append(alert)

            # 4. 预算预警（如果有预算数据）
            if proj.budget_total and proj.budget_total > 0:
                # 获取实际成本
                actual_cost = Decimal('0')

                # 从财务模块获取成本（如果存在）
                try:
                    from apps.finance.models import Expense

                    actual_cost = Expense.objects.filter(project=proj, status='APPROVED', is_deleted=False).aggregate(
                        total=Sum('amount')
                    )['total'] or Decimal('0')
                except:
                    pass

                if actual_cost > 0:
                    budget_usage = float(actual_cost / proj.budget_total * 100)

                    if budget_usage > 90:
                        alert = AlertService._create_alert(
                            project=proj,
                            alert_type='BUDGET',
                            severity='CRITICAL' if budget_usage > 100 else 'WARNING',
                            title=f'预算使用率 {budget_usage:.1f}%',
                            description=f'项目 {proj.name} 预算 {proj.budget_total}，已使用 {actual_cost}，使用率 {budget_usage:.1f}%',
                            alert_data={
                                'budget': float(proj.budget_total),
                                'actual': float(actual_cost),
                                'usage_rate': budget_usage,
                            },
                        )
                        if alert:
                            alerts_created.append(alert)

        return alerts_created

    @staticmethod
    def _calculate_actual_progress(project):
        """实际进度 = 项目下任务 progress_percent 的平均（无任务则 0）。
        Project 本身无 progress 字段，原 getattr(proj,'progress',0) 恒为 0 导致进度/时间预警系统性误报（审计 medium）。"""
        from apps.projects.models import ProjectTask

        result = ProjectTask.objects.filter(project=project, is_deleted=False).aggregate(avg=Avg('progress_percent'))
        return float(result['avg'] or 0)

    @staticmethod
    def _calculate_expected_progress(project):
        """计算项目预期进度"""
        if not project.start_date or not project.end_date:
            return 0

        total_days = (project.end_date - project.start_date).days
        elapsed_days = (date.today() - project.start_date).days

        if total_days <= 0:
            return 100

        expected = min(elapsed_days / total_days * 100, 100)
        return max(expected, 0)

    @staticmethod
    def _create_alert(project, alert_type, severity, title, description, alert_data):
        """创建预警记录（避免重复）"""
        # 检查是否已存在相同的活跃预警
        existing = ProjectAlert.objects.filter(
            project=project, alert_type=alert_type, status='ACTIVE', title=title
        ).exists()

        if existing:
            return None

        return ProjectAlert.objects.create(
            project=project,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            alert_data=alert_data,
        )


# =====================
# Serializers
# =====================


class ProjectAlertRuleSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = ProjectAlertRule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProjectAlertSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)

    class Meta:
        model = ProjectAlert
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'acknowledged_by', 'acknowledged_at', 'resolved_at']


class ProjectAlertListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ProjectAlert
        fields = [
            'id',
            'project',
            'project_name',
            'project_code',
            'alert_type',
            'severity',
            'title',
            'status',
            'status_display',
            'created_at',
        ]


# =====================
# ViewSets
# =====================


class ProjectAlertRuleViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """预警规则管理"""

    permission_module = 'projects'
    permission_resource = 'project_alert_rule'
    queryset = ProjectAlertRule.objects.filter(is_deleted=False)
    serializer_class = ProjectAlertRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['alert_type', 'severity', 'is_active']

    @action(detail=False, methods=['post'])
    def init_rules(self, request):
        """初始化默认规则"""
        rules = [
            ('进度落后10%预警', 'PROGRESS', 'WARNING', {'field': 'progress_gap', 'operator': '>', 'value': 10}),
            ('进度落后20%预警', 'PROGRESS', 'CRITICAL', {'field': 'progress_gap', 'operator': '>', 'value': 20}),
            ('即将到期预警', 'TIMELINE', 'WARNING', {'field': 'days_remaining', 'operator': '<', 'value': 7}),
            ('预算超支预警', 'BUDGET', 'WARNING', {'field': 'budget_usage', 'operator': '>', 'value': 90}),
            ('任务逾期预警', 'TASK', 'WARNING', {'field': 'overdue_tasks', 'operator': '>', 'value': 0}),
        ]

        created = 0
        for name, alert_type, severity, condition in rules:
            _, c = ProjectAlertRule.objects.get_or_create(
                name=name,
                defaults={
                    'alert_type': alert_type,
                    'severity': severity,
                    'condition': condition,
                    'created_by': request.user,
                },
            )
            if c:
                created += 1

        return Response({'success': True, 'created': created})


class ProjectAlertViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目预警管理"""

    permission_module = 'projects'
    permission_resource = 'project_alert'
    queryset = ProjectAlert.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'alert_type', 'severity', 'status']
    search_fields = ['title', 'description', 'project__name']
    ordering_fields = ['created_at', 'severity']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectAlertListSerializer
        return ProjectAlertSerializer

    @action(detail=False, methods=['post'])
    def check_all(self, request):
        """检查所有项目预警"""
        alerts = AlertService.check_project_alerts()
        return Response(
            {
                'success': True,
                'alerts_created': len(alerts),
                'alerts': ProjectAlertListSerializer(alerts, many=True).data,
            }
        )

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """确认预警"""
        alert = self.get_object()

        alert.status = 'ACKNOWLEDGED'
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()

        return Response(self.get_serializer(alert).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决预警"""
        alert = self.get_object()

        alert.status = 'RESOLVED'
        alert.resolved_at = timezone.now()
        alert.resolution = request.data.get('resolution', '')
        alert.save()

        return Response(self.get_serializer(alert).data)

    @action(detail=True, methods=['post'])
    def ignore(self, request, pk=None):
        """忽略预警"""
        alert = self.get_object()

        alert.status = 'IGNORED'
        alert.resolution = request.data.get('reason', '已忽略')
        alert.save()

        return Response(self.get_serializer(alert).data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取活跃预警"""
        alerts = self.get_queryset().filter(status='ACTIVE')
        return Response(ProjectAlertListSerializer(alerts, many=True).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """预警汇总"""
        qs = self.get_queryset().filter(status='ACTIVE')

        by_type = qs.values('alert_type').annotate(count=Count('id'))
        by_severity = qs.values('severity').annotate(count=Count('id'))
        by_project = qs.values('project__id', 'project__name').annotate(count=Count('id')).order_by('-count')[:10]

        return Response(
            {
                'total_active': qs.count(),
                'by_type': list(by_type),
                'by_severity': list(by_severity),
                'top_projects': list(by_project),
            }
        )
