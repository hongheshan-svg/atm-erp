"""
项目生产看板
Project Production Kanban

功能：生产监控大屏、实时数据展示

非标自动化行业适用说明：
- 看板显示当前进行中的项目生产任务
- 工作中心状态显示各工位当前任务
- 完成率统计按任务数量（非产品数量）
- 重点关注：任务进度、工位占用、异常预警

注：数量完成率在非标行业意义有限（通常每个任务数量为1），
建议关注任务完成数量和工时进度。
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class ProductionKanbanView(APIView):
    """生产看板API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取生产看板数据"""
        from apps.production.models import ProductionPlan, ProductionProcess
        from apps.production.aps import ScheduleOrder, WorkCenter
        
        today = date.today()
        now = timezone.now()
        
        # 今日生产概览
        today_orders = ScheduleOrder.objects.filter(
            planned_start__date=today,
            is_deleted=False
        )
        
        overview = {
            'total_orders': today_orders.count(),
            'pending': today_orders.filter(status='PENDING').count(),
            'in_progress': today_orders.filter(status='IN_PROGRESS').count(),
            'completed': today_orders.filter(status='COMPLETED').count(),
            'completion_rate': 0
        }
        
        if overview['total_orders'] > 0:
            overview['completion_rate'] = round(
                overview['completed'] / overview['total_orders'] * 100, 1
            )
        
        # 工作中心状态
        work_centers = WorkCenter.objects.filter(is_active=True, is_deleted=False)
        wc_status = []
        
        for wc in work_centers:
            current_order = ScheduleOrder.objects.filter(
                work_center=wc,
                status='IN_PROGRESS',
                is_deleted=False
            ).first()
            
            today_completed = ScheduleOrder.objects.filter(
                work_center=wc,
                status='COMPLETED',
                actual_end__date=today,
                is_deleted=False
            ).count()
            
            today_planned = ScheduleOrder.objects.filter(
                work_center=wc,
                planned_start__date=today,
                is_deleted=False
            ).count()
            
            wc_status.append({
                'id': wc.id,
                'name': wc.name,
                'status': 'BUSY' if current_order else 'IDLE',
                'current_order': current_order.order_no if current_order else None,
                'today_completed': today_completed,
                'today_planned': today_planned,
                'utilization': round(today_completed / today_planned * 100, 1) if today_planned > 0 else 0
            })
        
        # 进行中的工单
        active_orders = ScheduleOrder.objects.filter(
            status='IN_PROGRESS',
            is_deleted=False
        ).select_related('work_center', 'item').order_by('priority')[:10]
        
        active_list = []
        for order in active_orders:
            progress = 0
            if order.quantity and order.quantity > 0:
                progress = int(order.completed_qty / order.quantity * 100)
            
            active_list.append({
                'order_no': order.order_no,
                'item_name': order.item.name if order.item else '-',
                'work_center': order.work_center.name if order.work_center else '-',
                'quantity': float(order.quantity),
                'completed': float(order.completed_qty),
                'progress': progress,
                'planned_end': order.planned_end.isoformat() if order.planned_end else None
            })
        
        # 即将到期的工单
        upcoming_due = ScheduleOrder.objects.filter(
            status__in=['PENDING', 'SCHEDULED', 'IN_PROGRESS'],
            required_date__lte=today + timedelta(days=3),
            is_deleted=False
        ).order_by('required_date')[:5]
        
        due_list = []
        for order in upcoming_due:
            days_left = (order.required_date - today).days
            due_list.append({
                'order_no': order.order_no,
                'item_name': order.item.name if order.item else '-',
                'required_date': order.required_date.isoformat(),
                'days_left': days_left,
                'status': order.status,
                'is_urgent': days_left <= 1
            })
        
        # 质量数据
        from apps.production.models import QualityInspection
        today_inspections = QualityInspection.objects.filter(
            inspection_date=today,
            is_deleted=False
        )
        
        quality_data = {
            'total': today_inspections.count(),
            'passed': today_inspections.filter(result='PASSED').count(),
            'failed': today_inspections.filter(result='FAILED').count(),
            'pass_rate': 0
        }
        if quality_data['total'] > 0:
            quality_data['pass_rate'] = round(
                quality_data['passed'] / quality_data['total'] * 100, 1
            )
        
        return Response({
            'timestamp': now.isoformat(),
            'overview': overview,
            'work_centers': wc_status,
            'active_orders': active_list,
            'upcoming_due': due_list,
            'quality': quality_data
        })


class WorkCenterKanbanView(APIView):
    """工作中心看板API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, work_center_id):
        """获取工作中心看板"""
        from apps.production.aps import ScheduleOrder, WorkCenter, ScheduleTask
        
        try:
            wc = WorkCenter.objects.get(id=work_center_id, is_deleted=False)
        except WorkCenter.DoesNotExist:
            return Response({'error': '工作中心不存在'}, status=404)
        
        today = date.today()
        now = timezone.now()
        
        # 当前任务
        current_order = ScheduleOrder.objects.filter(
            work_center=wc,
            status='IN_PROGRESS',
            is_deleted=False
        ).first()
        
        current_task = None
        if current_order:
            current_task = {
                'order_no': current_order.order_no,
                'item_name': current_order.item.name if current_order.item else '-',
                'quantity': float(current_order.quantity),
                'completed': float(current_order.completed_qty),
                'progress': int(current_order.completed_qty / current_order.quantity * 100) if current_order.quantity else 0,
                'started_at': current_order.actual_start.isoformat() if current_order.actual_start else None,
                'planned_end': current_order.planned_end.isoformat() if current_order.planned_end else None
            }
        
        # 待处理队列
        queue = ScheduleOrder.objects.filter(
            work_center=wc,
            status='SCHEDULED',
            is_deleted=False
        ).order_by('priority', 'planned_start')[:10]
        
        queue_list = []
        for order in queue:
            queue_list.append({
                'order_no': order.order_no,
                'item_name': order.item.name if order.item else '-',
                'quantity': float(order.quantity),
                'priority': order.priority,
                'planned_start': order.planned_start.isoformat() if order.planned_start else None
            })
        
        # 今日统计
        today_stats = {
            'planned': ScheduleOrder.objects.filter(
                work_center=wc,
                planned_start__date=today,
                is_deleted=False
            ).count(),
            'completed': ScheduleOrder.objects.filter(
                work_center=wc,
                status='COMPLETED',
                actual_end__date=today,
                is_deleted=False
            ).count(),
            'total_hours': 0
        }
        
        completed_hours = ScheduleOrder.objects.filter(
            work_center=wc,
            status='COMPLETED',
            actual_end__date=today,
            is_deleted=False
        ).aggregate(total=Sum('planned_hours'))['total']
        
        today_stats['total_hours'] = float(completed_hours) if completed_hours else 0
        
        return Response({
            'work_center': {
                'id': wc.id,
                'name': wc.name,
                'efficiency': float(wc.efficiency)
            },
            'current_task': current_task,
            'queue': queue_list,
            'today_stats': today_stats,
            'timestamp': now.isoformat()
        })


class ProductionTrendView(APIView):
    """生产趋势API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取生产趋势"""
        from apps.production.aps import ScheduleOrder
        
        days = int(request.query_params.get('days', 7))
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        
        trend = []
        current = start_date
        
        while current <= end_date:
            day_orders = ScheduleOrder.objects.filter(
                actual_end__date=current,
                status='COMPLETED',
                is_deleted=False
            )
            
            completed = day_orders.count()
            total_qty = day_orders.aggregate(total=Sum('completed_qty'))['total'] or 0
            total_hours = day_orders.aggregate(total=Sum('planned_hours'))['total'] or 0
            
            trend.append({
                'date': current.isoformat(),
                'completed_orders': completed,
                'completed_qty': float(total_qty),
                'total_hours': float(total_hours)
            })
            
            current += timedelta(days=1)
        
        return Response({
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'trend': trend
        })


class AndonAlertView(APIView):
    """安灯预警API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取安灯预警"""
        from apps.production.aps import ScheduleOrder
        from apps.projects.equipment_models import Equipment
        
        now = timezone.now()
        today = date.today()
        alerts = []
        
        # 1. 生产延期预警
        delayed = ScheduleOrder.objects.filter(
            status='IN_PROGRESS',
            planned_end__lt=now,
            is_deleted=False
        )
        
        for order in delayed:
            delay_hours = (now - order.planned_end).total_seconds() / 3600
            alerts.append({
                'type': 'DELAY',
                'level': 'CRITICAL' if delay_hours > 4 else 'WARNING',
                'title': f'工单 {order.order_no} 生产延期',
                'message': f'已延期 {delay_hours:.1f} 小时',
                'source': order.order_no,
                'created_at': now.isoformat()
            })
        
        # 2. 设备故障预警
        try:
            faulty_equipment = Equipment.objects.filter(
                status='FAULT',
                is_deleted=False
            )
            
            for eq in faulty_equipment:
                alerts.append({
                    'type': 'EQUIPMENT',
                    'level': 'CRITICAL',
                    'title': f'设备 {eq.name} 故障',
                    'message': f'设备处于故障状态，需要维修',
                    'source': eq.code if hasattr(eq, 'code') else str(eq.id),
                    'created_at': now.isoformat()
                })
        except:
            pass
        
        # 3. 质量异常预警
        from apps.production.models import QualityInspection
        
        failed_inspections = QualityInspection.objects.filter(
            inspection_date=today,
            result='FAILED',
            is_deleted=False
        ).order_by('-created_at')[:5]
        
        for insp in failed_inspections:
            alerts.append({
                'type': 'QUALITY',
                'level': 'WARNING',
                'title': f'质检不合格',
                'message': f'检验 {insp.id} 不合格，请处理',
                'source': str(insp.id),
                'created_at': insp.created_at.isoformat() if insp.created_at else now.isoformat()
            })
        
        # 按级别排序
        level_order = {'CRITICAL': 0, 'WARNING': 1, 'INFO': 2}
        alerts.sort(key=lambda x: level_order.get(x['level'], 99))
        
        return Response({
            'alerts': alerts,
            'total': len(alerts),
            'critical_count': sum(1 for a in alerts if a['level'] == 'CRITICAL'),
            'timestamp': now.isoformat()
        })
