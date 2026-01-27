"""
调试管理模块
Commissioning Management - 调试计划、问题跟踪、参数记录、报告生成
"""
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from apps.core.models import BaseModel
from django.conf import settings

User = settings.AUTH_USER_MODEL


class CommissioningPlan(BaseModel):
    """调试计划"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('SUSPENDED', '已暂停'),
    ]
    
    plan_no = models.CharField('计划编号', max_length=50, unique=True)
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                               related_name='commissioning_plans', verbose_name='关联项目')
    
    title = models.CharField('计划标题', max_length=200)
    description = models.TextField('计划描述', blank=True)
    
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # 时间安排
    planned_start_date = models.DateField('计划开始日期')
    planned_end_date = models.DateField('计划结束日期')
    actual_start_date = models.DateField('实际开始日期', null=True, blank=True)
    actual_end_date = models.DateField('实际结束日期', null=True, blank=True)
    
    # 调试地点
    location = models.CharField('调试地点', max_length=200)
    is_onsite = models.BooleanField('是否现场调试', default=False)
    
    # 负责人
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              related_name='led_commissioning_plans', verbose_name='负责人')
    
    # 调试目标
    objectives = models.JSONField('调试目标', default=list)
    acceptance_criteria = models.JSONField('验收标准', default=list)
    
    # 资源需求
    required_equipment = models.JSONField('所需设备', default=list)
    required_tools = models.JSONField('所需工具', default=list)
    
    # 完成情况
    progress = models.IntegerField('完成进度%', default=0)
    
    class Meta:
        db_table = 'commissioning_plan'
        verbose_name = '调试计划'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class CommissioningTask(BaseModel):
    """调试任务"""
    STATUS_CHOICES = [
        ('PENDING', '待开始'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('BLOCKED', '已阻塞'),
    ]
    
    RESULT_CHOICES = [
        ('PASS', '通过'),
        ('FAIL', '失败'),
        ('PARTIAL', '部分通过'),
        ('NA', '不适用'),
    ]
    
    plan = models.ForeignKey(CommissioningPlan, on_delete=models.CASCADE,
                            related_name='tasks', verbose_name='调试计划')
    
    sequence = models.IntegerField('任务序号')
    name = models.CharField('任务名称', max_length=200)
    description = models.TextField('任务描述', blank=True)
    
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='PENDING')
    result = models.CharField('结果', max_length=20, choices=RESULT_CHOICES, null=True, blank=True)
    
    # 执行信息
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='commissioning_tasks', verbose_name='执行人')
    planned_hours = models.DecimalField('计划工时', max_digits=6, decimal_places=2, default=0)
    actual_hours = models.DecimalField('实际工时', max_digits=6, decimal_places=2, default=0)
    
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    
    # 测试标准
    test_standard = models.TextField('测试标准', blank=True)
    test_method = models.TextField('测试方法', blank=True)
    
    notes = models.TextField('备注', blank=True)
    
    class Meta:
        db_table = 'commissioning_task'
        verbose_name = '调试任务'
        verbose_name_plural = verbose_name
        ordering = ['plan', 'sequence']


class CommissioningIssue(BaseModel):
    """调试问题"""
    SEVERITY_CHOICES = [
        ('LOW', '轻微'),
        ('MEDIUM', '一般'),
        ('HIGH', '严重'),
        ('CRITICAL', '致命'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', '待处理'),
        ('ANALYZING', '分析中'),
        ('SOLVING', '解决中'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
        ('DEFERRED', '已延期'),
    ]
    
    CATEGORY_CHOICES = [
        ('MECHANICAL', '机械问题'),
        ('ELECTRICAL', '电气问题'),
        ('SOFTWARE', '软件问题'),
        ('PROCESS', '工艺问题'),
        ('DESIGN', '设计缺陷'),
        ('ASSEMBLY', '装配问题'),
        ('MATERIAL', '材料问题'),
        ('OTHER', '其他'),
    ]
    
    issue_no = models.CharField('问题编号', max_length=50, unique=True)
    plan = models.ForeignKey(CommissioningPlan, on_delete=models.CASCADE,
                            related_name='issues', verbose_name='调试计划')
    task = models.ForeignKey(CommissioningTask, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='issues', verbose_name='相关任务')
    
    title = models.CharField('问题标题', max_length=200)
    description = models.TextField('问题描述')
    
    category = models.CharField('问题分类', max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField('严重程度', max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # 发现信息
    found_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='found_issues', verbose_name='发现人')
    found_at = models.DateTimeField('发现时间', auto_now_add=True)
    
    # 原因分析
    root_cause = models.TextField('根本原因', blank=True)
    analysis_result = models.TextField('分析结果', blank=True)
    
    # 解决方案
    solution = models.TextField('解决方案', blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='resolved_issues', verbose_name='解决人')
    resolved_at = models.DateTimeField('解决时间', null=True, blank=True)
    
    # 验证
    verified = models.BooleanField('已验证', default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='verified_issues', verbose_name='验证人')
    verified_at = models.DateTimeField('验证时间', null=True, blank=True)
    
    # 影响
    time_impact = models.IntegerField('工期影响(小时)', default=0)
    cost_impact = models.DecimalField('成本影响', max_digits=12, decimal_places=2, default=0)
    
    # 附件
    attachments = models.JSONField('附件列表', default=list)
    
    class Meta:
        db_table = 'commissioning_issue'
        verbose_name = '调试问题'
        verbose_name_plural = verbose_name
        ordering = ['-found_at']


class CommissioningParameter(BaseModel):
    """调试参数记录"""
    plan = models.ForeignKey(CommissioningPlan, on_delete=models.CASCADE,
                            related_name='parameters', verbose_name='调试计划')
    task = models.ForeignKey(CommissioningTask, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='parameters', verbose_name='相关任务')
    
    parameter_name = models.CharField('参数名称', max_length=100)
    parameter_code = models.CharField('参数编码', max_length=50, blank=True)
    unit = models.CharField('单位', max_length=20, blank=True)
    
    # 标准值
    standard_value = models.CharField('标准值', max_length=100, blank=True)
    min_value = models.DecimalField('最小值', max_digits=14, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField('最大值', max_digits=14, decimal_places=4, null=True, blank=True)
    
    # 实测值
    actual_value = models.CharField('实测值', max_length=100)
    actual_numeric = models.DecimalField('实测数值', max_digits=14, decimal_places=4, null=True, blank=True)
    
    # 判定
    is_qualified = models.BooleanField('是否合格', default=True)
    
    # 记录信息
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='recorded_parameters', verbose_name='记录人')
    recorded_at = models.DateTimeField('记录时间', auto_now_add=True)
    
    notes = models.TextField('备注', blank=True)
    
    class Meta:
        db_table = 'commissioning_parameter'
        verbose_name = '调试参数'
        verbose_name_plural = verbose_name


class CommissioningReport(BaseModel):
    """调试报告"""
    REPORT_TYPE_CHOICES = [
        ('DAILY', '日报'),
        ('WEEKLY', '周报'),
        ('STAGE', '阶段报告'),
        ('FINAL', '最终报告'),
    ]
    
    plan = models.ForeignKey(CommissioningPlan, on_delete=models.CASCADE,
                            related_name='reports', verbose_name='调试计划')
    
    report_no = models.CharField('报告编号', max_length=50, unique=True)
    report_type = models.CharField('报告类型', max_length=20, choices=REPORT_TYPE_CHOICES)
    title = models.CharField('报告标题', max_length=200)
    
    report_date = models.DateField('报告日期')
    
    # 报告内容
    summary = models.TextField('工作总结')
    achievements = models.JSONField('完成内容', default=list)
    issues_summary = models.JSONField('问题汇总', default=list)
    next_plan = models.JSONField('下一步计划', default=list)
    
    # 统计数据
    total_tasks = models.IntegerField('总任务数', default=0)
    completed_tasks = models.IntegerField('完成任务数', default=0)
    total_issues = models.IntegerField('总问题数', default=0)
    resolved_issues = models.IntegerField('已解决问题数', default=0)
    total_hours = models.DecimalField('总工时', max_digits=8, decimal_places=2, default=0)
    
    # 附件
    report_file = models.FileField('报告文件', upload_to='commissioning/reports/', 
                                   null=True, blank=True)
    
    # 编制人
    prepared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='prepared_reports', verbose_name='编制人')
    
    class Meta:
        db_table = 'commissioning_report'
        verbose_name = '调试报告'
        verbose_name_plural = verbose_name
        ordering = ['-report_date']


# ============ Serializers ============

class CommissioningTaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    
    class Meta:
        model = CommissioningTask
        fields = '__all__'


class CommissioningIssueSerializer(serializers.ModelSerializer):
    found_by_name = serializers.CharField(source='found_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = CommissioningIssue
        fields = '__all__'


class CommissioningParameterSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = CommissioningParameter
        fields = '__all__'


class CommissioningReportSerializer(serializers.ModelSerializer):
    prepared_by_name = serializers.CharField(source='prepared_by.get_full_name', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    
    class Meta:
        model = CommissioningReport
        fields = '__all__'


class CommissioningPlanSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    leader_name = serializers.CharField(source='leader.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tasks = CommissioningTaskSerializer(many=True, read_only=True)
    task_count = serializers.SerializerMethodField()
    issue_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CommissioningPlan
        fields = '__all__'
    
    def get_task_count(self, obj):
        return obj.tasks.count()
    
    def get_issue_count(self, obj):
        return obj.issues.count()


# ============ ViewSets ============

class CommissioningPlanViewSet(viewsets.ModelViewSet):
    """调试计划视图集"""
    queryset = CommissioningPlan.objects.filter(is_deleted=False)
    serializer_class = CommissioningPlanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        project = self.request.query_params.get('project')
        if project:
            qs = qs.filter(project_id=project)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        return qs.select_related('project', 'leader')
    
    def perform_create(self, serializer):
        today = timezone.now()
        prefix = f"CP{today.strftime('%Y%m%d')}"
        count = CommissioningPlan.objects.filter(plan_no__startswith=prefix).count() + 1
        plan_no = f"{prefix}{count:03d}"
        
        serializer.save(
            plan_no=plan_no,
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始调试"""
        plan = self.get_object()
        if plan.status != 'CONFIRMED':
            return Response({'error': '只能开始已确认的计划'}, status=400)
        
        plan.status = 'IN_PROGRESS'
        plan.actual_start_date = timezone.now().date()
        plan.save()
        
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成调试"""
        plan = self.get_object()
        if plan.status != 'IN_PROGRESS':
            return Response({'error': '只能完成进行中的计划'}, status=400)
        
        plan.status = 'COMPLETED'
        plan.actual_end_date = timezone.now().date()
        plan.progress = 100
        plan.save()
        
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """获取调试统计"""
        plan = self.get_object()
        
        tasks = plan.tasks.all()
        issues = plan.issues.all()
        
        stats = {
            'tasks': {
                'total': tasks.count(),
                'completed': tasks.filter(status='COMPLETED').count(),
                'in_progress': tasks.filter(status='IN_PROGRESS').count(),
                'pending': tasks.filter(status='PENDING').count(),
                'pass_rate': 0,
            },
            'issues': {
                'total': issues.count(),
                'open': issues.filter(status='OPEN').count(),
                'resolved': issues.filter(status='RESOLVED').count(),
                'by_severity': {},
                'by_category': {},
            },
            'hours': {
                'planned': float(tasks.aggregate(Sum('planned_hours'))['planned_hours__sum'] or 0),
                'actual': float(tasks.aggregate(Sum('actual_hours'))['actual_hours__sum'] or 0),
            },
            'parameters': {
                'total': plan.parameters.count(),
                'qualified': plan.parameters.filter(is_qualified=True).count(),
            }
        }
        
        # 计算通过率
        completed_tasks = tasks.filter(status='COMPLETED')
        if completed_tasks.exists():
            passed = completed_tasks.filter(result='PASS').count()
            stats['tasks']['pass_rate'] = round(passed / completed_tasks.count() * 100, 1)
        
        # 问题分布
        for severity_code, severity_name in CommissioningIssue.SEVERITY_CHOICES:
            count = issues.filter(severity=severity_code).count()
            if count > 0:
                stats['issues']['by_severity'][severity_code] = count
        
        for cat_code, cat_name in CommissioningIssue.CATEGORY_CHOICES:
            count = issues.filter(category=cat_code).count()
            if count > 0:
                stats['issues']['by_category'][cat_code] = count
        
        return Response(stats)
    
    @action(detail=True, methods=['post'])
    def generate_report(self, request, pk=None):
        """生成调试报告"""
        plan = self.get_object()
        report_type = request.data.get('report_type', 'STAGE')
        
        tasks = plan.tasks.all()
        issues = plan.issues.all()
        
        # 生成报告编号
        today = timezone.now()
        prefix = f"CR{today.strftime('%Y%m%d')}"
        count = CommissioningReport.objects.filter(report_no__startswith=prefix).count() + 1
        report_no = f"{prefix}{count:03d}"
        
        # 统计数据
        completed_tasks = tasks.filter(status='COMPLETED')
        resolved_issues = issues.filter(status__in=['RESOLVED', 'CLOSED'])
        
        report = CommissioningReport.objects.create(
            plan=plan,
            report_no=report_no,
            report_type=report_type,
            title=f"{plan.title} - {dict(CommissioningReport.REPORT_TYPE_CHOICES)[report_type]}",
            report_date=today.date(),
            summary=request.data.get('summary', ''),
            achievements=list(completed_tasks.values('name', 'result', 'actual_hours')),
            issues_summary=list(issues.values('title', 'severity', 'status', 'solution')),
            next_plan=request.data.get('next_plan', []),
            total_tasks=tasks.count(),
            completed_tasks=completed_tasks.count(),
            total_issues=issues.count(),
            resolved_issues=resolved_issues.count(),
            total_hours=tasks.aggregate(Sum('actual_hours'))['actual_hours__sum'] or 0,
            prepared_by=request.user,
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response(CommissioningReportSerializer(report).data)


class CommissioningTaskViewSet(viewsets.ModelViewSet):
    """调试任务视图集"""
    queryset = CommissioningTask.objects.filter(is_deleted=False)
    serializer_class = CommissioningTaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs.select_related('plan', 'assignee')
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始任务"""
        task = self.get_object()
        task.status = 'IN_PROGRESS'
        task.started_at = timezone.now()
        task.save()
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        task = self.get_object()
        task.status = 'COMPLETED'
        task.result = request.data.get('result', 'PASS')
        task.actual_hours = Decimal(str(request.data.get('actual_hours', 0)))
        task.completed_at = timezone.now()
        task.notes = request.data.get('notes', '')
        task.save()
        
        # 更新计划进度
        plan = task.plan
        total = plan.tasks.count()
        completed = plan.tasks.filter(status='COMPLETED').count()
        plan.progress = int(completed / total * 100) if total > 0 else 0
        plan.save()
        
        return Response({'status': 'success'})


class CommissioningIssueViewSet(viewsets.ModelViewSet):
    """调试问题视图集"""
    queryset = CommissioningIssue.objects.filter(is_deleted=False)
    serializer_class = CommissioningIssueSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        severity = self.request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        
        return qs.select_related('plan', 'found_by', 'resolved_by')
    
    def perform_create(self, serializer):
        today = timezone.now()
        prefix = f"CI{today.strftime('%Y%m%d')}"
        count = CommissioningIssue.objects.filter(issue_no__startswith=prefix).count() + 1
        issue_no = f"{prefix}{count:03d}"
        
        serializer.save(
            issue_no=issue_no,
            found_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决问题"""
        issue = self.get_object()
        issue.solution = request.data.get('solution', '')
        issue.root_cause = request.data.get('root_cause', '')
        issue.status = 'RESOLVED'
        issue.resolved_by = request.user
        issue.resolved_at = timezone.now()
        issue.save()
        
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """验证问题"""
        issue = self.get_object()
        issue.verified = True
        issue.verified_by = request.user
        issue.verified_at = timezone.now()
        issue.status = 'CLOSED'
        issue.save()
        
        return Response({'status': 'success'})


class CommissioningParameterViewSet(viewsets.ModelViewSet):
    """调试参数视图集"""
    queryset = CommissioningParameter.objects.filter(is_deleted=False)
    serializer_class = CommissioningParameterSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs
    
    def perform_create(self, serializer):
        # 判断是否合格
        data = serializer.validated_data
        is_qualified = True
        
        if data.get('actual_numeric') is not None:
            if data.get('min_value') is not None and data['actual_numeric'] < data['min_value']:
                is_qualified = False
            if data.get('max_value') is not None and data['actual_numeric'] > data['max_value']:
                is_qualified = False
        
        serializer.save(
            is_qualified=is_qualified,
            recorded_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user
        )


class CommissioningReportViewSet(viewsets.ModelViewSet):
    """调试报告视图集"""
    queryset = CommissioningReport.objects.filter(is_deleted=False)
    serializer_class = CommissioningReportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs.select_related('plan', 'prepared_by')
