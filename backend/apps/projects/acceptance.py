"""
验收管理模块 - 针对非标自动化行业
包含：出厂验收(FAT)、现场验收(SAT)、验收检查项、验收报告
"""
from django.db import models
from django.db.models import Avg, Count
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin


# =============================================================================
# 模型定义
# =============================================================================

class AcceptanceTemplate(BaseModel):
    """验收模板"""
    TYPE_CHOICES = [
        ('FAT', '出厂验收'),
        ('SAT', '现场验收'),
        ('PARTIAL', '部分验收'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='模板编号')
    name = models.CharField(max_length=200, verbose_name='模板名称')
    acceptance_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='验收类型')
    description = models.TextField(blank=True, verbose_name='模板说明')
    
    # 验收检查项模板
    check_items = models.JSONField(default=list, verbose_name='检查项模板')
    # 格式: [{"category": "功能测试", "items": [{"name": "检查项名称", "criteria": "判定标准", "weight": 10}]}]
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'acceptance_template'
        verbose_name = '验收模板'
        verbose_name_plural = verbose_name
        ordering = ['acceptance_type', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Acceptance(BaseModel):
    """验收单"""
    TYPE_CHOICES = [
        ('FAT', '出厂验收'),
        ('SAT', '现场验收'),
        ('PARTIAL', '部分验收'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PLANNED', '已计划'),
        ('IN_PROGRESS', '进行中'),
        ('PENDING_REVIEW', '待评审'),
        ('PASSED', '验收通过'),
        ('CONDITIONAL', '有条件通过'),
        ('FAILED', '验收不通过'),
        ('CANCELLED', '已取消'),
    ]
    
    RESULT_CHOICES = [
        ('PASS', '通过'),
        ('CONDITIONAL_PASS', '有条件通过'),
        ('FAIL', '不通过'),
    ]
    
    # 基本信息
    acceptance_no = models.CharField(max_length=50, unique=True, verbose_name='验收单号')
    name = models.CharField(max_length=200, verbose_name='验收名称')
    acceptance_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='验收类型')
    
    # 关联信息
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='acceptances',
        verbose_name='项目'
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='acceptances',
        verbose_name='客户'
    )
    equipment = models.ForeignKey(
        'projects.EquipmentArchive',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acceptances',
        verbose_name='设备'
    )
    template = models.ForeignKey(
        AcceptanceTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='验收模板'
    )
    
    # 时间信息
    planned_date = models.DateField(verbose_name='计划验收日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际验收日期')
    
    # 地点
    location = models.CharField(max_length=200, verbose_name='验收地点')
    
    # 人员
    our_participants = models.ManyToManyField(
        'accounts.User',
        related_name='participated_acceptances',
        blank=True,
        verbose_name='我方参与人员'
    )
    customer_participants = models.TextField(blank=True, verbose_name='客户参与人员')
    
    # 状态和结果
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, null=True, blank=True, verbose_name='验收结果')
    
    # 验收意见
    our_opinion = models.TextField(blank=True, verbose_name='我方意见')
    customer_opinion = models.TextField(blank=True, verbose_name='客户意见')
    
    # 遗留问题和整改
    pending_issues = models.TextField(blank=True, verbose_name='遗留问题')
    rectification_deadline = models.DateField(null=True, blank=True, verbose_name='整改期限')
    
    # 签字信息
    our_signer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_acceptances',
        verbose_name='我方签字人'
    )
    our_sign_date = models.DateField(null=True, blank=True, verbose_name='我方签字日期')
    customer_signer = models.CharField(max_length=100, blank=True, verbose_name='客户签字人')
    customer_sign_date = models.DateField(null=True, blank=True, verbose_name='客户签字日期')
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'acceptance'
        verbose_name = '验收单'
        verbose_name_plural = verbose_name
        ordering = ['-planned_date']
    
    def __str__(self):
        return f"{self.acceptance_no} - {self.name}"
    
    def calculate_pass_rate(self):
        """计算通过率"""
        items = self.check_items.all()
        if not items.exists():
            return 0
        passed = items.filter(result='PASS').count()
        return round(passed / items.count() * 100, 2)


class AcceptanceCheckItem(BaseModel):
    """验收检查项"""
    RESULT_CHOICES = [
        ('PENDING', '待检查'),
        ('PASS', '通过'),
        ('FAIL', '不通过'),
        ('NA', '不适用'),
    ]
    
    acceptance = models.ForeignKey(
        Acceptance,
        on_delete=models.CASCADE,
        related_name='check_items',
        verbose_name='验收单'
    )
    
    # 检查项信息
    category = models.CharField(max_length=100, verbose_name='检查类别')
    sequence = models.IntegerField(default=0, verbose_name='序号')
    name = models.CharField(max_length=200, verbose_name='检查项名称')
    criteria = models.TextField(verbose_name='判定标准')
    weight = models.IntegerField(default=10, verbose_name='权重')
    
    # 检查结果
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default='PENDING', verbose_name='检查结果')
    actual_value = models.CharField(max_length=200, blank=True, verbose_name='实测值')
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    # 检查人
    checker = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_items',
        verbose_name='检查人'
    )
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='检查时间')
    
    # 附件（照片、视频等）
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'acceptance_check_item'
        verbose_name = '验收检查项'
        verbose_name_plural = verbose_name
        ordering = ['acceptance', 'category', 'sequence']
    
    def __str__(self):
        return f"{self.acceptance.acceptance_no} - {self.name}"


class AcceptanceIssue(BaseModel):
    """验收问题"""
    SEVERITY_CHOICES = [
        ('CRITICAL', '严重'),
        ('MAJOR', '主要'),
        ('MINOR', '次要'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', '待处理'),
        ('IN_PROGRESS', '处理中'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
        ('WAIVED', '已豁免'),
    ]
    
    acceptance = models.ForeignKey(
        Acceptance,
        on_delete=models.CASCADE,
        related_name='issues',
        verbose_name='验收单'
    )
    check_item = models.ForeignKey(
        AcceptanceCheckItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issues',
        verbose_name='相关检查项'
    )
    
    issue_no = models.CharField(max_length=50, verbose_name='问题编号')
    title = models.CharField(max_length=200, verbose_name='问题标题')
    description = models.TextField(verbose_name='问题描述')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, verbose_name='严重程度')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN', verbose_name='状态')
    
    # 整改信息
    root_cause = models.TextField(blank=True, verbose_name='原因分析')
    solution = models.TextField(blank=True, verbose_name='解决方案')
    responsible_person = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_issues',
        verbose_name='负责人'
    )
    deadline = models.DateField(null=True, blank=True, verbose_name='整改期限')
    resolved_date = models.DateField(null=True, blank=True, verbose_name='解决日期')
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'acceptance_issue'
        verbose_name = '验收问题'
        verbose_name_plural = verbose_name
        ordering = ['-severity', 'status']
    
    def __str__(self):
        return f"{self.issue_no} - {self.title}"


# =============================================================================
# 序列化器
# =============================================================================

class AcceptanceTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_acceptance_type_display', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AcceptanceTemplate
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_item_count(self, obj):
        count = 0
        for category in obj.check_items:
            count += len(category.get('items', []))
        return count


class AcceptanceCheckItemSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    checker_name = serializers.CharField(source='checker.get_full_name', read_only=True)
    
    class Meta:
        model = AcceptanceCheckItem
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class AcceptanceIssueSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    responsible_name = serializers.CharField(source='responsible_person.get_full_name', read_only=True)
    
    class Meta:
        model = AcceptanceIssue
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class AcceptanceSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_acceptance_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    our_signer_name = serializers.CharField(source='our_signer.get_full_name', read_only=True)
    check_items = AcceptanceCheckItemSerializer(many=True, read_only=True)
    issues = AcceptanceIssueSerializer(many=True, read_only=True)
    pass_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Acceptance
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_pass_rate(self, obj):
        return obj.calculate_pass_rate()


class AcceptanceListSerializer(serializers.ModelSerializer):
    """列表用简化序列化器"""
    type_display = serializers.CharField(source='get_acceptance_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    pass_rate = serializers.SerializerMethodField()
    issue_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Acceptance
        fields = [
            'id', 'acceptance_no', 'name', 'acceptance_type', 'type_display',
            'project', 'project_name', 'customer', 'customer_name',
            'equipment', 'equipment_no', 'planned_date', 'actual_date',
            'location', 'status', 'status_display', 'result', 'result_display',
            'pass_rate', 'issue_count', 'created_at'
        ]
    
    def get_pass_rate(self, obj):
        return obj.calculate_pass_rate()
    
    def get_issue_count(self, obj):
        return obj.issues.filter(status__in=['OPEN', 'IN_PROGRESS']).count()


# =============================================================================
# 视图集
# =============================================================================

class AcceptanceTemplateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """验收模板管理"""
    queryset = AcceptanceTemplate.objects.all()
    serializer_class = AcceptanceTemplateSerializer
    filterset_fields = ['acceptance_type', 'is_active', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'acceptance_type', 'created_at']
    
    @action(detail=False, methods=['get'])
    def active_templates(self, request):
        """获取所有启用的模板"""
        acceptance_type = request.query_params.get('type')
        queryset = self.get_queryset().filter(is_active=True, is_deleted=False)
        if acceptance_type:
            queryset = queryset.filter(acceptance_type=acceptance_type)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AcceptanceViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """验收单管理"""
    queryset = Acceptance.objects.all()
    filterset_fields = ['project', 'customer', 'equipment', 'acceptance_type', 'status', 'result', 'is_deleted']
    search_fields = ['acceptance_no', 'name', 'location']
    ordering_fields = ['acceptance_no', 'planned_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AcceptanceListSerializer
        return AcceptanceSerializer
    
    def get_queryset(self):
        return super().get_queryset().select_related(
            'project', 'customer', 'equipment', 'our_signer'
        )
    
    @action(detail=True, methods=['post'])
    def apply_template(self, request, pk=None):
        """应用验收模板"""
        acceptance = self.get_object()
        template_id = request.data.get('template_id')
        
        try:
            template = AcceptanceTemplate.objects.get(id=template_id)
            acceptance.template = template
            acceptance.save()
            
            # 创建检查项
            sequence = 0
            for category_data in template.check_items:
                category = category_data.get('category', '')
                for item_data in category_data.get('items', []):
                    sequence += 1
                    AcceptanceCheckItem.objects.create(
                        acceptance=acceptance,
                        category=category,
                        sequence=sequence,
                        name=item_data.get('name', ''),
                        criteria=item_data.get('criteria', ''),
                        weight=item_data.get('weight', 10)
                    )
            
            return Response(AcceptanceSerializer(acceptance).data)
        except AcceptanceTemplate.DoesNotExist:
            return Response({'error': '模板不存在'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始验收"""
        acceptance = self.get_object()
        if acceptance.status not in ['DRAFT', 'PLANNED']:
            return Response({'error': '只有草稿或已计划状态才能开始'}, status=status.HTTP_400_BAD_REQUEST)
        
        from datetime import date
        acceptance.status = 'IN_PROGRESS'
        acceptance.actual_date = date.today()
        acceptance.save()
        return Response(AcceptanceSerializer(acceptance).data)
    
    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交评审"""
        acceptance = self.get_object()
        if acceptance.status != 'IN_PROGRESS':
            return Response({'error': '只有进行中状态才能提交评审'}, status=status.HTTP_400_BAD_REQUEST)
        
        acceptance.status = 'PENDING_REVIEW'
        acceptance.our_opinion = request.data.get('our_opinion', '')
        acceptance.save()
        return Response(AcceptanceSerializer(acceptance).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成验收"""
        acceptance = self.get_object()
        if acceptance.status != 'PENDING_REVIEW':
            return Response({'error': '只有待评审状态才能完成'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = request.data.get('result')
        if result not in ['PASS', 'CONDITIONAL_PASS', 'FAIL']:
            return Response({'error': '无效的验收结果'}, status=status.HTTP_400_BAD_REQUEST)
        
        status_map = {
            'PASS': 'PASSED',
            'CONDITIONAL_PASS': 'CONDITIONAL',
            'FAIL': 'FAILED'
        }
        
        acceptance.result = result
        acceptance.status = status_map[result]
        acceptance.customer_opinion = request.data.get('customer_opinion', '')
        acceptance.pending_issues = request.data.get('pending_issues', '')
        acceptance.rectification_deadline = request.data.get('rectification_deadline')
        acceptance.customer_signer = request.data.get('customer_signer', '')
        acceptance.customer_sign_date = request.data.get('customer_sign_date')
        acceptance.our_signer = request.user
        acceptance.our_sign_date = request.data.get('our_sign_date')
        acceptance.save()
        
        return Response(AcceptanceSerializer(acceptance).data)
    
    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """生成验收报告数据"""
        acceptance = self.get_object()
        
        # 统计数据
        check_items = acceptance.check_items.all()
        total_items = check_items.count()
        passed_items = check_items.filter(result='PASS').count()
        failed_items = check_items.filter(result='FAIL').count()
        na_items = check_items.filter(result='NA').count()
        pending_items = check_items.filter(result='PENDING').count()
        
        # 按类别统计
        categories = {}
        for item in check_items:
            if item.category not in categories:
                categories[item.category] = {'total': 0, 'passed': 0, 'failed': 0}
            categories[item.category]['total'] += 1
            if item.result == 'PASS':
                categories[item.category]['passed'] += 1
            elif item.result == 'FAIL':
                categories[item.category]['failed'] += 1
        
        # 问题统计
        issues = acceptance.issues.all()
        open_issues = issues.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
        
        report_data = {
            'acceptance': AcceptanceSerializer(acceptance).data,
            'statistics': {
                'total_items': total_items,
                'passed_items': passed_items,
                'failed_items': failed_items,
                'na_items': na_items,
                'pending_items': pending_items,
                'pass_rate': round(passed_items / (total_items - na_items) * 100, 2) if (total_items - na_items) > 0 else 0,
            },
            'categories': categories,
            'issues': {
                'total': issues.count(),
                'open': open_issues,
                'critical': issues.filter(severity='CRITICAL').count(),
                'major': issues.filter(severity='MAJOR').count(),
                'minor': issues.filter(severity='MINOR').count(),
            }
        }
        
        return Response(report_data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """验收统计"""
        queryset = self.get_queryset().filter(is_deleted=False)
        
        # 按项目筛选
        project_id = request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        stats = {
            'total': queryset.count(),
            'by_type': {},
            'by_status': {},
            'by_result': {},
            'avg_pass_rate': 0,
        }
        
        # 按类型统计
        for type_code, type_name in Acceptance.TYPE_CHOICES:
            count = queryset.filter(acceptance_type=type_code).count()
            stats['by_type'][type_code] = {'name': type_name, 'count': count}
        
        # 按状态统计
        for status_code, status_name in Acceptance.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            stats['by_status'][status_code] = {'name': status_name, 'count': count}
        
        # 按结果统计
        for result_code, result_name in Acceptance.RESULT_CHOICES:
            count = queryset.filter(result=result_code).count()
            stats['by_result'][result_code] = {'name': result_name, 'count': count}
        
        return Response(stats)


class AcceptanceCheckItemViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """验收检查项管理"""
    queryset = AcceptanceCheckItem.objects.all()
    serializer_class = AcceptanceCheckItemSerializer
    filterset_fields = ['acceptance', 'category', 'result', 'is_deleted']
    search_fields = ['name', 'criteria']
    ordering_fields = ['sequence', 'created_at']
    
    @action(detail=True, methods=['post'])
    def check(self, request, pk=None):
        """执行检查"""
        item = self.get_object()
        
        from django.utils import timezone
        item.result = request.data.get('result', 'PENDING')
        item.actual_value = request.data.get('actual_value', '')
        item.remarks = request.data.get('remarks', '')
        item.checker = request.user
        item.check_time = timezone.now()
        item.save()
        
        # 如果检查不通过，自动创建问题
        if item.result == 'FAIL' and request.data.get('create_issue', False):
            AcceptanceIssue.objects.create(
                acceptance=item.acceptance,
                check_item=item,
                issue_no=f"ISS-{item.acceptance.acceptance_no}-{item.sequence:03d}",
                title=f"检查项不通过: {item.name}",
                description=request.data.get('issue_description', item.remarks),
                severity=request.data.get('severity', 'MAJOR'),
            )
        
        return Response(AcceptanceCheckItemSerializer(item).data)


class AcceptanceIssueViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """验收问题管理"""
    queryset = AcceptanceIssue.objects.all()
    serializer_class = AcceptanceIssueSerializer
    filterset_fields = ['acceptance', 'severity', 'status', 'responsible_person', 'is_deleted']
    search_fields = ['issue_no', 'title', 'description']
    ordering_fields = ['severity', 'status', 'deadline', 'created_at']
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决问题"""
        issue = self.get_object()
        if issue.status not in ['OPEN', 'IN_PROGRESS']:
            return Response({'error': '只有待处理或处理中状态才能解决'}, status=status.HTTP_400_BAD_REQUEST)
        
        from datetime import date
        issue.status = 'RESOLVED'
        issue.root_cause = request.data.get('root_cause', '')
        issue.solution = request.data.get('solution', '')
        issue.resolved_date = date.today()
        issue.save()
        
        return Response(AcceptanceIssueSerializer(issue).data)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭问题"""
        issue = self.get_object()
        if issue.status != 'RESOLVED':
            return Response({'error': '只有已解决状态才能关闭'}, status=status.HTTP_400_BAD_REQUEST)
        
        issue.status = 'CLOSED'
        issue.save()
        return Response(AcceptanceIssueSerializer(issue).data)
    
    @action(detail=True, methods=['post'])
    def waive(self, request, pk=None):
        """豁免问题"""
        issue = self.get_object()
        
        issue.status = 'WAIVED'
        issue.solution = request.data.get('waive_reason', '客户同意豁免')
        issue.save()
        return Response(AcceptanceIssueSerializer(issue).data)
