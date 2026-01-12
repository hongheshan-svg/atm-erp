"""
工时统计报表
Timelog Report Service
"""
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.projects.models import TimeLog, Project, ProjectTask


class TimelogStatisticsView(APIView):
    """工时统计总览"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        this_week_start = today - timedelta(days=today.weekday())
        this_month_start = today.replace(day=1)
        
        # 基础查询
        base_qs = TimeLog.objects.filter(is_deleted=False)
        
        # 如果不是管理员，只看自己的
        if not user.is_superuser and not user.groups.filter(name__in=['admin', 'general_manager', 'project_manager']).exists():
            base_qs = base_qs.filter(user=user)
        
        # 今日工时
        today_hours = base_qs.filter(date=today).aggregate(
            total=Sum('hours')
        )['total'] or 0
        
        # 本周工时
        week_hours = base_qs.filter(date__gte=this_week_start).aggregate(
            total=Sum('hours')
        )['total'] or 0
        
        # 本月工时
        month_hours = base_qs.filter(date__gte=this_month_start).aggregate(
            total=Sum('hours')
        )['total'] or 0
        
        # 本月工时趋势（按天）
        daily_trend = base_qs.filter(
            date__gte=this_month_start
        ).annotate(
            date=TruncDate('date')
        ).values('date').annotate(
            hours=Sum('hours')
        ).order_by('date')
        
        # 按项目分布
        by_project = base_qs.filter(
            date__gte=this_month_start
        ).values(
            'project__name', 'project__code'
        ).annotate(
            hours=Sum('hours'),
            count=Count('id')
        ).order_by('-hours')[:10]
        
        # 按任务类型分布
        by_task_type = base_qs.filter(
            date__gte=this_month_start,
            task__isnull=False
        ).values(
            'task__task_type'
        ).annotate(
            hours=Sum('hours')
        ).order_by('-hours')
        
        return Response({
            'today_hours': today_hours,
            'week_hours': week_hours,
            'month_hours': month_hours,
            'daily_trend': list(daily_trend),
            'by_project': list(by_project),
            'by_task_type': list(by_task_type),
        })


class TimelogByUserView(APIView):
    """按用户统计工时"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        project_id = request.query_params.get('project')
        
        today = timezone.now().date()
        if not start_date:
            start_date = today.replace(day=1)
        if not end_date:
            end_date = today
        
        qs = TimeLog.objects.filter(
            is_deleted=False,
            date__gte=start_date,
            date__lte=end_date
        )
        
        if project_id:
            qs = qs.filter(project_id=project_id)
        
        # 按用户统计
        by_user = qs.values(
            'user__id', 'user__username', 'user__first_name', 'user__last_name'
        ).annotate(
            total_hours=Sum('hours'),
            work_days=Count('date', distinct=True),
            avg_hours_per_day=Avg('hours'),
            log_count=Count('id')
        ).order_by('-total_hours')
        
        # 计算平均值
        totals = qs.aggregate(
            total_hours=Sum('hours'),
            total_logs=Count('id'),
            unique_users=Count('user', distinct=True)
        )
        
        return Response({
            'by_user': list(by_user),
            'totals': totals,
            'period': {'start': start_date, 'end': end_date}
        })


class TimelogByProjectView(APIView):
    """按项目统计工时"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        user_id = request.query_params.get('user')
        
        today = timezone.now().date()
        if not start_date:
            start_date = today.replace(day=1)
        if not end_date:
            end_date = today
        
        qs = TimeLog.objects.filter(
            is_deleted=False,
            date__gte=start_date,
            date__lte=end_date
        )
        
        if user_id:
            qs = qs.filter(user_id=user_id)
        
        # 按项目统计
        by_project = qs.values(
            'project__id', 'project__code', 'project__name', 'project__status'
        ).annotate(
            total_hours=Sum('hours'),
            unique_users=Count('user', distinct=True),
            log_count=Count('id'),
            avg_hours_per_log=Avg('hours')
        ).order_by('-total_hours')
        
        # 项目工时与预算对比
        projects_with_budget = []
        for p in by_project:
            project = Project.objects.filter(id=p['project__id']).first()
            if project:
                budget_hours = getattr(project, 'budget_hours', 0) or 0
                p['budget_hours'] = budget_hours
                p['usage_rate'] = (p['total_hours'] / budget_hours * 100) if budget_hours > 0 else 0
            projects_with_budget.append(p)
        
        return Response({
            'by_project': projects_with_budget,
            'period': {'start': start_date, 'end': end_date}
        })


class TimelogWeeklyReportView(APIView):
    """周报统计"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user_id = request.query_params.get('user', request.user.id)
        weeks_back = int(request.query_params.get('weeks', 4))
        
        today = timezone.now().date()
        start_date = today - timedelta(weeks=weeks_back)
        
        qs = TimeLog.objects.filter(
            is_deleted=False,
            user_id=user_id,
            date__gte=start_date
        )
        
        # 按周统计
        weekly_data = qs.annotate(
            week=TruncWeek('date')
        ).values('week').annotate(
            total_hours=Sum('hours'),
            work_days=Count('date', distinct=True),
            projects=Count('project', distinct=True),
            tasks=Count('task', distinct=True)
        ).order_by('week')
        
        # 每周工作内容摘要
        weekly_summary = []
        for week in weekly_data:
            week_logs = qs.filter(
                date__gte=week['week'],
                date__lt=week['week'] + timedelta(days=7)
            ).values(
                'project__name', 'task__name', 'description'
            )[:10]
            
            weekly_summary.append({
                **week,
                'details': list(week_logs)
            })
        
        return Response({
            'weekly_data': weekly_summary,
            'user_id': user_id
        })


class TimelogOvertimeView(APIView):
    """加班统计"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        daily_standard = float(request.query_params.get('daily_standard', 8))
        
        today = timezone.now().date()
        if not start_date:
            start_date = today.replace(day=1)
        if not end_date:
            end_date = today
        
        # 按用户按天统计
        daily_hours = TimeLog.objects.filter(
            is_deleted=False,
            date__gte=start_date,
            date__lte=end_date
        ).values(
            'user__id', 'user__username', 'date'
        ).annotate(
            daily_total=Sum('hours')
        )
        
        # 计算加班情况
        overtime_by_user = {}
        for record in daily_hours:
            user_id = record['user__id']
            username = record['user__username']
            daily_total = record['daily_total'] or 0
            overtime = max(0, daily_total - daily_standard)
            
            if user_id not in overtime_by_user:
                overtime_by_user[user_id] = {
                    'user_id': user_id,
                    'username': username,
                    'total_hours': 0,
                    'overtime_hours': 0,
                    'overtime_days': 0,
                    'work_days': 0
                }
            
            overtime_by_user[user_id]['total_hours'] += daily_total
            overtime_by_user[user_id]['overtime_hours'] += overtime
            overtime_by_user[user_id]['work_days'] += 1
            if overtime > 0:
                overtime_by_user[user_id]['overtime_days'] += 1
        
        overtime_list = sorted(
            overtime_by_user.values(), 
            key=lambda x: x['overtime_hours'], 
            reverse=True
        )
        
        return Response({
            'overtime_by_user': overtime_list,
            'period': {'start': start_date, 'end': end_date},
            'daily_standard': daily_standard
        })
