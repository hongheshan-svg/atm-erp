"""
项目健康度看板模块
Project Health Dashboard - 综合评分、预警等级、趋势预测
"""

from django.db import models
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import BaseModel


class ProjectHealthScore(BaseModel):
    """项目健康度评分记录"""

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='health_scores', verbose_name='项目'
    )
    score_date = models.DateField('评分日期')

    # 各维度得分 (0-100)
    schedule_score = models.IntegerField('进度得分', default=100)
    cost_score = models.IntegerField('成本得分', default=100)
    quality_score = models.IntegerField('质量得分', default=100)
    risk_score = models.IntegerField('风险得分', default=100)
    resource_score = models.IntegerField('资源得分', default=100)

    # 综合得分
    overall_score = models.IntegerField('综合得分', default=100)

    # 健康等级
    HEALTH_LEVEL_CHOICES = [
        ('GREEN', '健康'),
        ('YELLOW', '注意'),
        ('ORANGE', '警告'),
        ('RED', '危险'),
    ]
    health_level = models.CharField('健康等级', max_length=20, choices=HEALTH_LEVEL_CHOICES, default='GREEN')

    # 各维度详情
    schedule_details = models.JSONField('进度详情', default=dict)
    cost_details = models.JSONField('成本详情', default=dict)
    quality_details = models.JSONField('质量详情', default=dict)
    risk_details = models.JSONField('风险详情', default=dict)
    resource_details = models.JSONField('资源详情', default=dict)

    # 建议
    recommendations = models.JSONField('改进建议', default=list)

    class Meta:
        db_table = 'project_health_score'
        verbose_name = '项目健康度评分'
        unique_together = ['project', 'score_date']
        ordering = ['-score_date']


class ProjectHealthAlert(BaseModel):
    """项目健康预警"""

    ALERT_TYPE_CHOICES = [
        ('SCHEDULE', '进度预警'),
        ('COST', '成本预警'),
        ('QUALITY', '质量预警'),
        ('RISK', '风险预警'),
        ('RESOURCE', '资源预警'),
    ]

    SEVERITY_CHOICES = [
        ('INFO', '提示'),
        ('WARNING', '警告'),
        ('CRITICAL', '严重'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='health_alerts', verbose_name='项目'
    )
    alert_type = models.CharField('预警类型', max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField('严重程度', max_length=20, choices=SEVERITY_CHOICES, default='WARNING')

    title = models.CharField('预警标题', max_length=200)
    description = models.TextField('预警描述')
    metric_name = models.CharField('指标名称', max_length=100)
    current_value = models.CharField('当前值', max_length=100)
    threshold_value = models.CharField('阈值', max_length=100)

    # 状态
    is_active = models.BooleanField('是否激活', default=True)
    acknowledged = models.BooleanField('已确认', default=False)
    acknowledged_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_health_alerts',
        verbose_name='确认人',
    )
    acknowledged_at = models.DateTimeField('确认时间', null=True, blank=True)

    # 解决
    resolved = models.BooleanField('已解决', default=False)
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)
    resolution = models.TextField('解决措施', blank=True)

    class Meta:
        db_table = 'project_health_alert'
        verbose_name = '项目健康预警'
        ordering = ['-created_at']


class ProjectHealthService:
    """项目健康度计算服务"""

    @staticmethod
    def calculate_schedule_score(project):
        """计算进度得分"""
        from apps.projects.models import ProjectTask

        today = timezone.now().date()
        score = 100
        details = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'overdue_tasks': 0,
            'completion_rate': 0,
            'schedule_variance': 0,
        }

        tasks = ProjectTask.objects.filter(project=project, is_deleted=False)
        details['total_tasks'] = tasks.count()

        if details['total_tasks'] == 0:
            return score, details

        # 完成率
        details['completed_tasks'] = tasks.filter(status='COMPLETED').count()
        details['completion_rate'] = round(details['completed_tasks'] / details['total_tasks'] * 100, 1)

        # 逾期任务
        details['overdue_tasks'] = tasks.filter(status__in=['TODO', 'IN_PROGRESS'], end_date__lt=today).count()

        # 进度偏差
        if project.end_date and project.start_date:
            total_days = (project.end_date - project.start_date).days or 1
            elapsed_days = (today - project.start_date).days
            expected_progress = min(100, elapsed_days / total_days * 100)
            actual_progress = float(project.progress or 0)
            details['schedule_variance'] = actual_progress - expected_progress

        # 计算得分
        # 逾期任务扣分
        if details['overdue_tasks'] > 0:
            score -= min(30, details['overdue_tasks'] * 5)

        # 进度偏差扣分
        if details['schedule_variance'] < -20:
            score -= 30
        elif details['schedule_variance'] < -10:
            score -= 20
        elif details['schedule_variance'] < 0:
            score -= 10

        return max(0, score), details

    @staticmethod
    def calculate_cost_score(project):
        """计算成本得分"""
        score = 100
        details = {
            'budget_total': float(project.budget_total or 0),
            'actual_cost': 0,
            'budget_usage': 0,
            'cost_variance': 0,
            'forecast_at_completion': 0,
        }

        # 获取实际成本
        actual_material = float(project.get_actual_material_cost() or 0)
        actual_labor = float(project.get_actual_labor_cost() or 0)
        actual_expense = float(project.get_actual_expense_cost() or 0)
        details['actual_cost'] = actual_material + actual_labor + actual_expense

        if details['budget_total'] > 0:
            details['budget_usage'] = round(details['actual_cost'] / details['budget_total'] * 100, 1)

            # 基于进度的预期成本
            progress = float(project.progress or 0)
            expected_cost = details['budget_total'] * progress / 100 if progress > 0 else 0

            if expected_cost > 0:
                details['cost_variance'] = round((details['actual_cost'] - expected_cost) / expected_cost * 100, 1)

            # 完工估算
            if progress > 0:
                details['forecast_at_completion'] = round(details['actual_cost'] / progress * 100, 2)

        # 计算得分
        if details['budget_usage'] > 120:
            score -= 40
        elif details['budget_usage'] > 100:
            score -= 25
        elif details['budget_usage'] > 90:
            score -= 10

        if details['cost_variance'] > 30:
            score -= 20
        elif details['cost_variance'] > 15:
            score -= 10

        return max(0, score), details

    @staticmethod
    def calculate_quality_score(project):
        """计算质量得分"""
        score = 100
        details = {
            'debug_issues': 0,
            'critical_issues': 0,
            'ecn_count': 0,
            'inspection_pass_rate': 100,
        }

        # 调试问题
        from apps.projects.debug_management import DebugIssue

        issues = DebugIssue.objects.filter(plan__project=project, is_deleted=False).exclude(
            status__in=['RESOLVED', 'CLOSED']
        )

        details['debug_issues'] = issues.count()
        details['critical_issues'] = issues.filter(severity='CRITICAL').count()

        # ECN数量
        from apps.projects.ecn_enhanced import ECNChangeRequest

        details['ecn_count'] = ECNChangeRequest.objects.filter(project=project, is_deleted=False).count()

        # 计算得分
        if details['critical_issues'] > 0:
            score -= min(30, details['critical_issues'] * 10)

        if details['debug_issues'] > 5:
            score -= 20
        elif details['debug_issues'] > 2:
            score -= 10

        if details['ecn_count'] > 5:
            score -= 15
        elif details['ecn_count'] > 2:
            score -= 5

        return max(0, score), details

    @staticmethod
    def calculate_risk_score(project):
        """计算风险得分"""
        score = 100
        details = {
            'open_risks': 0,
            'high_risks': 0,
            'overdue_milestones': 0,
            'dependency_issues': 0,
        }

        today = timezone.now().date()

        # 逾期里程碑
        from apps.projects.models import Milestone

        details['overdue_milestones'] = Milestone.objects.filter(
            project=project, is_deleted=False, status__in=['PENDING', 'IN_PROGRESS'], planned_date__lt=today
        ).count()

        # 计算得分
        if details['overdue_milestones'] > 2:
            score -= 30
        elif details['overdue_milestones'] > 0:
            score -= 15

        return max(0, score), details

    @staticmethod
    def calculate_resource_score(project):
        """计算资源得分"""
        score = 100
        details = {
            'team_members': 0,
            'workload_balance': 100,
            'skill_coverage': 100,
        }

        # 项目成员数
        from apps.projects.models import ProjectMember

        details['team_members'] = ProjectMember.objects.filter(project=project, is_deleted=False).count()

        if details['team_members'] == 0:
            score -= 20

        return max(0, score), details

    @classmethod
    def calculate_overall_score(cls, project):
        """计算综合得分"""
        schedule_score, schedule_details = cls.calculate_schedule_score(project)
        cost_score, cost_details = cls.calculate_cost_score(project)
        quality_score, quality_details = cls.calculate_quality_score(project)
        risk_score, risk_details = cls.calculate_risk_score(project)
        resource_score, resource_details = cls.calculate_resource_score(project)

        # 权重
        weights = {
            'schedule': 0.25,
            'cost': 0.25,
            'quality': 0.25,
            'risk': 0.15,
            'resource': 0.10,
        }

        overall = (
            schedule_score * weights['schedule']
            + cost_score * weights['cost']
            + quality_score * weights['quality']
            + risk_score * weights['risk']
            + resource_score * weights['resource']
        )
        overall_score = round(overall)

        # 确定健康等级
        if overall_score >= 80:
            health_level = 'GREEN'
        elif overall_score >= 60:
            health_level = 'YELLOW'
        elif overall_score >= 40:
            health_level = 'ORANGE'
        else:
            health_level = 'RED'

        # 生成建议
        recommendations = []
        if schedule_score < 70:
            recommendations.append('进度落后，建议增加资源或调整计划')
        if cost_score < 70:
            recommendations.append('成本超支风险，建议控制开支或申请追加预算')
        if quality_score < 70:
            recommendations.append('质量问题较多，建议加强质量控制')
        if risk_score < 70:
            recommendations.append('存在较多风险，建议尽快制定应对措施')
        if resource_score < 70:
            recommendations.append('资源配置不足，建议补充人员')

        return {
            'schedule_score': schedule_score,
            'cost_score': cost_score,
            'quality_score': quality_score,
            'risk_score': risk_score,
            'resource_score': resource_score,
            'overall_score': overall_score,
            'health_level': health_level,
            'schedule_details': schedule_details,
            'cost_details': cost_details,
            'quality_details': quality_details,
            'risk_details': risk_details,
            'resource_details': resource_details,
            'recommendations': recommendations,
        }

    @classmethod
    def save_health_score(cls, project):
        """保存健康度评分"""
        today = timezone.now().date()
        scores = cls.calculate_overall_score(project)

        health_score, created = ProjectHealthScore.objects.update_or_create(
            project=project,
            score_date=today,
            defaults={
                'schedule_score': scores['schedule_score'],
                'cost_score': scores['cost_score'],
                'quality_score': scores['quality_score'],
                'risk_score': scores['risk_score'],
                'resource_score': scores['resource_score'],
                'overall_score': scores['overall_score'],
                'health_level': scores['health_level'],
                'schedule_details': scores['schedule_details'],
                'cost_details': scores['cost_details'],
                'quality_details': scores['quality_details'],
                'risk_details': scores['risk_details'],
                'resource_details': scores['resource_details'],
                'recommendations': scores['recommendations'],
            },
        )

        # 生成预警
        cls.generate_alerts(project, scores)

        return health_score

    @classmethod
    def generate_alerts(cls, project, scores):
        """生成健康预警"""
        alerts_to_create = []

        # 进度预警
        if scores['schedule_score'] < 60:
            alerts_to_create.append(
                {
                    'alert_type': 'SCHEDULE',
                    'severity': 'CRITICAL' if scores['schedule_score'] < 40 else 'WARNING',
                    'title': '进度严重落后' if scores['schedule_score'] < 40 else '进度落后',
                    'description': f"项目进度得分仅{scores['schedule_score']}分",
                    'metric_name': '进度得分',
                    'current_value': str(scores['schedule_score']),
                    'threshold_value': '60',
                }
            )

        # 成本预警
        if scores['cost_score'] < 60:
            alerts_to_create.append(
                {
                    'alert_type': 'COST',
                    'severity': 'CRITICAL' if scores['cost_score'] < 40 else 'WARNING',
                    'title': '成本严重超支' if scores['cost_score'] < 40 else '成本超支风险',
                    'description': f"项目成本得分仅{scores['cost_score']}分",
                    'metric_name': '成本得分',
                    'current_value': str(scores['cost_score']),
                    'threshold_value': '60',
                }
            )

        # 质量预警
        if scores['quality_score'] < 60:
            alerts_to_create.append(
                {
                    'alert_type': 'QUALITY',
                    'severity': 'CRITICAL' if scores['quality_score'] < 40 else 'WARNING',
                    'title': '质量问题严重' if scores['quality_score'] < 40 else '质量问题较多',
                    'description': f"项目质量得分仅{scores['quality_score']}分",
                    'metric_name': '质量得分',
                    'current_value': str(scores['quality_score']),
                    'threshold_value': '60',
                }
            )

        # 创建预警
        for alert_data in alerts_to_create:
            # 检查是否已存在相同预警
            existing = ProjectHealthAlert.objects.filter(
                project=project, alert_type=alert_data['alert_type'], is_active=True, resolved=False
            ).first()

            if not existing:
                ProjectHealthAlert.objects.create(project=project, **alert_data)


# ==================== API Views ====================


class ProjectHealthDashboardView(APIView):
    """项目健康度看板"""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id=None):
        from apps.projects.models import Project

        if project_id:
            # 单个项目详情
            try:
                project = Project.objects.get(pk=project_id, is_deleted=False)
            except Project.DoesNotExist:
                return Response({'error': '项目不存在'}, status=404)

            scores = ProjectHealthService.calculate_overall_score(project)

            # 历史趋势
            history = ProjectHealthScore.objects.filter(project=project).order_by('-score_date')[:30]

            trend = [
                {
                    'date': h.score_date,
                    'overall': h.overall_score,
                    'schedule': h.schedule_score,
                    'cost': h.cost_score,
                    'quality': h.quality_score,
                }
                for h in reversed(list(history))
            ]

            # 活跃预警
            alerts = ProjectHealthAlert.objects.filter(project=project, is_active=True, resolved=False).order_by(
                '-severity', '-created_at'
            )

            return Response(
                {
                    'project': {
                        'id': project.id,
                        'name': project.name,
                        'code': project.code,
                        'status': project.status,
                        'progress': project.progress,
                    },
                    'scores': scores,
                    'trend': trend,
                    'alerts': [
                        {
                            'id': a.id,
                            'type': a.alert_type,
                            'severity': a.severity,
                            'title': a.title,
                            'description': a.description,
                            'created_at': a.created_at,
                        }
                        for a in alerts
                    ],
                }
            )

        else:
            # 所有项目概览
            projects = Project.objects.filter(status__in=['IN_PROGRESS', 'ACTIVE', 'TESTING'], is_deleted=False)

            overview = []
            health_distribution = {'GREEN': 0, 'YELLOW': 0, 'ORANGE': 0, 'RED': 0}

            for project in projects:
                scores = ProjectHealthService.calculate_overall_score(project)
                health_distribution[scores['health_level']] += 1

                overview.append(
                    {
                        'id': project.id,
                        'name': project.name,
                        'code': project.code,
                        'manager_name': project.manager.get_full_name() if project.manager else '',
                        'progress': project.progress,
                        'overall_score': scores['overall_score'],
                        'health_level': scores['health_level'],
                        'schedule_score': scores['schedule_score'],
                        'cost_score': scores['cost_score'],
                        'quality_score': scores['quality_score'],
                        'recommendations': scores['recommendations'][:2],
                    }
                )

            # 按健康度排序
            overview.sort(key=lambda x: x['overall_score'])

            # 统计
            total_alerts = ProjectHealthAlert.objects.filter(
                is_active=True, resolved=False, project__status__in=['IN_PROGRESS', 'ACTIVE', 'TESTING']
            ).count()

            critical_alerts = ProjectHealthAlert.objects.filter(
                is_active=True,
                resolved=False,
                severity='CRITICAL',
                project__status__in=['IN_PROGRESS', 'ACTIVE', 'TESTING'],
            ).count()

            return Response(
                {
                    'summary': {
                        'total_projects': len(overview),
                        'health_distribution': health_distribution,
                        'total_alerts': total_alerts,
                        'critical_alerts': critical_alerts,
                        'avg_score': round(sum(p['overall_score'] for p in overview) / len(overview), 1)
                        if overview
                        else 0,
                    },
                    'projects': overview,
                }
            )


class ProjectHealthAlertView(APIView):
    """项目健康预警管理"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取预警列表"""
        project_id = request.query_params.get('project')
        severity = request.query_params.get('severity')
        alert_type = request.query_params.get('type')

        qs = ProjectHealthAlert.objects.filter(is_active=True, resolved=False, is_deleted=False)

        if project_id:
            qs = qs.filter(project_id=project_id)
        if severity:
            qs = qs.filter(severity=severity)
        if alert_type:
            qs = qs.filter(alert_type=alert_type)

        alerts = qs.select_related('project').order_by('-severity', '-created_at')[:100]

        return Response(
            [
                {
                    'id': a.id,
                    'project_id': a.project_id,
                    'project_name': a.project.name,
                    'type': a.alert_type,
                    'severity': a.severity,
                    'title': a.title,
                    'description': a.description,
                    'metric_name': a.metric_name,
                    'current_value': a.current_value,
                    'threshold_value': a.threshold_value,
                    'acknowledged': a.acknowledged,
                    'created_at': a.created_at,
                }
                for a in alerts
            ]
        )

    def post(self, request):
        """确认或解决预警"""
        alert_id = request.data.get('id')
        action = request.data.get('action')

        try:
            alert = ProjectHealthAlert.objects.get(pk=alert_id)
        except ProjectHealthAlert.DoesNotExist:
            return Response({'error': '预警不存在'}, status=404)

        if action == 'acknowledge':
            alert.acknowledged = True
            alert.acknowledged_by = request.user
            alert.acknowledged_at = timezone.now()
            alert.save()
            return Response({'message': '已确认预警'})

        elif action == 'resolve':
            alert.resolved = True
            alert.resolved_at = timezone.now()
            alert.resolution = request.data.get('resolution', '')
            alert.is_active = False
            alert.save()
            return Response({'message': '已解决预警'})

        return Response({'error': '无效操作'}, status=400)


class ProjectHealthBatchCalculateView(APIView):
    """批量计算项目健康度"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """批量计算并保存"""
        from apps.projects.models import Project

        projects = Project.objects.filter(status__in=['IN_PROGRESS', 'ACTIVE', 'TESTING'], is_deleted=False)

        count = 0
        for project in projects:
            ProjectHealthService.save_health_score(project)
            count += 1

        return Response({'message': f'已计算{count}个项目的健康度'})
