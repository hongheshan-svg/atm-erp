"""
APS高级排程和电子看板
Advanced Planning and Scheduling & Electronic Kanban
MES核心功能
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class WorkCenter(BaseModel):
    """工作中心"""
    code = models.CharField(max_length=50, unique=True, verbose_name='工作中心编码')
    name = models.CharField(max_length=100, verbose_name='工作中心名称')
    
    # 产能参数
    capacity_per_day = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=8,
        verbose_name='日产能(小时)'
    )
    efficiency = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        verbose_name='效率(%)'
    )
    
    # 关联设备
    equipment = models.ManyToManyField(
        'projects.Equipment',
        blank=True,
        related_name='work_centers',
        verbose_name='设备'
    )
    
    # 负责人
    manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_work_centers',
        verbose_name='负责人'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='启用')
    description = models.TextField(blank=True, verbose_name='描述')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_work_center'
        verbose_name = '工作中心'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f'{self.code} - {self.name}'


class ProductionSchedule(BaseModel):
    """生产排程"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('RELEASED', '已下达'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    schedule_no = models.CharField(max_length=50, unique=True, verbose_name='排程编号')
    
    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='production_schedules',
        verbose_name='项目'
    )
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules',
        verbose_name='工作中心'
    )
    
    # 计划时间
    planned_start = models.DateTimeField(verbose_name='计划开始')
    planned_end = models.DateTimeField(verbose_name='计划结束')
    
    # 实际时间
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')
    
    # 工时
    planned_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='计划工时'
    )
    actual_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='实际工时'
    )
    
    # 优先级
    priority = models.IntegerField(default=5, verbose_name='优先级(1-10)')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 负责人
    assignee = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_schedules',
        verbose_name='负责人'
    )
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_production_schedule'
        verbose_name = '生产排程'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'planned_start']
    
    def __str__(self):
        return f'{self.schedule_no} - {self.project.name}'
    
    def save(self, *args, **kwargs):
        if not self.schedule_no:
            from apps.core.utils import generate_code
            self.schedule_no = generate_code('SCH')
        super().save(*args, **kwargs)


class ScheduleTask(BaseModel):
    """排程任务"""
    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('PAUSED', '已暂停'),
    ]
    
    schedule = models.ForeignKey(
        ProductionSchedule,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='排程',
        null=True,
        blank=True
    )
    
    # 工序信息
    process = models.ForeignKey(
        'production.ProductionProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_tasks',
        verbose_name='工序'
    )
    task_name = models.CharField(max_length=200, verbose_name='任务名称')
    sequence = models.IntegerField(default=0, verbose_name='顺序')
    
    # 时间
    planned_start = models.DateTimeField(verbose_name='计划开始')
    planned_end = models.DateTimeField(verbose_name='计划结束')
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')
    
    # 工时
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='计划工时')
    actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='实际工时')
    
    # 负责人
    assignee = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_tasks',
        verbose_name='执行人'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    progress = models.IntegerField(default=0, verbose_name='进度(%)')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_schedule_task'
        verbose_name = '排程任务'
        verbose_name_plural = verbose_name
        ordering = ['schedule', 'sequence']


# =====================
# 电子看板数据视图
# =====================

class KanbanView(APIView):
    """电子看板API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取看板数据"""
        from apps.projects.models import Project
        from apps.production.models import ProductionPlan, QualityInspection
        
        today = date.today()
        
        # 生产概况
        production_stats = {
            'total_schedules': ProductionSchedule.objects.filter(
                planned_start__date=today,
                is_deleted=False
            ).count(),
            'in_progress': ProductionSchedule.objects.filter(
                status='IN_PROGRESS',
                is_deleted=False
            ).count(),
            'completed_today': ProductionSchedule.objects.filter(
                actual_end__date=today,
                status='COMPLETED',
                is_deleted=False
            ).count(),
            'delayed': ProductionSchedule.objects.filter(
                planned_end__lt=timezone.now(),
                status__in=['DRAFT', 'CONFIRMED', 'RELEASED', 'IN_PROGRESS'],
                is_deleted=False
            ).count()
        }
        
        # 项目进度
        projects = Project.objects.filter(
            status='IN_PROGRESS',
            is_deleted=False
        ).order_by('-created_at')[:10]
        
        project_list = [
            {
                'id': p.id,
                'name': p.name,
                'code': p.code if hasattr(p, 'code') else '',
                'progress': p.progress or 0,
                'start_date': p.start_date.isoformat() if p.start_date else None,
                'end_date': p.end_date.isoformat() if p.end_date else None
            }
            for p in projects
        ]
        
        # 工作中心负载
        work_centers = WorkCenter.objects.filter(is_active=True, is_deleted=False)
        center_loads = []
        
        for wc in work_centers:
            week_start = today
            week_end = today + timedelta(days=7)
            
            scheduled_hours = ProductionSchedule.objects.filter(
                work_center=wc,
                planned_start__date__gte=week_start,
                planned_start__date__lte=week_end,
                status__in=['CONFIRMED', 'RELEASED', 'IN_PROGRESS'],
                is_deleted=False
            ).aggregate(total=Sum('planned_hours'))['total'] or 0
            
            capacity = float(wc.capacity_per_day) * 7 * float(wc.efficiency) / 100
            load_rate = float(scheduled_hours) / capacity * 100 if capacity > 0 else 0
            
            center_loads.append({
                'id': wc.id,
                'name': wc.name,
                'code': wc.code,
                'scheduled_hours': float(scheduled_hours),
                'capacity': capacity,
                'load_rate': round(load_rate, 1)
            })
        
        # 质量概况
        quality_stats = {
            'inspections_today': QualityInspection.objects.filter(
                inspection_date=today,
                is_deleted=False
            ).count() if hasattr(QualityInspection, 'inspection_date') else 0,
            'pass_rate': 98.5,  # 示例数据
            'defects_today': 2   # 示例数据
        }
        
        # 今日排程列表
        today_schedules = ProductionSchedule.objects.filter(
            planned_start__date=today,
            is_deleted=False
        ).select_related('project', 'work_center', 'assignee').order_by('priority', 'planned_start')[:20]
        
        schedule_list = [
            {
                'id': s.id,
                'schedule_no': s.schedule_no,
                'project_name': s.project.name if s.project else '',
                'work_center': s.work_center.name if s.work_center else '',
                'planned_start': s.planned_start.strftime('%H:%M'),
                'planned_end': s.planned_end.strftime('%H:%M'),
                'status': s.status,
                'assignee': s.assignee.get_full_name() if s.assignee else ''
            }
            for s in today_schedules
        ]
        
        return Response({
            'timestamp': timezone.now().isoformat(),
            'production': production_stats,
            'projects': project_list,
            'work_centers': center_loads,
            'quality': quality_stats,
            'today_schedules': schedule_list
        })


class GanttView(APIView):
    """甘特图数据API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取甘特图数据"""
        work_center_id = request.query_params.get('work_center_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        qs = ProductionSchedule.objects.filter(
            is_deleted=False,
            status__in=['CONFIRMED', 'RELEASED', 'IN_PROGRESS']
        ).select_related('project', 'work_center', 'assignee')
        
        if work_center_id:
            qs = qs.filter(work_center_id=work_center_id)
        if start_date:
            qs = qs.filter(planned_end__date__gte=start_date)
        if end_date:
            qs = qs.filter(planned_start__date__lte=end_date)
        
        tasks = []
        for schedule in qs:
            tasks.append({
                'id': schedule.id,
                'name': f'{schedule.project.name if schedule.project else schedule.schedule_no}',
                'start': schedule.planned_start.isoformat(),
                'end': schedule.planned_end.isoformat(),
                'progress': 0,  # 可以根据实际任务计算
                'resource': schedule.work_center.name if schedule.work_center else '',
                'status': schedule.status
            })
        
        return Response({
            'tasks': tasks
        })


# =====================
# Serializers
# =====================

class WorkCenterSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    equipment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkCenter
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_equipment_count(self, obj):
        return obj.equipment.count()


class ScheduleTaskSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    process_name = serializers.CharField(source='process.name', read_only=True)
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    
    class Meta:
        model = ScheduleTask
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProductionScheduleSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    tasks = ScheduleTaskSerializer(many=True, read_only=True)
    
    class Meta:
        model = ProductionSchedule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'schedule_no']


class ProductionScheduleListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    
    class Meta:
        model = ProductionSchedule
        fields = [
            'id', 'schedule_no', 'project', 'project_name',
            'work_center', 'work_center_name', 'planned_start', 'planned_end',
            'planned_hours', 'priority', 'status', 'status_display',
            'assignee', 'assignee_name'
        ]


# =====================
# ViewSets
# =====================

class WorkCenterViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """工作中心管理"""
    queryset = WorkCenter.objects.filter(is_deleted=False)
    serializer_class = WorkCenterSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']
    
    @action(detail=True, methods=['get'])
    def load(self, request, pk=None):
        """获取工作中心负载"""
        wc = self.get_object()
        
        # 获取未来7天的负载
        today = date.today()
        loads = []
        
        for i in range(7):
            day = today + timedelta(days=i)
            
            scheduled = ProductionSchedule.objects.filter(
                work_center=wc,
                planned_start__date=day,
                status__in=['CONFIRMED', 'RELEASED', 'IN_PROGRESS'],
                is_deleted=False
            ).aggregate(total=Sum('planned_hours'))['total'] or 0
            
            capacity = float(wc.capacity_per_day) * float(wc.efficiency) / 100
            
            loads.append({
                'date': day.isoformat(),
                'scheduled_hours': float(scheduled),
                'capacity': capacity,
                'available': max(0, capacity - float(scheduled))
            })
        
        return Response({
            'work_center': wc.name,
            'loads': loads
        })


class ProductionScheduleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """生产排程管理"""
    queryset = ProductionSchedule.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'work_center', 'project', 'assignee']
    search_fields = ['schedule_no', 'project__name']
    ordering_fields = ['planned_start', 'priority', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ProductionScheduleListSerializer
        return ProductionScheduleSerializer
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认排程"""
        schedule = self.get_object()
        schedule.status = 'CONFIRMED'
        schedule.save()
        return Response(self.get_serializer(schedule).data)
    
    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """下达排程"""
        schedule = self.get_object()
        schedule.status = 'RELEASED'
        schedule.save()
        return Response(self.get_serializer(schedule).data)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始生产"""
        schedule = self.get_object()
        schedule.status = 'IN_PROGRESS'
        schedule.actual_start = timezone.now()
        schedule.save()
        return Response(self.get_serializer(schedule).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成生产"""
        schedule = self.get_object()
        schedule.status = 'COMPLETED'
        schedule.actual_end = timezone.now()
        if schedule.actual_start:
            duration = (schedule.actual_end - schedule.actual_start).total_seconds() / 3600
            schedule.actual_hours = Decimal(str(round(duration, 2)))
        schedule.save()
        return Response(self.get_serializer(schedule).data)
    
    @action(detail=False, methods=['get'])
    def by_date(self, request):
        """按日期查询"""
        date_str = request.query_params.get('date', date.today().isoformat())
        query_date = date.fromisoformat(date_str)
        
        schedules = self.get_queryset().filter(
            planned_start__date=query_date
        ).order_by('priority', 'planned_start')
        
        return Response(ProductionScheduleListSerializer(schedules, many=True).data)


class ScheduleTaskViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排程任务管理"""
    queryset = ScheduleTask.objects.filter(is_deleted=False)
    serializer_class = ScheduleTaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['schedule', 'status', 'assignee']
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始任务"""
        task = self.get_object()
        task.status = 'IN_PROGRESS'
        task.actual_start = timezone.now()
        task.save()
        return Response(self.get_serializer(task).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        task = self.get_object()
        task.status = 'COMPLETED'
        task.actual_end = timezone.now()
        task.progress = 100
        task.save()
        return Response(self.get_serializer(task).data)
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新进度"""
        task = self.get_object()
        progress = request.data.get('progress', 0)
        task.progress = min(100, max(0, progress))
        task.save()
        return Response(self.get_serializer(task).data)
