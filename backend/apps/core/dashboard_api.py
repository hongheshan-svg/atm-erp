"""
综合仪表盘视图
Dashboard Views - 汇总ERP各模块关键数据

提供：
- 管理层概览
- 项目经理看板
- 销售看板
- 生产看板
- 财务看板
"""
from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ExecutiveDashboardView(APIView):
    """
    管理层仪表盘 - 全局视图
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        data = {
            'summary': self._get_summary(),
            'project_overview': self._get_project_overview(),
            'sales_overview': self._get_sales_overview(this_month_start),
            'production_overview': self._get_production_overview(),
            'finance_overview': self._get_finance_overview(this_month_start),
            'alerts': self._get_alerts(today),
        }

        return Response(data)

    def _get_summary(self):
        """核心指标概要"""
        from apps.projects.models import Project
        from apps.sales.models import SalesOrder

        return {
            'active_projects': Project.objects.filter(
                status__in=['IN_PROGRESS', 'TESTING'],
                is_deleted=False
            ).count(),
            'pending_orders': SalesOrder.objects.filter(
                status='CONFIRMED',
                is_deleted=False
            ).count(),
            'collection_rate': self._calc_collection_rate(),
            'on_time_delivery_rate': self._calc_delivery_rate(),
        }

    def _calc_collection_rate(self):
        """计算回款率"""
        from apps.finance.collection_models import CollectionPlan
        plans = CollectionPlan.objects.filter(is_deleted=False).aggregate(
            total=Sum('total_amount'),
            collected=Sum('collected_amount')
        )
        if plans['total'] and plans['total'] > 0:
            return round(float(plans['collected'] or 0) / float(plans['total']) * 100, 1)
        return 0

    def _calc_delivery_rate(self):
        """计算准时交付率"""
        from apps.projects.models import Project
        today = timezone.now().date()
        completed = Project.objects.filter(
            status='COMPLETED',
            is_deleted=False
        ).exclude(actual_end_date__isnull=True)

        total = completed.count()
        if total == 0:
            return 100

        on_time = completed.filter(actual_end_date__lte=F('planned_end_date')).count()
        return round(on_time / total * 100, 1)

    def _get_project_overview(self):
        """项目概览"""
        from apps.projects.models import Project

        by_status = Project.objects.filter(is_deleted=False).values('status').annotate(
            count=Count('id')
        )

        return {
            'by_status': {item['status']: item['count'] for item in by_status},
            'total': sum(item['count'] for item in by_status),
        }

    def _get_sales_overview(self, month_start):
        """销售概览"""
        from apps.sales.crm_models import Opportunity
        from apps.sales.models import SalesOrder

        # 本月订单
        month_orders = SalesOrder.objects.filter(
            order_date__gte=month_start,
            is_deleted=False
        ).aggregate(
            count=Count('id'),
            amount=Sum('total_amount')
        )

        # 商机漏斗
        pipeline = Opportunity.objects.filter(
            is_deleted=False
        ).exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST']).aggregate(
            count=Count('id'),
            amount=Sum('weighted_amount')
        )

        return {
            'month_orders': month_orders['count'] or 0,
            'month_amount': float(month_orders['amount'] or 0),
            'pipeline_count': pipeline['count'] or 0,
            'pipeline_amount': float(pipeline['amount'] or 0),
        }

    def _get_production_overview(self):
        """生产概览"""
        from apps.production.models import ProductionPlan

        plans = ProductionPlan.objects.filter(is_deleted=False)

        return {
            'in_progress': plans.filter(status='IN_PROGRESS').count(),
            'pending': plans.filter(status__in=['DRAFT', 'CONFIRMED']).count(),
            'completed_this_month': plans.filter(
                status='COMPLETED',
                actual_end_date__month=timezone.now().month
            ).count(),
        }

    def _get_finance_overview(self, month_start):
        """财务概览"""
        from apps.finance.collection_models import CollectionMilestone

        today = timezone.now().date()

        # 逾期回款
        overdue = CollectionMilestone.objects.filter(
            status__in=['PENDING', 'PARTIAL'],
            planned_date__lt=today,
            is_deleted=False
        ).aggregate(
            count=Count('id'),
            amount=Sum(F('planned_amount') - F('collected_amount'))
        )

        # 本月预计回款
        month_due = CollectionMilestone.objects.filter(
            planned_date__gte=month_start,
            planned_date__lte=month_start.replace(day=28) + timedelta(days=4),  # 月末
            is_deleted=False
        ).aggregate(
            amount=Sum('planned_amount')
        )

        return {
            'overdue_count': overdue['count'] or 0,
            'overdue_amount': float(overdue['amount'] or 0),
            'month_due_amount': float(month_due['amount'] or 0),
        }

    def _get_alerts(self, today):
        """告警提醒"""
        alerts = []

        # 逾期项目
        from apps.projects.models import Project
        overdue_projects = Project.objects.filter(
            status__in=['IN_PROGRESS', 'TESTING'],
            planned_end_date__lt=today,
            is_deleted=False
        ).count()
        if overdue_projects > 0:
            alerts.append({
                'type': 'warning',
                'message': f'{overdue_projects}个项目已逾期',
                'module': 'projects'
            })

        # 逾期回款
        from apps.finance.collection_models import CollectionMilestone
        overdue_collections = CollectionMilestone.objects.filter(
            status__in=['PENDING', 'PARTIAL'],
            planned_date__lt=today,
            is_deleted=False
        ).count()
        if overdue_collections > 0:
            alerts.append({
                'type': 'error',
                'message': f'{overdue_collections}笔回款已逾期',
                'module': 'finance'
            })

        # 库存预警
        from apps.inventory.models import StockAlert
        stock_alerts = StockAlert.objects.filter(
            is_active=True,
            is_deleted=False
        ).count()
        if stock_alerts > 0:
            alerts.append({
                'type': 'warning',
                'message': f'{stock_alerts}项库存预警',
                'module': 'inventory'
            })

        return alerts


class ProjectManagerDashboardView(APIView):
    """
    项目经理看板
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        from apps.projects.models import Project, ProjectTask

        # 我负责的项目
        my_projects = Project.objects.filter(
            Q(manager=user) | Q(members__user=user),
            is_deleted=False
        ).distinct()

        # 项目状态分布
        project_status = my_projects.values('status').annotate(count=Count('id'))

        # 我的任务
        my_tasks = ProjectTask.objects.filter(
            assignee=user,
            is_deleted=False
        )

        # 即将到期的任务
        upcoming_tasks = my_tasks.filter(
            status__in=['TODO', 'IN_PROGRESS'],
            due_date__lte=today + timedelta(days=7)
        ).order_by('due_date')[:10]

        # 项目进度
        project_progress = my_projects.filter(
            status__in=['IN_PROGRESS', 'TESTING']
        ).values('id', 'name', 'project_no', 'progress', 'planned_end_date')[:10]

        data = {
            'my_projects_count': my_projects.count(),
            'active_projects': my_projects.filter(status__in=['IN_PROGRESS', 'TESTING']).count(),
            'project_status': {item['status']: item['count'] for item in project_status},
            'my_tasks': {
                'total': my_tasks.count(),
                'todo': my_tasks.filter(status='TODO').count(),
                'in_progress': my_tasks.filter(status='IN_PROGRESS').count(),
                'overdue': my_tasks.filter(status__in=['TODO', 'IN_PROGRESS'], due_date__lt=today).count(),
            },
            'upcoming_tasks': list(upcoming_tasks.values('id', 'name', 'due_date', 'priority', 'status')),
            'project_progress': list(project_progress),
        }

        return Response(data)


class SalesDashboardView(APIView):
    """
    销售看板
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        this_month = today.replace(day=1)

        from apps.sales.crm_models import Lead, Opportunity, OpportunityActivity
        from apps.sales.models import SalesOrder

        # 我的线索
        my_leads = Lead.objects.filter(owner=user, is_deleted=False)

        # 我的商机
        my_opportunities = Opportunity.objects.filter(owner=user, is_deleted=False)

        # 商机漏斗
        pipeline = my_opportunities.exclude(
            stage__in=['CLOSED_WON', 'CLOSED_LOST']
        ).values('stage').annotate(
            count=Count('id'),
            amount=Sum('estimated_amount'),
            weighted=Sum('weighted_amount')
        )

        # 本月业绩
        month_orders = SalesOrder.objects.filter(
            created_by=user,
            order_date__gte=this_month,
            is_deleted=False
        ).aggregate(
            count=Count('id'),
            amount=Sum('total_amount')
        )

        # 近期活动
        recent_activities = OpportunityActivity.objects.filter(
            recorded_by=user,
            is_deleted=False
        ).order_by('-activity_date')[:10]

        # 需要跟进的商机
        need_followup = my_opportunities.filter(
            stage__in=['QUALIFICATION', 'NEEDS_ANALYSIS', 'PROPOSAL', 'NEGOTIATION']
        ).order_by('expected_close_date')[:10]

        data = {
            'leads': {
                'total': my_leads.count(),
                'new': my_leads.filter(status='NEW').count(),
                'converted': my_leads.filter(status='CONVERTED').count(),
            },
            'opportunities': {
                'total': my_opportunities.count(),
                'active': my_opportunities.exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST']).count(),
                'won_this_month': my_opportunities.filter(
                    stage='CLOSED_WON',
                    actual_close_date__gte=this_month
                ).count(),
            },
            'pipeline': list(pipeline),
            'month_performance': {
                'orders': month_orders['count'] or 0,
                'amount': float(month_orders['amount'] or 0),
            },
            'recent_activities': list(recent_activities.values(
                'id', 'activity_type', 'subject', 'activity_date', 'opportunity__name'
            )),
            'need_followup': list(need_followup.values(
                'id', 'opportunity_no', 'name', 'stage', 'expected_close_date', 'estimated_amount'
            )),
        }

        return Response(data)


class ProductionDashboardView(APIView):
    """
    生产看板
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()

        from apps.production.models import DebugRecord, ProductionPlan, ProductionPlanProcess, QualityInspection

        # 生产计划状态
        plans = ProductionPlan.objects.filter(is_deleted=False)
        plan_status = plans.values('status').annotate(count=Count('id'))

        # 进行中的计划
        active_plans = plans.filter(status='IN_PROGRESS').order_by('-updated_at')[:10]

        # 今日工序
        today_processes = ProductionPlanProcess.objects.filter(
            plan__status='IN_PROGRESS',
            planned_start_date__lte=today,
            planned_end_date__gte=today,
            is_deleted=False
        )

        # 调试记录
        debug_records = DebugRecord.objects.filter(is_deleted=False)
        debug_stats = {
            'in_progress': debug_records.filter(status='IN_PROGRESS').count(),
            'completed': debug_records.filter(status='COMPLETED').count(),
            'pass_rate': self._calc_debug_pass_rate(debug_records),
        }

        # 质量检验
        inspections = QualityInspection.objects.filter(is_deleted=False)
        quality_stats = {
            'pending': inspections.filter(status='PENDING').count(),
            'in_progress': inspections.filter(status='IN_PROGRESS').count(),
            'pass_rate': self._calc_inspection_pass_rate(inspections),
        }

        data = {
            'plan_status': {item['status']: item['count'] for item in plan_status},
            'active_plans': list(active_plans.values(
                'id', 'plan_no', 'project__name', 'progress', 'planned_end_date'
            )),
            'today_processes': {
                'total': today_processes.count(),
                'in_progress': today_processes.filter(status='IN_PROGRESS').count(),
                'completed': today_processes.filter(status='COMPLETED').count(),
            },
            'debug_stats': debug_stats,
            'quality_stats': quality_stats,
        }

        return Response(data)

    def _calc_debug_pass_rate(self, queryset):
        completed = queryset.filter(status='COMPLETED')
        if completed.count() == 0:
            return 100
        passed = completed.filter(result='PASS').count()
        return round(passed / completed.count() * 100, 1)

    def _calc_inspection_pass_rate(self, queryset):
        completed = queryset.filter(status='COMPLETED')
        if completed.count() == 0:
            return 100
        passed = completed.filter(result='PASS').count()
        return round(passed / completed.count() * 100, 1)


class FinanceDashboardView(APIView):
    """
    财务看板
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        this_month = today.replace(day=1)

        from apps.finance.collection_models import CollectionMilestone, CollectionPlan, CollectionRecord
        from apps.finance.models import AccountPayable, AccountReceivable

        # 回款统计
        collection_stats = CollectionPlan.objects.filter(is_deleted=False).aggregate(
            total_amount=Sum('total_amount'),
            collected_amount=Sum('collected_amount')
        )

        # 逾期回款
        overdue_milestones = CollectionMilestone.objects.filter(
            status__in=['PENDING', 'PARTIAL'],
            planned_date__lt=today,
            is_deleted=False
        )

        # 本月到期
        month_due = CollectionMilestone.objects.filter(
            planned_date__gte=this_month,
            planned_date__month=today.month,
            is_deleted=False
        )

        # 本月已收
        month_collected = CollectionRecord.objects.filter(
            collection_date__gte=this_month,
            is_deleted=False
        ).aggregate(amount=Sum('amount'))

        # 应收应付
        ar_stats = AccountReceivable.objects.filter(
            is_deleted=False
        ).aggregate(
            total=Sum('amount'),
            overdue=Sum('amount', filter=Q(status='OVERDUE'))
        )

        ap_stats = AccountPayable.objects.filter(
            is_deleted=False
        ).aggregate(
            total=Sum('amount'),
            overdue=Sum('amount', filter=Q(status='OVERDUE'))
        )

        data = {
            'collection': {
                'total_amount': float(collection_stats['total_amount'] or 0),
                'collected_amount': float(collection_stats['collected_amount'] or 0),
                'rate': round(
                    float(collection_stats['collected_amount'] or 0) /
                    float(collection_stats['total_amount'] or 1) * 100, 1
                ),
            },
            'overdue': {
                'count': overdue_milestones.count(),
                'amount': float(overdue_milestones.aggregate(
                    total=Sum(F('planned_amount') - F('collected_amount'))
                )['total'] or 0),
            },
            'month_due': {
                'count': month_due.count(),
                'amount': float(month_due.aggregate(total=Sum('planned_amount'))['total'] or 0),
            },
            'month_collected': float(month_collected['amount'] or 0),
            'receivables': {
                'total': float(ar_stats['total'] or 0),
                'overdue': float(ar_stats['overdue'] or 0),
            },
            'payables': {
                'total': float(ap_stats['total'] or 0),
                'overdue': float(ap_stats['overdue'] or 0),
            },
        }

        return Response(data)
