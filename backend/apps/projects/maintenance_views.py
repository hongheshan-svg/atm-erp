"""
设备维保管理视图
Equipment Maintenance Views
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# 注意：原 MaintenanceScheduleViewSet 死代码已移除——其字段名(next_maintenance_date/
# cycle_type/actual_date/status='PENDING')与 equipment_models.MaintenanceSchedule 不符，
# 且 urls 注册的是 equipment_views.MaintenanceScheduleViewSet，此处类从未被引用。


class MaintenanceReminderView(viewsets.ViewSet):
    """维保提醒API"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def warranty_expiring(self, request):
        """获取保修即将到期的设备"""
        from apps.projects.equipment_models import Equipment

        days = int(request.query_params.get('days', 30))
        today = timezone.now().date()
        end_date = today + timedelta(days=days)

        expiring = Equipment.objects.filter(
            warranty_end_date__gte=today, warranty_end_date__lte=end_date, is_deleted=False
        ).select_related('project')

        data = [
            {
                'id': eq.id,
                'equipment_no': eq.equipment_no,
                'name': eq.name,
                'warranty_end_date': eq.warranty_end_date,
                'days_remaining': (eq.warranty_end_date - today).days,
                'project_name': eq.project.name if eq.project else None,
            }
            for eq in expiring
        ]

        return Response(data)

    @action(detail=False, methods=['get'])
    def calibration_due(self, request):
        """获取校准即将到期的工装夹具"""
        from apps.projects.fixture_models import Fixture

        days = int(request.query_params.get('days', 30))
        today = timezone.now().date()
        end_date = today + timedelta(days=days)

        due = Fixture.objects.filter(
            next_calibration__gte=today, next_calibration__lte=end_date, is_deleted=False
        )

        data = [
            {
                'id': f.id,
                'fixture_no': f.fixture_no,
                'name': f.name,
                'next_calibration_date': f.next_calibration,
                'days_remaining': (f.next_calibration - today).days,
                'responsible_person': f.custodian.username if f.custodian else None,
            }
            for f in due
        ]

        return Response(data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """获取维保提醒汇总"""
        from apps.projects.equipment_models import Equipment, MaintenanceSchedule
        from apps.projects.fixture_models import Fixture

        today = timezone.now().date()

        # 7天内
        seven_days = today + timedelta(days=7)
        # 30天内
        thirty_days = today + timedelta(days=30)

        summary = {
            'warranty_expiring_7d': Equipment.objects.filter(
                warranty_end_date__gte=today, warranty_end_date__lte=seven_days, is_deleted=False
            ).count(),
            'warranty_expiring_30d': Equipment.objects.filter(
                warranty_end_date__gte=today, warranty_end_date__lte=thirty_days, is_deleted=False
            ).count(),
            'maintenance_due_7d': MaintenanceSchedule.objects.filter(
                status='PLANNED',
                scheduled_date__gte=today,
                scheduled_date__lte=seven_days,
                is_deleted=False,
            ).count(),
            'maintenance_overdue': MaintenanceSchedule.objects.filter(
                status__in=['PLANNED', 'OVERDUE'], scheduled_date__lt=today, is_deleted=False
            ).count(),
            'calibration_due_7d': Fixture.objects.filter(
                next_calibration__gte=today, next_calibration__lte=seven_days, is_deleted=False
            ).count(),
            'calibration_due_30d': Fixture.objects.filter(
                next_calibration__gte=today, next_calibration__lte=thirty_days, is_deleted=False
            ).count(),
        }

        return Response(summary)
