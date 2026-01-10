"""
操作日志分析API
Audit Log Analytics API
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta


class AuditLogAnalyticsView(APIView):
    """
    操作日志分析统计
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        from apps.core.models import AuditLog
        
        today = timezone.now().date()
        this_week_start = today - timedelta(days=today.weekday())
        this_month_start = today.replace(day=1)
        
        # 基础统计
        total_logs = AuditLog.objects.count()
        today_logs = AuditLog.objects.filter(created_at__date=today).count()
        week_logs = AuditLog.objects.filter(created_at__date__gte=this_week_start).count()
        month_logs = AuditLog.objects.filter(created_at__date__gte=this_month_start).count()
        
        # 按操作类型统计
        by_action = AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # 按用户统计（本月）
        by_user = AuditLog.objects.filter(
            created_at__date__gte=this_month_start
        ).values(
            'user__username'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # 按模块统计
        by_model = AuditLog.objects.values('content_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # 每日趋势（近30天）
        thirty_days_ago = today - timedelta(days=30)
        daily_trend = AuditLog.objects.filter(
            created_at__date__gte=thirty_days_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # 每小时分布（今天）
        hourly_distribution = AuditLog.objects.filter(
            created_at__date=today
        ).annotate(
            hour=TruncHour('created_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        return Response({
            'summary': {
                'total': total_logs,
                'today': today_logs,
                'this_week': week_logs,
                'this_month': month_logs,
            },
            'by_action': list(by_action),
            'by_user': list(by_user),
            'by_model': list(by_model),
            'daily_trend': list(daily_trend),
            'hourly_distribution': list(hourly_distribution),
        })


class AuditLogSecurityView(APIView):
    """
    安全相关日志分析
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        from apps.core.models import AuditLog
        from apps.core.security_views import LoginLog
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # 敏感操作（删除、导出等）
        sensitive_actions = ['delete', 'export', 'bulk_delete', 'restore', 'approve', 'reject']
        sensitive_logs = AuditLog.objects.filter(
            action__in=sensitive_actions,
            created_at__date__gte=week_ago
        ).count()
        
        # 按敏感操作类型统计
        sensitive_by_action = AuditLog.objects.filter(
            action__in=sensitive_actions,
            created_at__date__gte=week_ago
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # 登录失败统计
        login_stats = {
            'success': 0,
            'failed': 0,
            'locked': 0
        }
        
        try:
            login_logs = LoginLog.objects.filter(
                login_time__date__gte=week_ago
            )
            login_stats['success'] = login_logs.filter(status='SUCCESS').count()
            login_stats['failed'] = login_logs.filter(status='FAILED').count()
            login_stats['locked'] = login_logs.filter(status='LOCKED').count()
        except Exception:
            pass
        
        # 异常操作（短时间内大量操作）
        from django.db.models import Count
        from django.db.models.functions import TruncMinute
        
        # 找出每分钟操作超过10次的记录
        high_frequency = AuditLog.objects.filter(
            created_at__date=today
        ).annotate(
            minute=TruncMinute('created_at')
        ).values('user__username', 'minute').annotate(
            count=Count('id')
        ).filter(count__gt=10).order_by('-count')[:10]
        
        # 最近的敏感操作
        recent_sensitive = AuditLog.objects.filter(
            action__in=sensitive_actions
        ).select_related('user').order_by('-created_at')[:20]
        
        recent_sensitive_data = [
            {
                'id': log.id,
                'action': log.action,
                'user': log.user.username if log.user else 'system',
                'content_type': log.content_type,
                'object_id': log.object_id,
                'created_at': log.created_at.isoformat(),
                'ip_address': log.ip_address
            }
            for log in recent_sensitive
        ]
        
        return Response({
            'sensitive_operations': {
                'count': sensitive_logs,
                'by_action': list(sensitive_by_action)
            },
            'login_stats': login_stats,
            'high_frequency_users': list(high_frequency),
            'recent_sensitive': recent_sensitive_data
        })


class UserActivityView(APIView):
    """
    用户活动分析
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from apps.core.models import AuditLog
        
        user = request.user
        user_id = request.query_params.get('user_id')
        
        # 管理员可以查看其他用户
        if user_id and user.is_superuser:
            from apps.accounts.models import User
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({'error': '用户不存在'}, status=404)
        else:
            target_user = user
        
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        
        # 用户操作统计
        user_logs = AuditLog.objects.filter(user=target_user)
        
        total_operations = user_logs.count()
        month_operations = user_logs.filter(created_at__date__gte=this_month_start).count()
        today_operations = user_logs.filter(created_at__date=today).count()
        
        # 按操作类型
        by_action = user_logs.filter(
            created_at__date__gte=this_month_start
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # 最近操作
        recent = user_logs.order_by('-created_at')[:20]
        recent_data = [
            {
                'id': log.id,
                'action': log.action,
                'content_type': log.content_type,
                'object_id': log.object_id,
                'created_at': log.created_at.isoformat(),
            }
            for log in recent
        ]
        
        # 每日操作趋势
        thirty_days_ago = today - timedelta(days=30)
        daily_trend = user_logs.filter(
            created_at__date__gte=thirty_days_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return Response({
            'user': {
                'id': target_user.id,
                'username': target_user.username,
            },
            'summary': {
                'total': total_operations,
                'this_month': month_operations,
                'today': today_operations,
            },
            'by_action': list(by_action),
            'recent_operations': recent_data,
            'daily_trend': list(daily_trend)
        })
