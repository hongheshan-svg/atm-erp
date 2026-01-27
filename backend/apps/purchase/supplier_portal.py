"""
供应商协同门户模块
Supplier Portal - 在线接单、进度更新、质量追溯
"""
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import serializers
import secrets

from apps.core.models import BaseModel
from django.conf import settings

User = settings.AUTH_USER_MODEL


class SupplierAccount(BaseModel):
    """供应商账户"""
    supplier = models.OneToOneField('masterdata.Supplier', on_delete=models.CASCADE,
                                    related_name='portal_account', verbose_name='供应商')
    
    username = models.CharField('用户名', max_length=100, unique=True)
    password_hash = models.CharField('密码', max_length=255)
    email = models.EmailField('邮箱', blank=True)
    mobile = models.CharField('手机', max_length=20, blank=True)
    
    is_active = models.BooleanField('是否激活', default=True)
    last_login = models.DateTimeField('最后登录', null=True, blank=True)
    
    # 权限
    can_view_orders = models.BooleanField('查看订单', default=True)
    can_confirm_orders = models.BooleanField('确认订单', default=True)
    can_update_progress = models.BooleanField('更新进度', default=True)
    can_upload_documents = models.BooleanField('上传文档', default=True)
    can_view_quality = models.BooleanField('查看质量', default=True)
    
    class Meta:
        db_table = 'supplier_account'
        verbose_name = '供应商账户'
    
    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)
    
    def generate_token(self):
        return secrets.token_urlsafe(32)


class SupplierOrderView(BaseModel):
    """供应商订单视图（供应商可见的订单信息）"""
    purchase_order = models.ForeignKey('purchase.PurchaseOrder', on_delete=models.CASCADE,
                                       related_name='supplier_views', verbose_name='采购订单')
    supplier = models.ForeignKey('masterdata.Supplier', on_delete=models.CASCADE,
                                related_name='order_views', verbose_name='供应商')
    
    # 供应商确认
    confirmed = models.BooleanField('已确认', default=False)
    confirmed_at = models.DateTimeField('确认时间', null=True, blank=True)
    confirmed_delivery_date = models.DateField('确认交期', null=True, blank=True)
    rejection_reason = models.TextField('拒绝原因', blank=True)
    
    # 进度
    PROGRESS_CHOICES = [
        ('PENDING', '待处理'),
        ('CONFIRMED', '已确认'),
        ('PRODUCING', '生产中'),
        ('QUALITY_CHECK', '质检中'),
        ('READY', '待发货'),
        ('SHIPPED', '已发货'),
        ('DELIVERED', '已送达'),
    ]
    progress_status = models.CharField('进度状态', max_length=20, choices=PROGRESS_CHOICES, default='PENDING')
    progress_percentage = models.IntegerField('进度百分比', default=0)
    progress_remarks = models.TextField('进度说明', blank=True)
    last_update = models.DateTimeField('最后更新', auto_now=True)
    
    class Meta:
        db_table = 'supplier_order_view'
        verbose_name = '供应商订单视图'
        unique_together = ['purchase_order', 'supplier']


class SupplierProgressUpdate(BaseModel):
    """供应商进度更新记录"""
    order_view = models.ForeignKey(SupplierOrderView, on_delete=models.CASCADE,
                                  related_name='progress_updates', verbose_name='订单视图')
    
    progress_status = models.CharField('进度状态', max_length=20)
    progress_percentage = models.IntegerField('进度百分比')
    remarks = models.TextField('说明', blank=True)
    
    # 附件
    attachments = models.JSONField('附件', default=list)
    
    updated_by_supplier = models.BooleanField('供应商更新', default=True)
    
    class Meta:
        db_table = 'supplier_progress_update'
        verbose_name = '供应商进度更新'
        ordering = ['-created_at']


class SupplierDocument(BaseModel):
    """供应商文档"""
    DOC_TYPE_CHOICES = [
        ('QUALITY_CERT', '质量证书'),
        ('INSPECTION_REPORT', '检验报告'),
        ('DELIVERY_NOTE', '送货单'),
        ('INVOICE', '发票'),
        ('COC', '合格证'),
        ('OTHER', '其他'),
    ]
    
    supplier = models.ForeignKey('masterdata.Supplier', on_delete=models.CASCADE,
                                related_name='portal_documents', verbose_name='供应商')
    purchase_order = models.ForeignKey('purchase.PurchaseOrder', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='supplier_documents',
                                       verbose_name='采购订单')
    
    doc_type = models.CharField('文档类型', max_length=20, choices=DOC_TYPE_CHOICES)
    title = models.CharField('标题', max_length=200)
    file_path = models.CharField('文件路径', max_length=500)
    file_size = models.IntegerField('文件大小', default=0)
    
    # 审核
    reviewed = models.BooleanField('已审核', default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='reviewed_supplier_docs', verbose_name='审核人')
    reviewed_at = models.DateTimeField('审核时间', null=True, blank=True)
    review_remarks = models.TextField('审核意见', blank=True)
    
    class Meta:
        db_table = 'supplier_document'
        verbose_name = '供应商文档'


class SupplierQualityRecord(BaseModel):
    """供应商质量记录"""
    supplier = models.ForeignKey('masterdata.Supplier', on_delete=models.CASCADE,
                                related_name='quality_records', verbose_name='供应商')
    purchase_order = models.ForeignKey('purchase.PurchaseOrder', on_delete=models.CASCADE,
                                       related_name='quality_records', verbose_name='采购订单')
    purchase_line = models.ForeignKey('purchase.PurchaseOrderLine', on_delete=models.CASCADE,
                                      related_name='quality_records', verbose_name='采购行')
    
    # 检验信息
    inspection_date = models.DateField('检验日期')
    inspected_qty = models.DecimalField('检验数量', max_digits=14, decimal_places=4)
    qualified_qty = models.DecimalField('合格数量', max_digits=14, decimal_places=4)
    rejected_qty = models.DecimalField('不合格数量', max_digits=14, decimal_places=4, default=0)
    
    # 结果
    RESULT_CHOICES = [
        ('PASS', '合格'),
        ('FAIL', '不合格'),
        ('CONDITIONAL', '让步接收'),
    ]
    result = models.CharField('检验结果', max_length=20, choices=RESULT_CHOICES)
    
    # 不合格描述
    defect_description = models.TextField('缺陷描述', blank=True)
    defect_photos = models.JSONField('缺陷照片', default=list)
    
    # 处理
    corrective_action = models.TextField('纠正措施', blank=True)
    supplier_response = models.TextField('供应商回复', blank=True)
    
    class Meta:
        db_table = 'supplier_quality_record'
        verbose_name = '供应商质量记录'


class SupplierMessage(BaseModel):
    """供应商消息"""
    supplier = models.ForeignKey('masterdata.Supplier', on_delete=models.CASCADE,
                                related_name='portal_messages', verbose_name='供应商')
    purchase_order = models.ForeignKey('purchase.PurchaseOrder', on_delete=models.SET_NULL,
                                       null=True, blank=True, verbose_name='采购订单')
    
    subject = models.CharField('主题', max_length=200)
    content = models.TextField('内容')
    
    # 发送方
    from_supplier = models.BooleanField('来自供应商', default=False)
    from_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='supplier_messages', verbose_name='发送人')
    
    # 状态
    is_read = models.BooleanField('已读', default=False)
    read_at = models.DateTimeField('阅读时间', null=True, blank=True)
    
    class Meta:
        db_table = 'supplier_message'
        verbose_name = '供应商消息'
        ordering = ['-created_at']


# ==================== Serializers ====================

class SupplierAccountSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
    class Meta:
        model = SupplierAccount
        exclude = ['password_hash']


class SupplierOrderViewSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='purchase_order.order_no', read_only=True)
    order_date = serializers.DateField(source='purchase_order.order_date', read_only=True)
    expected_date = serializers.DateField(source='purchase_order.expected_date', read_only=True)
    total_amount = serializers.DecimalField(source='purchase_order.total_amount', 
                                           max_digits=14, decimal_places=2, read_only=True)
    progress_status_display = serializers.CharField(source='get_progress_status_display', read_only=True)
    
    class Meta:
        model = SupplierOrderView
        fields = '__all__'


class SupplierProgressUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierProgressUpdate
        fields = '__all__'


class SupplierDocumentSerializer(serializers.ModelSerializer):
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)
    
    class Meta:
        model = SupplierDocument
        fields = '__all__'


class SupplierQualityRecordSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='purchase_line.item.name', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    pass_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = SupplierQualityRecord
        fields = '__all__'
    
    def get_pass_rate(self, obj):
        if obj.inspected_qty > 0:
            return round(float(obj.qualified_qty / obj.inspected_qty * 100), 1)
        return 0


class SupplierMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierMessage
        fields = '__all__'


# ==================== ViewSets ====================

class SupplierAccountViewSet(viewsets.ModelViewSet):
    """供应商账户管理（内部管理）"""
    queryset = SupplierAccount.objects.filter(is_deleted=False)
    serializer_class = SupplierAccountSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """重置密码"""
        account = self.get_object()
        new_password = request.data.get('password', secrets.token_urlsafe(8))
        account.set_password(new_password)
        account.save()
        return Response({'message': '密码已重置', 'new_password': new_password})
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """启用/禁用"""
        account = self.get_object()
        account.is_active = not account.is_active
        account.save()
        return Response({'is_active': account.is_active})


class SupplierOrderViewViewSet(viewsets.ModelViewSet):
    """供应商订单视图管理"""
    queryset = SupplierOrderView.objects.filter(is_deleted=False)
    serializer_class = SupplierOrderViewSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        supplier = self.request.query_params.get('supplier')
        status_filter = self.request.query_params.get('status')
        
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        if status_filter:
            qs = qs.filter(progress_status=status_filter)
        
        return qs.select_related('purchase_order', 'supplier')


class SupplierQualityRecordViewSet(viewsets.ModelViewSet):
    """供应商质量记录管理"""
    queryset = SupplierQualityRecord.objects.filter(is_deleted=False)
    serializer_class = SupplierQualityRecordSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = super().get_queryset()
        supplier = self.request.query_params.get('supplier')
        if supplier:
            qs = qs.filter(supplier_id=supplier)
        return qs


# ==================== 供应商门户API ====================

class SupplierPortalLoginView(APIView):
    """供应商登录"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        try:
            account = SupplierAccount.objects.get(username=username, is_active=True)
        except SupplierAccount.DoesNotExist:
            return Response({'error': '用户名或密码错误'}, status=401)
        
        if not account.check_password(password):
            return Response({'error': '用户名或密码错误'}, status=401)
        
        account.last_login = timezone.now()
        account.save()
        
        token = account.generate_token()
        
        return Response({
            'token': token,
            'supplier_id': account.supplier_id,
            'supplier_name': account.supplier.name,
            'permissions': {
                'can_view_orders': account.can_view_orders,
                'can_confirm_orders': account.can_confirm_orders,
                'can_update_progress': account.can_update_progress,
                'can_upload_documents': account.can_upload_documents,
                'can_view_quality': account.can_view_quality,
            }
        })


class SupplierPortalOrdersView(APIView):
    """供应商订单列表（门户）"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, supplier_id):
        status_filter = request.query_params.get('status')
        
        qs = SupplierOrderView.objects.filter(
            supplier_id=supplier_id,
            is_deleted=False
        ).select_related('purchase_order')
        
        if status_filter:
            qs = qs.filter(progress_status=status_filter)
        
        orders = []
        for view in qs:
            po = view.purchase_order
            orders.append({
                'id': view.id,
                'order_no': po.order_no,
                'order_date': po.order_date,
                'expected_date': po.expected_date,
                'total_amount': float(po.total_amount),
                'confirmed': view.confirmed,
                'progress_status': view.progress_status,
                'progress_percentage': view.progress_percentage,
                'last_update': view.last_update,
            })
        
        return Response(orders)


class SupplierPortalOrderDetailView(APIView):
    """供应商订单详情（门户）"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, supplier_id, order_view_id):
        try:
            view = SupplierOrderView.objects.get(
                pk=order_view_id,
                supplier_id=supplier_id,
                is_deleted=False
            )
        except SupplierOrderView.DoesNotExist:
            return Response({'error': '订单不存在'}, status=404)
        
        po = view.purchase_order
        
        # 订单行
        lines = []
        for line in po.lines.filter(is_deleted=False):
            lines.append({
                'id': line.id,
                'item_code': line.item.sku if line.item else '',
                'item_name': line.item.name if line.item else '',
                'specification': line.specification,
                'quantity': float(line.quantity),
                'unit': line.unit,
                'unit_price': float(line.unit_price),
                'amount': float(line.amount),
                'expected_date': line.expected_date,
            })
        
        # 进度更新记录
        updates = SupplierProgressUpdateSerializer(
            view.progress_updates.all()[:20], many=True
        ).data
        
        return Response({
            'order': {
                'order_no': po.order_no,
                'order_date': po.order_date,
                'expected_date': po.expected_date,
                'total_amount': float(po.total_amount),
                'remarks': po.remarks,
            },
            'confirmation': {
                'confirmed': view.confirmed,
                'confirmed_at': view.confirmed_at,
                'confirmed_delivery_date': view.confirmed_delivery_date,
            },
            'progress': {
                'status': view.progress_status,
                'percentage': view.progress_percentage,
                'remarks': view.progress_remarks,
            },
            'lines': lines,
            'updates': updates,
        })
    
    def post(self, request, supplier_id, order_view_id):
        """更新订单（确认或更新进度）"""
        try:
            view = SupplierOrderView.objects.get(
                pk=order_view_id,
                supplier_id=supplier_id,
                is_deleted=False
            )
        except SupplierOrderView.DoesNotExist:
            return Response({'error': '订单不存在'}, status=404)
        
        action = request.data.get('action')
        
        if action == 'confirm':
            # 确认订单
            view.confirmed = True
            view.confirmed_at = timezone.now()
            view.confirmed_delivery_date = request.data.get('delivery_date')
            view.progress_status = 'CONFIRMED'
            view.save()
            
            return Response({'message': '订单已确认'})
        
        elif action == 'reject':
            # 拒绝订单
            view.confirmed = False
            view.rejection_reason = request.data.get('reason', '')
            view.save()
            
            return Response({'message': '已拒绝订单'})
        
        elif action == 'update_progress':
            # 更新进度
            new_status = request.data.get('status')
            new_percentage = request.data.get('percentage', view.progress_percentage)
            remarks = request.data.get('remarks', '')
            
            view.progress_status = new_status
            view.progress_percentage = new_percentage
            view.progress_remarks = remarks
            view.save()
            
            # 记录更新
            SupplierProgressUpdate.objects.create(
                order_view=view,
                progress_status=new_status,
                progress_percentage=new_percentage,
                remarks=remarks,
                created_by=request.user,
                updated_by=request.user
            )
            
            return Response({'message': '进度已更新'})
        
        return Response({'error': '无效操作'}, status=400)


class SupplierPortalQualityView(APIView):
    """供应商质量记录（门户）"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, supplier_id):
        records = SupplierQualityRecord.objects.filter(
            supplier_id=supplier_id,
            is_deleted=False
        ).select_related('purchase_order', 'purchase_line__item').order_by('-inspection_date')[:50]
        
        # 统计
        total = records.count()
        passed = records.filter(result='PASS').count()
        pass_rate = round(passed / total * 100, 1) if total > 0 else 100
        
        return Response({
            'summary': {
                'total_inspections': total,
                'passed': passed,
                'pass_rate': pass_rate,
            },
            'records': SupplierQualityRecordSerializer(records, many=True).data
        })
    
    def post(self, request, supplier_id):
        """供应商回复质量问题"""
        record_id = request.data.get('record_id')
        response_text = request.data.get('response')
        
        try:
            record = SupplierQualityRecord.objects.get(
                pk=record_id,
                supplier_id=supplier_id
            )
        except SupplierQualityRecord.DoesNotExist:
            return Response({'error': '记录不存在'}, status=404)
        
        record.supplier_response = response_text
        record.save()
        
        return Response({'message': '回复已提交'})


class SupplierPortalMessagesView(APIView):
    """供应商消息（门户）"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, supplier_id):
        messages = SupplierMessage.objects.filter(
            supplier_id=supplier_id,
            is_deleted=False
        ).order_by('-created_at')[:50]
        
        unread_count = messages.filter(is_read=False, from_supplier=False).count()
        
        return Response({
            'unread_count': unread_count,
            'messages': SupplierMessageSerializer(messages, many=True).data
        })
    
    def post(self, request, supplier_id):
        """发送消息"""
        SupplierMessage.objects.create(
            supplier_id=supplier_id,
            purchase_order_id=request.data.get('order_id'),
            subject=request.data.get('subject'),
            content=request.data.get('content'),
            from_supplier=True,
            created_by=request.user,
            updated_by=request.user
        )
        
        return Response({'message': '消息已发送'})


class SupplierDashboardView(APIView):
    """供应商协同看板（内部）"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # 统计数据
        pending_confirmation = SupplierOrderView.objects.filter(
            confirmed=False,
            progress_status='PENDING',
            is_deleted=False
        ).count()
        
        in_progress = SupplierOrderView.objects.filter(
            progress_status__in=['CONFIRMED', 'PRODUCING', 'QUALITY_CHECK'],
            is_deleted=False
        ).count()
        
        ready_to_ship = SupplierOrderView.objects.filter(
            progress_status='READY',
            is_deleted=False
        ).count()
        
        # 逾期订单
        today = timezone.now().date()
        overdue = SupplierOrderView.objects.filter(
            progress_status__in=['PENDING', 'CONFIRMED', 'PRODUCING'],
            purchase_order__expected_date__lt=today,
            is_deleted=False
        ).count()
        
        # 质量问题
        quality_issues = SupplierQualityRecord.objects.filter(
            result='FAIL',
            supplier_response='',
            is_deleted=False
        ).count()
        
        # 未读消息
        unread_messages = SupplierMessage.objects.filter(
            from_supplier=True,
            is_read=False,
            is_deleted=False
        ).count()
        
        return Response({
            'pending_confirmation': pending_confirmation,
            'in_progress': in_progress,
            'ready_to_ship': ready_to_ship,
            'overdue': overdue,
            'quality_issues': quality_issues,
            'unread_messages': unread_messages,
        })
