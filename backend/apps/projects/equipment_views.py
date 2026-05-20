"""
设备台账和工装夹具视图
"""

from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin

from .equipment_models import (
    Equipment,
    EquipmentAcceptance,
    EquipmentInstallation,
    EquipmentShipment,
    InstallationLog,
    MaintenanceSchedule,
    TrainingRecord,
)
from .equipment_serializers import (
    EquipmentAcceptanceSerializer,
    EquipmentInstallationSerializer,
    EquipmentListSerializer,
    EquipmentSerializer,
    EquipmentShipmentSerializer,
    FixtureCalibrationSerializer,
    FixtureCategorySerializer,
    FixtureCategoryTreeSerializer,
    FixtureListSerializer,
    FixtureMaintenanceSerializer,
    FixtureSerializer,
    FixtureUsageRecordSerializer,
    InstallationLogSerializer,
    MaintenanceScheduleSerializer,
    TrainingRecordSerializer,
)
from .fixture_models import Fixture, FixtureCalibration, FixtureCategory, FixtureMaintenance, FixtureUsageRecord

# ============================================================
# 设备台账视图
# ============================================================


class EquipmentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    设备台账管理
    """

    queryset = Equipment.objects.select_related('project', 'customer', 'sales_order')
    serializer_class = EquipmentSerializer
    filterset_fields = ['status', 'project', 'customer']
    search_fields = ['equipment_no', 'name', 'model', 'serial_no']
    ordering_fields = ['equipment_no', 'created_at', 'acceptance_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return EquipmentListSerializer
        return EquipmentSerializer

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """设备统计"""
        queryset = self.filter_queryset(self.get_queryset())
        today = timezone.now().date()

        stats = {
            'total': queryset.count(),
            'by_status': {},
            'in_warranty': 0,
            'warranty_expiring_soon': 0,  # 30天内到期
        }

        # 按状态统计
        status_counts = queryset.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats['by_status'][item['status']] = item['count']

        # 质保统计
        stats['in_warranty'] = queryset.filter(warranty_end_date__gte=today).count()

        from datetime import timedelta

        stats['warranty_expiring_soon'] = queryset.filter(
            warranty_end_date__gte=today, warranty_end_date__lte=today + timedelta(days=30)
        ).count()

        return Response(stats)

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """创建发货记录"""
        equipment = self.get_object()

        # 创建发货记录
        shipment_data = request.data.copy()
        shipment_data['equipment'] = equipment.id

        serializer = EquipmentShipmentSerializer(data=shipment_data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)

            # 更新设备状态
            equipment.status = 'SHIPPING'
            equipment.shipping_date = shipment_data.get('shipment_date')
            equipment.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def start_installation(self, request, pk=None):
        """开始安装"""
        equipment = self.get_object()

        installation_data = request.data.copy()
        installation_data['equipment'] = equipment.id

        serializer = EquipmentInstallationSerializer(data=installation_data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)

            # 更新设备状态
            equipment.status = 'INSTALLING'
            equipment.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """创建验收记录"""
        equipment = self.get_object()

        acceptance_data = request.data.copy()
        acceptance_data['equipment'] = equipment.id

        serializer = EquipmentAcceptanceSerializer(data=acceptance_data)
        if serializer.is_valid():
            acceptance = serializer.save(
                created_by=request.user, updated_by=request.user, our_representative=request.user
            )

            # 如果验收通过，更新设备状态
            if acceptance.status == 'PASSED':
                equipment.status = 'ACCEPTED'
                equipment.acceptance_date = acceptance.acceptance_date
                # 开始质保
                equipment.warranty_start_date = acceptance.acceptance_date
                equipment.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EquipmentShipmentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    设备发货记录管理
    """

    queryset = EquipmentShipment.objects.select_related('equipment')
    serializer_class = EquipmentShipmentSerializer
    filterset_fields = ['status', 'equipment']
    search_fields = ['shipment_no', 'tracking_number', 'equipment__name']

    @action(detail=True, methods=['post'])
    def confirm_delivery(self, request, pk=None):
        """确认送达"""
        shipment = self.get_object()
        shipment.status = 'DELIVERED'
        shipment.actual_arrival = request.data.get('arrival_date', timezone.now().date())
        shipment.save()

        # 更新设备状态
        equipment = shipment.equipment
        if equipment.status == 'SHIPPING':
            equipment.status = 'INSTALLING'
            equipment.save()

        return Response(EquipmentShipmentSerializer(shipment).data)


class EquipmentInstallationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    现场安装记录管理
    """

    queryset = EquipmentInstallation.objects.select_related('equipment', 'team_leader')
    serializer_class = EquipmentInstallationSerializer
    filterset_fields = ['status', 'equipment', 'team_leader']
    search_fields = ['installation_no', 'equipment__name']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始安装"""
        installation = self.get_object()
        installation.status = 'ONGOING'
        installation.actual_start = request.data.get('start_date', timezone.now().date())
        installation.save()

        # 更新设备状态
        equipment = installation.equipment
        equipment.status = 'INSTALLING'
        equipment.save()

        return Response(EquipmentInstallationSerializer(installation).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成安装"""
        installation = self.get_object()
        installation.status = 'COMPLETED'
        installation.actual_end = request.data.get('end_date', timezone.now().date())
        installation.progress = 100
        installation.save()

        # 更新设备状态
        equipment = installation.equipment
        equipment.status = 'COMMISSIONING'
        equipment.installation_date = installation.actual_end
        equipment.save()

        return Response(EquipmentInstallationSerializer(installation).data)

    @action(detail=True, methods=['post'])
    def add_log(self, request, pk=None):
        """添加安装日志"""
        installation = self.get_object()

        log_data = request.data.copy()
        log_data['installation'] = installation.id
        log_data['recorded_by'] = request.user.id

        serializer = InstallationLogSerializer(data=log_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstallationLogViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    安装日志管理
    """

    queryset = InstallationLog.objects.select_related('installation', 'recorded_by')
    serializer_class = InstallationLogSerializer
    filterset_fields = ['installation']


class EquipmentAcceptanceViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    设备验收记录管理
    """

    queryset = EquipmentAcceptance.objects.select_related('equipment', 'our_representative')
    serializer_class = EquipmentAcceptanceSerializer
    filterset_fields = ['status', 'equipment']
    search_fields = ['acceptance_no', 'equipment__name']

    @action(detail=True, methods=['post'])
    def pass_acceptance(self, request, pk=None):
        """验收通过"""
        acceptance = self.get_object()
        acceptance.status = 'PASSED'
        acceptance.conclusion = request.data.get('conclusion', '验收通过')
        acceptance.save()

        # 更新设备状态
        equipment = acceptance.equipment
        equipment.status = 'WARRANTY'
        equipment.acceptance_date = acceptance.acceptance_date
        equipment.warranty_start_date = acceptance.acceptance_date
        equipment.save()

        return Response(EquipmentAcceptanceSerializer(acceptance).data)

    @action(detail=True, methods=['post'])
    def fail_acceptance(self, request, pk=None):
        """验收不通过"""
        acceptance = self.get_object()
        acceptance.status = 'FAILED'
        acceptance.issues_found = request.data.get('issues', '')
        acceptance.rectification_plan = request.data.get('plan', '')
        acceptance.save()

        return Response(EquipmentAcceptanceSerializer(acceptance).data)


class MaintenanceScheduleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    设备保养计划管理
    """

    queryset = MaintenanceSchedule.objects.select_related('equipment')
    serializer_class = MaintenanceScheduleSerializer
    filterset_fields = ['status', 'maintenance_type', 'equipment']

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """获取即将到期的保养"""
        today = timezone.now().date()
        from datetime import timedelta

        upcoming = (
            self.get_queryset()
            .filter(status='PLANNED', scheduled_date__lte=today + timedelta(days=7))
            .order_by('scheduled_date')
        )

        return Response(MaintenanceScheduleSerializer(upcoming, many=True).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成保养"""
        schedule = self.get_object()
        schedule.status = 'COMPLETED'
        schedule.completed_date = request.data.get('completed_date', timezone.now().date())
        schedule.maintenance_result = request.data.get('result', '')
        schedule.performed_by = request.data.get('performed_by', '')
        schedule.save()

        return Response(MaintenanceScheduleSerializer(schedule).data)


class TrainingRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    客户培训记录管理
    """

    queryset = TrainingRecord.objects.select_related('equipment', 'trainer')
    serializer_class = TrainingRecordSerializer
    filterset_fields = ['training_type', 'equipment', 'trainer']
    search_fields = ['training_no', 'equipment__name']


# ============================================================
# 工装夹具视图
# ============================================================


class FixtureCategoryViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    工装分类管理
    """

    queryset = FixtureCategory.objects.all()
    serializer_class = FixtureCategorySerializer
    filterset_fields = ['parent']
    search_fields = ['code', 'name']

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取树形结构"""
        root_categories = (
            self.get_queryset().filter(parent__isnull=True, is_deleted=False).order_by('sort_order', 'code')
        )

        return Response(FixtureCategoryTreeSerializer(root_categories, many=True).data)


class FixtureViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    工装夹具管理
    """

    queryset = Fixture.objects.select_related('category', 'project', 'equipment', 'custodian', 'warehouse', 'supplier')
    serializer_class = FixtureSerializer
    filterset_fields = ['status', 'category', 'ownership', 'custodian', 'needs_calibration']
    search_fields = ['fixture_no', 'name', 'model', 'drawing_no']
    ordering_fields = ['fixture_no', 'name', 'created_at', 'next_calibration']

    def get_serializer_class(self):
        if self.action == 'list':
            return FixtureListSerializer
        return FixtureSerializer

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """工装统计"""
        queryset = self.filter_queryset(self.get_queryset())
        today = timezone.now().date()

        stats = {
            'total': queryset.count(),
            'by_status': {},
            'calibration_due': 0,
            'calibration_upcoming': 0,  # 30天内到期
        }

        # 按状态统计
        status_counts = queryset.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats['by_status'][item['status']] = item['count']

        # 校验统计
        from datetime import timedelta

        stats['calibration_due'] = queryset.filter(needs_calibration=True, next_calibration__lte=today).count()

        stats['calibration_upcoming'] = queryset.filter(
            needs_calibration=True, next_calibration__gt=today, next_calibration__lte=today + timedelta(days=30)
        ).count()

        return Response(stats)

    @action(detail=False, methods=['get'])
    def calibration_due(self, request):
        """获取需要校验的工装"""
        today = timezone.now().date()

        due_fixtures = (
            self.get_queryset().filter(needs_calibration=True, next_calibration__lte=today).order_by('next_calibration')
        )

        return Response(FixtureListSerializer(due_fixtures, many=True).data)

    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """领用工装"""
        fixture = self.get_object()

        if fixture.status != 'IDLE' and fixture.status != 'IN_USE':
            return Response({'error': '工装状态不允许领用'}, status=status.HTTP_400_BAD_REQUEST)

        usage_data = {
            'fixture': fixture.id,
            'project': request.data.get('project'),
            'used_by': request.user.id,
            'checkout_time': timezone.now(),
            'expected_return': request.data.get('expected_return'),
            'purpose': request.data.get('purpose', ''),
        }

        serializer = FixtureUsageRecordSerializer(data=usage_data)
        if serializer.is_valid():
            serializer.save()

            fixture.status = 'IN_USE'
            fixture.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def return_fixture(self, request, pk=None):
        """归还工装"""
        fixture = self.get_object()

        # 找到最新的未归还记录
        usage_record = fixture.usage_records.filter(return_time__isnull=True).order_by('-checkout_time').first()

        if not usage_record:
            return Response({'error': '未找到领用记录'}, status=status.HTTP_400_BAD_REQUEST)

        usage_record.return_time = timezone.now()
        usage_record.condition_after = request.data.get('condition', '良好')
        usage_record.save()

        fixture.status = 'IDLE'
        fixture.save()

        return Response(FixtureUsageRecordSerializer(usage_record).data)

    @action(detail=True, methods=['post'])
    def add_calibration(self, request, pk=None):
        """添加校验记录"""
        fixture = self.get_object()

        calibration_data = request.data.copy()
        calibration_data['fixture'] = fixture.id

        serializer = FixtureCalibrationSerializer(data=calibration_data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FixtureUsageRecordViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    工装使用记录管理
    """

    queryset = FixtureUsageRecord.objects.select_related('fixture', 'project', 'used_by')
    serializer_class = FixtureUsageRecordSerializer
    filterset_fields = ['fixture', 'project', 'used_by']


class FixtureCalibrationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    工装校验记录管理
    """

    queryset = FixtureCalibration.objects.select_related('fixture')
    serializer_class = FixtureCalibrationSerializer
    filterset_fields = ['fixture', 'result']


class FixtureMaintenanceViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    工装维护记录管理
    """

    queryset = FixtureMaintenance.objects.select_related('fixture', 'performed_by')
    serializer_class = FixtureMaintenanceSerializer
    filterset_fields = ['fixture', 'maintenance_type', 'performed_by']
