"""
项目里程碑管理
Project Milestone Management
跟踪项目关键节点和交付物
"""
from datetime import date, timedelta

from django.db import models
from django.db.models import Sum
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class Milestone(BaseModel):
    """
    项目里程碑
    """
    MILESTONE_TYPES = [
        ('KICKOFF', '项目启动'),
        ('DESIGN', '设计评审'),
        ('PROCUREMENT', '采购完成'),
        ('ASSEMBLY', '组装完成'),
        ('DEBUGGING', '调试完成'),
        ('FAT', '厂内验收'),
        ('SHIPMENT', '设备发货'),
        ('INSTALLATION', '安装完成'),
        ('SAT', '现场验收'),
        ('HANDOVER', '项目移交'),
        ('WARRANTY', '质保到期'),
        ('CUSTOM', '自定义'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待开始'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('DELAYED', '已延期'),
        ('CANCELLED', '已取消'),
    ]

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='milestones',
        verbose_name='项目'
    )

    code = models.CharField(max_length=50, verbose_name='里程碑编码')
    name = models.CharField(max_length=200, verbose_name='里程碑名称')
    milestone_type = models.CharField(
        max_length=20,
        choices=MILESTONE_TYPES,
        default='CUSTOM',
        verbose_name='类型'
    )

    # 时间
    planned_date = models.DateField(verbose_name='计划日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际日期')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    progress = models.IntegerField(default=0, verbose_name='进度%')

    # 权重（用于计算项目整体进度）
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        verbose_name='权重%'
    )

    # 负责人
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_milestones',
        verbose_name='负责人'
    )

    # 关联付款节点
    payment_linked = models.BooleanField(default=False, verbose_name='关联付款')
    payment_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='付款比例%'
    )

    # 交付物
    deliverables = models.TextField(blank=True, verbose_name='交付物说明')

    # 前置里程碑
    predecessors = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='successors',
        verbose_name='前置里程碑'
    )

    description = models.TextField(blank=True, verbose_name='说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'project_milestone'
        verbose_name = '项目里程碑'
        verbose_name_plural = verbose_name
        ordering = ['project', 'sort_order', 'planned_date']
        unique_together = ['project', 'code']

    def __str__(self):
        return f'{self.project.name} - {self.name}'

    @property
    def days_remaining(self):
        """剩余天数"""
        if self.status == 'COMPLETED':
            return 0
        return (self.planned_date - date.today()).days

    @property
    def is_overdue(self):
        """是否逾期"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False
        return self.planned_date < date.today()

    @property
    def delay_days(self):
        """延期天数"""
        if self.actual_date and self.planned_date:
            return (self.actual_date - self.planned_date).days
        elif self.is_overdue:
            return (date.today() - self.planned_date).days
        return 0


class MilestoneChecklist(BaseModel):
    """
    里程碑检查项
    """
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.CASCADE,
        related_name='checklist_items',
        verbose_name='里程碑'
    )

    name = models.CharField(max_length=200, verbose_name='检查项')
    is_required = models.BooleanField(default=True, verbose_name='必须项')
    is_completed = models.BooleanField(default=False, verbose_name='已完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    completed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_checklists',
        verbose_name='完成人'
    )
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'project_milestone_checklist'
        verbose_name = '里程碑检查项'
        verbose_name_plural = verbose_name
        ordering = ['milestone', 'sort_order']

    def __str__(self):
        return f'{self.milestone.name} - {self.name}'


class MilestoneComment(BaseModel):
    """
    里程碑评论/进展记录
    """
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='里程碑'
    )
    content = models.TextField(verbose_name='内容')
    comment_type = models.CharField(
        max_length=20,
        choices=[
            ('PROGRESS', '进展更新'),
            ('ISSUE', '问题反馈'),
            ('DECISION', '决策记录'),
            ('NOTE', '备注'),
        ],
        default='PROGRESS',
        verbose_name='类型'
    )
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    class Meta:
        db_table = 'project_milestone_comment'
        verbose_name = '里程碑评论'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.milestone.name} - {self.content[:30]}'


# =====================
# Serializers
# =====================

class MilestoneChecklistSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source='completed_by.get_full_name', read_only=True)

    class Meta:
        model = MilestoneChecklist
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'completed_at', 'completed_by']


class MilestoneCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    comment_type_display = serializers.CharField(source='get_comment_type_display', read_only=True)

    class Meta:
        model = MilestoneComment
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class MilestoneSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    delay_days = serializers.IntegerField(read_only=True)
    checklist_items = MilestoneChecklistSerializer(many=True, read_only=True)
    checklist_progress = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_checklist_progress(self, obj):
        total = obj.checklist_items.count()
        if total == 0:
            return {'total': 0, 'completed': 0, 'percentage': 0}
        completed = obj.checklist_items.filter(is_completed=True).count()
        return {
            'total': total,
            'completed': completed,
            'percentage': round(completed / total * 100, 1)
        }


class MilestoneListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Milestone
        fields = [
            'id', 'project', 'project_name', 'code', 'name', 'milestone_type', 'milestone_type_display',
            'planned_date', 'actual_date', 'status', 'status_display', 'progress',
            'owner', 'owner_name', 'days_remaining', 'is_overdue', 'payment_linked'
        ]


# =====================
# ViewSets
# =====================

class MilestoneViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目里程碑管理"""
    queryset = Milestone.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'milestone_type', 'status', 'owner']
    search_fields = ['code', 'name', 'project__name']
    ordering_fields = ['planned_date', 'sort_order', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return MilestoneListSerializer
        return MilestoneSerializer

    @action(detail=False, methods=['get'])
    def milestone_types(self, request):
        """获取里程碑类型"""
        return Response([
            {'value': t[0], 'label': t[1]}
            for t in Milestone.MILESTONE_TYPES
        ])

    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """按项目获取里程碑"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response({'error': '请提供项目ID'}, status=400)

        milestones = self.get_queryset().filter(project_id=project_id).order_by('sort_order', 'planned_date')
        return Response(MilestoneListSerializer(milestones, many=True).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成里程碑"""
        milestone = self.get_object()
        actual_date = request.data.get('actual_date', date.today().isoformat())

        milestone.status = 'COMPLETED'
        milestone.progress = 100
        milestone.actual_date = actual_date
        milestone.save()

        # 更新项目进度
        self._update_project_progress(milestone.project)

        return Response(self.get_serializer(milestone).data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新进度"""
        milestone = self.get_object()
        progress = request.data.get('progress', 0)

        milestone.progress = min(max(int(progress), 0), 100)
        if milestone.progress == 100:
            milestone.status = 'COMPLETED'
            milestone.actual_date = date.today()
        elif milestone.progress > 0:
            milestone.status = 'IN_PROGRESS'
        milestone.save()

        self._update_project_progress(milestone.project)

        return Response(self.get_serializer(milestone).data)

    @action(detail=True, methods=['post'])
    def add_checklist(self, request, pk=None):
        """添加检查项"""
        milestone = self.get_object()
        items = request.data.get('items', [])

        created = []
        for item in items:
            checklist = MilestoneChecklist.objects.create(
                milestone=milestone,
                name=item.get('name'),
                is_required=item.get('is_required', True),
                sort_order=item.get('sort_order', 0),
                created_by=request.user
            )
            created.append(MilestoneChecklistSerializer(checklist).data)

        return Response(created)

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """添加评论"""
        milestone = self.get_object()

        comment = MilestoneComment.objects.create(
            milestone=milestone,
            content=request.data.get('content'),
            comment_type=request.data.get('comment_type', 'PROGRESS'),
            attachments=request.data.get('attachments', []),
            created_by=request.user
        )

        return Response(MilestoneCommentSerializer(comment).data)

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """获取评论"""
        milestone = self.get_object()
        comments = milestone.comments.all()
        return Response(MilestoneCommentSerializer(comments, many=True).data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """获取逾期里程碑"""
        milestones = self.get_queryset().filter(
            planned_date__lt=date.today(),
            status__in=['PENDING', 'IN_PROGRESS']
        ).order_by('planned_date')

        return Response(MilestoneListSerializer(milestones, many=True).data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """获取即将到期的里程碑"""
        days = int(request.query_params.get('days', 7))
        end_date = date.today() + timedelta(days=days)

        milestones = self.get_queryset().filter(
            planned_date__gte=date.today(),
            planned_date__lte=end_date,
            status__in=['PENDING', 'IN_PROGRESS']
        ).order_by('planned_date')

        return Response(MilestoneListSerializer(milestones, many=True).data)

    @action(detail=False, methods=['get'])
    def my_milestones(self, request):
        """我负责的里程碑"""
        milestones = self.get_queryset().filter(
            owner=request.user,
            status__in=['PENDING', 'IN_PROGRESS']
        ).order_by('planned_date')

        return Response(MilestoneListSerializer(milestones, many=True).data)

    @action(detail=False, methods=['post'])
    def init_template(self, request):
        """从模板初始化项目里程碑"""
        project_id = request.data.get('project_id')
        template = request.data.get('template', 'standard')
        start_date = request.data.get('start_date', date.today().isoformat())

        if not project_id:
            return Response({'error': '请提供项目ID'}, status=400)

        from apps.projects.models import Project
        project = Project.objects.get(id=project_id)

        start = date.fromisoformat(start_date)

        # 标准模板
        templates = {
            'standard': [
                ('M01', '项目启动', 'KICKOFF', 0, 5),
                ('M02', '设计评审', 'DESIGN', 7, 10),
                ('M03', '采购完成', 'PROCUREMENT', 21, 15),
                ('M04', '组装完成', 'ASSEMBLY', 35, 20),
                ('M05', '调试完成', 'DEBUGGING', 45, 15),
                ('M06', '厂内验收', 'FAT', 50, 10),
                ('M07', '设备发货', 'SHIPMENT', 52, 5),
                ('M08', '安装调试', 'INSTALLATION', 60, 10),
                ('M09', '现场验收', 'SAT', 65, 10),
            ]
        }

        milestones_data = templates.get(template, templates['standard'])
        created = []

        for i, (code, name, mtype, days_offset, weight) in enumerate(milestones_data):
            milestone, c = Milestone.objects.get_or_create(
                project=project,
                code=code,
                defaults={
                    'name': name,
                    'milestone_type': mtype,
                    'planned_date': start + timedelta(days=days_offset),
                    'weight': weight,
                    'sort_order': i * 10,
                    'created_by': request.user
                }
            )
            if c:
                created.append(MilestoneListSerializer(milestone).data)

        return Response({
            'success': True,
            'created': len(created),
            'milestones': created
        })

    def _update_project_progress(self, project):
        """更新项目整体进度"""
        milestones = project.milestones.filter(is_deleted=False)
        if not milestones.exists():
            return

        total_weight = milestones.aggregate(total=Sum('weight'))['total'] or 0
        if total_weight == 0:
            return

        weighted_progress = sum(
            (m.progress * float(m.weight) / 100) for m in milestones
        )

        project.progress = int(weighted_progress / float(total_weight) * 100)
        project.save()


class MilestoneChecklistViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """里程碑检查项管理"""
    queryset = MilestoneChecklist.objects.filter(is_deleted=False)
    serializer_class = MilestoneChecklistSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['milestone', 'is_required', 'is_completed']

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成检查项"""
        from django.utils import timezone

        item = self.get_object()
        item.is_completed = True
        item.completed_at = timezone.now()
        item.completed_by = request.user
        item.save()

        # 更新里程碑进度
        milestone = item.milestone
        total = milestone.checklist_items.filter(is_required=True).count()
        if total > 0:
            completed = milestone.checklist_items.filter(is_required=True, is_completed=True).count()
            milestone.progress = int(completed / total * 100)
            if milestone.progress == 100:
                milestone.status = 'COMPLETED'
                milestone.actual_date = date.today()
            elif milestone.progress > 0:
                milestone.status = 'IN_PROGRESS'
            milestone.save()

        return Response(self.get_serializer(item).data)
