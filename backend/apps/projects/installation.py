"""
Installation Site Management for Non-standard Automation Equipment
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel


class InstallationTask(BaseModel):
    STATUS_CHOICES = [
        ('pending', '待安排'),
        ('dispatched', '已派遣'),
        ('in_transit', '运输中'),
        ('on_site', '已到场'),
        ('installing', '安装中'),
        ('commissioning', '调试中'),
        ('acceptance', '验收中'),
        ('completed', '已完成'),
    ]

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE,
        related_name='installation_tasks', verbose_name='项目'
    )
    task_number = models.CharField(max_length=50, unique=True, verbose_name='任务编号')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态'
    )
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installation_tasks_led', verbose_name='负责人'
    )
    site_address = models.TextField(verbose_name='现场地址')
    site_contact = models.CharField(max_length=100, blank=True, default='', verbose_name='现场联系人')
    site_phone = models.CharField(max_length=50, blank=True, default='', verbose_name='现场电话')
    planned_start = models.DateField(null=True, blank=True, verbose_name='计划开始日期')
    planned_end = models.DateField(null=True, blank=True, verbose_name='计划结束日期')
    actual_start = models.DateField(null=True, blank=True, verbose_name='实际开始日期')
    actual_end = models.DateField(null=True, blank=True, verbose_name='实际结束日期')
    progress = models.IntegerField(default=0, verbose_name='进度(%)')
    equipment_list = models.JSONField(default=list, verbose_name='设备清单')
    tools_required = models.JSONField(default=list, verbose_name='工具清单')
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'projects_installation_task'
        ordering = ['-created_at']
        verbose_name = '安装任务'
        verbose_name_plural = '安装任务'

    def __str__(self):
        return self.task_number

    def save(self, *args, **kwargs):
        if not self.task_number:
            last = InstallationTask.objects.order_by('-id').first()
            num = (last.id + 1) if last else 1
            self.task_number = f"INST-{num:06d}"
        super().save(*args, **kwargs)


class SiteLog(BaseModel):
    LOG_TYPE_CHOICES = [
        ('daily', '日报'),
        ('progress', '进度'),
        ('issue', '问题'),
        ('milestone', '里程碑'),
    ]

    task = models.ForeignKey(
        InstallationTask, on_delete=models.CASCADE,
        related_name='site_logs', verbose_name='安装任务'
    )
    log_type = models.CharField(
        max_length=20, choices=LOG_TYPE_CHOICES, verbose_name='日志类型'
    )
    log_date = models.DateField(verbose_name='日志日期')
    content = models.TextField(verbose_name='内容')
    work_hours = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, verbose_name='工时'
    )
    workers_count = models.IntegerField(default=1, verbose_name='人数')
    gps_location = models.CharField(max_length=100, blank=True, default='', verbose_name='GPS位置')
    images = models.JSONField(default=list, verbose_name='图片')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='site_logs_created', verbose_name='记录人'
    )

    class Meta:
        db_table = 'projects_site_log'
        ordering = ['-log_date', '-created_at']
        verbose_name = '现场日志'
        verbose_name_plural = '现场日志'

    def __str__(self):
        return f"{self.task.task_number} - {self.log_date}"


class CommissioningRecord(BaseModel):
    RESULT_CHOICES = [
        ('pass', '通过'),
        ('fail', '未通过'),
        ('conditional', '有条件通过'),
    ]

    task = models.ForeignKey(
        InstallationTask, on_delete=models.CASCADE,
        related_name='commissioning_records', verbose_name='安装任务'
    )
    test_item = models.CharField(max_length=200, verbose_name='测试项目')
    test_date = models.DateField(verbose_name='测试日期')
    parameters = models.JSONField(default=dict, verbose_name='测试参数')
    standard = models.JSONField(default=dict, verbose_name='验收标准')
    result = models.CharField(
        max_length=20, choices=RESULT_CHOICES, verbose_name='测试结果'
    )
    actual_values = models.JSONField(default=dict, verbose_name='实际值')
    tester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commissioning_tests', verbose_name='测试人'
    )
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'projects_commissioning_record'
        ordering = ['-test_date']
        verbose_name = '调试记录'
        verbose_name_plural = '调试记录'

    def __str__(self):
        return f"{self.test_item} - {self.get_result_display()}"


class SiteIssue(BaseModel):
    SEVERITY_CHOICES = [
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
        ('critical', '严重'),
    ]
    STATUS_CHOICES = [
        ('open', '待处理'),
        ('processing', '处理中'),
        ('resolved', '已解决'),
        ('closed', '已关闭'),
    ]

    task = models.ForeignKey(
        InstallationTask, on_delete=models.CASCADE,
        related_name='site_issues', verbose_name='安装任务'
    )
    title = models.CharField(max_length=300, verbose_name='问题标题')
    description = models.TextField(verbose_name='问题描述')
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, verbose_name='严重程度'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='状态'
    )
    images = models.JSONField(default=list, verbose_name='图片')
    resolution = models.TextField(blank=True, default='', verbose_name='解决方案')
    need_return = models.BooleanField(default=False, verbose_name='是否需要返厂')
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='site_issues_reported', verbose_name='报告人'
    )

    class Meta:
        db_table = 'projects_site_issue'
        ordering = ['-created_at']
        verbose_name = '现场问题'
        verbose_name_plural = '现场问题'

    def __str__(self):
        return self.title


class CustomerAcceptance(BaseModel):
    RESULT_CHOICES = [
        ('accepted', '验收通过'),
        ('conditional', '有条件通过'),
        ('rejected', '验收未通过'),
    ]

    task = models.ForeignKey(
        InstallationTask, on_delete=models.CASCADE,
        related_name='acceptances', verbose_name='安装任务'
    )
    acceptance_date = models.DateField(verbose_name='验收日期')
    checklist = models.JSONField(default=list, verbose_name='验收清单')
    result = models.CharField(
        max_length=20, choices=RESULT_CHOICES, verbose_name='验收结果'
    )
    customer_representative = models.CharField(max_length=100, verbose_name='客户代表')
    signature_data = models.TextField(blank=True, default='', verbose_name='签名数据')
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'projects_customer_acceptance'
        ordering = ['-acceptance_date']
        verbose_name = '客户验收'
        verbose_name_plural = '客户验收'

    def __str__(self):
        return f"{self.task.task_number} - {self.get_result_display()}"


# ─── Serializers ────────────────────────────────────────────────

class SiteLogSerializer(serializers.ModelSerializer):
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)

    class Meta:
        model = SiteLog
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CommissioningRecordSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = CommissioningRecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SiteIssueSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SiteIssue
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CustomerAcceptanceSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = CustomerAcceptance
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class InstallationTaskSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    site_logs = SiteLogSerializer(many=True, read_only=True)

    class Meta:
        model = InstallationTask
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'task_number']


# ─── ViewSets ───────────────────────────────────────────────────

class InstallationTaskViewSet(viewsets.ModelViewSet):
    serializer_class = InstallationTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = InstallationTask.objects.filter(is_deleted=False)
        project_id = self.request.query_params.get('project_id')
        task_status = self.request.query_params.get('status')
        if project_id:
            qs = qs.filter(project_id=project_id)
        if task_status:
            qs = qs.filter(status=task_status)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def dispatch(self, request, pk=None):
        task = self.get_object()
        if task.status != 'pending':
            return Response({'error': '只有待安排的任务才能派遣'}, status=status.HTTP_400_BAD_REQUEST)
        leader_id = request.data.get('leader_id')
        task.status = 'dispatched'
        if leader_id:
            task.leader_id = leader_id
        task.save(update_fields=['status', 'leader_id', 'updated_at'])
        return Response(InstallationTaskSerializer(task).data)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        task = self.get_object()
        new_status = request.data.get('status')
        valid_statuses = [c[0] for c in InstallationTask.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({'error': f'无效状态: {new_status}'}, status=status.HTTP_400_BAD_REQUEST)
        task.status = new_status
        progress = request.data.get('progress')
        if progress is not None:
            task.progress = int(progress)
        if new_status == 'installing' and not task.actual_start:
            task.actual_start = timezone.now().date()
        if new_status == 'completed':
            task.actual_end = timezone.now().date()
            task.progress = 100
        task.save()
        return Response(InstallationTaskSerializer(task).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.get_queryset()
        from django.db.models import Count
        summary = qs.values('status').annotate(count=Count('id'))
        return Response({
            'total': qs.count(),
            'by_status': list(summary),
        })


class SiteLogViewSet(viewsets.ModelViewSet):
    serializer_class = SiteLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SiteLog.objects.filter(is_deleted=False)
        task_id = self.request.query_params.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CommissioningRecordViewSet(viewsets.ModelViewSet):
    serializer_class = CommissioningRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CommissioningRecord.objects.filter(is_deleted=False)
        task_id = self.request.query_params.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SiteIssueViewSet(viewsets.ModelViewSet):
    serializer_class = SiteIssueSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SiteIssue.objects.filter(is_deleted=False)
        task_id = self.request.query_params.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        issue = self.get_object()
        if issue.status in ('resolved', 'closed'):
            return Response({'error': '该问题已解决或已关闭'}, status=status.HTTP_400_BAD_REQUEST)
        issue.status = 'resolved'
        issue.resolution = request.data.get('resolution', '')
        issue.save(update_fields=['status', 'resolution', 'updated_at'])
        return Response(SiteIssueSerializer(issue).data)


class CustomerAcceptanceViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerAcceptanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CustomerAcceptance.objects.filter(is_deleted=False)
        task_id = self.request.query_params.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
