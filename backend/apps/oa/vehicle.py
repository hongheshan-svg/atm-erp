"""
车辆管理
Vehicle Management

功能：公司车辆登记、申请用车、维护保养

非标自动化行业建议：
- 用车申请可关联项目（如项目现场调试用车）
- 可在申请表单中增加项目编号字段
"""
import logging
from datetime import date, timedelta

from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.workflow.mixins import WorkflowEnforcementMixin

logger = logging.getLogger(__name__)


class Vehicle(BaseModel):
    """
    车辆信息
    """
    STATUS_CHOICES = [
        ('AVAILABLE', '可用'),
        ('IN_USE', '使用中'),
        ('MAINTENANCE', '维护中'),
        ('DISABLED', '停用'),
    ]

    VEHICLE_TYPES = [
        ('CAR', '轿车'),
        ('SUV', 'SUV'),
        ('VAN', '面包车'),
        ('TRUCK', '货车'),
        ('BUS', '大巴'),
        ('OTHER', '其他'),
    ]

    plate_number = models.CharField(max_length=20, unique=True, verbose_name='车牌号')
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPES,
        default='CAR',
        verbose_name='车辆类型'
    )
    brand = models.CharField(max_length=50, verbose_name='品牌')
    model = models.CharField(max_length=50, verbose_name='型号')
    color = models.CharField(max_length=20, blank=True, verbose_name='颜色')

    # 车辆信息
    seats = models.IntegerField(default=5, verbose_name='座位数')
    engine_no = models.CharField(max_length=50, blank=True, verbose_name='发动机号')
    vin = models.CharField(max_length=50, blank=True, verbose_name='车架号')

    # 保险信息
    insurance_company = models.CharField(max_length=100, blank=True, verbose_name='保险公司')
    insurance_no = models.CharField(max_length=50, blank=True, verbose_name='保险单号')
    insurance_expire_date = models.DateField(null=True, blank=True, verbose_name='保险到期日')

    # 年检信息
    annual_inspection_date = models.DateField(null=True, blank=True, verbose_name='年检日期')
    next_inspection_date = models.DateField(null=True, blank=True, verbose_name='下次年检日')

    # 里程
    current_mileage = models.IntegerField(default=0, verbose_name='当前里程(km)')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE',
        verbose_name='状态'
    )

    # 负责人
    manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_vehicles',
        verbose_name='负责人'
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'oa_vehicle'
        verbose_name = '车辆'
        verbose_name_plural = verbose_name
        ordering = ['plate_number']

    def __str__(self):
        return f'{self.plate_number} ({self.brand} {self.model})'


class VehicleRequest(BaseModel):
    """
    用车申请
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('IN_USE', '使用中'),
        ('RETURNED', '已归还'),
        ('CANCELLED', '已取消'),
    ]

    PURPOSE_CHOICES = [
        ('BUSINESS', '商务出行'),
        ('VISIT', '客户拜访'),
        ('DELIVERY', '送货'),
        ('PICKUP', '接送'),
        ('MEETING', '外出开会'),
        ('OTHER', '其他'),
    ]

    request_no = models.CharField(max_length=50, unique=True, verbose_name='申请单号')

    applicant = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='vehicle_requests',
        verbose_name='申请人'
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests',
        verbose_name='申请车辆'
    )

    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default='BUSINESS',
        verbose_name='用途'
    )
    purpose_detail = models.TextField(verbose_name='详细说明')

    # 时间
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='预计结束时间')
    actual_end_time = models.DateTimeField(null=True, blank=True, verbose_name='实际结束时间')

    # 行程
    departure = models.CharField(max_length=200, verbose_name='出发地')
    destination = models.CharField(max_length=200, verbose_name='目的地')
    passengers = models.IntegerField(default=1, verbose_name='乘客人数')
    passenger_names = models.JSONField(default=list, blank=True, verbose_name='乘客名单')

    # 里程
    start_mileage = models.IntegerField(default=0, verbose_name='出发里程')
    end_mileage = models.IntegerField(default=0, verbose_name='归还里程')

    # 费用
    fuel_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='油费')
    toll_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='过路费')
    parking_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='停车费')
    other_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='其他费用')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )

    # 审批
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_vehicle_requests',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    approval_remarks = models.CharField(max_length=500, blank=True, verbose_name='审批意见')

    class Meta:
        db_table = 'oa_vehicle_request'
        verbose_name = '用车申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_no} - {self.applicant.get_full_name()}'

    def save(self, *args, **kwargs):
        if not self.request_no:
            from apps.core.utils import generate_code
            self.request_no = generate_code('VR')
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return self.fuel_cost + self.toll_cost + self.parking_cost + self.other_cost

    @property
    def travel_distance(self):
        return max(0, self.end_mileage - self.start_mileage)


class VehicleMaintenance(BaseModel):
    """
    车辆维护记录
    """
    MAINTENANCE_TYPES = [
        ('REGULAR', '常规保养'),
        ('REPAIR', '维修'),
        ('INSPECTION', '年检'),
        ('INSURANCE', '保险'),
        ('OTHER', '其他'),
    ]

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name='车辆'
    )

    maintenance_type = models.CharField(
        max_length=20,
        choices=MAINTENANCE_TYPES,
        default='REGULAR',
        verbose_name='维护类型'
    )

    maintenance_date = models.DateField(verbose_name='维护日期')
    mileage = models.IntegerField(default=0, verbose_name='里程数')

    description = models.TextField(verbose_name='维护内容')
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='费用')
    vendor = models.CharField(max_length=100, blank=True, verbose_name='服务商')

    next_maintenance_date = models.DateField(null=True, blank=True, verbose_name='下次维护日期')
    next_maintenance_mileage = models.IntegerField(default=0, verbose_name='下次维护里程')

    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    class Meta:
        db_table = 'oa_vehicle_maintenance'
        verbose_name = '车辆维护'
        verbose_name_plural = verbose_name
        ordering = ['-maintenance_date']

    def __str__(self):
        return f'{self.vehicle.plate_number} - {self.get_maintenance_type_display()}'


# =====================
# Serializers
# =====================

class VehicleSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_vehicle_type_display', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)

    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class VehicleListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_vehicle_type_display', read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'plate_number', 'vehicle_type', 'type_display', 'brand', 'model',
            'color', 'seats', 'status', 'status_display', 'current_mileage'
        ]


class VehicleRequestSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    purpose_display = serializers.CharField(source='get_purpose_display', read_only=True)
    applicant_name = serializers.CharField(source='applicant.get_full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    total_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    travel_distance = serializers.IntegerField(read_only=True)

    class Meta:
        model = VehicleRequest
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'request_no', 'approver', 'approved_at']


class VehicleRequestListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    purpose_display = serializers.CharField(source='get_purpose_display', read_only=True)
    applicant_name = serializers.CharField(source='applicant.get_full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True)

    class Meta:
        model = VehicleRequest
        fields = [
            'id', 'request_no', 'applicant_name', 'vehicle', 'vehicle_plate',
            'purpose', 'purpose_display', 'start_time', 'end_time',
            'departure', 'destination', 'status', 'status_display', 'created_at'
        ]


class VehicleMaintenanceSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True)

    class Meta:
        model = VehicleMaintenance
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================

class VehicleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """车辆管理"""
    queryset = Vehicle.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'vehicle_type', 'manager']
    search_fields = ['plate_number', 'brand', 'model']
    ordering_fields = ['plate_number', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return VehicleListSerializer
        return VehicleSerializer

    @action(detail=False, methods=['get'])
    def available(self, request):
        """获取可用车辆"""
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')

        vehicles = self.get_queryset().filter(status='AVAILABLE')

        if start_time and end_time:
            # 排除时间段内有申请的车辆
            busy_vehicle_ids = VehicleRequest.objects.filter(
                status__in=['APPROVED', 'IN_USE'],
                start_time__lt=end_time,
                end_time__gt=start_time
            ).values_list('vehicle_id', flat=True)
            vehicles = vehicles.exclude(id__in=busy_vehicle_ids)

        return Response(VehicleListSerializer(vehicles, many=True).data)

    @action(detail=True, methods=['post'])
    def update_mileage(self, request, pk=None):
        """更新里程"""
        vehicle = self.get_object()
        mileage = request.data.get('mileage', 0)

        if mileage < vehicle.current_mileage:
            return Response({'error': '里程数不能小于当前里程'}, status=400)

        vehicle.current_mileage = mileage
        vehicle.save()
        return Response(self.get_serializer(vehicle).data)


class VehicleRequestViewSet(WorkflowEnforcementMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """用车申请管理"""
    queryset = VehicleRequest.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'vehicle', 'applicant', 'purpose']
    search_fields = ['request_no', 'purpose_detail', 'destination']
    ordering_fields = ['start_time', 'created_at']

    # Workflow configuration
    workflow_business_type = 'VEHICLE_REQUEST'
    workflow_amount_field = None
    workflow_no_field = 'request_no'

    def get_serializer_class(self):
        if self.action == 'list':
            return VehicleRequestListSerializer
        return VehicleRequestSerializer

    def perform_create(self, serializer):
        serializer.save(applicant=self.request.user, created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """我的用车申请"""
        requests = self.get_queryset().filter(applicant=request.user)
        return Response(VehicleRequestListSerializer(requests, many=True).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交申请 - 走流程配置的审批流程"""
        req = self.get_object()
        if req.status not in ['DRAFT', 'REJECTED']:
            return Response({'error': '只能提交草稿或已拒绝状态的申请'}, status=400)

        try:
            from apps.core.workflow.services import WorkflowService

            instance, error = WorkflowService.start_workflow(
                business_type='VEHICLE_REQUEST',
                business_id=req.id,
                business_no=req.request_no or f'VR-{req.id}',
                submitter=request.user,
                amount=None
            )

            if instance:
                req.status = 'PENDING'
                req.save()
                return Response({
                    **self.get_serializer(req).data,
                    'workflow_started': True,
                    'workflow_id': instance.id,
                    'message': '已提交审批，请在审批中心查看审批进度'
                })
            else:
                # 未配置审批流程，自动批准
                req.status = 'APPROVED'
                req.approver = request.user
                req.approved_at = timezone.now()
                req.save()
                logger.info(f'用车申请 {req.request_no or req.id} 自动批准（未配置审批流程）')
                return Response({
                    **self.get_serializer(req).data,
                    'workflow_started': False,
                    'auto_approved': True,
                    'message': error or '未配置审批流程，已自动批准'
                })

        except Exception as e:
            # 工作流服务异常，自动批准
            logger.warning(f'工作流服务异常，用车申请 {req.request_no or req.id} 自动批准: {e}')
            req.status = 'APPROVED'
            req.approver = request.user
            req.approved_at = timezone.now()
            req.save()
            return Response({
                **self.get_serializer(req).data,
                'auto_approved': True,
                'message': '工作流服务不可用，已自动批准'
            })

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过 - 仅在无活跃工作流时允许直接审批"""
        req = self.get_object()
        if req.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)

        # 检查是否有活跃工作流
        workflow_error = self.check_workflow_allows_direct_action(req, '审批')
        if workflow_error:
            return workflow_error

        vehicle_id = request.data.get('vehicle_id')
        if vehicle_id:
            req.vehicle_id = vehicle_id

        req.status = 'APPROVED'
        req.approver = request.user
        req.approved_at = timezone.now()
        req.approval_remarks = request.data.get('remarks', '')
        req.save()

        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审批拒绝 - 仅在无活跃工作流时允许直接拒绝"""
        req = self.get_object()
        if req.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)

        # 检查是否有活跃工作流
        workflow_error = self.check_workflow_allows_direct_action(req, '拒绝')
        if workflow_error:
            return workflow_error

        req.status = 'REJECTED'
        req.approver = request.user
        req.approved_at = timezone.now()
        req.approval_remarks = request.data.get('remarks', '')
        req.save()

        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=['post'])
    def pickup(self, request, pk=None):
        """取车"""
        req = self.get_object()
        if req.status != 'APPROVED':
            return Response({'error': '只有已批准的申请可以取车'}, status=400)

        req.status = 'IN_USE'
        req.start_mileage = req.vehicle.current_mileage
        req.save()

        # 更新车辆状态
        req.vehicle.status = 'IN_USE'
        req.vehicle.save()

        return Response(self.get_serializer(req).data)

    @action(detail=True, methods=['post'])
    def return_vehicle(self, request, pk=None):
        """还车"""
        req = self.get_object()
        if req.status != 'IN_USE':
            return Response({'error': '只有使用中的申请可以还车'}, status=400)

        end_mileage = request.data.get('end_mileage', req.vehicle.current_mileage)

        req.status = 'RETURNED'
        req.actual_end_time = timezone.now()
        req.end_mileage = end_mileage
        req.fuel_cost = request.data.get('fuel_cost', 0)
        req.toll_cost = request.data.get('toll_cost', 0)
        req.parking_cost = request.data.get('parking_cost', 0)
        req.other_cost = request.data.get('other_cost', 0)
        req.save()

        # 更新车辆里程和状态
        req.vehicle.current_mileage = end_mileage
        req.vehicle.status = 'AVAILABLE'
        req.vehicle.save()

        return Response(self.get_serializer(req).data)


class VehicleMaintenanceViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """车辆维护管理"""
    queryset = VehicleMaintenance.objects.filter(is_deleted=False)
    serializer_class = VehicleMaintenanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['vehicle', 'maintenance_type']
    search_fields = ['description', 'vendor']
    ordering_fields = ['maintenance_date', 'created_at']

    @action(detail=False, methods=['get'])
    def due_maintenance(self, request):
        """即将到期的维护"""
        today = date.today()
        next_week = today + timedelta(days=7)

        vehicles = Vehicle.objects.filter(
            is_deleted=False,
            status__in=['AVAILABLE', 'IN_USE']
        )

        due_list = []
        for vehicle in vehicles:
            # 检查下次维护日期
            last_maintenance = vehicle.maintenance_records.filter(
                maintenance_type='REGULAR'
            ).order_by('-maintenance_date').first()

            if last_maintenance and last_maintenance.next_maintenance_date:
                if last_maintenance.next_maintenance_date <= next_week:
                    due_list.append({
                        'vehicle_id': vehicle.id,
                        'plate_number': vehicle.plate_number,
                        'maintenance_type': '常规保养',
                        'due_date': last_maintenance.next_maintenance_date,
                        'current_mileage': vehicle.current_mileage
                    })

        return Response(due_list)
