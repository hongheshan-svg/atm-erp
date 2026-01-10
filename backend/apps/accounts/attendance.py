"""
员工考勤管理
Employee Attendance Management
支持打卡记录、加班申请、请假管理等
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class AttendanceConfig(BaseModel):
    """
    考勤配置
    """
    name = models.CharField(max_length=100, verbose_name='配置名称')
    
    # 工作时间
    work_start_time = models.TimeField(default=time(9, 0), verbose_name='上班时间')
    work_end_time = models.TimeField(default=time(18, 0), verbose_name='下班时间')
    lunch_start_time = models.TimeField(default=time(12, 0), verbose_name='午休开始')
    lunch_end_time = models.TimeField(default=time(13, 0), verbose_name='午休结束')
    
    # 弹性设置
    flexible_minutes = models.IntegerField(default=0, verbose_name='弹性时间(分钟)')
    late_grace_minutes = models.IntegerField(default=10, verbose_name='迟到宽限(分钟)')
    
    # 加班设置
    overtime_min_hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=1,
        verbose_name='最小加班时长(小时)'
    )
    weekday_overtime_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.5,
        verbose_name='工作日加班倍率'
    )
    weekend_overtime_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=2,
        verbose_name='周末加班倍率'
    )
    holiday_overtime_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=3,
        verbose_name='节假日加班倍率'
    )
    
    # 工作日
    workdays = models.JSONField(
        default=list,
        blank=True,
        verbose_name='工作日',
        help_text='0-6: 周一到周日'
    )
    
    is_default = models.BooleanField(default=False, verbose_name='默认配置')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    class Meta:
        db_table = 'accounts_attendance_config'
        verbose_name = '考勤配置'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.workdays:
            self.workdays = [0, 1, 2, 3, 4]  # 周一到周五
        if self.is_default:
            AttendanceConfig.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class AttendanceRecord(BaseModel):
    """
    考勤记录
    """
    STATUS_CHOICES = [
        ('NORMAL', '正常'),
        ('LATE', '迟到'),
        ('EARLY', '早退'),
        ('ABSENT', '缺勤'),
        ('LEAVE', '请假'),
        ('OVERTIME', '加班'),
        ('TRAVEL', '出差'),
        ('REMOTE', '远程'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name='员工'
    )
    attendance_date = models.DateField(verbose_name='考勤日期')
    
    # 打卡记录
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name='签到时间')
    check_out_time = models.DateTimeField(null=True, blank=True, verbose_name='签退时间')
    
    # 打卡地点
    check_in_location = models.CharField(max_length=200, blank=True, verbose_name='签到地点')
    check_out_location = models.CharField(max_length=200, blank=True, verbose_name='签退地点')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NORMAL',
        verbose_name='状态'
    )
    
    # 工时统计
    work_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='工作时长(小时)'
    )
    overtime_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='加班时长(小时)'
    )
    
    # 异常记录
    late_minutes = models.IntegerField(default=0, verbose_name='迟到分钟')
    early_minutes = models.IntegerField(default=0, verbose_name='早退分钟')
    
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'accounts_attendance_record'
        verbose_name = '考勤记录'
        verbose_name_plural = verbose_name
        unique_together = ['user', 'attendance_date']
        ordering = ['-attendance_date']
    
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.attendance_date}'
    
    def calculate_work_hours(self):
        """计算工作时长"""
        if not self.check_in_time or not self.check_out_time:
            return Decimal('0')
        
        # 获取配置
        config = AttendanceConfig.objects.filter(is_default=True, is_active=True).first()
        if not config:
            config = AttendanceConfig.objects.create(
                name='默认配置',
                is_default=True
            )
        
        # 计算总时长
        total_seconds = (self.check_out_time - self.check_in_time).total_seconds()
        total_hours = Decimal(str(total_seconds / 3600))
        
        # 扣除午休时间
        lunch_duration = datetime.combine(date.today(), config.lunch_end_time) - \
                         datetime.combine(date.today(), config.lunch_start_time)
        lunch_hours = Decimal(str(lunch_duration.total_seconds() / 3600))
        
        work_hours = total_hours - lunch_hours
        return max(work_hours, Decimal('0'))


class LeaveRequest(BaseModel):
    """
    请假申请
    """
    LEAVE_TYPES = [
        ('ANNUAL', '年假'),
        ('SICK', '病假'),
        ('PERSONAL', '事假'),
        ('MARRIAGE', '婚假'),
        ('MATERNITY', '产假'),
        ('PATERNITY', '陪产假'),
        ('FUNERAL', '丧假'),
        ('WORK_INJURY', '工伤假'),
        ('OTHER', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('CANCELLED', '已取消'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='leave_requests',
        verbose_name='申请人'
    )
    leave_type = models.CharField(
        max_length=20,
        choices=LEAVE_TYPES,
        default='PERSONAL',
        verbose_name='请假类型'
    )
    
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    start_time = models.TimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.TimeField(null=True, blank=True, verbose_name='结束时间')
    
    days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=1,
        verbose_name='请假天数'
    )
    
    reason = models.TextField(verbose_name='请假原因')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
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
        related_name='approved_leaves',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    approval_remarks = models.CharField(max_length=500, blank=True, verbose_name='审批意见')
    
    class Meta:
        db_table = 'accounts_leave_request'
        verbose_name = '请假申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.get_leave_type_display()} - {self.start_date}'


class OvertimeRequest(BaseModel):
    """
    加班申请
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('CANCELLED', '已取消'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='overtime_requests',
        verbose_name='申请人'
    )
    
    overtime_date = models.DateField(verbose_name='加班日期')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    
    hours = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=0,
        verbose_name='加班时长(小时)'
    )
    
    reason = models.TextField(verbose_name='加班原因')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='overtime_requests',
        verbose_name='关联项目'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_overtimes',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    class Meta:
        db_table = 'accounts_overtime_request'
        verbose_name = '加班申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.overtime_date}'


# =====================
# Serializers
# =====================

class AttendanceConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceConfig
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AttendanceRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='user.department.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AttendanceRecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'work_hours', 'late_minutes', 'early_minutes']


class LeaveRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approver', 'approved_at']


class OvertimeRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    
    class Meta:
        model = OvertimeRequest
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approver', 'approved_at']


# =====================
# ViewSets
# =====================

class AttendanceConfigViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """考勤配置管理"""
    queryset = AttendanceConfig.objects.filter(is_deleted=False)
    serializer_class = AttendanceConfigSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设为默认配置"""
        config = self.get_object()
        config.is_default = True
        config.save()
        return Response(self.get_serializer(config).data)


class AttendanceRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """考勤记录管理"""
    queryset = AttendanceRecord.objects.filter(is_deleted=False)
    serializer_class = AttendanceRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['user', 'status', 'attendance_date']
    search_fields = ['user__first_name', 'user__last_name', 'user__username']
    ordering_fields = ['attendance_date', 'check_in_time']
    
    @action(detail=False, methods=['post'])
    def check_in(self, request):
        """签到"""
        today = date.today()
        now = timezone.now()
        location = request.data.get('location', '')
        
        record, created = AttendanceRecord.objects.get_or_create(
            user=request.user,
            attendance_date=today,
            defaults={
                'check_in_time': now,
                'check_in_location': location,
                'created_by': request.user
            }
        )
        
        if not created and record.check_in_time:
            return Response({'error': '今日已签到'}, status=400)
        
        if not record.check_in_time:
            record.check_in_time = now
            record.check_in_location = location
        
        # 检查是否迟到
        config = AttendanceConfig.objects.filter(is_default=True, is_active=True).first()
        if config:
            work_start = datetime.combine(today, config.work_start_time)
            grace_time = work_start + timedelta(minutes=config.late_grace_minutes)
            if now.replace(tzinfo=None) > grace_time:
                late_delta = now.replace(tzinfo=None) - work_start
                record.late_minutes = int(late_delta.total_seconds() / 60)
                record.status = 'LATE'
        
        record.save()
        return Response(self.get_serializer(record).data)
    
    @action(detail=False, methods=['post'])
    def check_out(self, request):
        """签退"""
        today = date.today()
        now = timezone.now()
        location = request.data.get('location', '')
        
        try:
            record = AttendanceRecord.objects.get(user=request.user, attendance_date=today)
        except AttendanceRecord.DoesNotExist:
            return Response({'error': '今日未签到'}, status=400)
        
        record.check_out_time = now
        record.check_out_location = location
        
        # 检查是否早退
        config = AttendanceConfig.objects.filter(is_default=True, is_active=True).first()
        if config:
            work_end = datetime.combine(today, config.work_end_time)
            if now.replace(tzinfo=None) < work_end:
                early_delta = work_end - now.replace(tzinfo=None)
                record.early_minutes = int(early_delta.total_seconds() / 60)
                if record.status == 'NORMAL':
                    record.status = 'EARLY'
        
        # 计算工作时长
        record.work_hours = record.calculate_work_hours()
        record.save()
        
        return Response(self.get_serializer(record).data)
    
    @action(detail=False, methods=['get'])
    def my_records(self, request):
        """我的考勤记录"""
        month = request.query_params.get('month')
        
        queryset = self.get_queryset().filter(user=request.user)
        if month:
            year, m = month.split('-')
            queryset = queryset.filter(
                attendance_date__year=int(year),
                attendance_date__month=int(m)
            )
        
        return Response(self.get_serializer(queryset, many=True).data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """今日打卡状态"""
        try:
            record = AttendanceRecord.objects.get(
                user=request.user,
                attendance_date=date.today()
            )
            return Response(self.get_serializer(record).data)
        except AttendanceRecord.DoesNotExist:
            return Response({
                'check_in_time': None,
                'check_out_time': None,
                'status': 'NOT_CHECKED'
            })
    
    @action(detail=False, methods=['get'])
    def monthly_summary(self, request):
        """月度考勤汇总"""
        month = request.query_params.get('month', date.today().strftime('%Y-%m'))
        year, m = month.split('-')
        
        user_id = request.query_params.get('user_id')
        if user_id:
            users = [user_id]
        elif request.user.is_superuser:
            from apps.accounts.models import User
            users = User.objects.filter(is_active=True).values_list('id', flat=True)
        else:
            users = [request.user.id]
        
        summaries = []
        for uid in users:
            records = AttendanceRecord.objects.filter(
                user_id=uid,
                attendance_date__year=int(year),
                attendance_date__month=int(m),
                is_deleted=False
            )
            
            from apps.accounts.models import User
            user = User.objects.get(id=uid)
            
            summary = {
                'user_id': uid,
                'user_name': user.get_full_name(),
                'total_days': records.count(),
                'normal_days': records.filter(status='NORMAL').count(),
                'late_days': records.filter(status='LATE').count(),
                'early_days': records.filter(status='EARLY').count(),
                'absent_days': records.filter(status='ABSENT').count(),
                'leave_days': records.filter(status='LEAVE').count(),
                'total_work_hours': records.aggregate(total=Sum('work_hours'))['total'] or 0,
                'total_overtime_hours': records.aggregate(total=Sum('overtime_hours'))['total'] or 0,
            }
            summaries.append(summary)
        
        return Response(summaries)


class LeaveRequestViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """请假申请管理"""
    queryset = LeaveRequest.objects.filter(is_deleted=False)
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['user', 'leave_type', 'status']
    search_fields = ['user__first_name', 'user__last_name', 'reason']
    ordering_fields = ['start_date', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def leave_types(self, request):
        """获取请假类型"""
        return Response([
            {'value': t[0], 'label': t[1]}
            for t in LeaveRequest.LEAVE_TYPES
        ])
    
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """我的请假申请"""
        requests = self.get_queryset().filter(user=request.user)
        return Response(self.get_serializer(requests, many=True).data)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """待我审批的请假"""
        # 简化：假设管理员可以审批所有请假
        if not request.user.is_superuser:
            return Response([])
        
        requests = self.get_queryset().filter(status='PENDING')
        return Response(self.get_serializer(requests, many=True).data)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交申请"""
        leave = self.get_object()
        if leave.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的申请'}, status=400)
        
        leave.status = 'PENDING'
        leave.save()
        return Response(self.get_serializer(leave).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过"""
        leave = self.get_object()
        if leave.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        leave.status = 'APPROVED'
        leave.approver = request.user
        leave.approved_at = timezone.now()
        leave.approval_remarks = request.data.get('remarks', '')
        leave.save()
        
        # 更新考勤记录
        current = leave.start_date
        while current <= leave.end_date:
            AttendanceRecord.objects.update_or_create(
                user=leave.user,
                attendance_date=current,
                defaults={'status': 'LEAVE', 'remarks': f'{leave.get_leave_type_display()}'}
            )
            current += timedelta(days=1)
        
        return Response(self.get_serializer(leave).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审批拒绝"""
        leave = self.get_object()
        if leave.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        leave.status = 'REJECTED'
        leave.approver = request.user
        leave.approved_at = timezone.now()
        leave.approval_remarks = request.data.get('remarks', '')
        leave.save()
        
        return Response(self.get_serializer(leave).data)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """假期余额"""
        year = int(request.query_params.get('year', date.today().year))
        
        # 年假余额（示例：每年10天）
        annual_total = 10
        annual_used = LeaveRequest.objects.filter(
            user=request.user,
            leave_type='ANNUAL',
            status='APPROVED',
            start_date__year=year
        ).aggregate(total=Sum('days'))['total'] or 0
        
        return Response({
            'annual': {
                'total': annual_total,
                'used': float(annual_used),
                'remaining': annual_total - float(annual_used)
            }
        })


class OvertimeRequestViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """加班申请管理"""
    queryset = OvertimeRequest.objects.filter(is_deleted=False)
    serializer_class = OvertimeRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['user', 'status', 'project']
    search_fields = ['user__first_name', 'user__last_name', 'reason']
    ordering_fields = ['overtime_date', 'created_at']
    
    def perform_create(self, serializer):
        # 计算加班时长
        start_time = serializer.validated_data.get('start_time')
        end_time = serializer.validated_data.get('end_time')
        
        start_dt = datetime.combine(date.today(), start_time)
        end_dt = datetime.combine(date.today(), end_time)
        hours = Decimal(str((end_dt - start_dt).total_seconds() / 3600))
        
        serializer.save(user=self.request.user, hours=hours, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """我的加班申请"""
        requests = self.get_queryset().filter(user=request.user)
        return Response(self.get_serializer(requests, many=True).data)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交申请"""
        overtime = self.get_object()
        if overtime.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的申请'}, status=400)
        
        overtime.status = 'PENDING'
        overtime.save()
        return Response(self.get_serializer(overtime).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过"""
        overtime = self.get_object()
        if overtime.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        overtime.status = 'APPROVED'
        overtime.approver = request.user
        overtime.approved_at = timezone.now()
        overtime.save()
        
        # 更新考勤记录
        record, _ = AttendanceRecord.objects.get_or_create(
            user=overtime.user,
            attendance_date=overtime.overtime_date,
            defaults={'created_by': request.user}
        )
        record.overtime_hours = overtime.hours
        record.status = 'OVERTIME'
        record.save()
        
        return Response(self.get_serializer(overtime).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审批拒绝"""
        overtime = self.get_object()
        if overtime.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        overtime.status = 'REJECTED'
        overtime.approver = request.user
        overtime.approved_at = timezone.now()
        overtime.save()
        
        return Response(self.get_serializer(overtime).data)
