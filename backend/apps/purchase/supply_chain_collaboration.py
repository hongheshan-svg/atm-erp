"""
供应链协同平台模块
Supply Chain Collaboration Platform

功能：
- 供应商门户
- 询报价协同
- 交期协同
- 质量协同
- 对账协同
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


# =============================================================================
# 模型定义
# =============================================================================

class SupplierPortalUser(BaseModel):
    """供应商门户用户"""
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.CASCADE,
        related_name='portal_users',
        verbose_name='供应商'
    )
    
    username = models.CharField(max_length=100, unique=True, verbose_name='用户名')
    email = models.EmailField(verbose_name='邮箱')
    phone = models.CharField(max_length=20, blank=True, verbose_name='电话')
    
    # 角色
    role = models.CharField(
        max_length=20,
        choices=[
            ('ADMIN', '管理员'),
            ('SALES', '销售'),
            ('QUALITY', '质量'),
            ('LOGISTICS', '物流'),
            ('FINANCE', '财务'),
        ],
        default='SALES',
        verbose_name='角色'
    )
    
    # 权限
    can_view_orders = models.BooleanField(default=True, verbose_name='查看订单')
    can_confirm_orders = models.BooleanField(default=False, verbose_name='确认订单')
    can_update_delivery = models.BooleanField(default=False, verbose_name='更新交期')
    can_view_forecast = models.BooleanField(default=False, verbose_name='查看预测')
    can_submit_invoice = models.BooleanField(default=False, verbose_name='提交发票')
    
    is_active = models.BooleanField(default=True, verbose_name='启用')
    last_login = models.DateTimeField(null=True, blank=True, verbose_name='最后登录')
    
    class Meta:
        db_table = 'supplier_portal_user'
        verbose_name = '供应商门户用户'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.supplier.name} - {self.username}'


class RFQCollaboration(BaseModel):
    """询报价协同"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SENT', '已发送'),
        ('QUOTED', '已报价'),
        ('NEGOTIATING', '议价中'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
        ('EXPIRED', '已过期'),
    ]
    
    rfq_no = models.CharField(max_length=50, unique=True, verbose_name='询价单号')
    
    # 询价内容
    title = models.CharField(max_length=200, verbose_name='询价标题')
    description = models.TextField(blank=True, verbose_name='询价说明')
    
    # 供应商
    suppliers = models.ManyToManyField(
        'masterdata.Supplier',
        through='RFQSupplierResponse',
        related_name='rfq_collaborations',
        verbose_name='供应商'
    )
    
    # 时间
    issue_date = models.DateField(auto_now_add=True, verbose_name='发布日期')
    deadline = models.DateField(verbose_name='截止日期')
    required_delivery_date = models.DateField(null=True, blank=True, verbose_name='要求交期')
    
    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rfq_collaborations',
        verbose_name='关联项目'
    )
    
    # 负责人
    buyer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='rfq_collaborations',
        verbose_name='采购员'
    )
    
    class Meta:
        db_table = 'rfq_collaboration'
        verbose_name = '询报价协同'
        verbose_name_plural = verbose_name
        ordering = ['-issue_date']
    
    def __str__(self):
        return f'{self.rfq_no} - {self.title}'
    
    def save(self, *args, **kwargs):
        if not self.rfq_no:
            from apps.core.models import CodeRule
            self.rfq_no = CodeRule.generate_code('RFQ')
        super().save(*args, **kwargs)


class RFQItem(BaseModel):
    """询价明细"""
    rfq = models.ForeignKey(
        RFQCollaboration,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='询价单'
    )
    
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='物料'
    )
    item_code = models.CharField(max_length=50, blank=True, verbose_name='物料编码')
    item_name = models.CharField(max_length=200, verbose_name='物料名称')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格')
    
    quantity = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='数量')
    unit = models.CharField(max_length=20, default='件', verbose_name='单位')
    
    # 目标价格
    target_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, verbose_name='目标价')
    
    # 附件
    drawings = models.JSONField(default=list, blank=True, verbose_name='图纸')
    technical_requirements = models.TextField(blank=True, verbose_name='技术要求')
    
    class Meta:
        db_table = 'rfq_item'
        verbose_name = '询价明细'
        verbose_name_plural = verbose_name
        ordering = ['id']


class RFQSupplierResponse(BaseModel):
    """供应商报价响应"""
    rfq = models.ForeignKey(
        RFQCollaboration,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='询价单'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.CASCADE,
        related_name='rfq_responses',
        verbose_name='供应商'
    )
    
    # 响应状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待响应'),
            ('QUOTED', '已报价'),
            ('DECLINED', '拒绝报价'),
        ],
        default='PENDING',
        verbose_name='状态'
    )
    
    # 报价信息
    quoted_at = models.DateTimeField(null=True, blank=True, verbose_name='报价时间')
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='报价总额')
    validity_days = models.IntegerField(default=30, verbose_name='报价有效期(天)')
    
    # 交期
    quoted_delivery_date = models.DateField(null=True, blank=True, verbose_name='报价交期')
    delivery_terms = models.CharField(max_length=200, blank=True, verbose_name='交货条款')
    
    # 付款条款
    payment_terms = models.CharField(max_length=200, blank=True, verbose_name='付款条款')
    
    # 备注
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    # 是否选中
    is_selected = models.BooleanField(default=False, verbose_name='已选中')
    
    class Meta:
        db_table = 'rfq_supplier_response'
        verbose_name = '供应商报价'
        verbose_name_plural = verbose_name
        unique_together = ['rfq', 'supplier']


class RFQItemQuote(BaseModel):
    """报价明细"""
    response = models.ForeignKey(
        RFQSupplierResponse,
        on_delete=models.CASCADE,
        related_name='item_quotes',
        verbose_name='供应商报价'
    )
    rfq_item = models.ForeignKey(
        RFQItem,
        on_delete=models.CASCADE,
        related_name='quotes',
        verbose_name='询价明细'
    )
    
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='单价')
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额')
    
    lead_time_days = models.IntegerField(default=0, verbose_name='交期(天)')
    min_order_qty = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name='最小订货量')
    
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'rfq_item_quote'
        verbose_name = '报价明细'
        verbose_name_plural = verbose_name
    
    def save(self, *args, **kwargs):
        self.amount = self.unit_price * self.rfq_item.quantity
        super().save(*args, **kwargs)


class DeliveryCollaboration(BaseModel):
    """交期协同"""
    purchase_order = models.ForeignKey(
        'purchase.PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='delivery_collaborations',
        verbose_name='采购订单'
    )
    
    # 原始交期
    original_delivery_date = models.DateField(verbose_name='原交期')
    
    # 供应商承诺
    supplier_confirmed_date = models.DateField(null=True, blank=True, verbose_name='供应商确认交期')
    supplier_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    
    # 交期更新
    current_delivery_date = models.DateField(verbose_name='当前交期')
    
    # 变更历史
    change_history = models.JSONField(default=list, blank=True, verbose_name='变更历史')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待确认'),
            ('CONFIRMED', '已确认'),
            ('DELAYED', '已延期'),
            ('DELIVERED', '已交付'),
        ],
        default='PENDING',
        verbose_name='状态'
    )
    
    # 预警
    is_at_risk = models.BooleanField(default=False, verbose_name='交期风险')
    risk_reason = models.CharField(max_length=500, blank=True, verbose_name='风险原因')
    
    class Meta:
        db_table = 'delivery_collaboration'
        verbose_name = '交期协同'
        verbose_name_plural = verbose_name
        ordering = ['current_delivery_date']


class QualityCollaboration(BaseModel):
    """质量协同"""
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.CASCADE,
        related_name='quality_collaborations',
        verbose_name='供应商'
    )
    
    # 关联单据
    purchase_order = models.ForeignKey(
        'purchase.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='采购订单'
    )
    inspection = models.ForeignKey(
        'purchase.OutsourceInspection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='检验记录'
    )
    
    # 问题类型
    issue_type = models.CharField(
        max_length=30,
        choices=[
            ('QUALITY_ISSUE', '质量问题'),
            ('DOCUMENTATION', '文档问题'),
            ('PACKAGING', '包装问题'),
            ('DELIVERY', '交付问题'),
            ('OTHER', '其他'),
        ],
        verbose_name='问题类型'
    )
    
    # 问题描述
    issue_description = models.TextField(verbose_name='问题描述')
    evidence_files = models.JSONField(default=list, blank=True, verbose_name='证据文件')
    
    # 供应商响应
    supplier_response = models.TextField(blank=True, verbose_name='供应商回复')
    response_date = models.DateTimeField(null=True, blank=True, verbose_name='回复时间')
    
    # 纠正措施
    corrective_action = models.TextField(blank=True, verbose_name='纠正措施')
    action_deadline = models.DateField(null=True, blank=True, verbose_name='措施截止日期')
    action_completed = models.BooleanField(default=False, verbose_name='措施完成')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('OPEN', '待处理'),
            ('RESPONDED', '已回复'),
            ('IN_PROGRESS', '处理中'),
            ('CLOSED', '已关闭'),
        ],
        default='OPEN',
        verbose_name='状态'
    )
    
    class Meta:
        db_table = 'quality_collaboration'
        verbose_name = '质量协同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class ReconciliationCollaboration(BaseModel):
    """对账协同"""
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.CASCADE,
        related_name='reconciliations',
        verbose_name='供应商'
    )
    
    # 对账期间
    period_start = models.DateField(verbose_name='开始日期')
    period_end = models.DateField(verbose_name='结束日期')
    
    # 我方数据
    our_order_count = models.IntegerField(default=0, verbose_name='我方订单数')
    our_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='我方金额')
    
    # 供应商数据
    supplier_order_count = models.IntegerField(default=0, verbose_name='供方订单数')
    supplier_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='供方金额')
    
    # 差异
    amount_difference = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额差异')
    difference_items = models.JSONField(default=list, blank=True, verbose_name='差异明细')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', '草稿'),
            ('SENT', '已发送'),
            ('SUPPLIER_CONFIRMED', '供方已确认'),
            ('DISPUTED', '有争议'),
            ('RECONCILED', '已核对'),
        ],
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 确认
    our_confirmed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_reconciliations',
        verbose_name='我方确认人'
    )
    our_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='我方确认时间')
    
    supplier_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='供方确认时间')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'reconciliation_collaboration'
        verbose_name = '对账协同'
        verbose_name_plural = verbose_name
        ordering = ['-period_end']


class SupplierNotification(BaseModel):
    """供应商通知"""
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='供应商'
    )
    
    notification_type = models.CharField(
        max_length=30,
        choices=[
            ('NEW_RFQ', '新询价'),
            ('NEW_ORDER', '新订单'),
            ('DELIVERY_REMINDER', '交期提醒'),
            ('QUALITY_ISSUE', '质量问题'),
            ('RECONCILIATION', '对账通知'),
            ('SYSTEM', '系统通知'),
        ],
        verbose_name='通知类型'
    )
    
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='内容')
    
    # 关联
    related_type = models.CharField(max_length=50, blank=True, verbose_name='关联类型')
    related_id = models.IntegerField(null=True, blank=True, verbose_name='关联ID')
    
    is_read = models.BooleanField(default=False, verbose_name='已读')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='阅读时间')
    
    class Meta:
        db_table = 'supplier_notification'
        verbose_name = '供应商通知'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


# =============================================================================
# 序列化器
# =============================================================================

class SupplierPortalUserSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = SupplierPortalUser
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}


class RFQItemSerializer(serializers.ModelSerializer):
    item_name_display = serializers.CharField(source='item.name', read_only=True)
    
    class Meta:
        model = RFQItem
        fields = '__all__'


class RFQItemQuoteSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='rfq_item.item_name', read_only=True)
    quantity = serializers.DecimalField(source='rfq_item.quantity', max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = RFQItemQuote
        fields = '__all__'
        read_only_fields = ['amount']


class RFQSupplierResponseSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    item_quotes = RFQItemQuoteSerializer(many=True, read_only=True)
    
    class Meta:
        model = RFQSupplierResponse
        fields = '__all__'


class RFQCollaborationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    buyer_name = serializers.CharField(source='buyer.get_full_name', read_only=True)
    items = RFQItemSerializer(many=True, read_only=True)
    responses = RFQSupplierResponseSerializer(many=True, read_only=True)
    
    class Meta:
        model = RFQCollaboration
        fields = '__all__'
        read_only_fields = ['rfq_no']


class RFQCollaborationListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    buyer_name = serializers.CharField(source='buyer.get_full_name', read_only=True)
    item_count = serializers.SerializerMethodField()
    response_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RFQCollaboration
        fields = [
            'id', 'rfq_no', 'title', 'issue_date', 'deadline',
            'status', 'status_display', 'buyer', 'buyer_name',
            'item_count', 'response_count'
        ]
    
    def get_item_count(self, obj):
        return obj.items.count()
    
    def get_response_count(self, obj):
        return obj.responses.filter(status='QUOTED').count()


class DeliveryCollaborationSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='purchase_order.order_no', read_only=True)
    supplier_name = serializers.CharField(source='purchase_order.supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = DeliveryCollaboration
        fields = '__all__'


class QualityCollaborationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = QualityCollaboration
        fields = '__all__'


class ReconciliationCollaborationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ReconciliationCollaboration
        fields = '__all__'


class SupplierNotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = SupplierNotification
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================

class SupplierPortalUserViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """供应商门户用户管理"""
    queryset = SupplierPortalUser.objects.filter(is_deleted=False)
    serializer_class = SupplierPortalUserSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'role', 'is_active']
    search_fields = ['username', 'email']


class RFQCollaborationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """询报价协同管理"""
    queryset = RFQCollaboration.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'buyer', 'project']
    search_fields = ['rfq_no', 'title']
    ordering_fields = ['issue_date', 'deadline']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RFQCollaborationListSerializer
        return RFQCollaborationSerializer
    
    @action(detail=True, methods=['post'])
    def send_to_suppliers(self, request, pk=None):
        """发送给供应商"""
        rfq = self.get_object()
        supplier_ids = request.data.get('supplier_ids', [])
        
        for supplier_id in supplier_ids:
            RFQSupplierResponse.objects.get_or_create(
                rfq=rfq,
                supplier_id=supplier_id,
                defaults={'created_by': request.user}
            )
            
            # 发送通知
            SupplierNotification.objects.create(
                supplier_id=supplier_id,
                notification_type='NEW_RFQ',
                title=f'新询价: {rfq.rfq_no}',
                content=f'您收到一份新的询价单，请登录门户查看并报价。\n询价标题: {rfq.title}\n截止日期: {rfq.deadline}',
                related_type='RFQCollaboration',
                related_id=rfq.id,
                created_by=request.user
            )
        
        rfq.status = 'SENT'
        rfq.save()
        
        return Response({
            'message': f'已发送给 {len(supplier_ids)} 家供应商',
            'rfq': RFQCollaborationSerializer(rfq).data
        })
    
    @action(detail=True, methods=['post'])
    def select_supplier(self, request, pk=None):
        """选定供应商"""
        rfq = self.get_object()
        response_id = request.data.get('response_id')
        
        try:
            response = RFQSupplierResponse.objects.get(id=response_id, rfq=rfq)
        except RFQSupplierResponse.DoesNotExist:
            return Response({'error': '报价不存在'}, status=404)
        
        # 取消其他选择
        rfq.responses.update(is_selected=False)
        
        # 选中
        response.is_selected = True
        response.save()
        
        rfq.status = 'ACCEPTED'
        rfq.save()
        
        return Response({
            'message': f'已选定供应商: {response.supplier.name}',
            'rfq': RFQCollaborationSerializer(rfq).data
        })
    
    @action(detail=True, methods=['get'])
    def compare_quotes(self, request, pk=None):
        """报价比较"""
        rfq = self.get_object()
        
        comparison = []
        for item in rfq.items.all():
            item_data = {
                'item_id': item.id,
                'item_name': item.item_name,
                'quantity': float(item.quantity),
                'target_price': float(item.target_price) if item.target_price else None,
                'quotes': []
            }
            
            for response in rfq.responses.filter(status='QUOTED'):
                quote = response.item_quotes.filter(rfq_item=item).first()
                if quote:
                    item_data['quotes'].append({
                        'supplier_id': response.supplier_id,
                        'supplier_name': response.supplier.name,
                        'unit_price': float(quote.unit_price),
                        'amount': float(quote.amount),
                        'lead_time_days': quote.lead_time_days,
                    })
            
            comparison.append(item_data)
        
        return Response(comparison)


class DeliveryCollaborationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """交期协同管理"""
    queryset = DeliveryCollaboration.objects.filter(is_deleted=False)
    serializer_class = DeliveryCollaborationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'is_at_risk']
    ordering_fields = ['current_delivery_date']
    
    @action(detail=True, methods=['post'])
    def supplier_confirm(self, request, pk=None):
        """供应商确认交期"""
        collab = self.get_object()
        confirmed_date = request.data.get('confirmed_date')
        
        collab.supplier_confirmed_date = confirmed_date
        collab.supplier_confirmed_at = timezone.now()
        collab.status = 'CONFIRMED'
        
        # 记录历史
        collab.change_history.append({
            'date': str(date.today()),
            'action': 'SUPPLIER_CONFIRM',
            'confirmed_date': confirmed_date,
        })
        
        collab.save()
        return Response(DeliveryCollaborationSerializer(collab).data)
    
    @action(detail=True, methods=['post'])
    def update_delivery(self, request, pk=None):
        """更新交期"""
        collab = self.get_object()
        new_date = request.data.get('new_date')
        reason = request.data.get('reason', '')
        
        old_date = collab.current_delivery_date
        collab.current_delivery_date = new_date
        
        if new_date > str(collab.original_delivery_date):
            collab.status = 'DELAYED'
            collab.is_at_risk = True
            collab.risk_reason = reason
        
        # 记录历史
        collab.change_history.append({
            'date': str(date.today()),
            'action': 'UPDATE',
            'old_date': str(old_date),
            'new_date': new_date,
            'reason': reason,
        })
        
        collab.save()
        return Response(DeliveryCollaborationSerializer(collab).data)
    
    @action(detail=False, methods=['get'])
    def at_risk(self, request):
        """风险交期"""
        collabs = self.get_queryset().filter(
            is_at_risk=True,
            status__in=['PENDING', 'CONFIRMED', 'DELAYED']
        )
        return Response(DeliveryCollaborationSerializer(collabs, many=True).data)


class QualityCollaborationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """质量协同管理"""
    queryset = QualityCollaboration.objects.filter(is_deleted=False)
    serializer_class = QualityCollaborationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'issue_type', 'status']
    ordering_fields = ['created_at', 'action_deadline']
    
    @action(detail=True, methods=['post'])
    def supplier_respond(self, request, pk=None):
        """供应商回复"""
        collab = self.get_object()
        collab.supplier_response = request.data.get('response', '')
        collab.response_date = timezone.now()
        collab.status = 'RESPONDED'
        collab.save()
        return Response(QualityCollaborationSerializer(collab).data)
    
    @action(detail=True, methods=['post'])
    def submit_corrective_action(self, request, pk=None):
        """提交纠正措施"""
        collab = self.get_object()
        collab.corrective_action = request.data.get('action', '')
        collab.action_deadline = request.data.get('deadline')
        collab.status = 'IN_PROGRESS'
        collab.save()
        return Response(QualityCollaborationSerializer(collab).data)
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭问题"""
        collab = self.get_object()
        collab.status = 'CLOSED'
        collab.action_completed = True
        collab.save()
        return Response(QualityCollaborationSerializer(collab).data)


class ReconciliationCollaborationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """对账协同管理"""
    queryset = ReconciliationCollaboration.objects.filter(is_deleted=False)
    serializer_class = ReconciliationCollaborationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'status']
    ordering_fields = ['period_end']
    
    @action(detail=True, methods=['post'])
    def send_to_supplier(self, request, pk=None):
        """发送给供应商"""
        recon = self.get_object()
        recon.status = 'SENT'
        recon.save()
        
        # 发送通知
        SupplierNotification.objects.create(
            supplier=recon.supplier,
            notification_type='RECONCILIATION',
            title=f'对账单: {recon.period_start} - {recon.period_end}',
            content=f'请登录门户确认对账单。\n我方金额: ¥{recon.our_amount}',
            related_type='ReconciliationCollaboration',
            related_id=recon.id,
            created_by=request.user
        )
        
        return Response(ReconciliationCollaborationSerializer(recon).data)
    
    @action(detail=True, methods=['post'])
    def supplier_confirm(self, request, pk=None):
        """供应商确认"""
        recon = self.get_object()
        
        recon.supplier_order_count = request.data.get('order_count', 0)
        recon.supplier_amount = Decimal(str(request.data.get('amount', 0)))
        recon.supplier_confirmed_at = timezone.now()
        
        # 计算差异
        recon.amount_difference = recon.our_amount - recon.supplier_amount
        
        if abs(recon.amount_difference) < Decimal('0.01'):
            recon.status = 'SUPPLIER_CONFIRMED'
        else:
            recon.status = 'DISPUTED'
        
        recon.save()
        return Response(ReconciliationCollaborationSerializer(recon).data)
    
    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """确认核对"""
        recon = self.get_object()
        recon.status = 'RECONCILED'
        recon.our_confirmed_by = request.user
        recon.our_confirmed_at = timezone.now()
        recon.save()
        return Response(ReconciliationCollaborationSerializer(recon).data)


class SupplierNotificationViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """供应商通知管理"""
    queryset = SupplierNotification.objects.filter(is_deleted=False)
    serializer_class = SupplierNotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'notification_type', 'is_read']
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """标记已读"""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response(SupplierNotificationSerializer(notification).data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """全部已读"""
        supplier_id = request.data.get('supplier_id')
        if supplier_id:
            self.get_queryset().filter(
                supplier_id=supplier_id, is_read=False
            ).update(is_read=True, read_at=timezone.now())
        return Response({'status': 'ok'})
