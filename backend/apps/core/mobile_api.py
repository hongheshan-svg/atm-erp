"""
移动端功能API模块
Mobile API - 工时填报、拍照上传、扫码、审批
"""
import os
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import BaseModel

User = settings.AUTH_USER_MODEL


class MobileTimeEntry(BaseModel):
    """移动端工时记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                            related_name='mobile_time_entries', verbose_name='用户')

    # 关联
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='mobile_time_entries', verbose_name='项目')
    task = models.ForeignKey('projects.ProjectTask', on_delete=models.SET_NULL,
                            null=True, blank=True, related_name='mobile_time_entries', verbose_name='任务')

    # 时间
    work_date = models.DateField('工作日期')
    start_time = models.TimeField('开始时间', null=True, blank=True)
    end_time = models.TimeField('结束时间', null=True, blank=True)
    hours = models.DecimalField('工时', max_digits=5, decimal_places=2)

    # 工作类型
    WORK_TYPE_CHOICES = [
        ('DESIGN', '设计'),
        ('DEVELOPMENT', '开发'),
        ('ASSEMBLY', '装配'),
        ('DEBUGGING', '调试'),
        ('TESTING', '测试'),
        ('INSTALLATION', '安装'),
        ('TRAINING', '培训'),
        ('TRAVEL', '出差'),
        ('MEETING', '会议'),
        ('OTHER', '其他'),
    ]
    work_type = models.CharField('工作类型', max_length=20, choices=WORK_TYPE_CHOICES)

    description = models.TextField('工作描述')

    # 位置
    location = models.CharField('位置', max_length=200, blank=True)
    latitude = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)

    # 状态
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已驳回'),
    ]
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # 审批
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_time_entries', verbose_name='审批人')
    approved_at = models.DateTimeField('审批时间', null=True, blank=True)
    rejection_reason = models.TextField('驳回原因', blank=True)

    class Meta:
        db_table = 'mobile_time_entry'
        verbose_name = '移动工时记录'
        ordering = ['-work_date', '-created_at']


class MobilePhoto(BaseModel):
    """移动端照片上传"""
    PHOTO_TYPE_CHOICES = [
        ('PROGRESS', '进度照片'),
        ('QUALITY', '质量检验'),
        ('ISSUE', '问题记录'),
        ('DELIVERY', '交付'),
        ('RECEIPT', '收货'),
        ('EQUIPMENT', '设备'),
        ('OTHER', '其他'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                            related_name='mobile_photos', verbose_name='上传用户')

    photo_type = models.CharField('照片类型', max_length=20, choices=PHOTO_TYPE_CHOICES)
    file_path = models.CharField('文件路径', max_length=500)
    file_name = models.CharField('文件名', max_length=200)
    file_size = models.IntegerField('文件大小', default=0)
    thumbnail_path = models.CharField('缩略图路径', max_length=500, blank=True)

    # 关联
    related_type = models.CharField('关联类型', max_length=50, blank=True)
    related_id = models.IntegerField('关联ID', null=True, blank=True)

    # 描述
    description = models.TextField('描述', blank=True)
    tags = models.JSONField('标签', default=list)

    # 位置
    latitude = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)
    location_name = models.CharField('位置名称', max_length=200, blank=True)

    # 拍摄时间
    taken_at = models.DateTimeField('拍摄时间', default=timezone.now)

    class Meta:
        db_table = 'mobile_photo'
        verbose_name = '移动端照片'
        ordering = ['-taken_at']


class MobileScanRecord(BaseModel):
    """移动端扫码记录"""
    SCAN_TYPE_CHOICES = [
        ('INVENTORY', '库存盘点'),
        ('RECEIPT', '收货入库'),
        ('ISSUE', '领料出库'),
        ('TRANSFER', '库存调拨'),
        ('EQUIPMENT', '设备扫码'),
        ('TRACKING', '物流追踪'),
        ('ATTENDANCE', '考勤打卡'),
        ('OTHER', '其他'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                            related_name='scan_records', verbose_name='扫码用户')

    scan_type = models.CharField('扫码类型', max_length=20, choices=SCAN_TYPE_CHOICES)
    barcode = models.CharField('条码内容', max_length=500)
    barcode_type = models.CharField('条码类型', max_length=50, blank=True)  # QR, EAN, Code128等

    # 扫码结果
    result_type = models.CharField('结果类型', max_length=50, blank=True)
    result_id = models.IntegerField('结果ID', null=True, blank=True)
    result_data = models.JSONField('结果数据', default=dict)

    # 后续操作
    action_taken = models.CharField('执行操作', max_length=100, blank=True)
    quantity = models.DecimalField('数量', max_digits=14, decimal_places=4, null=True, blank=True)

    # 位置
    latitude = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)

    scanned_at = models.DateTimeField('扫码时间', default=timezone.now)

    class Meta:
        db_table = 'mobile_scan_record'
        verbose_name = '扫码记录'
        ordering = ['-scanned_at']


class MobileApproval(BaseModel):
    """移动端审批"""
    APPROVAL_TYPE_CHOICES = [
        ('PURCHASE_REQUEST', '采购申请'),
        ('EXPENSE', '费用报销'),
        ('LEAVE', '请假申请'),
        ('OVERTIME', '加班申请'),
        ('TIME_ENTRY', '工时审批'),
        ('PAYMENT', '付款申请'),
        ('CONTRACT', '合同审批'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('DELEGATED', '已转交'),
    ]

    approval_type = models.CharField('审批类型', max_length=30, choices=APPROVAL_TYPE_CHOICES)
    related_type = models.CharField('关联对象类型', max_length=100)
    related_id = models.IntegerField('关联对象ID')

    # 申请人
    applicant = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='submitted_approvals', verbose_name='申请人')

    # 审批人
    approver = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='pending_approvals', verbose_name='审批人')

    # 审批信息
    title = models.CharField('审批标题', max_length=200)
    summary = models.TextField('摘要')
    amount = models.DecimalField('金额', max_digits=14, decimal_places=2, null=True, blank=True)

    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='PENDING')

    # 审批结果
    decision = models.CharField('审批意见', max_length=50, blank=True)
    comments = models.TextField('审批备注', blank=True)
    decided_at = models.DateTimeField('决定时间', null=True, blank=True)

    # 转交
    delegated_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='delegated_approvals', verbose_name='转交给')

    class Meta:
        db_table = 'mobile_approval'
        verbose_name = '移动审批'
        ordering = ['-created_at']


class MobileNotification(BaseModel):
    """移动端通知"""
    NOTIFICATION_TYPE_CHOICES = [
        ('APPROVAL', '审批通知'),
        ('TASK', '任务通知'),
        ('MESSAGE', '消息'),
        ('ALERT', '预警'),
        ('REMINDER', '提醒'),
        ('SYSTEM', '系统通知'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                            related_name='mobile_notifications', verbose_name='用户')

    notification_type = models.CharField('通知类型', max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField('标题', max_length=200)
    content = models.TextField('内容')

    # 关联
    related_type = models.CharField('关联类型', max_length=50, blank=True)
    related_id = models.IntegerField('关联ID', null=True, blank=True)
    action_url = models.CharField('操作链接', max_length=500, blank=True)

    # 状态
    is_read = models.BooleanField('已读', default=False)
    read_at = models.DateTimeField('阅读时间', null=True, blank=True)

    # 推送
    pushed = models.BooleanField('已推送', default=False)
    pushed_at = models.DateTimeField('推送时间', null=True, blank=True)

    class Meta:
        db_table = 'mobile_notification'
        verbose_name = '移动通知'
        ordering = ['-created_at']


# ==================== Serializers ====================

class MobileTimeEntrySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    task_name = serializers.CharField(source='task.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    work_type_display = serializers.CharField(source='get_work_type_display', read_only=True)

    class Meta:
        model = MobileTimeEntry
        fields = '__all__'


class MobilePhotoSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    photo_type_display = serializers.CharField(source='get_photo_type_display', read_only=True)

    class Meta:
        model = MobilePhoto
        fields = '__all__'


class MobileScanRecordSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    scan_type_display = serializers.CharField(source='get_scan_type_display', read_only=True)

    class Meta:
        model = MobileScanRecord
        fields = '__all__'


class MobileApprovalSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source='applicant.get_full_name', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    approval_type_display = serializers.CharField(source='get_approval_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MobileApproval
        fields = '__all__'


class MobileNotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = MobileNotification
        fields = '__all__'


# ==================== ViewSets ====================

class MobileTimeEntryViewSet(viewsets.ModelViewSet):
    """移动工时填报"""
    queryset = MobileTimeEntry.objects.filter(is_deleted=False)
    serializer_class = MobileTimeEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # 普通用户只能看自己的
        if not user.is_staff:
            qs = qs.filter(user=user)

        project = self.request.query_params.get('project')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if project:
            qs = qs.filter(project_id=project)
        if date_from:
            qs = qs.filter(work_date__gte=date_from)
        if date_to:
            qs = qs.filter(work_date__lte=date_to)

        return qs.select_related('user', 'project', 'task')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_entries(self, request):
        """我的工时记录"""
        entries = self.get_queryset().filter(user=request.user)
        return Response(MobileTimeEntrySerializer(entries, many=True).data)

    @action(detail=False, methods=['get'])
    def weekly_summary(self, request):
        """本周工时汇总"""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())

        entries = self.get_queryset().filter(
            user=request.user,
            work_date__gte=week_start,
            work_date__lte=today
        )

        total_hours = entries.aggregate(total=Sum('hours'))['total'] or 0
        by_type = entries.values('work_type').annotate(hours=Sum('hours'))
        by_project = entries.values('project__name').annotate(hours=Sum('hours'))

        return Response({
            'total_hours': float(total_hours),
            'by_type': list(by_type),
            'by_project': list(by_project),
        })

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交审批"""
        entry = self.get_object()
        entry.status = 'SUBMITTED'
        entry.save()

        # 创建审批
        # 假设项目经理审批
        if entry.project and entry.project.manager:
            MobileApproval.objects.create(
                approval_type='TIME_ENTRY',
                related_type='MobileTimeEntry',
                related_id=entry.id,
                applicant=entry.user,
                approver=entry.project.manager,
                title=f'{entry.user.get_full_name()}的工时提交',
                summary=f'{entry.work_date} {entry.hours}小时 - {entry.description[:50]}',
                created_by=request.user,
                updated_by=request.user
            )

        return Response({'message': '已提交审批'})


class MobilePhotoViewSet(viewsets.ModelViewSet):
    """移动端照片管理"""
    queryset = MobilePhoto.objects.filter(is_deleted=False)
    serializer_class = MobilePhotoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def upload(self, request):
        """上传照片"""
        file = request.FILES.get('photo')
        if not file:
            return Response({'error': '请选择照片'}, status=400)

        # 保存文件
        ext = os.path.splitext(file.name)[1]
        filename = f'{uuid.uuid4().hex}{ext}'
        file_path = f'uploads/photos/{timezone.now().strftime("%Y%m")}/{filename}'

        # 实际保存逻辑（需要配置存储）
        full_path = os.path.join('/app/media', file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        photo = MobilePhoto.objects.create(
            user=request.user,
            photo_type=request.data.get('photo_type', 'OTHER'),
            file_path=file_path,
            file_name=file.name,
            file_size=file.size,
            description=request.data.get('description', ''),
            latitude=request.data.get('latitude'),
            longitude=request.data.get('longitude'),
            location_name=request.data.get('location_name', ''),
            related_type=request.data.get('related_type', ''),
            related_id=request.data.get('related_id'),
            created_by=request.user,
            updated_by=request.user
        )

        return Response(MobilePhotoSerializer(photo).data)


class MobileScanRecordViewSet(viewsets.ModelViewSet):
    """扫码记录管理"""
    queryset = MobileScanRecord.objects.filter(is_deleted=False)
    serializer_class = MobileScanRecordSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def scan(self, request):
        """扫码"""
        barcode = request.data.get('barcode')
        scan_type = request.data.get('scan_type')

        if not barcode:
            return Response({'error': '条码内容不能为空'}, status=400)

        # 解析条码
        result = self._parse_barcode(barcode, scan_type)

        # 创建记录
        record = MobileScanRecord.objects.create(
            user=request.user,
            scan_type=scan_type or 'OTHER',
            barcode=barcode,
            barcode_type=request.data.get('barcode_type', ''),
            result_type=result.get('type', ''),
            result_id=result.get('id'),
            result_data=result.get('data', {}),
            latitude=request.data.get('latitude'),
            longitude=request.data.get('longitude'),
            created_by=request.user,
            updated_by=request.user
        )

        return Response({
            'record_id': record.id,
            'result': result,
        })

    def _parse_barcode(self, barcode, scan_type):
        """解析条码"""
        result = {'type': 'UNKNOWN', 'data': {}}

        # 尝试解析为物料
        from apps.masterdata.models import Item
        try:
            item = Item.objects.get(Q(sku=barcode) | Q(barcode=barcode))
            result = {
                'type': 'ITEM',
                'id': item.id,
                'data': {
                    'sku': item.sku,
                    'name': item.name,
                    'unit': item.unit,
                }
            }
        except Item.DoesNotExist:
            pass

        return result

    @action(detail=False, methods=['post'])
    def inventory_count(self, request):
        """库存盘点扫码"""
        barcode = request.data.get('barcode')
        quantity = Decimal(str(request.data.get('quantity', 1)))
        warehouse_id = request.data.get('warehouse_id')

        from apps.inventory.models import StockOnHand
        from apps.masterdata.models import Item

        try:
            item = Item.objects.get(Q(sku=barcode) | Q(barcode=barcode))
        except Item.DoesNotExist:
            return Response({'error': '物料不存在'}, status=404)

        # 获取当前库存
        current_stock = StockOnHand.objects.filter(
            item=item,
            warehouse_id=warehouse_id
        ).first()

        current_qty = current_stock.quantity if current_stock else 0

        # 创建扫码记录
        record = MobileScanRecord.objects.create(
            user=request.user,
            scan_type='INVENTORY',
            barcode=barcode,
            result_type='ITEM',
            result_id=item.id,
            result_data={
                'sku': item.sku,
                'name': item.name,
                'current_qty': float(current_qty),
                'counted_qty': float(quantity),
            },
            quantity=quantity,
            action_taken='INVENTORY_COUNT',
            created_by=request.user,
            updated_by=request.user
        )

        return Response({
            'item': {
                'id': item.id,
                'sku': item.sku,
                'name': item.name,
            },
            'current_qty': float(current_qty),
            'counted_qty': float(quantity),
            'difference': float(quantity - current_qty),
        })


class MobileApprovalViewSet(viewsets.ModelViewSet):
    """移动审批管理"""
    queryset = MobileApproval.objects.filter(is_deleted=False)
    serializer_class = MobileApprovalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # 只显示与我相关的审批
        qs = qs.filter(Q(approver=user) | Q(applicant=user))

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.select_related('applicant', 'approver')

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """待我审批"""
        approvals = self.get_queryset().filter(
            approver=request.user,
            status='PENDING'
        )
        return Response(MobileApprovalSerializer(approvals, many=True).data)

    @action(detail=False, methods=['get'])
    def my_submitted(self, request):
        """我提交的"""
        approvals = self.get_queryset().filter(applicant=request.user)
        return Response(MobileApprovalSerializer(approvals, many=True).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准"""
        approval = self.get_object()

        if approval.approver != request.user:
            return Response({'error': '您没有审批权限'}, status=403)

        approval.status = 'APPROVED'
        approval.decision = 'APPROVED'
        approval.comments = request.data.get('comments', '')
        approval.decided_at = timezone.now()
        approval.save()

        # 更新关联对象状态
        self._update_related_status(approval, 'APPROVED')

        # 通知申请人
        MobileNotification.objects.create(
            user=approval.applicant,
            notification_type='APPROVAL',
            title='审批通过',
            content=f'您的{approval.get_approval_type_display()}已批准',
            related_type='MobileApproval',
            related_id=approval.id,
            created_by=request.user,
            updated_by=request.user
        )

        return Response({'message': '已批准'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝"""
        approval = self.get_object()

        if approval.approver != request.user:
            return Response({'error': '您没有审批权限'}, status=403)

        approval.status = 'REJECTED'
        approval.decision = 'REJECTED'
        approval.comments = request.data.get('comments', '')
        approval.decided_at = timezone.now()
        approval.save()

        # 更新关联对象状态
        self._update_related_status(approval, 'REJECTED')

        # 通知申请人
        MobileNotification.objects.create(
            user=approval.applicant,
            notification_type='APPROVAL',
            title='审批被拒绝',
            content=f'您的{approval.get_approval_type_display()}已被拒绝: {approval.comments}',
            related_type='MobileApproval',
            related_id=approval.id,
            created_by=request.user,
            updated_by=request.user
        )

        return Response({'message': '已拒绝'})

    @action(detail=True, methods=['post'])
    def delegate(self, request, pk=None):
        """转交"""
        approval = self.get_object()
        delegate_to_id = request.data.get('user_id')

        if approval.approver != request.user:
            return Response({'error': '您没有权限转交'}, status=403)

        approval.status = 'DELEGATED'
        approval.delegated_to_id = delegate_to_id
        approval.comments = request.data.get('comments', '')
        approval.save()

        # 创建新的审批给转交人
        MobileApproval.objects.create(
            approval_type=approval.approval_type,
            related_type=approval.related_type,
            related_id=approval.related_id,
            applicant=approval.applicant,
            approver_id=delegate_to_id,
            title=approval.title,
            summary=approval.summary,
            amount=approval.amount,
            created_by=request.user,
            updated_by=request.user
        )

        return Response({'message': '已转交'})

    def _update_related_status(self, approval, status):
        """更新关联对象状态"""
        if approval.related_type == 'MobileTimeEntry':
            try:
                entry = MobileTimeEntry.objects.get(pk=approval.related_id)
                entry.status = status
                if status == 'APPROVED':
                    entry.approved_by = approval.approver
                    entry.approved_at = timezone.now()
                entry.save()
            except MobileTimeEntry.DoesNotExist:
                pass


class MobileNotificationViewSet(viewsets.ModelViewSet):
    """移动通知管理"""
    queryset = MobileNotification.objects.filter(is_deleted=False)
    serializer_class = MobileNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """未读通知"""
        notifications = self.get_queryset().filter(is_read=False)
        return Response(MobileNotificationSerializer(notifications, many=True).data)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """未读数量"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """标记已读"""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({'message': '已标记已读'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """全部已读"""
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'message': '已全部标记已读'})


# ==================== 移动端首页API ====================

class MobileDashboardView(APIView):
    """移动端首页"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # 待审批数
        pending_approvals = MobileApproval.objects.filter(
            approver=user,
            status='PENDING',
            is_deleted=False
        ).count()

        # 未读通知
        unread_notifications = MobileNotification.objects.filter(
            user=user,
            is_read=False,
            is_deleted=False
        ).count()

        # 本周工时
        week_start = today - timedelta(days=today.weekday())
        week_hours = MobileTimeEntry.objects.filter(
            user=user,
            work_date__gte=week_start,
            work_date__lte=today,
            is_deleted=False
        ).aggregate(total=Sum('hours'))['total'] or 0

        # 我的任务
        from apps.projects.models import ProjectTask
        my_tasks = ProjectTask.objects.filter(
            assignee=user,
            status__in=['NOT_STARTED', 'IN_PROGRESS'],
            is_deleted=False
        ).count()

        return Response({
            'pending_approvals': pending_approvals,
            'unread_notifications': unread_notifications,
            'week_hours': float(week_hours),
            'my_tasks': my_tasks,
        })


class MobileQuickActionsView(APIView):
    """移动端快捷操作"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取可用的快捷操作"""
        actions = [
            {
                'id': 'time_entry',
                'name': '填报工时',
                'icon': 'clock',
                'route': '/mobile/time-entry',
            },
            {
                'id': 'scan',
                'name': '扫一扫',
                'icon': 'scan',
                'route': '/mobile/scan',
            },
            {
                'id': 'photo',
                'name': '拍照上传',
                'icon': 'camera',
                'route': '/mobile/photo',
            },
            {
                'id': 'approval',
                'name': '审批',
                'icon': 'check-circle',
                'route': '/mobile/approval',
            },
            {
                'id': 'tasks',
                'name': '我的任务',
                'icon': 'tasks',
                'route': '/mobile/tasks',
            },
        ]

        return Response(actions)
