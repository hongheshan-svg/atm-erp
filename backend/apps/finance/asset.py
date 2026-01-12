"""
固定资产管理模块
Fixed Asset Management
ERP财务管理功能
"""
from datetime import date, datetime
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class AssetCategory(BaseModel):
    """资产分类"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类编码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级分类'
    )
    
    # 折旧配置
    depreciation_method = models.CharField(
        max_length=20,
        choices=[
            ('STRAIGHT', '直线法'),
            ('DECLINING', '余额递减法'),
            ('SUM_OF_YEARS', '年数总和法'),
        ],
        default='STRAIGHT',
        verbose_name='折旧方法'
    )
    useful_life_years = models.IntegerField(default=5, verbose_name='使用年限(年)')
    residual_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5,
        verbose_name='残值率(%)'
    )
    
    description = models.TextField(blank=True, verbose_name='描述')
    
    class Meta:
        db_table = 'erp_asset_category'
        verbose_name = '资产分类'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f'{self.code} - {self.name}'


class FixedAsset(BaseModel):
    """固定资产"""
    STATUS_CHOICES = [
        ('IDLE', '闲置'),
        ('IN_USE', '使用中'),
        ('MAINTENANCE', '维修中'),
        ('SCRAPPED', '已报废'),
        ('SOLD', '已变卖'),
    ]
    
    asset_no = models.CharField(max_length=50, unique=True, verbose_name='资产编号')
    name = models.CharField(max_length=200, verbose_name='资产名称')
    
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
        verbose_name='资产分类'
    )
    
    # 规格信息
    model = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    manufacturer = models.CharField(max_length=100, blank=True, verbose_name='制造商')
    serial_no = models.CharField(max_length=100, blank=True, verbose_name='出厂编号')
    
    # 财务信息
    purchase_date = models.DateField(null=True, blank=True, verbose_name='购置日期')
    purchase_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='购置价格'
    )
    original_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='原值'
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='累计折旧'
    )
    net_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='净值'
    )
    residual_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='残值'
    )
    
    # 折旧信息
    depreciation_method = models.CharField(
        max_length=20,
        choices=[
            ('STRAIGHT', '直线法'),
            ('DECLINING', '余额递减法'),
            ('SUM_OF_YEARS', '年数总和法'),
        ],
        default='STRAIGHT',
        verbose_name='折旧方法'
    )
    useful_life_months = models.IntegerField(default=60, verbose_name='使用年限(月)')
    start_depreciation_date = models.DateField(null=True, blank=True, verbose_name='开始折旧日期')
    monthly_depreciation = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='月折旧额'
    )
    
    # 使用信息
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='IDLE',
        verbose_name='状态'
    )
    location = models.CharField(max_length=200, blank=True, verbose_name='存放地点')
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
        verbose_name='使用部门'
    )
    custodian = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custodian_assets',
        verbose_name='保管人'
    )
    
    # 供应商
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplied_assets',
        verbose_name='供应商'
    )
    
    # 关联项目
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
        verbose_name='项目'
    )
    
    warranty_end_date = models.DateField(null=True, blank=True, verbose_name='保修到期')
    disposal_date = models.DateField(null=True, blank=True, verbose_name='处置日期')
    disposal_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='处置金额'
    )
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'erp_fixed_asset'
        verbose_name = '固定资产'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.asset_no} - {self.name}'
    
    def save(self, *args, **kwargs):
        if not self.asset_no:
            from apps.core.utils import generate_code
            self.asset_no = generate_code('FA')
        
        # 计算净值
        self.net_value = self.original_value - self.accumulated_depreciation
        
        # 计算月折旧额
        if self.useful_life_months > 0 and self.original_value > 0:
            depreciable_value = self.original_value - self.residual_value
            self.monthly_depreciation = depreciable_value / self.useful_life_months
        
        super().save(*args, **kwargs)
    
    def calculate_depreciation(self, year, month):
        """计算指定月份的折旧额"""
        if self.depreciation_method == 'STRAIGHT':
            return self.monthly_depreciation
        elif self.depreciation_method == 'DECLINING':
            # 余额递减法: 净值 × 2/使用年限
            rate = Decimal('2') / Decimal(self.useful_life_months / 12)
            return self.net_value * rate / Decimal('12')
        else:
            return self.monthly_depreciation


class AssetDepreciation(BaseModel):
    """资产折旧记录"""
    asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name='depreciations',
        verbose_name='资产'
    )
    
    year = models.IntegerField(verbose_name='年份')
    month = models.IntegerField(verbose_name='月份')
    
    # 期初值
    opening_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期初净值')
    
    # 折旧
    depreciation_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='折旧金额')
    
    # 期末值
    closing_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期末净值')
    
    # 累计
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='累计折旧')
    
    is_posted = models.BooleanField(default=False, verbose_name='已过账')
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='过账时间')
    
    class Meta:
        db_table = 'erp_asset_depreciation'
        verbose_name = '资产折旧'
        verbose_name_plural = verbose_name
        unique_together = ['asset', 'year', 'month']
        ordering = ['-year', '-month']


class AssetTransfer(BaseModel):
    """资产转移"""
    asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name='transfers',
        verbose_name='资产'
    )
    
    transfer_date = models.DateField(default=date.today, verbose_name='转移日期')
    
    # 原信息
    from_department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_transfers_out',
        verbose_name='原部门'
    )
    from_custodian = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_transfers_out',
        verbose_name='原保管人'
    )
    from_location = models.CharField(max_length=200, blank=True, verbose_name='原存放地点')
    
    # 新信息
    to_department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_transfers_in',
        verbose_name='新部门'
    )
    to_custodian = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_transfers_in',
        verbose_name='新保管人'
    )
    to_location = models.CharField(max_length=200, blank=True, verbose_name='新存放地点')
    
    reason = models.TextField(blank=True, verbose_name='转移原因')
    
    class Meta:
        db_table = 'erp_asset_transfer'
        verbose_name = '资产转移'
        verbose_name_plural = verbose_name
        ordering = ['-transfer_date']


class AssetDisposal(BaseModel):
    """资产处置"""
    DISPOSAL_TYPES = [
        ('SCRAP', '报废'),
        ('SELL', '变卖'),
        ('DONATE', '捐赠'),
        ('LOSS', '损失'),
    ]
    
    asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name='disposals',
        verbose_name='资产'
    )
    
    disposal_type = models.CharField(
        max_length=20,
        choices=DISPOSAL_TYPES,
        verbose_name='处置类型'
    )
    disposal_date = models.DateField(default=date.today, verbose_name='处置日期')
    
    # 金额
    disposal_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='处置收入')
    net_book_value = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='账面净值')
    gain_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='处置损益')
    
    reason = models.TextField(blank=True, verbose_name='处置原因')
    approval_no = models.CharField(max_length=50, blank=True, verbose_name='审批单号')
    
    class Meta:
        db_table = 'erp_asset_disposal'
        verbose_name = '资产处置'
        verbose_name_plural = verbose_name
        ordering = ['-disposal_date']


# =====================
# Serializers
# =====================

class AssetCategorySerializer(serializers.ModelSerializer):
    depreciation_method_display = serializers.CharField(source='get_depreciation_method_display', read_only=True)
    
    class Meta:
        model = AssetCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AssetDepreciationSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    
    class Meta:
        model = AssetDepreciation
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AssetTransferSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    from_department_name = serializers.CharField(source='from_department.name', read_only=True)
    to_department_name = serializers.CharField(source='to_department.name', read_only=True)
    
    class Meta:
        model = AssetTransfer
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AssetDisposalSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    disposal_type_display = serializers.CharField(source='get_disposal_type_display', read_only=True)
    
    class Meta:
        model = AssetDisposal
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class FixedAssetSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    depreciation_method_display = serializers.CharField(source='get_depreciation_method_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    custodian_name = serializers.CharField(source='custodian.get_full_name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    depreciations = AssetDepreciationSerializer(many=True, read_only=True)
    transfers = AssetTransferSerializer(many=True, read_only=True)
    
    class Meta:
        model = FixedAsset
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'asset_no', 'net_value', 'monthly_depreciation']


class FixedAssetListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    custodian_name = serializers.CharField(source='custodian.get_full_name', read_only=True)
    
    class Meta:
        model = FixedAsset
        fields = [
            'id', 'asset_no', 'name', 'model', 'category', 'category_name',
            'status', 'status_display', 'department', 'department_name',
            'custodian', 'custodian_name', 'location',
            'original_value', 'accumulated_depreciation', 'net_value',
            'purchase_date', 'warranty_end_date'
        ]


# =====================
# ViewSets
# =====================

class AssetCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """资产分类管理"""
    queryset = AssetCategory.objects.filter(is_deleted=False)
    serializer_class = AssetCategorySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'code']

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取分类树形结构"""
        categories = self.get_queryset().filter(parent__isnull=True)
        
        def build_tree(category):
            node = {
                'id': category.id,
                'name': category.name,
                'code': category.code,
                'children': []
            }
            children = AssetCategory.objects.filter(parent=category, is_deleted=False)
            for child in children:
                node['children'].append(build_tree(child))
            return node
        
        tree = [build_tree(cat) for cat in categories]
        return Response(tree)


class FixedAssetViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """固定资产管理"""
    queryset = FixedAsset.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'category', 'department', 'custodian']
    search_fields = ['asset_no', 'name', 'model', 'serial_no']
    ordering_fields = ['created_at', 'purchase_date', 'original_value']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FixedAssetListSerializer
        return FixedAssetSerializer
    
    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """资产转移"""
        asset = self.get_object()
        
        transfer = AssetTransfer.objects.create(
            asset=asset,
            from_department=asset.department,
            from_custodian=asset.custodian,
            from_location=asset.location,
            to_department_id=request.data.get('to_department'),
            to_custodian_id=request.data.get('to_custodian'),
            to_location=request.data.get('to_location', ''),
            reason=request.data.get('reason', ''),
            created_by=request.user
        )
        
        # 更新资产信息
        asset.department_id = request.data.get('to_department')
        asset.custodian_id = request.data.get('to_custodian')
        asset.location = request.data.get('to_location', '')
        asset.save()
        
        return Response(AssetTransferSerializer(transfer).data)
    
    @action(detail=True, methods=['post'])
    def dispose(self, request, pk=None):
        """资产处置"""
        asset = self.get_object()
        
        disposal = AssetDisposal.objects.create(
            asset=asset,
            disposal_type=request.data.get('disposal_type'),
            disposal_value=request.data.get('disposal_value', 0),
            net_book_value=asset.net_value,
            gain_loss=Decimal(str(request.data.get('disposal_value', 0))) - asset.net_value,
            reason=request.data.get('reason', ''),
            approval_no=request.data.get('approval_no', ''),
            created_by=request.user
        )
        
        # 更新资产状态
        asset.status = 'SCRAPPED' if request.data.get('disposal_type') == 'SCRAP' else 'SOLD'
        asset.disposal_date = date.today()
        asset.disposal_value = request.data.get('disposal_value', 0)
        asset.save()
        
        return Response(AssetDisposalSerializer(disposal).data)
    
    @action(detail=False, methods=['post'])
    def run_depreciation(self, request):
        """执行折旧计算"""
        year = request.data.get('year', date.today().year)
        month = request.data.get('month', date.today().month)
        
        assets = self.get_queryset().filter(status='IN_USE')
        depreciated_count = 0
        
        for asset in assets:
            if asset.start_depreciation_date and asset.start_depreciation_date <= date(year, month, 1):
                # 检查是否已折旧
                exists = AssetDepreciation.objects.filter(
                    asset=asset, year=year, month=month
                ).exists()
                
                if not exists:
                    depreciation_amount = asset.calculate_depreciation(year, month)
                    
                    AssetDepreciation.objects.create(
                        asset=asset,
                        year=year,
                        month=month,
                        opening_value=asset.net_value,
                        depreciation_amount=depreciation_amount,
                        closing_value=asset.net_value - depreciation_amount,
                        accumulated_depreciation=asset.accumulated_depreciation + depreciation_amount,
                        created_by=request.user
                    )
                    
                    # 更新资产累计折旧
                    asset.accumulated_depreciation += depreciation_amount
                    asset.save()
                    
                    depreciated_count += 1
        
        return Response({
            'success': True,
            'year': year,
            'month': month,
            'depreciated_count': depreciated_count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """资产统计"""
        qs = self.get_queryset()
        
        by_status = qs.values('status').annotate(
            count=Count('id'),
            total_value=Sum('original_value'),
            net_value=Sum('net_value')
        )
        
        by_category = qs.values('category__name').annotate(
            count=Count('id'),
            total_value=Sum('original_value')
        )
        
        total = qs.aggregate(
            count=Count('id'),
            total_original=Sum('original_value'),
            total_depreciation=Sum('accumulated_depreciation'),
            total_net=Sum('net_value')
        )
        
        return Response({
            'total': total,
            'by_status': list(by_status),
            'by_category': list(by_category)
        })


class AssetDepreciationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """资产折旧管理"""
    queryset = AssetDepreciation.objects.filter(is_deleted=False)
    serializer_class = AssetDepreciationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['asset', 'year', 'month', 'is_posted']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """折旧汇总"""
        year = request.query_params.get('year', date.today().year)
        
        summary = self.get_queryset().filter(year=year).values('month').annotate(
            total_depreciation=Sum('depreciation_amount'),
            asset_count=Count('asset', distinct=True)
        ).order_by('month')
        
        return Response(list(summary))


class AssetTransferViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """资产转移管理"""
    queryset = AssetTransfer.objects.filter(is_deleted=False)
    serializer_class = AssetTransferSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['asset', 'from_department', 'to_department']


class AssetDisposalViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """资产处置管理"""
    queryset = AssetDisposal.objects.filter(is_deleted=False)
    serializer_class = AssetDisposalSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['asset', 'disposal_type']
