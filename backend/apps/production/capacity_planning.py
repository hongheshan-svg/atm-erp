"""
项目资源分配模块
Project Resource Allocation

功能：资源看板、冲突预警、优先级调度

非标自动化行业适用说明：
- 资源分配以项目为单位，而非按日产能计算
- 关注资源是否被多个项目同时占用（冲突预警）
- 日产能(capacity_per_day)为参考值，实际按项目工时分配
- 重点是资源可用性和项目优先级协调

建议使用方式：
- 工位、设备、人员分配到具体项目
- 检查同一时段资源冲突
- 根据项目交付优先级调整分配
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import BaseModel

User = settings.AUTH_USER_MODEL


class ResourceType(BaseModel):
    """资源类型"""
    RESOURCE_CATEGORY_CHOICES = [
        ('WORKSTATION', '工位'),
        ('EQUIPMENT', '设备'),
        ('PERSONNEL', '人员'),
        ('TOOL', '工装夹具'),
    ]

    code = models.CharField('代码', max_length=50, unique=True)
    name = models.CharField('名称', max_length=100)
    category = models.CharField('类别', max_length=20, choices=RESOURCE_CATEGORY_CHOICES)
    description = models.TextField('描述', blank=True)

    class Meta:
        db_table = 'resource_type'
        verbose_name = '资源类型'


class Resource(BaseModel):
    """资源"""
    STATUS_CHOICES = [
        ('AVAILABLE', '可用'),
        ('OCCUPIED', '占用中'),
        ('MAINTENANCE', '维护中'),
        ('UNAVAILABLE', '不可用'),
    ]

    code = models.CharField('资源编码', max_length=50, unique=True)
    name = models.CharField('资源名称', max_length=100)
    resource_type = models.ForeignKey(ResourceType, on_delete=models.CASCADE,
                                      related_name='resources', verbose_name='资源类型')

    # 产能信息
    capacity_per_day = models.DecimalField('日产能', max_digits=10, decimal_places=2, default=8)
    capacity_unit = models.CharField('产能单位', max_length=20, default='小时')
    efficiency = models.DecimalField('效率系数', max_digits=5, decimal_places=2, default=1.0)

    # 成本信息
    hourly_cost = models.DecimalField('小时成本', max_digits=10, decimal_places=2, default=0)

    # 状态
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    # 关联
    work_center = models.ForeignKey('production.WorkCenter', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='resources', verbose_name='工作中心')
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='responsible_resources', verbose_name='负责人')

    # 技能/能力 (JSON)
    capabilities = models.JSONField('能力标签', default=list)

    class Meta:
        db_table = 'resource'
        verbose_name = '资源'

    def __str__(self):
        return f'{self.code} - {self.name}'


class ResourceAllocation(BaseModel):
    """资源分配"""
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE,
                                related_name='allocations', verbose_name='资源')

    # 分配对象
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                               related_name='resource_allocations', verbose_name='项目')
    task_type = models.CharField('任务类型', max_length=50, blank=True)  # 调试、装配、加工等
    task_reference = models.CharField('任务引用', max_length=100, blank=True)  # 关联的任务ID

    # 时间
    start_date = models.DateField('开始日期')
    end_date = models.DateField('结束日期')
    start_time = models.TimeField('开始时间', null=True, blank=True)
    end_time = models.TimeField('结束时间', null=True, blank=True)

    # 占用
    allocated_hours = models.DecimalField('分配工时', max_digits=10, decimal_places=2)
    priority = models.IntegerField('优先级', default=5)  # 1-10, 10最高

    # 状态
    STATUS_CHOICES = [
        ('PLANNED', '计划中'),
        ('CONFIRMED', '已确认'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='PLANNED')

    remarks = models.TextField('备注', blank=True)

    class Meta:
        db_table = 'resource_allocation'
        verbose_name = '资源分配'
        ordering = ['start_date', 'priority']


class CapacityResourceConflict(BaseModel):
    """产能资源冲突"""
    CONFLICT_TYPE_CHOICES = [
        ('OVERLAP', '时间重叠'),
        ('OVERLOAD', '超负荷'),
        ('UNAVAILABLE', '资源不可用'),
        ('SKILL_MISMATCH', '技能不匹配'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('CRITICAL', '严重'),
    ]

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE,
                                related_name='capacity_conflicts', verbose_name='资源')
    conflict_type = models.CharField('冲突类型', max_length=20, choices=CONFLICT_TYPE_CHOICES)
    severity = models.CharField('严重程度', max_length=20, choices=SEVERITY_CHOICES)

    conflict_date = models.DateField('冲突日期')
    description = models.TextField('冲突描述')

    # 冲突的分配
    allocation1 = models.ForeignKey(ResourceAllocation, on_delete=models.CASCADE,
                                   related_name='cap_conflicts_as_first', verbose_name='分配1')
    allocation2 = models.ForeignKey(ResourceAllocation, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='cap_conflicts_as_second',
                                   verbose_name='分配2')

    # 解决
    resolved = models.BooleanField('已解决', default=False)
    resolution = models.TextField('解决方案', blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='cap_resolved_conflicts', verbose_name='解决人')
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)

    class Meta:
        db_table = 'capacity_resource_conflict'
        verbose_name = '产能资源冲突'
        ordering = ['-severity', 'conflict_date']


class CapacityPlan(BaseModel):
    """产能计划"""
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE,
                                related_name='capacity_plans', verbose_name='资源')
    plan_date = models.DateField('计划日期')

    # 产能
    available_hours = models.DecimalField('可用工时', max_digits=10, decimal_places=2)
    allocated_hours = models.DecimalField('已分配工时', max_digits=10, decimal_places=2, default=0)
    remaining_hours = models.DecimalField('剩余工时', max_digits=10, decimal_places=2)

    # 利用率
    utilization_rate = models.DecimalField('利用率%', max_digits=5, decimal_places=2, default=0)

    # 状态
    is_overloaded = models.BooleanField('超负荷', default=False)
    is_holiday = models.BooleanField('休息日', default=False)

    class Meta:
        db_table = 'capacity_plan'
        verbose_name = '产能计划'
        unique_together = ['resource', 'plan_date']
        ordering = ['plan_date', 'resource']


# ==================== Services ====================

class CapacityPlanningService:
    """产能规划服务"""

    @staticmethod
    def calculate_resource_load(resource, start_date, end_date):
        """计算资源负荷"""
        allocations = ResourceAllocation.objects.filter(
            resource=resource,
            status__in=['PLANNED', 'CONFIRMED', 'IN_PROGRESS'],
            start_date__lte=end_date,
            end_date__gte=start_date,
            is_deleted=False
        )

        # 按日期统计
        daily_load = {}
        current_date = start_date
        while current_date <= end_date:
            daily_load[current_date] = {
                'available': float(resource.capacity_per_day),
                'allocated': 0,
                'allocations': [],
            }
            current_date += timedelta(days=1)

        for alloc in allocations:
            alloc_start = max(alloc.start_date, start_date)
            alloc_end = min(alloc.end_date, end_date)
            days = (alloc_end - alloc_start).days + 1
            daily_hours = float(alloc.allocated_hours) / days if days > 0 else 0

            current = alloc_start
            while current <= alloc_end:
                if current in daily_load:
                    daily_load[current]['allocated'] += daily_hours
                    daily_load[current]['allocations'].append({
                        'id': alloc.id,
                        'project_name': alloc.project.name,
                        'hours': daily_hours,
                        'priority': alloc.priority,
                    })
                current += timedelta(days=1)

        # 计算利用率
        for dt, data in daily_load.items():
            data['utilization'] = round(data['allocated'] / data['available'] * 100, 1) if data['available'] > 0 else 0
            data['remaining'] = max(0, data['available'] - data['allocated'])
            data['overloaded'] = data['allocated'] > data['available']

        return daily_load

    @staticmethod
    def detect_conflicts(resource, start_date, end_date):
        """检测资源冲突"""
        conflicts = []
        daily_load = CapacityPlanningService.calculate_resource_load(resource, start_date, end_date)

        for dt, data in daily_load.items():
            if data['overloaded']:
                # 超负荷冲突
                if len(data['allocations']) >= 2:
                    allocs = sorted(data['allocations'], key=lambda x: x['priority'], reverse=True)
                    conflicts.append({
                        'type': 'OVERLOAD',
                        'severity': 'HIGH' if data['utilization'] > 150 else 'MEDIUM',
                        'date': dt,
                        'description': f"资源{resource.name}在{dt}超负荷，利用率{data['utilization']}%",
                        'allocations': allocs,
                    })

        return conflicts

    @staticmethod
    def find_available_slot(resource, required_hours, preferred_start, preferred_end):
        """查找可用时间段"""
        daily_load = CapacityPlanningService.calculate_resource_load(
            resource, preferred_start, preferred_end
        )

        available_slots = []
        for dt, data in daily_load.items():
            if data['remaining'] >= required_hours:
                available_slots.append({
                    'date': dt,
                    'available_hours': data['remaining'],
                })

        return available_slots

    @staticmethod
    def suggest_alternative_resources(required_capability, start_date, end_date, required_hours):
        """推荐替代资源"""
        alternatives = []

        resources = Resource.objects.filter(
            status='AVAILABLE',
            is_deleted=False
        )

        for resource in resources:
            # 检查能力匹配
            if required_capability and required_capability not in resource.capabilities:
                continue

            # 检查可用性
            daily_load = CapacityPlanningService.calculate_resource_load(resource, start_date, end_date)
            total_available = sum(d['remaining'] for d in daily_load.values())

            if total_available >= required_hours:
                alternatives.append({
                    'resource_id': resource.id,
                    'resource_name': resource.name,
                    'resource_code': resource.code,
                    'available_hours': total_available,
                    'efficiency': float(resource.efficiency),
                    'hourly_cost': float(resource.hourly_cost),
                })

        # 按效率和成本排序
        alternatives.sort(key=lambda x: (-x['efficiency'], x['hourly_cost']))

        return alternatives


# ==================== Serializers ====================

class ResourceTypeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    resource_count = serializers.SerializerMethodField()

    class Meta:
        model = ResourceType
        fields = '__all__'

    def get_resource_count(self, obj):
        return obj.resources.filter(is_deleted=False).count()


class ResourceSerializer(serializers.ModelSerializer):
    resource_type_name = serializers.CharField(source='resource_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    responsible_name = serializers.CharField(source='responsible.get_full_name', read_only=True)

    class Meta:
        model = Resource
        fields = '__all__'


class ResourceAllocationSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ResourceAllocation
        fields = '__all__'


class CapacityResourceConflictSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source='resource.name', read_only=True)

    class Meta:
        model = CapacityResourceConflict
        fields = '__all__'


# ==================== ViewSets ====================

class ResourceTypeViewSet(viewsets.ModelViewSet):
    """资源类型管理"""
    queryset = ResourceType.objects.filter(is_deleted=False)
    serializer_class = ResourceTypeSerializer
    permission_classes = [IsAuthenticated]


class ResourceViewSet(viewsets.ModelViewSet):
    """资源管理"""
    queryset = Resource.objects.filter(is_deleted=False)
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        resource_type = self.request.query_params.get('type')
        status_filter = self.request.query_params.get('status')
        category = self.request.query_params.get('category')

        if resource_type:
            qs = qs.filter(resource_type_id=resource_type)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if category:
            qs = qs.filter(resource_type__category=category)

        return qs.select_related('resource_type', 'responsible')

    @action(detail=True, methods=['get'])
    def load(self, request, pk=None):
        """获取资源负荷"""
        resource = self.get_object()

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not start_date:
            start_date = timezone.now().date()
        else:
            start_date = date.fromisoformat(start_date)

        if not end_date:
            end_date = start_date + timedelta(days=30)
        else:
            end_date = date.fromisoformat(end_date)

        daily_load = CapacityPlanningService.calculate_resource_load(resource, start_date, end_date)

        return Response({
            'resource': ResourceSerializer(resource).data,
            'period': {'start': start_date, 'end': end_date},
            'daily_load': [
                {
                    'date': dt.isoformat(),
                    **data
                } for dt, data in daily_load.items()
            ],
        })

    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """检测资源冲突"""
        resource = self.get_object()

        start_date = date.fromisoformat(request.query_params.get('start_date', timezone.now().date().isoformat()))
        end_date = date.fromisoformat(request.query_params.get('end_date', (timezone.now().date() + timedelta(days=30)).isoformat()))

        conflicts = CapacityPlanningService.detect_conflicts(resource, start_date, end_date)

        return Response(conflicts)


class ResourceAllocationViewSet(viewsets.ModelViewSet):
    """资源分配管理"""
    queryset = ResourceAllocation.objects.filter(is_deleted=False)
    serializer_class = ResourceAllocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        resource = self.request.query_params.get('resource')
        project = self.request.query_params.get('project')
        status_filter = self.request.query_params.get('status')

        if resource:
            qs = qs.filter(resource_id=resource)
        if project:
            qs = qs.filter(project_id=project)
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.select_related('resource', 'project')

    @action(detail=False, methods=['post'])
    def check_availability(self, request):
        """检查可用性"""
        resource_id = request.data.get('resource')
        start_date = date.fromisoformat(request.data.get('start_date'))
        end_date = date.fromisoformat(request.data.get('end_date'))
        required_hours = Decimal(str(request.data.get('hours', 0)))

        resource = Resource.objects.get(pk=resource_id)

        slots = CapacityPlanningService.find_available_slot(
            resource, required_hours, start_date, end_date
        )

        return Response({
            'available': len(slots) > 0,
            'slots': slots,
        })

    @action(detail=False, methods=['post'])
    def find_alternatives(self, request):
        """查找替代资源"""
        capability = request.data.get('capability')
        start_date = date.fromisoformat(request.data.get('start_date'))
        end_date = date.fromisoformat(request.data.get('end_date'))
        required_hours = float(request.data.get('hours', 0))

        alternatives = CapacityPlanningService.suggest_alternative_resources(
            capability, start_date, end_date, required_hours
        )

        return Response(alternatives)


class CapacityDashboardView(APIView):
    """产能看板"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        category = request.query_params.get('category')

        if not start_date:
            start_date = timezone.now().date()
        else:
            start_date = date.fromisoformat(start_date)

        if not end_date:
            end_date = start_date + timedelta(days=14)
        else:
            end_date = date.fromisoformat(end_date)

        # 获取资源
        resources = Resource.objects.filter(
            status='AVAILABLE',
            is_deleted=False
        )
        if category:
            resources = resources.filter(resource_type__category=category)

        resources = resources.select_related('resource_type')

        # 汇总数据
        dashboard_data = {
            'period': {'start': start_date, 'end': end_date},
            'summary': {
                'total_resources': resources.count(),
                'total_capacity_hours': 0,
                'total_allocated_hours': 0,
                'avg_utilization': 0,
                'overloaded_resources': 0,
                'conflicts_count': 0,
            },
            'resources': [],
        }

        total_capacity = 0
        total_allocated = 0
        overloaded_count = 0

        for resource in resources:
            daily_load = CapacityPlanningService.calculate_resource_load(resource, start_date, end_date)

            resource_capacity = sum(d['available'] for d in daily_load.values())
            resource_allocated = sum(d['allocated'] for d in daily_load.values())
            resource_utilization = round(resource_allocated / resource_capacity * 100, 1) if resource_capacity > 0 else 0

            is_overloaded = any(d['overloaded'] for d in daily_load.values())
            if is_overloaded:
                overloaded_count += 1

            total_capacity += resource_capacity
            total_allocated += resource_allocated

            dashboard_data['resources'].append({
                'id': resource.id,
                'code': resource.code,
                'name': resource.name,
                'type': resource.resource_type.name,
                'category': resource.resource_type.category,
                'capacity_hours': resource_capacity,
                'allocated_hours': resource_allocated,
                'utilization': resource_utilization,
                'is_overloaded': is_overloaded,
            })

        dashboard_data['summary']['total_capacity_hours'] = total_capacity
        dashboard_data['summary']['total_allocated_hours'] = total_allocated
        dashboard_data['summary']['avg_utilization'] = round(total_allocated / total_capacity * 100, 1) if total_capacity > 0 else 0
        dashboard_data['summary']['overloaded_resources'] = overloaded_count

        # 冲突统计
        conflicts = CapacityResourceConflict.objects.filter(
            conflict_date__gte=start_date,
            conflict_date__lte=end_date,
            resolved=False,
            is_deleted=False
        ).count()
        dashboard_data['summary']['conflicts_count'] = conflicts

        return Response(dashboard_data)


class CapacityResourceConflictViewSet(viewsets.ModelViewSet):
    """产能资源冲突管理"""
    queryset = CapacityResourceConflict.objects.filter(is_deleted=False)
    serializer_class = CapacityResourceConflictSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            qs = qs.filter(resolved=resolved.lower() == 'true')
        return qs

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决冲突"""
        conflict = self.get_object()

        conflict.resolved = True
        conflict.resolution = request.data.get('resolution', '')
        conflict.resolved_by = request.user
        conflict.resolved_at = timezone.now()
        conflict.save()

        return Response({'message': '冲突已解决'})
