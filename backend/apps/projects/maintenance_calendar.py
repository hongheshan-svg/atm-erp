"""
设备维护日历
Equipment Maintenance Calendar
设备维护计划日历视图
"""

from datetime import date, timedelta

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class MaintenanceCalendarView(APIView):
    """设备维护日历API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取维护日历数据"""
        from apps.projects.equipment_models import Equipment, MaintenanceSchedule

        # 获取日期范围
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        equipment_id = request.query_params.get('equipment_id')

        if not start_date:
            # 默认当月
            today = date.today()
            start_date = date(today.year, today.month, 1)
        else:
            start_date = date.fromisoformat(start_date)

        if not end_date:
            # 默认下月底
            if start_date.month == 12:
                end_date = date(start_date.year + 1, 2, 1) - timedelta(days=1)
            else:
                end_date = date(start_date.year, start_date.month + 2, 1) - timedelta(days=1)
        else:
            end_date = date.fromisoformat(end_date)

        # 查询维护计划
        schedules = MaintenanceSchedule.objects.filter(is_deleted=False).select_related('equipment')

        if equipment_id:
            schedules = schedules.filter(equipment_id=equipment_id)

        # 构建日历事件
        events = []

        for schedule in schedules:
            # 获取计划维护日期
            planned_dates = MaintenanceCalendarView._get_planned_dates(schedule, start_date, end_date)

            for planned_date in planned_dates:
                event_type = 'maintenance'
                title = f'{schedule.equipment.name} - {schedule.maintenance_type}'

                # 判断状态
                if planned_date < date.today():
                    if schedule.status == 'COMPLETED':
                        status = 'completed'
                    else:
                        status = 'overdue'
                elif planned_date == date.today():
                    status = 'today'
                else:
                    status = 'upcoming'

                events.append(
                    {
                        'id': f'{schedule.id}_{planned_date.isoformat()}',
                        'schedule_id': schedule.id,
                        'equipment_id': schedule.equipment_id,
                        'equipment_name': schedule.equipment.name,
                        'equipment_code': schedule.equipment.code if hasattr(schedule.equipment, 'code') else '',
                        'title': title,
                        'date': planned_date.isoformat(),
                        'type': event_type,
                        'status': status,
                        'maintenance_type': schedule.maintenance_type,
                        'description': schedule.description if hasattr(schedule, 'description') else '',
                    }
                )

        # 添加设备保修到期提醒
        equipments = Equipment.objects.filter(
            warranty_end_date__gte=start_date, warranty_end_date__lte=end_date, is_deleted=False
        )

        for eq in equipments:
            events.append(
                {
                    'id': f'warranty_{eq.id}',
                    'equipment_id': eq.id,
                    'equipment_name': eq.name,
                    'equipment_code': eq.code if hasattr(eq, 'code') else '',
                    'title': f'{eq.name} 保修到期',
                    'date': eq.warranty_end_date.isoformat(),
                    'type': 'warranty',
                    'status': 'warning',
                    'maintenance_type': 'WARRANTY_EXPIRE',
                    'description': f'设备保修将于 {eq.warranty_end_date} 到期',
                }
            )

        # 按日期排序
        events.sort(key=lambda x: x['date'])

        return Response(
            {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'events': events,
                'summary': {
                    'total': len(events),
                    'completed': sum(1 for e in events if e['status'] == 'completed'),
                    'overdue': sum(1 for e in events if e['status'] == 'overdue'),
                    'upcoming': sum(1 for e in events if e['status'] == 'upcoming'),
                    'today': sum(1 for e in events if e['status'] == 'today'),
                },
            }
        )

    @staticmethod
    def _get_planned_dates(schedule, start_date, end_date):
        """获取计划维护日期列表"""
        dates = []

        # 获取基准日期
        if hasattr(schedule, 'next_date') and schedule.next_date:
            next_date = schedule.next_date
        elif hasattr(schedule, 'last_date') and schedule.last_date:
            next_date = schedule.last_date + timedelta(days=schedule.interval_days or 30)
        else:
            next_date = start_date

        interval = schedule.interval_days if hasattr(schedule, 'interval_days') else 30
        if not interval or interval <= 0:
            interval = 30

        # 找到第一个在范围内的日期
        while next_date < start_date:
            next_date += timedelta(days=interval)

        # 生成日期范围内的所有计划日期
        while next_date <= end_date:
            dates.append(next_date)
            next_date += timedelta(days=interval)

        return dates


class MaintenanceStatisticsView(APIView):
    """维护统计API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取维护统计"""
        from django.db.models import Count

        from apps.projects.equipment_models import Equipment, MaintenanceSchedule

        today = date.today()

        # 逾期维护
        overdue_count = MaintenanceSchedule.objects.filter(
            next_date__lt=today, status__in=['PENDING', 'IN_PROGRESS'], is_deleted=False
        ).count()

        # 今日维护
        today_count = MaintenanceSchedule.objects.filter(next_date=today, is_deleted=False).count()

        # 本周维护
        week_end = today + timedelta(days=7)
        week_count = MaintenanceSchedule.objects.filter(
            next_date__gte=today, next_date__lte=week_end, is_deleted=False
        ).count()

        # 本月完成
        month_start = date(today.year, today.month, 1)
        completed_count = MaintenanceSchedule.objects.filter(
            completed_date__gte=month_start, status='COMPLETED', is_deleted=False
        ).count()

        # 保修即将到期
        warranty_warning = Equipment.objects.filter(
            warranty_end__gte=today, warranty_end__lte=today + timedelta(days=30), is_deleted=False
        ).count()

        # 按维护类型统计
        by_type = (
            MaintenanceSchedule.objects.filter(is_deleted=False).values('maintenance_type').annotate(count=Count('id'))
        )

        return Response(
            {
                'overdue': overdue_count,
                'today': today_count,
                'this_week': week_count,
                'completed_this_month': completed_count,
                'warranty_warning': warranty_warning,
                'by_type': list(by_type),
            }
        )


class EquipmentMaintenanceHistoryView(APIView):
    """设备维护历史API"""

    permission_classes = [IsAuthenticated]

    def get(self, request, equipment_id):
        """获取设备维护历史"""
        from apps.projects.equipment_models import MaintenanceSchedule

        schedules = MaintenanceSchedule.objects.filter(equipment_id=equipment_id, is_deleted=False).order_by(
            '-completed_date', '-created_at'
        )

        history = []
        for s in schedules:
            history.append(
                {
                    'id': s.id,
                    'maintenance_type': s.maintenance_type,
                    'status': s.status,
                    'planned_date': s.next_date.isoformat() if hasattr(s, 'next_date') and s.next_date else None,
                    'completed_date': s.completed_date.isoformat()
                    if hasattr(s, 'completed_date') and s.completed_date
                    else None,
                    'description': s.description if hasattr(s, 'description') else '',
                    'cost': float(s.cost) if hasattr(s, 'cost') and s.cost else 0,
                    'created_at': s.created_at.isoformat(),
                }
            )

        return Response({'equipment_id': equipment_id, 'history': history, 'total': len(history)})
