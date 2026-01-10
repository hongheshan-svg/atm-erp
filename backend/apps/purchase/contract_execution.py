"""
采购合同执行跟踪
Purchase Contract Execution Tracking
跟踪采购合同的执行进度、交货情况、付款情况等
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class ContractExecution(BaseModel):
    """
    合同执行记录
    """
    EXECUTION_STATUS = [
        ('NOT_STARTED', '未开始'),
        ('IN_PROGRESS', '执行中'),
        ('DELAYED', '延迟'),
        ('COMPLETED', '已完成'),
        ('TERMINATED', '已终止'),
    ]
    
    contract = models.OneToOneField(
        'purchase.PurchaseContract',
        on_delete=models.CASCADE,
        related_name='execution',
        verbose_name='采购合同'
    )
    
    # 执行状态
    status = models.CharField(
        max_length=20,
        choices=EXECUTION_STATUS,
        default='NOT_STARTED',
        verbose_name='执行状态'
    )
    
    # 交货进度
    total_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='总数量')
    delivered_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='已交数量')
    qualified_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='合格数量')
    rejected_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='不合格数量')
    
    # 金额统计
    contract_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='合同金额')
    invoiced_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='已开票金额')
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='已付金额')
    
    # 时间
    planned_start_date = models.DateField(null=True, blank=True, verbose_name='计划开始日期')
    planned_end_date = models.DateField(null=True, blank=True, verbose_name='计划结束日期')
    actual_start_date = models.DateField(null=True, blank=True, verbose_name='实际开始日期')
    actual_end_date = models.DateField(null=True, blank=True, verbose_name='实际结束日期')
    
    # 延期记录
    delay_days = models.IntegerField(default=0, verbose_name='延期天数')
    delay_reason = models.TextField(blank=True, verbose_name='延期原因')
    
    # 评价
    delivery_score = models.IntegerField(null=True, blank=True, verbose_name='交货评分')
    quality_score = models.IntegerField(null=True, blank=True, verbose_name='质量评分')
    service_score = models.IntegerField(null=True, blank=True, verbose_name='服务评分')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_contract_execution'
        verbose_name = '合同执行'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.contract.contract_no} - {self.get_status_display()}'
    
    @property
    def delivery_rate(self):
        """交货进度"""
        if self.total_qty <= 0:
            return 0
        return round(float(self.delivered_qty) / float(self.total_qty) * 100, 2)
    
    @property
    def payment_rate(self):
        """付款进度"""
        if self.contract_amount <= 0:
            return 0
        return round(float(self.paid_amount) / float(self.contract_amount) * 100, 2)
    
    @property
    def qualified_rate(self):
        """合格率"""
        if self.delivered_qty <= 0:
            return 0
        return round(float(self.qualified_qty) / float(self.delivered_qty) * 100, 2)
    
    @property
    def is_overdue(self):
        """是否逾期"""
        if self.status == 'COMPLETED':
            return False
        if self.planned_end_date and date.today() > self.planned_end_date:
            return True
        return False


class DeliveryRecord(BaseModel):
    """
    交货记录
    """
    DELIVERY_STATUS = [
        ('PENDING', '待收货'),
        ('RECEIVED', '已收货'),
        ('INSPECTING', '检验中'),
        ('QUALIFIED', '合格入库'),
        ('REJECTED', '退货'),
        ('PARTIAL', '部分合格'),
    ]
    
    execution = models.ForeignKey(
        ContractExecution,
        on_delete=models.CASCADE,
        related_name='deliveries',
        verbose_name='合同执行'
    )
    
    # 交货信息
    delivery_no = models.CharField(max_length=50, verbose_name='交货单号')
    delivery_date = models.DateField(verbose_name='交货日期')
    receive_date = models.DateField(null=True, blank=True, verbose_name='收货日期')
    
    # 数量
    delivery_qty = models.DecimalField(max_digits=18, decimal_places=4, verbose_name='交货数量')
    received_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='收货数量')
    qualified_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='合格数量')
    rejected_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='不合格数量')
    
    status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 检验
    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspected_deliveries',
        verbose_name='检验员'
    )
    inspection_date = models.DateField(null=True, blank=True, verbose_name='检验日期')
    inspection_result = models.TextField(blank=True, verbose_name='检验结果')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_delivery_record'
        verbose_name = '交货记录'
        verbose_name_plural = verbose_name
        ordering = ['-delivery_date']
    
    def __str__(self):
        return f'{self.delivery_no} - {self.delivery_qty}'


class PaymentRecord(BaseModel):
    """
    付款记录
    """
    PAYMENT_TYPES = [
        ('ADVANCE', '预付款'),
        ('PROGRESS', '进度款'),
        ('DELIVERY', '到货款'),
        ('ACCEPTANCE', '验收款'),
        ('RETENTION', '质保金'),
        ('OTHER', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待付款'),
        ('APPROVED', '已审批'),
        ('PAID', '已付款'),
        ('CANCELLED', '已取消'),
    ]
    
    execution = models.ForeignKey(
        ContractExecution,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='合同执行'
    )
    
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPES,
        default='PROGRESS',
        verbose_name='付款类型'
    )
    
    # 付款信息
    payment_no = models.CharField(max_length=50, verbose_name='付款单号')
    planned_date = models.DateField(verbose_name='计划付款日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际付款日期')
    
    # 金额
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='付款金额')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 审批
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_contract_payments',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_payment_record'
        verbose_name = '付款记录'
        verbose_name_plural = verbose_name
        ordering = ['planned_date']
    
    def __str__(self):
        return f'{self.payment_no} - {self.amount}'


class ContractIssue(BaseModel):
    """
    合同执行问题
    """
    ISSUE_TYPES = [
        ('QUALITY', '质量问题'),
        ('DELIVERY', '交期问题'),
        ('QUANTITY', '数量问题'),
        ('PRICE', '价格问题'),
        ('SERVICE', '服务问题'),
        ('OTHER', '其他'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', '轻微'),
        ('MEDIUM', '一般'),
        ('HIGH', '严重'),
        ('CRITICAL', '紧急'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', '待处理'),
        ('IN_PROGRESS', '处理中'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
    ]
    
    execution = models.ForeignKey(
        ContractExecution,
        on_delete=models.CASCADE,
        related_name='issues',
        verbose_name='合同执行'
    )
    
    issue_type = models.CharField(
        max_length=20,
        choices=ISSUE_TYPES,
        verbose_name='问题类型'
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_LEVELS,
        default='MEDIUM',
        verbose_name='严重程度'
    )
    
    title = models.CharField(max_length=200, verbose_name='问题标题')
    description = models.TextField(verbose_name='问题描述')
    
    # 处理
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN',
        verbose_name='状态'
    )
    handler = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_contract_issues',
        verbose_name='处理人'
    )
    solution = models.TextField(blank=True, verbose_name='解决方案')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    
    class Meta:
        db_table = 'purchase_contract_issue'
        verbose_name = '合同问题'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title}'


# =====================
# Serializers
# =====================

class DeliveryRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    
    class Meta:
        model = DeliveryRecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class PaymentRecordSerializer(serializers.ModelSerializer):
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    
    class Meta:
        model = PaymentRecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approver', 'approved_at']


class ContractIssueSerializer(serializers.ModelSerializer):
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    handler_name = serializers.CharField(source='handler.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = ContractIssue
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ContractExecutionSerializer(serializers.ModelSerializer):
    contract_no = serializers.CharField(source='contract.contract_no', read_only=True)
    supplier_name = serializers.CharField(source='contract.supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_rate = serializers.FloatField(read_only=True)
    payment_rate = serializers.FloatField(read_only=True)
    qualified_rate = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    deliveries = DeliveryRecordSerializer(many=True, read_only=True)
    payments = PaymentRecordSerializer(many=True, read_only=True)
    issues = ContractIssueSerializer(many=True, read_only=True)
    
    class Meta:
        model = ContractExecution
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ContractExecutionListSerializer(serializers.ModelSerializer):
    contract_no = serializers.CharField(source='contract.contract_no', read_only=True)
    supplier_name = serializers.CharField(source='contract.supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_rate = serializers.FloatField(read_only=True)
    payment_rate = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    issue_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractExecution
        fields = [
            'id', 'contract', 'contract_no', 'supplier_name', 'status', 'status_display',
            'contract_amount', 'paid_amount', 'total_qty', 'delivered_qty',
            'delivery_rate', 'payment_rate', 'is_overdue', 'planned_end_date', 'issue_count'
        ]
    
    def get_issue_count(self, obj):
        return obj.issues.filter(status__in=['OPEN', 'IN_PROGRESS']).count()


# =====================
# ViewSets
# =====================

class ContractExecutionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """合同执行管理"""
    queryset = ContractExecution.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'contract__supplier']
    search_fields = ['contract__contract_no', 'contract__supplier__name']
    ordering_fields = ['planned_end_date', 'contract_amount']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractExecutionListSerializer
        return ContractExecutionSerializer
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """更新执行状态"""
        execution = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in dict(ContractExecution.EXECUTION_STATUS):
            return Response({'error': '无效的状态'}, status=400)
        
        execution.status = new_status
        if new_status == 'IN_PROGRESS' and not execution.actual_start_date:
            execution.actual_start_date = date.today()
        elif new_status == 'COMPLETED':
            execution.actual_end_date = date.today()
        
        execution.save()
        return Response(self.get_serializer(execution).data)
    
    @action(detail=True, methods=['post'])
    def add_delivery(self, request, pk=None):
        """添加交货记录"""
        execution = self.get_object()
        
        delivery = DeliveryRecord.objects.create(
            execution=execution,
            delivery_no=request.data.get('delivery_no'),
            delivery_date=request.data.get('delivery_date'),
            delivery_qty=request.data.get('delivery_qty'),
            remarks=request.data.get('remarks', ''),
            created_by=request.user
        )
        
        # 更新执行数据
        execution.delivered_qty = execution.deliveries.aggregate(
            total=Sum('received_qty')
        )['total'] or 0
        execution.save()
        
        return Response(DeliveryRecordSerializer(delivery).data)
    
    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """添加付款计划"""
        execution = self.get_object()
        
        payment = PaymentRecord.objects.create(
            execution=execution,
            payment_type=request.data.get('payment_type', 'PROGRESS'),
            payment_no=request.data.get('payment_no'),
            planned_date=request.data.get('planned_date'),
            amount=request.data.get('amount'),
            remarks=request.data.get('remarks', ''),
            created_by=request.user
        )
        
        return Response(PaymentRecordSerializer(payment).data)
    
    @action(detail=True, methods=['post'])
    def add_issue(self, request, pk=None):
        """添加问题"""
        execution = self.get_object()
        
        issue = ContractIssue.objects.create(
            execution=execution,
            issue_type=request.data.get('issue_type'),
            severity=request.data.get('severity', 'MEDIUM'),
            title=request.data.get('title'),
            description=request.data.get('description'),
            created_by=request.user
        )
        
        return Response(ContractIssueSerializer(issue).data)
    
    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        """合同评价"""
        execution = self.get_object()
        
        execution.delivery_score = request.data.get('delivery_score')
        execution.quality_score = request.data.get('quality_score')
        execution.service_score = request.data.get('service_score')
        execution.save()
        
        return Response(self.get_serializer(execution).data)
    
    @action(detail=False, methods=['get'])
    def overdue_list(self, request):
        """逾期合同列表"""
        today = date.today()
        executions = self.get_queryset().filter(
            status__in=['NOT_STARTED', 'IN_PROGRESS', 'DELAYED'],
            planned_end_date__lt=today
        ).order_by('planned_end_date')
        
        return Response(ContractExecutionListSerializer(executions, many=True).data)
    
    @action(detail=False, methods=['get'])
    def upcoming_payments(self, request):
        """即将到期的付款"""
        days = int(request.query_params.get('days', 7))
        end_date = date.today() + timedelta(days=days)
        
        payments = PaymentRecord.objects.filter(
            status='PENDING',
            planned_date__lte=end_date,
            is_deleted=False
        ).select_related('execution', 'execution__contract').order_by('planned_date')
        
        return Response(PaymentRecordSerializer(payments, many=True).data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """执行统计"""
        qs = self.get_queryset()
        
        by_status = qs.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('contract_amount')
        )
        
        total_amount = qs.aggregate(total=Sum('contract_amount'))['total'] or 0
        total_paid = qs.aggregate(total=Sum('paid_amount'))['total'] or 0
        
        overdue_count = qs.filter(
            status__in=['NOT_STARTED', 'IN_PROGRESS', 'DELAYED'],
            planned_end_date__lt=date.today()
        ).count()
        
        return Response({
            'total_contracts': qs.count(),
            'total_amount': float(total_amount),
            'total_paid': float(total_paid),
            'payment_rate': round(float(total_paid) / float(total_amount) * 100, 2) if total_amount > 0 else 0,
            'overdue_count': overdue_count,
            'by_status': list(by_status)
        })


class DeliveryRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """交货记录管理"""
    queryset = DeliveryRecord.objects.filter(is_deleted=False)
    serializer_class = DeliveryRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['execution', 'status']
    
    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """收货"""
        delivery = self.get_object()
        
        delivery.receive_date = request.data.get('receive_date', date.today().isoformat())
        delivery.received_qty = request.data.get('received_qty', delivery.delivery_qty)
        delivery.status = 'RECEIVED'
        delivery.save()
        
        return Response(self.get_serializer(delivery).data)
    
    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """检验"""
        delivery = self.get_object()
        
        delivery.qualified_qty = Decimal(str(request.data.get('qualified_qty', 0)))
        delivery.rejected_qty = Decimal(str(request.data.get('rejected_qty', 0)))
        delivery.inspector = request.user
        delivery.inspection_date = date.today()
        delivery.inspection_result = request.data.get('inspection_result', '')
        
        if delivery.rejected_qty > 0 and delivery.qualified_qty > 0:
            delivery.status = 'PARTIAL'
        elif delivery.rejected_qty > 0:
            delivery.status = 'REJECTED'
        else:
            delivery.status = 'QUALIFIED'
        
        delivery.save()
        
        # 更新执行记录
        execution = delivery.execution
        agg = execution.deliveries.aggregate(
            delivered=Sum('received_qty'),
            qualified=Sum('qualified_qty'),
            rejected=Sum('rejected_qty')
        )
        execution.delivered_qty = agg['delivered'] or 0
        execution.qualified_qty = agg['qualified'] or 0
        execution.rejected_qty = agg['rejected'] or 0
        execution.save()
        
        return Response(self.get_serializer(delivery).data)


class PaymentRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """付款记录管理"""
    queryset = PaymentRecord.objects.filter(is_deleted=False)
    serializer_class = PaymentRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['execution', 'status', 'payment_type']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批"""
        payment = self.get_object()
        payment.status = 'APPROVED'
        payment.approver = request.user
        payment.approved_at = timezone.now()
        payment.save()
        return Response(self.get_serializer(payment).data)
    
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """付款"""
        payment = self.get_object()
        
        if payment.status != 'APPROVED':
            return Response({'error': '需要先审批才能付款'}, status=400)
        
        payment.status = 'PAID'
        payment.actual_date = request.data.get('actual_date', date.today().isoformat())
        payment.save()
        
        # 更新执行记录
        execution = payment.execution
        execution.paid_amount = execution.payments.filter(status='PAID').aggregate(
            total=Sum('amount')
        )['total'] or 0
        execution.save()
        
        return Response(self.get_serializer(payment).data)


class ContractIssueViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """合同问题管理"""
    queryset = ContractIssue.objects.filter(is_deleted=False)
    serializer_class = ContractIssueSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['execution', 'status', 'issue_type', 'severity']
    search_fields = ['title', 'description']
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分配处理人"""
        issue = self.get_object()
        handler_id = request.data.get('handler_id')
        
        from apps.accounts.models import User
        issue.handler = User.objects.get(id=handler_id)
        issue.status = 'IN_PROGRESS'
        issue.save()
        
        return Response(self.get_serializer(issue).data)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决"""
        issue = self.get_object()
        
        issue.solution = request.data.get('solution', '')
        issue.status = 'RESOLVED'
        issue.resolved_at = timezone.now()
        issue.save()
        
        return Response(self.get_serializer(issue).data)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭"""
        issue = self.get_object()
        issue.status = 'CLOSED'
        issue.save()
        return Response(self.get_serializer(issue).data)
