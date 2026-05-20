"""
设备维保管理视图
Equipment Maintenance Views
"""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class MaintenanceScheduleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """维保计划管理"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from apps.projects.equipment_models import MaintenanceSchedule
        return MaintenanceSchedule.objects.filter(is_deleted=False)

    def get_serializer_class(self):
        from apps.projects.equipment_serializers import MaintenanceScheduleSerializer
        return MaintenanceScheduleSerializer

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """获取即将到期的维保计划"""
        days = int(request.query_params.get('days', 7))
        today = timezone.now().date()
        end_date = today + timedelta(days=days)

        upcoming = self.get_queryset().filter(
            status='PENDING',
            next_maintenance_date__gte=today,
            next_maintenance_date__lte=end_date
        ).select_related('equipment')

        from apps.projects.equipment_serializers import MaintenanceScheduleSerializer
        serializer = MaintenanceScheduleSerializer(upcoming, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """获取逾期未完成的维保计划"""
        today = timezone.now().date()

        overdue = self.get_queryset().filter(
            status='PENDING',
            next_maintenance_date__lt=today
        ).select_related('equipment')

        from apps.projects.equipment_serializers import MaintenanceScheduleSerializer
        serializer = MaintenanceScheduleSerializer(overdue, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """标记维保完成"""
        schedule = self.get_object()

        schedule.status = 'COMPLETED'
        schedule.actual_date = timezone.now().date()
        schedule.completed_by = request.user
        schedule.completion_notes = request.data.get('notes', '')

        # 根据周期自动设置下次维保日期
        if schedule.cycle_type == 'MONTHLY':
            schedule.next_maintenance_date = schedule.actual_date + timedelta(days=30)
        elif schedule.cycle_type == 'QUARTERLY':
            schedule.next_maintenance_date = schedule.actual_date + timedelta(days=90)
        elif schedule.cycle_type == 'YEARLY':
            schedule.next_maintenance_date = schedule.actual_date + timedelta(days=365)

        schedule.save()

        # 创建下一次计划
        from apps.projects.equipment_models import MaintenanceSchedule
        if schedule.next_maintenance_date and schedule.cycle_type != 'ONCE':
            MaintenanceSchedule.objects.create(
                equipment=schedule.equipment,
                maintenance_type=schedule.maintenance_type,
                cycle_type=schedule.cycle_type,
                next_maintenance_date=schedule.next_maintenance_date,
                responsible_person=schedule.responsible_person,
                status='PENDING',
                created_by=request.user
            )

        from apps.projects.equipment_serializers import MaintenanceScheduleSerializer
        return Response(MaintenanceScheduleSerializer(schedule).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """维保统计"""
        today = timezone.now().date()

        stats = {
            'total_pending': self.get_queryset().filter(status='PENDING').count(),
            'overdue_count': self.get_queryset().filter(
                status='PENDING',
                next_maintenance_date__lt=today
            ).count(),
            'due_this_week': self.get_queryset().filter(
                status='PENDING',
                next_maintenance_date__gte=today,
                next_maintenance_date__lte=today + timedelta(days=7)
            ).count(),
            'completed_this_month': self.get_queryset().filter(
                status='COMPLETED',
                actual_date__gte=today.replace(day=1)
            ).count(),
        }

        # 按类型统计
        by_type = self.get_queryset().filter(
            status='PENDING'
        ).values('maintenance_type').annotate(count=Count('id'))

        stats['by_type'] = list(by_type)

        return Response(stats)


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
            warranty_end_date__gte=today,
            warranty_end_date__lte=end_date,
            is_deleted=False
        ).select_related('project')

        data = [{
            'id': eq.id,
            'equipment_no': eq.equipment_no,
            'name': eq.name,
            'warranty_end_date': eq.warranty_end_date,
            'days_remaining': (eq.warranty_end_date - today).days,
            'project_name': eq.project.name if eq.project else None
        } for eq in expiring]

        return Response(data)

    @action(detail=False, methods=['get'])
    def calibration_due(self, request):
        """获取校准即将到期的工装夹具"""
        from apps.projects.fixture_models import Fixture

        days = int(request.query_params.get('days', 30))
        today = timezone.now().date()
        end_date = today + timedelta(days=days)

        due = Fixture.objects.filter(
            next_calibration_date__gte=today,
            next_calibration_date__lte=end_date,
            is_deleted=False
        )

        data = [{
            'id': f.id,
            'fixture_no': f.fixture_no,
            'name': f.name,
            'next_calibration_date': f.next_calibration_date,
            'days_remaining': (f.next_calibration_date - today).days,
            'responsible_person': f.responsible_person.username if f.responsible_person else None
        } for f in due]

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
                warranty_end_date__gte=today,
                warranty_end_date__lte=seven_days,
                is_deleted=False
            ).count(),
            'warranty_expiring_30d': Equipment.objects.filter(
                warranty_end_date__gte=today,
                warranty_end_date__lte=thirty_days,
                is_deleted=False
            ).count(),
            'maintenance_due_7d': MaintenanceSchedule.objects.filter(
                status='PENDING',
                next_maintenance_date__gte=today,
                next_maintenance_date__lte=seven_days,
                is_deleted=False
            ).count(),
            'maintenance_overdue': MaintenanceSchedule.objects.filter(
                status='PENDING',
                next_maintenance_date__lt=today,
                is_deleted=False
            ).count(),
            'calibration_due_7d': Fixture.objects.filter(
                next_calibration_date__gte=today,
                next_calibration_date__lte=seven_days,
                is_deleted=False
            ).count(),
            'calibration_due_30d': Fixture.objects.filter(
                next_calibration_date__gte=today,
                next_calibration_date__lte=thirty_days,
                is_deleted=False
            ).count(),
        }

        return Response(summary)
