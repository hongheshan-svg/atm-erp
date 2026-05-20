"""
客户培训管理增强模块
Customer Training Management Enhancement

功能：
- 培训计划管理
- 培训课程库
- 培训考核记录
- 培训资料管理
- 培训证书生成
"""

from datetime import date

from django.db import models
from django.db.models import Avg
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel

# =============================================================================
# 模型定义
# =============================================================================


class TrainingCourse(BaseModel):
    """培训课程"""

    COURSE_TYPE_CHOICES = [
        ('OPERATION', '操作培训'),
        ('MAINTENANCE', '维护保养'),
        ('SAFETY', '安全培训'),
        ('PROGRAMMING', '编程培训'),
        ('TROUBLESHOOTING', '故障排除'),
        ('UPGRADE', '升级培训'),
        ('OTHER', '其他'),
    ]

    LEVEL_CHOICES = [
        ('BASIC', '基础'),
        ('INTERMEDIATE', '中级'),
        ('ADVANCED', '高级'),
        ('EXPERT', '专家'),
    ]

    # 基本信息
    course_code = models.CharField(max_length=50, unique=True, verbose_name='课程编码')
    course_name = models.CharField(max_length=200, verbose_name='课程名称')
    course_type = models.CharField(max_length=20, choices=COURSE_TYPE_CHOICES, verbose_name='课程类型')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='BASIC', verbose_name='难度等级')

    # 课程内容
    description = models.TextField(blank=True, verbose_name='课程描述')
    objectives = models.TextField(blank=True, verbose_name='培训目标')
    outline = models.TextField(blank=True, verbose_name='课程大纲')
    prerequisites = models.TextField(blank=True, verbose_name='前置条件')

    # 时间和费用
    duration_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='课时(小时)')
    duration_days = models.DecimalField(max_digits=5, decimal_places=1, default=0, verbose_name='天数')
    max_participants = models.IntegerField(default=10, verbose_name='最大人数')

    standard_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='标准费用')

    # 关联设备/产品
    applicable_equipment = models.ManyToManyField(
        'projects.Equipment', blank=True, related_name='training_courses', verbose_name='适用设备'
    )

    # 培训资料
    materials = models.JSONField(default=list, blank=True, verbose_name='培训资料')

    # 考核要求
    requires_exam = models.BooleanField(default=False, verbose_name='需要考核')
    passing_score = models.IntegerField(default=60, verbose_name='及格分数')

    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'training_course'
        verbose_name = '培训课程'
        verbose_name_plural = verbose_name
        ordering = ['course_code']

    def __str__(self):
        return f'{self.course_code} - {self.course_name}'


class TrainingPlan(BaseModel):
    """培训计划"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SCHEDULED', '已安排'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    TRAINING_MODE_CHOICES = [
        ('ON_SITE', '现场培训'),
        ('FACTORY', '厂内培训'),
        ('ONLINE', '线上培训'),
        ('MIXED', '混合培训'),
    ]

    # 基本信息
    plan_no = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    title = models.CharField(max_length=200, verbose_name='培训主题')

    # 关联信息
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.PROTECT, related_name='training_plans', verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_plans',
        verbose_name='关联项目',
    )
    service_order = models.ForeignKey(
        'projects.ServiceOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_plans',
        verbose_name='服务单',
    )

    # 培训课程
    courses = models.ManyToManyField(
        TrainingCourse, through='TrainingPlanCourse', related_name='plans', verbose_name='培训课程'
    )

    # 培训方式和地点
    training_mode = models.CharField(
        max_length=20, choices=TRAINING_MODE_CHOICES, default='ON_SITE', verbose_name='培训方式'
    )
    training_location = models.CharField(max_length=300, blank=True, verbose_name='培训地点')

    # 时间
    planned_start = models.DateField(verbose_name='计划开始日期')
    planned_end = models.DateField(verbose_name='计划结束日期')
    actual_start = models.DateField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateField(null=True, blank=True, verbose_name='实际结束')

    # 培训师
    trainers = models.ManyToManyField(
        'accounts.User', blank=True, related_name='training_assignments', verbose_name='培训师'
    )

    # 费用
    total_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='培训费用')
    is_chargeable = models.BooleanField(default=True, verbose_name='是否收费')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 联系人
    contact_name = models.CharField(max_length=50, blank=True, verbose_name='联系人')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')
    contact_email = models.EmailField(blank=True, verbose_name='联系邮箱')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'training_plan'
        verbose_name = '培训计划'
        verbose_name_plural = verbose_name
        ordering = ['-planned_start']

    def __str__(self):
        return f'{self.plan_no} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.plan_no:
            from apps.core.models import CodeRule

            self.plan_no = CodeRule.generate_code('TRAIN')
        super().save(*args, **kwargs)


class TrainingPlanCourse(BaseModel):
    """培训计划课程"""

    plan = models.ForeignKey(
        TrainingPlan, on_delete=models.CASCADE, related_name='plan_courses', verbose_name='培训计划'
    )
    course = models.ForeignKey(
        TrainingCourse, on_delete=models.CASCADE, related_name='plan_courses', verbose_name='课程'
    )

    # 排期
    sequence = models.IntegerField(default=1, verbose_name='顺序')
    scheduled_date = models.DateField(null=True, blank=True, verbose_name='安排日期')
    scheduled_time = models.TimeField(null=True, blank=True, verbose_name='开始时间')

    # 培训师
    trainer = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='培训师'
    )

    # 状态
    is_completed = models.BooleanField(default=False, verbose_name='已完成')
    completed_date = models.DateField(null=True, blank=True, verbose_name='完成日期')

    class Meta:
        db_table = 'training_plan_course'
        verbose_name = '培训计划课程'
        verbose_name_plural = verbose_name
        unique_together = ['plan', 'course']
        ordering = ['sequence']


class Trainee(BaseModel):
    """学员"""

    plan = models.ForeignKey(TrainingPlan, on_delete=models.CASCADE, related_name='trainees', verbose_name='培训计划')

    # 学员信息
    name = models.CharField(max_length=50, verbose_name='姓名')
    employee_id = models.CharField(max_length=50, blank=True, verbose_name='工号')
    department = models.CharField(max_length=100, blank=True, verbose_name='部门')
    position = models.CharField(max_length=100, blank=True, verbose_name='职位')

    phone = models.CharField(max_length=20, blank=True, verbose_name='电话')
    email = models.EmailField(blank=True, verbose_name='邮箱')

    # 签到
    checked_in = models.BooleanField(default=False, verbose_name='已签到')
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name='签到时间')

    # 培训完成情况
    completed_courses = models.IntegerField(default=0, verbose_name='完成课程数')
    total_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0, verbose_name='培训时长')

    # 证书
    certificate_issued = models.BooleanField(default=False, verbose_name='已发证')
    certificate_no = models.CharField(max_length=100, blank=True, verbose_name='证书编号')
    certificate_date = models.DateField(null=True, blank=True, verbose_name='发证日期')

    class Meta:
        db_table = 'training_trainee'
        verbose_name = '学员'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return f'{self.plan.plan_no} - {self.name}'


class TrainingExam(BaseModel):
    """培训考核"""

    EXAM_TYPE_CHOICES = [
        ('WRITTEN', '笔试'),
        ('PRACTICAL', '实操'),
        ('ORAL', '口试'),
        ('MIXED', '综合'),
    ]

    plan_course = models.ForeignKey(
        TrainingPlanCourse, on_delete=models.CASCADE, related_name='exams', verbose_name='培训课程'
    )

    exam_name = models.CharField(max_length=200, verbose_name='考核名称')
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES, default='WRITTEN', verbose_name='考核类型')
    exam_date = models.DateField(verbose_name='考核日期')

    # 考核内容
    total_score = models.IntegerField(default=100, verbose_name='满分')
    passing_score = models.IntegerField(default=60, verbose_name='及格分')
    duration_minutes = models.IntegerField(default=60, verbose_name='时长(分钟)')

    # 试题
    exam_content = models.TextField(blank=True, verbose_name='考核内容')
    exam_file = models.FileField(upload_to='training/exams/', blank=True, verbose_name='试卷文件')

    class Meta:
        db_table = 'training_exam'
        verbose_name = '培训考核'
        verbose_name_plural = verbose_name
        ordering = ['-exam_date']


class TrainingExamResult(BaseModel):
    """考核成绩"""

    exam = models.ForeignKey(TrainingExam, on_delete=models.CASCADE, related_name='results', verbose_name='考核')
    trainee = models.ForeignKey(Trainee, on_delete=models.CASCADE, related_name='exam_results', verbose_name='学员')

    score = models.IntegerField(default=0, verbose_name='分数')
    is_passed = models.BooleanField(default=False, verbose_name='是否通过')

    # 答题详情
    answers = models.JSONField(default=dict, blank=True, verbose_name='答题情况')

    # 评语
    comments = models.TextField(blank=True, verbose_name='评语')
    graded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='评分人'
    )
    graded_at = models.DateTimeField(null=True, blank=True, verbose_name='评分时间')

    class Meta:
        db_table = 'training_exam_result'
        verbose_name = '考核成绩'
        verbose_name_plural = verbose_name
        unique_together = ['exam', 'trainee']
        ordering = ['-score']

    def save(self, *args, **kwargs):
        self.is_passed = self.score >= self.exam.passing_score
        super().save(*args, **kwargs)


class TrainingFeedback(BaseModel):
    """培训反馈"""

    plan = models.ForeignKey(TrainingPlan, on_delete=models.CASCADE, related_name='feedbacks', verbose_name='培训计划')
    trainee = models.ForeignKey(
        Trainee, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks', verbose_name='学员'
    )

    # 评分
    content_rating = models.IntegerField(default=0, verbose_name='内容评分(1-5)')
    trainer_rating = models.IntegerField(default=0, verbose_name='讲师评分(1-5)')
    facility_rating = models.IntegerField(default=0, verbose_name='设施评分(1-5)')
    overall_rating = models.IntegerField(default=0, verbose_name='总体评分(1-5)')

    # 反馈
    strengths = models.TextField(blank=True, verbose_name='优点')
    improvements = models.TextField(blank=True, verbose_name='改进建议')
    comments = models.TextField(blank=True, verbose_name='其他意见')

    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')

    class Meta:
        db_table = 'training_feedback'
        verbose_name = '培训反馈'
        verbose_name_plural = verbose_name
        ordering = ['-submitted_at']


class TrainingMaterial(BaseModel):
    """培训资料"""

    MATERIAL_TYPE_CHOICES = [
        ('MANUAL', '操作手册'),
        ('PPT', '演示文稿'),
        ('VIDEO', '视频'),
        ('DOCUMENT', '文档'),
        ('EXERCISE', '练习题'),
        ('REFERENCE', '参考资料'),
        ('OTHER', '其他'),
    ]

    course = models.ForeignKey(
        TrainingCourse, on_delete=models.CASCADE, related_name='training_materials', verbose_name='课程'
    )

    title = models.CharField(max_length=200, verbose_name='资料标题')
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPE_CHOICES, verbose_name='资料类型')

    description = models.TextField(blank=True, verbose_name='描述')

    # 文件
    file = models.FileField(upload_to='training/materials/', blank=True, verbose_name='文件')
    file_url = models.URLField(blank=True, verbose_name='外部链接')
    file_size = models.IntegerField(default=0, verbose_name='文件大小(KB)')

    # 版本
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')

    is_public = models.BooleanField(default=False, verbose_name='对客户可见')

    class Meta:
        db_table = 'training_material'
        verbose_name = '培训资料'
        verbose_name_plural = verbose_name
        ordering = ['course', 'material_type']


# =============================================================================
# 序列化器
# =============================================================================


class TrainingCourseSerializer(serializers.ModelSerializer):
    course_type_display = serializers.CharField(source='get_course_type_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = TrainingCourse
        fields = '__all__'


class TrainingMaterialSerializer(serializers.ModelSerializer):
    material_type_display = serializers.CharField(source='get_material_type_display', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)

    class Meta:
        model = TrainingMaterial
        fields = '__all__'


class TraineeSerializer(serializers.ModelSerializer):
    plan_no = serializers.CharField(source='plan.plan_no', read_only=True)

    class Meta:
        model = Trainee
        fields = '__all__'


class TrainingExamResultSerializer(serializers.ModelSerializer):
    trainee_name = serializers.CharField(source='trainee.name', read_only=True)
    exam_name = serializers.CharField(source='exam.exam_name', read_only=True)

    class Meta:
        model = TrainingExamResult
        fields = '__all__'


class TrainingExamSerializer(serializers.ModelSerializer):
    exam_type_display = serializers.CharField(source='get_exam_type_display', read_only=True)
    course_name = serializers.CharField(source='plan_course.course.course_name', read_only=True)
    results = TrainingExamResultSerializer(many=True, read_only=True)

    class Meta:
        model = TrainingExam
        fields = '__all__'


class TrainingPlanCourseSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    duration_hours = serializers.DecimalField(
        source='course.duration_hours', max_digits=5, decimal_places=1, read_only=True
    )
    trainer_name = serializers.CharField(source='trainer.get_full_name', read_only=True)

    class Meta:
        model = TrainingPlanCourse
        fields = '__all__'


class TrainingFeedbackSerializer(serializers.ModelSerializer):
    trainee_name = serializers.CharField(source='trainee.name', read_only=True)
    plan_no = serializers.CharField(source='plan.plan_no', read_only=True)

    class Meta:
        model = TrainingFeedback
        fields = '__all__'


class TrainingPlanSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    training_mode_display = serializers.CharField(source='get_training_mode_display', read_only=True)
    plan_courses = TrainingPlanCourseSerializer(many=True, read_only=True)
    trainees = TraineeSerializer(many=True, read_only=True)
    trainee_count = serializers.SerializerMethodField()

    class Meta:
        model = TrainingPlan
        fields = '__all__'
        read_only_fields = ['plan_no']

    def get_trainee_count(self, obj):
        return obj.trainees.count()


class TrainingPlanListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    training_mode_display = serializers.CharField(source='get_training_mode_display', read_only=True)
    trainee_count = serializers.SerializerMethodField()
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = TrainingPlan
        fields = [
            'id',
            'plan_no',
            'title',
            'customer',
            'customer_name',
            'training_mode',
            'training_mode_display',
            'planned_start',
            'planned_end',
            'status',
            'status_display',
            'trainee_count',
            'course_count',
            'total_fee',
            'is_chargeable',
        ]

    def get_trainee_count(self, obj):
        return obj.trainees.count()

    def get_course_count(self, obj):
        return obj.plan_courses.count()


# =============================================================================
# 视图集
# =============================================================================


class TrainingCourseViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """培训课程管理"""

    queryset = TrainingCourse.objects.filter(is_deleted=False)
    serializer_class = TrainingCourseSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['course_type', 'level', 'is_active', 'requires_exam']
    search_fields = ['course_code', 'course_name']
    ordering_fields = ['course_code', 'duration_hours', 'standard_fee']


class TrainingMaterialViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """培训资料管理"""

    queryset = TrainingMaterial.objects.filter(is_deleted=False)
    serializer_class = TrainingMaterialSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['course', 'material_type', 'is_public']
    search_fields = ['title']


class TrainingPlanViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """培训计划管理"""

    queryset = TrainingPlan.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'project', 'status', 'training_mode']
    search_fields = ['plan_no', 'title', 'customer__name']
    ordering_fields = ['planned_start', 'total_fee']

    def get_serializer_class(self):
        if self.action == 'list':
            return TrainingPlanListSerializer
        return TrainingPlanSerializer

    @action(detail=True, methods=['post'])
    def add_trainee(self, request, pk=None):
        """添加学员"""
        plan = self.get_object()
        trainee = Trainee.objects.create(
            plan=plan,
            name=request.data.get('name'),
            employee_id=request.data.get('employee_id', ''),
            department=request.data.get('department', ''),
            position=request.data.get('position', ''),
            phone=request.data.get('phone', ''),
            email=request.data.get('email', ''),
            created_by=request.user,
        )
        return Response(TraineeSerializer(trainee).data)

    @action(detail=True, methods=['post'])
    def batch_add_trainees(self, request, pk=None):
        """批量添加学员"""
        plan = self.get_object()
        trainees_data = request.data.get('trainees', [])

        created = []
        for data in trainees_data:
            trainee = Trainee.objects.create(
                plan=plan,
                name=data.get('name'),
                employee_id=data.get('employee_id', ''),
                department=data.get('department', ''),
                position=data.get('position', ''),
                phone=data.get('phone', ''),
                email=data.get('email', ''),
                created_by=request.user,
            )
            created.append(trainee)

        return Response(
            {'message': f'成功添加 {len(created)} 名学员', 'trainees': TraineeSerializer(created, many=True).data}
        )

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始培训"""
        plan = self.get_object()
        plan.status = 'IN_PROGRESS'
        plan.actual_start = date.today()
        plan.save()
        return Response(TrainingPlanSerializer(plan).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成培训"""
        plan = self.get_object()
        plan.status = 'COMPLETED'
        plan.actual_end = date.today()
        plan.save()
        return Response(TrainingPlanSerializer(plan).data)

    @action(detail=True, methods=['post'])
    def issue_certificates(self, request, pk=None):
        """发放证书"""
        plan = self.get_object()
        trainee_ids = request.data.get('trainee_ids', [])

        if not trainee_ids:
            trainees = plan.trainees.filter(certificate_issued=False)
        else:
            trainees = plan.trainees.filter(id__in=trainee_ids, certificate_issued=False)

        issued = 0
        for trainee in trainees:
            # 检查是否通过所有考核
            all_passed = True
            for exam in TrainingExam.objects.filter(plan_course__plan=plan):
                result = TrainingExamResult.objects.filter(exam=exam, trainee=trainee).first()
                if not result or not result.is_passed:
                    all_passed = False
                    break

            if all_passed or not plan.plan_courses.filter(course__requires_exam=True).exists():
                trainee.certificate_issued = True
                trainee.certificate_date = date.today()
                trainee.certificate_no = f'CERT-{plan.plan_no}-{trainee.id:04d}'
                trainee.save()
                issued += 1

        return Response({'message': f'成功发放 {issued} 份证书', 'issued_count': issued})

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """培训统计"""
        plan = self.get_object()

        trainees = plan.trainees.all()
        total_trainees = trainees.count()
        checked_in = trainees.filter(checked_in=True).count()
        certified = trainees.filter(certificate_issued=True).count()

        # 考核统计
        exams = TrainingExam.objects.filter(plan_course__plan=plan)
        exam_stats = []
        for exam in exams:
            results = exam.results.all()
            passed = results.filter(is_passed=True).count()
            avg_score = results.aggregate(avg=Avg('score'))['avg'] or 0
            exam_stats.append(
                {
                    'exam_name': exam.exam_name,
                    'total': results.count(),
                    'passed': passed,
                    'pass_rate': round(passed / results.count() * 100, 1) if results.count() > 0 else 0,
                    'avg_score': round(avg_score, 1),
                }
            )

        # 反馈统计
        feedbacks = plan.feedbacks.all()
        feedback_stats = feedbacks.aggregate(
            avg_content=Avg('content_rating'),
            avg_trainer=Avg('trainer_rating'),
            avg_facility=Avg('facility_rating'),
            avg_overall=Avg('overall_rating'),
        )

        return Response(
            {
                'total_trainees': total_trainees,
                'checked_in': checked_in,
                'certified': certified,
                'certification_rate': round(certified / total_trainees * 100, 1) if total_trainees > 0 else 0,
                'exam_stats': exam_stats,
                'feedback_stats': {
                    'content_rating': round(feedback_stats['avg_content'] or 0, 1),
                    'trainer_rating': round(feedback_stats['avg_trainer'] or 0, 1),
                    'facility_rating': round(feedback_stats['avg_facility'] or 0, 1),
                    'overall_rating': round(feedback_stats['avg_overall'] or 0, 1),
                    'feedback_count': feedbacks.count(),
                },
            }
        )


class TraineeViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """学员管理"""

    queryset = Trainee.objects.filter(is_deleted=False)
    serializer_class = TraineeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['plan', 'checked_in', 'certificate_issued']
    search_fields = ['name', 'employee_id', 'department']

    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """签到"""
        trainee = self.get_object()
        trainee.checked_in = True
        trainee.check_in_time = timezone.now()
        trainee.save()
        return Response(TraineeSerializer(trainee).data)


class TrainingExamViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """培训考核管理"""

    queryset = TrainingExam.objects.filter(is_deleted=False)
    serializer_class = TrainingExamSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['plan_course', 'exam_type']

    @action(detail=True, methods=['post'])
    def submit_result(self, request, pk=None):
        """提交成绩"""
        exam = self.get_object()
        trainee_id = request.data.get('trainee_id')
        score = request.data.get('score', 0)

        result, created = TrainingExamResult.objects.update_or_create(
            exam=exam,
            trainee_id=trainee_id,
            defaults={
                'score': score,
                'comments': request.data.get('comments', ''),
                'graded_by': request.user,
                'graded_at': timezone.now(),
            },
        )

        return Response(TrainingExamResultSerializer(result).data)

    @action(detail=True, methods=['post'])
    def batch_submit_results(self, request, pk=None):
        """批量提交成绩"""
        exam = self.get_object()
        results_data = request.data.get('results', [])

        submitted = 0
        for data in results_data:
            result, created = TrainingExamResult.objects.update_or_create(
                exam=exam,
                trainee_id=data.get('trainee_id'),
                defaults={
                    'score': data.get('score', 0),
                    'comments': data.get('comments', ''),
                    'graded_by': request.user,
                    'graded_at': timezone.now(),
                },
            )
            submitted += 1

        return Response({'message': f'成功提交 {submitted} 份成绩', 'submitted_count': submitted})


class TrainingFeedbackViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """培训反馈管理"""

    queryset = TrainingFeedback.objects.filter(is_deleted=False)
    serializer_class = TrainingFeedbackSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['plan', 'trainee']
