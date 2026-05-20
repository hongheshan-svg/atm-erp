"""
办公资产管理
Office Asset Management

功能：办公资产登记、借用、维护、折旧等

非标自动化行业扩展建议：
- 资产类别可增加：测试设备、工装夹具、量检具、专用工具
- 可关联项目：增加project字段，记录资产分配到哪个项目使用
- 与设备管理(equipment)的区别：
  - 此模块：通用办公/生产辅助资产
  - equipment模块：客户项目中交付的设备

建议使用方式：
- 公司内部测试设备、工具等用此模块管理
- 需要追踪项目占用时，可在借用记录中关联项目
"""
from datetime import date, datetime
from decimal import Decimal
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin


class OAAssetCategory(BaseModel):
    """
    办公资产分类
    """
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=20, unique=True, verbose_name='分类编码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='父分类'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    depreciation_years = models.IntegerField(default=5, verbose_name='折旧年限')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'oa_asset_category'
        verbose_name = '办公资产分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name

# Alias for backwards compatibility
AssetCategory = OAAssetCategory


class Asset(BaseModel):
    """
    办公资产
    """
    STATUS_CHOICES = [
        ('IDLE', '闲置'),
        ('IN_USE', '使用中'),
        ('REPAIR', '维修中'),
        ('SCRAPPED', '已报废'),
        ('LOST', '丢失'),
    ]
    
    asset_no = models.CharField(max_length=50, unique=True, verbose_name='资产编号')
    name = models.CharField(max_length=200, verbose_name='资产名称')
    
    category = models.ForeignKey(
        OAAssetCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oa_assets',
        verbose_name='资产分类'
    )
    
    # 基本信息
    brand = models.CharField(max_length=50, blank=True, verbose_name='品牌')
    model = models.CharField(max_length=100, blank=True, verbose_name='型号')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格')
    serial_no = models.CharField(max_length=100, blank=True, verbose_name='序列号')
    
    # 采购信息
    purchase_date = models.DateField(null=True, blank=True, verbose_name='购置日期')
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='购置价格'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oa_supplied_assets',
        verbose_name='供应商'
    )
    warranty_expire_date = models.DateField(null=True, blank=True, verbose_name='保修到期')
    
    # 折旧
    depreciation_method = models.CharField(
        max_length=20,
        default='STRAIGHT',
        verbose_name='折旧方法'
    )
    depreciation_years = models.IntegerField(default=5, verbose_name='折旧年限')
    residual_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5,
        verbose_name='残值率(%)'
    )
    current_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='当前价值'
    )
    
    # 位置
    location = models.CharField(max_length=200, blank=True, verbose_name='存放位置')
    department_name = models.CharField(max_length=100, blank=True, verbose_name='所属部门')
    
    # 使用人
    current_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='using_assets',
        verbose_name='当前使用人'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='IDLE',
        verbose_name='状态'
    )
    
    # 附件和备注
    image = models.CharField(max_length=500, blank=True, verbose_name='图片')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'oa_asset'
        verbose_name = '办公资产'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.asset_no} - {self.name}'
    
    def save(self, *args, **kwargs):
        if not self.asset_no:
            from apps.core.utils import generate_code
            self.asset_no = generate_code('AST')
        if not self.current_value and self.purchase_price:
            self.current_value = self.purchase_price
        super().save(*args, **kwargs)
    
    def calculate_depreciation(self):
        """计算当前折旧值"""
        if not self.purchase_date or not self.purchase_price:
            return self.purchase_price
        
        years = (date.today() - self.purchase_date).days / 365
        if years >= self.depreciation_years:
            return self.purchase_price * self.residual_rate / 100
        
        annual_depreciation = self.purchase_price * (1 - self.residual_rate / 100) / self.depreciation_years
        depreciated = annual_depreciation * Decimal(str(years))
        return max(self.purchase_price - depreciated, self.purchase_price * self.residual_rate / 100)


class AssetBorrow(BaseModel):
    """
    资产借用
    """
    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('BORROWED', '借用中'),
        ('RETURNED', '已归还'),
        ('CANCELLED', '已取消'),
    ]
    
    borrow_no = models.CharField(max_length=50, unique=True, verbose_name='借用单号')
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='borrows',
        verbose_name='资产'
    )
    
    borrower = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='asset_borrows',
        verbose_name='借用人'
    )
    
    borrow_date = models.DateField(verbose_name='借用日期')
    expected_return_date = models.DateField(verbose_name='预计归还日期')
    actual_return_date = models.DateField(null=True, blank=True, verbose_name='实际归还日期')
    
    purpose = models.TextField(verbose_name='借用目的')
    
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
        related_name='approved_asset_borrows',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    # 归还
    return_remarks = models.TextField(blank=True, verbose_name='归还备注')
    return_condition = models.CharField(max_length=200, blank=True, verbose_name='归还状况')
    
    class Meta:
        db_table = 'oa_asset_borrow'
        verbose_name = '资产借用'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.borrow_no} - {self.asset.name}'
    
    def save(self, *args, **kwargs):
        if not self.borrow_no:
            from apps.core.utils import generate_code
            self.borrow_no = generate_code('AB')
        super().save(*args, **kwargs)


class OAAssetTransfer(BaseModel):
    """
    办公资产调拨/转移
    """
    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('REJECTED', '已拒绝'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    transfer_no = models.CharField(max_length=50, unique=True, verbose_name='调拨单号')
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='oa_transfers',
        verbose_name='资产'
    )
    
    # 调出
    from_department_name = models.CharField(max_length=100, blank=True, verbose_name='调出部门')
    from_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oa_asset_transfers_out',
        verbose_name='调出人'
    )
    
    # 调入
    to_department_name = models.CharField(max_length=100, blank=True, verbose_name='调入部门')
    to_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oa_asset_transfers_in',
        verbose_name='调入人'
    )
    
    transfer_date = models.DateField(verbose_name='调拨日期')
    reason = models.TextField(verbose_name='调拨原因')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oa_approved_asset_transfers',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    class Meta:
        db_table = 'oa_asset_transfer'
        verbose_name = '办公资产调拨'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.transfer_no} - {self.asset.name}'
    
    def save(self, *args, **kwargs):
        if not self.transfer_no:
            from apps.core.utils import generate_code
            self.transfer_no = generate_code('OAT')
        super().save(*args, **kwargs)

# Alias for backwards compatibility
AssetTransfer = OAAssetTransfer


class AssetMaintenance(BaseModel):
    """
    资产维修/保养
    """
    MAINTENANCE_TYPES = [
        ('REPAIR', '维修'),
        ('MAINTAIN', '保养'),
        ('UPGRADE', '升级'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('IN_PROGRESS', '处理中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    maintenance_no = models.CharField(max_length=50, unique=True, verbose_name='维修单号')
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name='资产'
    )
    
    maintenance_type = models.CharField(
        max_length=20,
        choices=MAINTENANCE_TYPES,
        default='REPAIR',
        verbose_name='类型'
    )
    
    reporter = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='reported_asset_maintenance',
        verbose_name='报修人'
    )
    
    fault_description = models.TextField(verbose_name='故障描述')
    
    # 处理
    handler = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_asset_maintenance',
        verbose_name='处理人'
    )
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='完成日期')
    result = models.TextField(blank=True, verbose_name='处理结果')
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='费用')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    class Meta:
        db_table = 'oa_asset_maintenance'
        verbose_name = '资产维修'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.maintenance_no} - {self.asset.name}'
    
    def save(self, *args, **kwargs):
        if not self.maintenance_no:
            from apps.core.utils import generate_code
            self.maintenance_no = generate_code('AM')
        super().save(*args, **kwargs)


# =====================
# Serializers
# =====================

class AssetCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = OAAssetCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False)
        return AssetCategorySerializer(children, many=True).data


class AssetSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_user_name = serializers.CharField(source='current_user.get_full_name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
    class Meta:
        model = Asset
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'asset_no']


class AssetListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_user_name = serializers.CharField(source='current_user.get_full_name', read_only=True)
    
    class Meta:
        model = Asset
        fields = [
            'id', 'asset_no', 'name', 'category', 'category_name',
            'brand', 'model', 'status', 'status_display',
            'current_user', 'current_user_name', 'location',
            'purchase_price', 'current_value'
        ]


class AssetBorrowSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    asset_no = serializers.CharField(source='asset.asset_no', read_only=True)
    borrower_name = serializers.CharField(source='borrower.get_full_name', read_only=True)
    approver_name = serializers.CharField(source='approver.get_full_name', read_only=True)
    
    class Meta:
        model = AssetBorrow
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'borrow_no', 'approver', 'approved_at']


class AssetTransferSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    asset_no = serializers.CharField(source='asset.asset_no', read_only=True)
    from_user_name = serializers.CharField(source='from_user.get_full_name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.get_full_name', read_only=True)
    
    class Meta:
        model = OAAssetTransfer
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'transfer_no', 'approver', 'approved_at']


class AssetMaintenanceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    asset_no = serializers.CharField(source='asset.asset_no', read_only=True)
    reporter_name = serializers.CharField(source='reporter.get_full_name', read_only=True)
    handler_name = serializers.CharField(source='handler.get_full_name', read_only=True)
    
    class Meta:
        model = AssetMaintenance
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'maintenance_no']


# =====================
# ViewSets
# =====================

class AssetCategoryViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'oa'
    permission_resource = 'asset_category'
    """办公资产分类管理"""
    queryset = OAAssetCategory.objects.filter(is_deleted=False)
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['parent']
    search_fields = ['name', 'code']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取分类树"""
        roots = self.get_queryset().filter(parent__isnull=True)
        return Response(AssetCategorySerializer(roots, many=True).data)


class AssetViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'oa'
    permission_resource = 'asset'
    """办公资产管理"""
    queryset = Asset.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'category', 'current_user']
    search_fields = ['asset_no', 'name', 'brand', 'model', 'serial_no', 'department_name']
    ordering_fields = ['asset_no', 'purchase_date', 'purchase_price', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return AssetListSerializer
        return AssetSerializer
    
    @action(detail=False, methods=['get'])
    def idle(self, request):
        """获取闲置资产"""
        assets = self.get_queryset().filter(status='IDLE')
        return Response(AssetListSerializer(assets, many=True).data)
    
    @action(detail=False, methods=['get'])
    def my_assets(self, request):
        """我的资产"""
        assets = self.get_queryset().filter(current_user=request.user)
        return Response(AssetListSerializer(assets, many=True).data)
    
    @action(detail=False, methods=['get'])
    def warranty_expiring(self, request):
        """即将过保的资产"""
        today = date.today()
        next_month = today.replace(month=today.month + 1) if today.month < 12 else today.replace(year=today.year + 1, month=1)
        
        assets = self.get_queryset().filter(
            warranty_expire_date__gte=today,
            warranty_expire_date__lte=next_month
        )
        return Response(AssetListSerializer(assets, many=True).data)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分配资产给用户"""
        asset = self.get_object()
        user_id = request.data.get('user_id')
        
        from apps.accounts.models import User
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=400)
        
        asset.current_user = user
        asset.status = 'IN_USE'
        asset.save()
        
        return Response(self.get_serializer(asset).data)
    
    @action(detail=True, methods=['post'])
    def reclaim(self, request, pk=None):
        """回收资产"""
        asset = self.get_object()
        asset.current_user = None
        asset.status = 'IDLE'
        asset.save()
        
        return Response(self.get_serializer(asset).data)
    
    @action(detail=True, methods=['post'])
    def scrap(self, request, pk=None):
        """报废资产"""
        asset = self.get_object()
        asset.status = 'SCRAPPED'
        asset.current_value = 0
        asset.save()
        
        return Response(self.get_serializer(asset).data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """资产统计"""
        from django.db.models import Sum, Count
        
        qs = self.get_queryset()
        
        by_status = qs.values('status').annotate(
            count=Count('id'),
            total_value=Sum('current_value')
        )
        
        by_category = qs.values('category__name').annotate(
            count=Count('id'),
            total_value=Sum('current_value')
        )
        
        total_count = qs.count()
        total_value = qs.aggregate(total=Sum('current_value'))['total'] or 0
        total_purchase = qs.aggregate(total=Sum('purchase_price'))['total'] or 0
        
        return Response({
            'total_count': total_count,
            'total_current_value': float(total_value),
            'total_purchase_value': float(total_purchase),
            'depreciation': float(total_purchase - total_value),
            'by_status': list(by_status),
            'by_category': list(by_category)
        })


class AssetBorrowViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'oa'
    permission_resource = 'asset_borrow'
    """资产借用管理"""
    queryset = AssetBorrow.objects.filter(is_deleted=False)
    serializer_class = AssetBorrowSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'asset', 'borrower']
    search_fields = ['borrow_no', 'purpose']
    ordering_fields = ['borrow_date', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(borrower=self.request.user, created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_borrows(self, request):
        """我的借用"""
        borrows = self.get_queryset().filter(borrower=request.user)
        return Response(self.get_serializer(borrows, many=True).data)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交申请 - 走流程配置的审批流程"""
        borrow = self.get_object()
        if borrow.status not in ['PENDING', 'REJECTED']:
            return Response({'error': '只能提交待审批或已拒绝状态的申请'}, status=400)
        
        try:
            from apps.core.workflow.services import WorkflowService
            
            instance, error = WorkflowService.start_workflow(
                business_type='ASSET_BORROW',
                business_id=borrow.id,
                business_no=borrow.borrow_no or f'AB-{borrow.id}',
                submitter=request.user,
                amount=None
            )
            
            if instance:
                borrow.status = 'PENDING'
                borrow.save()
                return Response({
                    **self.get_serializer(borrow).data,
                    'workflow_started': True,
                    'workflow_id': instance.id,
                    'message': '已提交审批，请在审批中心查看审批进度'
                })
            else:
                borrow.status = 'PENDING'
                borrow.save()
                return Response({
                    **self.get_serializer(borrow).data,
                    'workflow_started': False,
                    'message': error or '未配置审批流程，请等待人工审批'
                })
                
        except Exception as e:
            borrow.status = 'PENDING'
            borrow.save()
            return Response({
                **self.get_serializer(borrow).data,
                'workflow_started': False,
                'message': f'已提交，但工作流服务异常: {e}'
            })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过（手动审批，用于未配置流程时）"""
        borrow = self.get_object()
        if borrow.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        borrow.status = 'APPROVED'
        borrow.approver = request.user
        borrow.approved_at = timezone.now()
        borrow.save()
        
        return Response(self.get_serializer(borrow).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审批拒绝"""
        borrow = self.get_object()
        if borrow.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        borrow.status = 'REJECTED'
        borrow.approver = request.user
        borrow.approved_at = timezone.now()
        borrow.save()
        
        return Response(self.get_serializer(borrow).data)
    
    @action(detail=True, methods=['post'])
    def borrow(self, request, pk=None):
        """确认借出"""
        borrow = self.get_object()
        if borrow.status != 'APPROVED':
            return Response({'error': '只有已批准的申请可以借出'}, status=400)

        from django.db import transaction
        with transaction.atomic():
            borrow.status = 'BORROWED'
            borrow.save()

            borrow.asset.status = 'IN_USE'
            borrow.asset.current_user = borrow.borrower
            borrow.asset.save(update_fields=['status', 'current_user'])

        return Response(self.get_serializer(borrow).data)

    @action(detail=True, methods=['post'])
    def return_asset(self, request, pk=None):
        """归还资产"""
        borrow = self.get_object()
        if borrow.status != 'BORROWED':
            return Response({'error': '只有借用中的资产可以归还'}, status=400)

        from django.db import transaction
        with transaction.atomic():
            borrow.status = 'RETURNED'
            borrow.actual_return_date = date.today()
            borrow.return_remarks = request.data.get('remarks', '')
            borrow.return_condition = request.data.get('condition', '完好')
            borrow.save()

            borrow.asset.status = 'IDLE'
            borrow.asset.current_user = None
            borrow.asset.save(update_fields=['status', 'current_user'])

        return Response(self.get_serializer(borrow).data)


class AssetTransferViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'oa'
    permission_resource = 'asset_transfer'
    """办公资产调拨管理"""
    queryset = OAAssetTransfer.objects.filter(is_deleted=False)
    serializer_class = AssetTransferSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'asset']
    search_fields = ['transfer_no', 'reason']
    ordering_fields = ['transfer_date', 'created_at']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过"""
        transfer = self.get_object()
        if transfer.status != 'PENDING':
            return Response({'error': '只能审批待审批的申请'}, status=400)
        
        transfer.status = 'APPROVED'
        transfer.approver = request.user
        transfer.approved_at = timezone.now()
        transfer.save()
        
        return Response(self.get_serializer(transfer).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成调拨"""
        transfer = self.get_object()
        if transfer.status != 'APPROVED':
            return Response({'error': '只有已审批的调拨可以完成'}, status=400)

        from django.db import transaction
        with transaction.atomic():
            transfer.status = 'COMPLETED'
            transfer.save()

            transfer.asset.department_name = transfer.to_department_name
            transfer.asset.current_user = transfer.to_user
            transfer.asset.save(update_fields=['department_name', 'current_user'])

        return Response(self.get_serializer(transfer).data)


class AssetMaintenanceViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'oa'
    permission_resource = 'asset_maintenance'
    """资产维修管理"""
    queryset = AssetMaintenance.objects.filter(is_deleted=False)
    serializer_class = AssetMaintenanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'asset', 'maintenance_type', 'handler']
    search_fields = ['maintenance_no', 'fault_description']
    ordering_fields = ['created_at', 'start_date']
    
    def perform_create(self, serializer):
        from django.db import transaction
        with transaction.atomic():
            maintenance = serializer.save(reporter=self.request.user, created_by=self.request.user)
            maintenance.asset.status = 'REPAIR'
            maintenance.asset.save(update_fields=['status'])
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """指派处理人"""
        maintenance = self.get_object()
        handler_id = request.data.get('handler_id')
        
        from apps.accounts.models import User
        try:
            handler = User.objects.get(id=handler_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=400)
        
        maintenance.handler = handler
        maintenance.status = 'IN_PROGRESS'
        maintenance.start_date = date.today()
        maintenance.save()
        
        return Response(self.get_serializer(maintenance).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成维修"""
        maintenance = self.get_object()

        from django.db import transaction
        with transaction.atomic():
            maintenance.status = 'COMPLETED'
            maintenance.end_date = date.today()
            maintenance.result = request.data.get('result', '')
            maintenance.cost = request.data.get('cost', 0)
            maintenance.save()

            maintenance.asset.status = 'IN_USE' if maintenance.asset.current_user else 'IDLE'
            maintenance.asset.save(update_fields=['status'])

        return Response(self.get_serializer(maintenance).data)
