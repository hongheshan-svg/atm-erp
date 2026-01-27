"""
调试管理模块
Debug Management - 调试计划、问题跟踪、参数记录、报告生成
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


class DebugPlan(BaseModel):
    """调试计划"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('SUSPENDED', '暂停'),
        ('CANCELLED', '已取消'),
    ]
    
    plan_no = models.CharField('计划编号', max_length=50, unique=True)
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                               related_name='debug_plans', verbose_name='项目')
    equipment = models.ForeignKey('projects.EquipmentArchive', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='debug_plans', verbose_name='设备')
    
    name = models.CharField('计划名称', max_length=200)
    description = models.TextField('调试内容描述', blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # 计划时间
    planned_start_date = models.DateField('计划开始日期')
    planned_end_date = models.DateField('计划结束日期')
    actual_start_date = models.DateField('实际开始日期', null=True, blank=True)
    actual_end_date = models.DateField('实际结束日期', null=True, blank=True)
    
    # 资源
    workstation = models.CharField('调试工位', max_length=100, blank=True)
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                              related_name='led_debug_plans', verbose_name='负责人')
    
    # 目标
    target_parameters = models.TextField('目标参数', blank=True)
    acceptance_criteria = models.TextField('验收标准', blank=True)
    
    # 结果
    result = models.CharField('调试结果', max_length=20, blank=True,
                             choices=[('PASS', '通过'), ('FAIL', '失败'), ('PARTIAL', '部分通过')])
    result_summary = models.TextField('结果总结', blank=True)
    
    class Meta:
        db_table = 'debug_plan'
        verbose_name = '调试计划'
        ordering = ['-planned_start_date']
    
    def __str__(self):
        return f'{self.plan_no} - {self.name}'
    
    def save(self, *args, **kwargs):
        if not self.plan_no:
            today = timezone.now()
            prefix = f'DBG{today.strftime("%Y%m%d")}'
            last = DebugPlan.objects.filter(plan_no__startswith=prefix).order_by('-plan_no').first()
            if last:
                seq = int(last.plan_no[-4:]) + 1
            else:
                seq = 1
            self.plan_no = f'{prefix}{seq:04d}'
        super().save(*args, **kwargs)


class DebugPlanMember(BaseModel):
    """调试计划成员"""
    plan = models.ForeignKey(DebugPlan, on_delete=models.CASCADE,
                            related_name='members', verbose_name='调试计划')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                            related_name='debug_assignments', verbose_name='人员')
    role = models.CharField('角色', max_length=50)  # 主调、协调、记录等
    
    class Meta:
        db_table = 'debug_plan_member'
        verbose_name = '调试计划成员'
        unique_together = ['plan', 'user']


class DebugTask(BaseModel):
    """调试任务"""
    STATUS_CHOICES = [
        ('PENDING', '待开始'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('BLOCKED', '受阻'),
        ('SKIPPED', '跳过'),
    ]
    
    plan = models.ForeignKey(DebugPlan, on_delete=models.CASCADE,
                            related_name='tasks', verbose_name='调试计划')
    sequence = models.IntegerField('序号', default=0)
    name = models.CharField('任务名称', max_length=200)
    description = models.TextField('任务描述', blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='debug_tasks', verbose_name='执行人')
    planned_hours = models.DecimalField('计划工时', max_digits=8, decimal_places=2, default=0)
    actual_hours = models.DecimalField('实际工时', max_digits=8, decimal_places=2, default=0)
    
    start_time = models.DateTimeField('开始时间', null=True, blank=True)
    end_time = models.DateTimeField('结束时间', null=True, blank=True)
    
    result = models.CharField('结果', max_length=20, blank=True,
                             choices=[('PASS', '通过'), ('FAIL', '失败'), ('NA', '不适用')])
    result_notes = models.TextField('结果说明', blank=True)
    
    class Meta:
        db_table = 'debug_task'
        verbose_name = '调试任务'
        ordering = ['plan', 'sequence']


class DebugIssue(BaseModel):
    """调试问题"""
    SEVERITY_CHOICES = [
        ('CRITICAL', '严重'),
        ('MAJOR', '重要'),
        ('MINOR', '一般'),
        ('TRIVIAL', '轻微'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', '待处理'),
        ('ANALYZING', '分析中'),
        ('FIXING', '修复中'),
        ('TESTING', '测试中'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
        ('DEFERRED', '延后处理'),
    ]
    
    issue_no = models.CharField('问题编号', max_length=50, unique=True)
    plan = models.ForeignKey(DebugPlan, on_delete=models.CASCADE,
                            related_name='issues', verbose_name='调试计划')
    task = models.ForeignKey(DebugTask, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='issues', verbose_name='关联任务')
    
    title = models.CharField('问题标题', max_length=200)
    description = models.TextField('问题描述')
    severity = models.CharField('严重程度', max_length=20, choices=SEVERITY_CHOICES, default='MINOR')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # 问题分类
    CATEGORY_CHOICES = [
        ('MECHANICAL', '机械问题'),
        ('ELECTRICAL', '电气问题'),
        ('SOFTWARE', '软件问题'),
        ('PROCESS', '工艺问题'),
        ('MATERIAL', '材料问题'),
        ('DESIGN', '设计问题'),
        ('OTHER', '其他'),
    ]
    category = models.CharField('问题分类', max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    
    # 发现信息
    found_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                related_name='found_debug_issues', verbose_name='发现人')
    found_date = models.DateTimeField('发现时间', auto_now_add=True)
    
    # 分析
    root_cause = models.TextField('根本原因', blank=True)
    analysis_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='analyzed_debug_issues', verbose_name='分析人')
    
    # 解决方案
    solution = models.TextField('解决方案', blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='resolved_debug_issues', verbose_name='解决人')
    resolved_date = models.DateTimeField('解决时间', null=True, blank=True)
    
    # 预防措施
    preventive_action = models.TextField('预防措施', blank=True)
    
    # 关联ECN
    ecn_required = models.BooleanField('需要设计变更', default=False)
    ecn_no = models.CharField('关联ECN编号', max_length=50, blank=True)
    
    class Meta:
        db_table = 'debug_issue'
        verbose_name = '调试问题'
        ordering = ['-found_date']
    
    def save(self, *args, **kwargs):
        if not self.issue_no:
            today = timezone.now()
            prefix = f'DBI{today.strftime("%Y%m%d")}'
            last = DebugIssue.objects.filter(issue_no__startswith=prefix).order_by('-issue_no').first()
            if last:
                seq = int(last.issue_no[-4:]) + 1
            else:
                seq = 1
            self.issue_no = f'{prefix}{seq:04d}'
        super().save(*args, **kwargs)


class DebugParameter(BaseModel):
    """调试参数记录"""
    plan = models.ForeignKey(DebugPlan, on_delete=models.CASCADE,
                            related_name='parameters', verbose_name='调试计划')
    task = models.ForeignKey(DebugTask, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='parameters', verbose_name='调试任务')
    
    parameter_name = models.CharField('参数名称', max_length=100)
    parameter_code = models.CharField('参数代码', max_length=50, blank=True)
    unit = models.CharField('单位', max_length=20, blank=True)
    
    # 目标值
    target_value = models.CharField('目标值', max_length=100, blank=True)
    min_value = models.DecimalField('最小值', max_digits=14, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField('最大值', max_digits=14, decimal_places=4, null=True, blank=True)
    
    # 实际值
    actual_value = models.CharField('实际值', max_length=100, blank=True)
    actual_numeric = models.DecimalField('实际数值', max_digits=14, decimal_places=4, null=True, blank=True)
    
    # 判定
    is_qualified = models.BooleanField('是否合格', null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='recorded_debug_params', verbose_name='记录人')
    recorded_at = models.DateTimeField('记录时间', auto_now_add=True)
    remarks = models.TextField('备注', blank=True)
    
    class Meta:
        db_table = 'debug_parameter'
        verbose_name = '调试参数记录'
        ordering = ['plan', 'parameter_name']


class DebugLog(BaseModel):
    """调试日志"""
    plan = models.ForeignKey(DebugPlan, on_delete=models.CASCADE,
                            related_name='logs', verbose_name='调试计划')
    
    LOG_TYPE_CHOICES = [
        ('START', '开始调试'),
        ('PAUSE', '暂停'),
        ('RESUME', '恢复'),
        ('COMPLETE', '完成'),
        ('ISSUE', '发现问题'),
        ('PROGRESS', '进度更新'),
        ('PARAMETER', '参数记录'),
        ('NOTE', '备注'),
    ]
    
    log_type = models.CharField('日志类型', max_length=20, choices=LOG_TYPE_CHOICES)
    content = models.TextField('日志内容')
    logged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                 related_name='debug_logs', verbose_name='记录人')
    logged_at = models.DateTimeField('记录时间', auto_now_add=True)
    
    # 关联图片/附件
    attachments = models.JSONField('附件', default=list, blank=True)
    
    class Meta:
        db_table = 'debug_log'
        verbose_name = '调试日志'
        ordering = ['-logged_at']


# ==================== Serializers ====================

class DebugPlanMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = DebugPlanMember
        fields = '__all__'


class DebugTaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = DebugTask
        fields = '__all__'


class DebugIssueSerializer(serializers.ModelSerializer):
    found_by_name = serializers.CharField(source='found_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = DebugIssue
        fields = '__all__'


class DebugParameterSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = DebugParameter
        fields = '__all__'


class DebugLogSerializer(serializers.ModelSerializer):
    logged_by_name = serializers.CharField(source='logged_by.get_full_name', read_only=True)
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    
    class Meta:
        model = DebugLog
        fields = '__all__'


class DebugPlanSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    leader_name = serializers.CharField(source='leader.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    members = DebugPlanMemberSerializer(many=True, read_only=True)
    tasks = DebugTaskSerializer(many=True, read_only=True)
    
    # 统计
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()
    issue_count = serializers.SerializerMethodField()
    open_issue_count = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    
    class Meta:
        model = DebugPlan
        fields = '__all__'
    
    def get_task_count(self, obj):
        return obj.tasks.count()
    
    def get_completed_task_count(self, obj):
        return obj.tasks.filter(status='COMPLETED').count()
    
    def get_issue_count(self, obj):
        return obj.issues.count()
    
    def get_open_issue_count(self, obj):
        return obj.issues.exclude(status__in=['RESOLVED', 'CLOSED']).count()
    
    def get_progress(self, obj):
        total = obj.tasks.count()
        if total == 0:
            return 0
        completed = obj.tasks.filter(status='COMPLETED').count()
        return round(completed / total * 100, 1)


# ==================== ViewSets ====================

class DebugPlanViewSet(viewsets.ModelViewSet):
    """调试计划管理"""
    queryset = DebugPlan.objects.filter(is_deleted=False)
    serializer_class = DebugPlanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get('project')
        status_filter = self.request.query_params.get('status')
        
        if project:
            qs = qs.filter(project_id=project)
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        return qs.select_related('project', 'leader', 'equipment')
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始调试"""
        plan = self.get_object()
        plan.status = 'IN_PROGRESS'
        plan.actual_start_date = timezone.now().date()
        plan.save()
        
        # 记录日志
        DebugLog.objects.create(
            plan=plan,
            log_type='START',
            content='调试开始',
            logged_by=request.user,
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response({'message': '调试已开始'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成调试"""
        plan = self.get_object()
        
        plan.status = 'COMPLETED'
        plan.actual_end_date = timezone.now().date()
        plan.result = request.data.get('result', 'PASS')
        plan.result_summary = request.data.get('result_summary', '')
        plan.save()
        
        # 记录日志
        DebugLog.objects.create(
            plan=plan,
            log_type='COMPLETE',
            content=f'调试完成，结果：{plan.get_result_display()}',
            logged_by=request.user,
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response({'message': '调试已完成'})
    
    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """生成调试报告"""
        plan = self.get_object()
        
        # 汇总数据
        tasks = plan.tasks.all()
        issues = plan.issues.all()
        parameters = plan.parameters.all()
        logs = plan.logs.all()
        
        report_data = {
            'plan': DebugPlanSerializer(plan).data,
            'summary': {
                'total_tasks': tasks.count(),
                'completed_tasks': tasks.filter(status='COMPLETED').count(),
                'passed_tasks': tasks.filter(result='PASS').count(),
                'failed_tasks': tasks.filter(result='FAIL').count(),
                'total_issues': issues.count(),
                'resolved_issues': issues.filter(status__in=['RESOLVED', 'CLOSED']).count(),
                'open_issues': issues.exclude(status__in=['RESOLVED', 'CLOSED']).count(),
                'critical_issues': issues.filter(severity='CRITICAL').count(),
                'total_parameters': parameters.count(),
                'qualified_parameters': parameters.filter(is_qualified=True).count(),
                'unqualified_parameters': parameters.filter(is_qualified=False).count(),
                'total_hours': float(tasks.aggregate(total=Sum('actual_hours'))['total'] or 0),
            },
            'issues_by_category': list(issues.values('category').annotate(count=Count('id'))),
            'issues_by_severity': list(issues.values('severity').annotate(count=Count('id'))),
            'parameter_results': DebugParameterSerializer(parameters, many=True).data,
            'issue_list': DebugIssueSerializer(issues, many=True).data,
            'activity_log': DebugLogSerializer(logs[:50], many=True).data,
        }
        
        return Response(report_data)
    
    @action(detail=False, methods=['get'])
    def workstation_schedule(self, request):
        """工位排班"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        qs = self.get_queryset().filter(
            status__in=['CONFIRMED', 'IN_PROGRESS']
        )
        
        if start_date:
            qs = qs.filter(planned_end_date__gte=start_date)
        if end_date:
            qs = qs.filter(planned_start_date__lte=end_date)
        
        # 按工位分组
        schedule = {}
        for plan in qs:
            ws = plan.workstation or '未分配'
            if ws not in schedule:
                schedule[ws] = []
            schedule[ws].append({
                'id': plan.id,
                'plan_no': plan.plan_no,
                'name': plan.name,
                'project_name': plan.project.name,
                'start_date': plan.planned_start_date,
                'end_date': plan.planned_end_date,
                'status': plan.status,
                'leader_name': plan.leader.get_full_name() if plan.leader else '',
            })
        
        return Response(schedule)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """调试统计"""
        project_id = request.query_params.get('project')
        
        qs = self.get_queryset()
        if project_id:
            qs = qs.filter(project_id=project_id)
        
        # 基础统计
        stats = {
            'total_plans': qs.count(),
            'by_status': {},
            'by_result': {},
            'avg_duration_days': 0,
            'issue_stats': {},
        }
        
        # 按状态统计
        status_counts = qs.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats['by_status'][item['status']] = item['count']
        
        # 按结果统计
        result_counts = qs.exclude(result='').values('result').annotate(count=Count('id'))
        for item in result_counts:
            stats['by_result'][item['result']] = item['count']
        
        # 问题统计
        all_issues = DebugIssue.objects.filter(plan__in=qs, is_deleted=False)
        stats['issue_stats'] = {
            'total': all_issues.count(),
            'open': all_issues.exclude(status__in=['RESOLVED', 'CLOSED']).count(),
            'critical': all_issues.filter(severity='CRITICAL').count(),
            'by_category': list(all_issues.values('category').annotate(count=Count('id'))),
        }
        
        return Response(stats)


class DebugTaskViewSet(viewsets.ModelViewSet):
    """调试任务管理"""
    queryset = DebugTask.objects.filter(is_deleted=False)
    serializer_class = DebugTaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始任务"""
        task = self.get_object()
        task.status = 'IN_PROGRESS'
        task.start_time = timezone.now()
        task.save()
        return Response({'message': '任务已开始'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        task = self.get_object()
        task.status = 'COMPLETED'
        task.end_time = timezone.now()
        task.result = request.data.get('result', 'PASS')
        task.result_notes = request.data.get('result_notes', '')
        task.actual_hours = request.data.get('actual_hours', 0)
        task.save()
        return Response({'message': '任务已完成'})


class DebugIssueViewSet(viewsets.ModelViewSet):
    """调试问题管理"""
    queryset = DebugIssue.objects.filter(is_deleted=False)
    serializer_class = DebugIssueSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        status_filter = self.request.query_params.get('status')
        severity = self.request.query_params.get('severity')
        
        if plan:
            qs = qs.filter(plan_id=plan)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if severity:
            qs = qs.filter(severity=severity)
        
        return qs
    
    def perform_create(self, serializer):
        serializer.save(found_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决问题"""
        issue = self.get_object()
        issue.status = 'RESOLVED'
        issue.solution = request.data.get('solution', '')
        issue.resolved_by = request.user
        issue.resolved_date = timezone.now()
        issue.preventive_action = request.data.get('preventive_action', '')
        issue.save()
        return Response({'message': '问题已解决'})
    
    @action(detail=False, methods=['get'])
    def knowledge_base(self, request):
        """问题知识库 - 已解决的问题及解决方案"""
        category = request.query_params.get('category')
        keyword = request.query_params.get('keyword')
        
        qs = self.get_queryset().filter(status__in=['RESOLVED', 'CLOSED'])
        
        if category:
            qs = qs.filter(category=category)
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(solution__icontains=keyword)
            )
        
        return Response(DebugIssueSerializer(qs[:50], many=True).data)


class DebugParameterViewSet(viewsets.ModelViewSet):
    """调试参数管理"""
    queryset = DebugParameter.objects.filter(is_deleted=False)
    serializer_class = DebugParameterSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs
    
    def perform_create(self, serializer):
        instance = serializer.save(recorded_by=self.request.user)
        # 自动判定合格
        if instance.actual_numeric is not None:
            if instance.min_value is not None and instance.max_value is not None:
                instance.is_qualified = instance.min_value <= instance.actual_numeric <= instance.max_value
                instance.save()
    
    @action(detail=False, methods=['post'])
    def batch_record(self, request):
        """批量记录参数"""
        plan_id = request.data.get('plan')
        parameters = request.data.get('parameters', [])
        
        created = []
        for param in parameters:
            obj = DebugParameter.objects.create(
                plan_id=plan_id,
                parameter_name=param.get('name'),
                parameter_code=param.get('code', ''),
                unit=param.get('unit', ''),
                target_value=param.get('target_value', ''),
                min_value=param.get('min_value'),
                max_value=param.get('max_value'),
                actual_value=param.get('actual_value', ''),
                actual_numeric=param.get('actual_numeric'),
                recorded_by=request.user,
                created_by=request.user,
                updated_by=request.user
            )
            # 自动判定
            if obj.actual_numeric is not None and obj.min_value is not None and obj.max_value is not None:
                obj.is_qualified = obj.min_value <= obj.actual_numeric <= obj.max_value
                obj.save()
            created.append(obj.id)
        
        return Response({'message': f'已记录{len(created)}个参数', 'ids': created})


class DebugLogViewSet(viewsets.ModelViewSet):
    """调试日志管理"""
    queryset = DebugLog.objects.filter(is_deleted=False)
    serializer_class = DebugLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        plan = self.request.query_params.get('plan')
        if plan:
            qs = qs.filter(plan_id=plan)
        return qs
    
    def perform_create(self, serializer):
        serializer.save(logged_by=self.request.user)
