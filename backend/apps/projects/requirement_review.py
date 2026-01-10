"""
需求评审模块
Requirement Review
需求评审流程、评审记录、评审结果管理
"""
from datetime import date, datetime
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class ReviewTemplate(BaseModel):
    """评审模板"""
    name = models.CharField(max_length=100, verbose_name='模板名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    description = models.TextField(blank=True, verbose_name='描述')
    review_type = models.CharField(
        max_length=20,
        choices=[
            ('REQUIREMENT', '需求评审'),
            ('DESIGN', '设计评审'),
            ('TECHNICAL', '技术评审'),
        ],
        default='REQUIREMENT',
        verbose_name='评审类型'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'plm_review_template'
        verbose_name = '评审模板'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return self.name


class ReviewCheckItem(BaseModel):
    """评审检查项"""
    template = models.ForeignKey(
        ReviewTemplate,
        on_delete=models.CASCADE,
        related_name='check_items',
        verbose_name='评审模板'
    )
    name = models.CharField(max_length=200, verbose_name='检查项名称')
    description = models.TextField(blank=True, verbose_name='检查说明')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_required = models.BooleanField(default=True, verbose_name='是否必填')
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, 
        default=1.0, 
        verbose_name='权重'
    )
    
    class Meta:
        db_table = 'plm_review_check_item'
        verbose_name = '评审检查项'
        verbose_name_plural = verbose_name
        ordering = ['template', 'sort_order']
    
    def __str__(self):
        return f"{self.template.name} - {self.name}"


class RequirementReview(BaseModel):
    """需求评审"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SCHEDULED', '已安排'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    RESULT_CHOICES = [
        ('PENDING', '待定'),
        ('APPROVED', '通过'),
        ('CONDITIONAL', '有条件通过'),
        ('REJECTED', '不通过'),
    ]
    
    review_no = models.CharField(max_length=50, unique=True, verbose_name='评审编号')
    title = models.CharField(max_length=200, verbose_name='评审标题')
    
    # 关联需求
    requirement = models.ForeignKey(
        'projects.Requirement',
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='需求'
    )
    
    # 评审模板
    template = models.ForeignKey(
        ReviewTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name='评审模板'
    )
    
    # 评审安排
    scheduled_date = models.DateField(null=True, blank=True, verbose_name='计划日期')
    scheduled_time = models.TimeField(null=True, blank=True, verbose_name='计划时间')
    location = models.CharField(max_length=200, blank=True, verbose_name='评审地点')
    duration_hours = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='预计时长(小时)'
    )
    
    # 评审组织者
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='organized_req_reviews',
        verbose_name='组织者'
    )
    
    # 状态和结果
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default='PENDING',
        verbose_name='评审结果'
    )
    
    # 实际评审信息
    actual_start_time = models.DateTimeField(null=True, blank=True, verbose_name='实际开始时间')
    actual_end_time = models.DateTimeField(null=True, blank=True, verbose_name='实际结束时间')
    
    # 评审总结
    summary = models.TextField(blank=True, verbose_name='评审总结')
    issues_found = models.TextField(blank=True, verbose_name='发现的问题')
    action_items = models.TextField(blank=True, verbose_name='后续行动项')
    
    # 评审得分
    total_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='总评分'
    )
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'plm_requirement_review'
        verbose_name = '需求评审'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.review_no} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.review_no:
            from apps.core.utils import generate_code
            self.review_no = generate_code('RRV')
        super().save(*args, **kwargs)
    
    def calculate_score(self):
        """计算评审总分"""
        results = self.item_results.filter(is_deleted=False)
        if not results.exists():
            return None
        
        total_weight = results.aggregate(total=Sum('check_item__weight'))['total'] or 1
        weighted_score = sum(
            r.score * float(r.check_item.weight) 
            for r in results if r.score is not None
        )
        
        self.total_score = round(Decimal(weighted_score / float(total_weight)), 2)
        return self.total_score


class ReviewParticipant(BaseModel):
    """评审参与者"""
    ROLE_CHOICES = [
        ('REVIEWER', '评审人'),
        ('EXPERT', '专家'),
        ('OBSERVER', '观察员'),
        ('PRESENTER', '汇报人'),
    ]
    
    review = models.ForeignKey(
        RequirementReview,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name='评审'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_participations',
        verbose_name='参与者'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='REVIEWER',
        verbose_name='角色'
    )
    is_required = models.BooleanField(default=True, verbose_name='是否必须参加')
    attended = models.BooleanField(default=False, verbose_name='是否出席')
    feedback = models.TextField(blank=True, verbose_name='反馈意见')
    
    class Meta:
        db_table = 'plm_review_participant'
        verbose_name = '评审参与者'
        verbose_name_plural = verbose_name
        unique_together = ('review', 'user')
    
    def __str__(self):
        return f"{self.review.review_no} - {self.user.username}"


class ReviewItemResult(BaseModel):
    """评审检查项结果"""
    review = models.ForeignKey(
        RequirementReview,
        on_delete=models.CASCADE,
        related_name='item_results',
        verbose_name='评审'
    )
    check_item = models.ForeignKey(
        ReviewCheckItem,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='检查项'
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name='评分'
    )
    result = models.CharField(
        max_length=20,
        choices=[
            ('PASS', '通过'),
            ('FAIL', '不通过'),
            ('NA', '不适用'),
        ],
        default='PASS',
        verbose_name='结果'
    )
    comment = models.TextField(blank=True, verbose_name='评审意见')
    issues = models.TextField(blank=True, verbose_name='发现问题')
    
    class Meta:
        db_table = 'plm_review_item_result'
        verbose_name = '评审检查项结果'
        verbose_name_plural = verbose_name
        unique_together = ('review', 'check_item')
    
    def __str__(self):
        return f"{self.review.review_no} - {self.check_item.name}"


class ReviewActionItem(BaseModel):
    """评审行动项"""
    STATUS_CHOICES = [
        ('OPEN', '待处理'),
        ('IN_PROGRESS', '处理中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    review = models.ForeignKey(
        RequirementReview,
        on_delete=models.CASCADE,
        related_name='action_item_list',
        verbose_name='评审'
    )
    title = models.CharField(max_length=200, verbose_name='行动项标题')
    description = models.TextField(blank=True, verbose_name='描述')
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_review_actions',
        verbose_name='负责人'
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='截止日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN',
        verbose_name='状态'
    )
    completed_date = models.DateField(null=True, blank=True, verbose_name='完成日期')
    resolution = models.TextField(blank=True, verbose_name='解决方案')
    
    class Meta:
        db_table = 'plm_review_action_item'
        verbose_name = '评审行动项'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.review.review_no} - {self.title}"


# =====================
# Serializers
# =====================

class ReviewCheckItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewCheckItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ReviewTemplateSerializer(serializers.ModelSerializer):
    check_items = ReviewCheckItemSerializer(many=True, read_only=True)
    type_display = serializers.CharField(source='get_review_type_display', read_only=True)
    
    class Meta:
        model = ReviewTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ReviewParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = ReviewParticipant
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ReviewItemResultSerializer(serializers.ModelSerializer):
    check_item_name = serializers.CharField(source='check_item.name', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    
    class Meta:
        model = ReviewItemResult
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ReviewActionItemSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ReviewActionItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class RequirementReviewSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    requirement_title = serializers.CharField(source='requirement.title', read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    participants = ReviewParticipantSerializer(many=True, read_only=True)
    item_results = ReviewItemResultSerializer(many=True, read_only=True)
    action_item_list = ReviewActionItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = RequirementReview
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'review_no', 'total_score']


class RequirementReviewListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    requirement_title = serializers.CharField(source='requirement.title', read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    participant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RequirementReview
        fields = [
            'id', 'review_no', 'title', 'requirement', 'requirement_title',
            'scheduled_date', 'status', 'status_display', 'result', 'result_display',
            'organizer', 'organizer_name', 'total_score', 'participant_count', 'created_at'
        ]
    
    def get_participant_count(self, obj):
        return obj.participants.count()


# =====================
# ViewSets
# =====================

class ReviewTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """评审模板管理"""
    queryset = ReviewTemplate.objects.filter(is_deleted=False)
    serializer_class = ReviewTemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['review_type', 'is_active']
    search_fields = ['name', 'code']
    
    @action(detail=True, methods=['post'])
    def add_check_item(self, request, pk=None):
        """添加检查项"""
        template = self.get_object()
        
        item = ReviewCheckItem.objects.create(
            template=template,
            name=request.data.get('name'),
            description=request.data.get('description', ''),
            sort_order=request.data.get('sort_order', 0),
            is_required=request.data.get('is_required', True),
            weight=request.data.get('weight', 1.0),
            created_by=request.user
        )
        
        return Response(ReviewCheckItemSerializer(item).data, status=status.HTTP_201_CREATED)


class RequirementReviewViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """需求评审管理"""
    queryset = RequirementReview.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['requirement', 'status', 'result', 'organizer', 'template']
    search_fields = ['review_no', 'title']
    ordering_fields = ['scheduled_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RequirementReviewListSerializer
        return RequirementReviewSerializer
    
    @action(detail=True, methods=['post'])
    def add_participant(self, request, pk=None):
        """添加参与者"""
        review = self.get_object()
        
        participant, created = ReviewParticipant.objects.get_or_create(
            review=review,
            user_id=request.data.get('user_id'),
            defaults={
                'role': request.data.get('role', 'REVIEWER'),
                'is_required': request.data.get('is_required', True),
                'created_by': request.user
            }
        )
        
        return Response(ReviewParticipantSerializer(participant).data)
    
    @action(detail=True, methods=['post'])
    def start_review(self, request, pk=None):
        """开始评审"""
        review = self.get_object()
        if review.status not in ['DRAFT', 'SCHEDULED']:
            return Response({'error': '只有草稿或已安排的评审可以开始'}, status=400)
        
        review.status = 'IN_PROGRESS'
        review.actual_start_time = timezone.now()
        review.save()
        
        # 将需求状态改为评审中
        review.requirement.status = 'REVIEWING'
        review.requirement.save()
        
        return Response(self.get_serializer(review).data)
    
    @action(detail=True, methods=['post'])
    def complete_review(self, request, pk=None):
        """完成评审"""
        review = self.get_object()
        if review.status != 'IN_PROGRESS':
            return Response({'error': '只有进行中的评审可以完成'}, status=400)
        
        review.status = 'COMPLETED'
        review.actual_end_time = timezone.now()
        review.result = request.data.get('result', 'APPROVED')
        review.summary = request.data.get('summary', '')
        review.issues_found = request.data.get('issues_found', '')
        
        # 计算总分
        review.calculate_score()
        review.save()
        
        # 更新需求状态
        if review.result == 'APPROVED':
            review.requirement.status = 'APPROVED'
        elif review.result == 'REJECTED':
            review.requirement.status = 'DRAFT'  # 退回草稿
        review.requirement.save()
        
        return Response(self.get_serializer(review).data)
    
    @action(detail=True, methods=['post'])
    def add_item_result(self, request, pk=None):
        """添加检查项结果"""
        review = self.get_object()
        
        result, created = ReviewItemResult.objects.update_or_create(
            review=review,
            check_item_id=request.data.get('check_item_id'),
            defaults={
                'score': request.data.get('score'),
                'result': request.data.get('result', 'PASS'),
                'comment': request.data.get('comment', ''),
                'issues': request.data.get('issues', ''),
                'created_by': request.user
            }
        )
        
        return Response(ReviewItemResultSerializer(result).data)
    
    @action(detail=True, methods=['post'])
    def add_action_item(self, request, pk=None):
        """添加行动项"""
        review = self.get_object()
        
        action_item = ReviewActionItem.objects.create(
            review=review,
            title=request.data.get('title'),
            description=request.data.get('description', ''),
            assignee_id=request.data.get('assignee_id'),
            due_date=request.data.get('due_date'),
            created_by=request.user
        )
        
        return Response(ReviewActionItemSerializer(action_item).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """评审统计"""
        qs = self.get_queryset()
        
        total = qs.count()
        by_status = qs.values('status').annotate(count=Count('id'))
        by_result = qs.filter(status='COMPLETED').values('result').annotate(count=Count('id'))
        
        # 平均评审时长
        completed = qs.filter(
            status='COMPLETED',
            actual_start_time__isnull=False,
            actual_end_time__isnull=False
        )
        
        avg_duration = None
        if completed.exists():
            durations = [
                (r.actual_end_time - r.actual_start_time).total_seconds() / 3600
                for r in completed
            ]
            avg_duration = round(sum(durations) / len(durations), 2)
        
        # 本月评审数
        month_start = date.today().replace(day=1)
        this_month = qs.filter(created_at__date__gte=month_start).count()
        
        return Response({
            'total': total,
            'this_month': this_month,
            'by_status': list(by_status),
            'by_result': list(by_result),
            'avg_duration_hours': avg_duration
        })


class ReviewActionItemViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """评审行动项管理"""
    queryset = ReviewActionItem.objects.filter(is_deleted=False)
    serializer_class = ReviewActionItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['review', 'assignee', 'status']
    search_fields = ['title', 'description']
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成行动项"""
        item = self.get_object()
        item.status = 'COMPLETED'
        item.completed_date = date.today()
        item.resolution = request.data.get('resolution', '')
        item.save()
        return Response(self.get_serializer(item).data)
