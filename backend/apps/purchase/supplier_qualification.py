"""
供应商资质管理
Supplier Qualification Management
管理供应商资质证书、有效期提醒等
"""
from datetime import date, timedelta
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class QualificationType(BaseModel):
    """
    资质类型
    """
    code = models.CharField(max_length=50, unique=True, verbose_name='类型编码')
    name = models.CharField(max_length=100, verbose_name='类型名称')
    is_required = models.BooleanField(default=False, verbose_name='必须资质')
    validity_period = models.IntegerField(
        default=365,
        verbose_name='有效期(天)',
        help_text='默认有效期'
    )
    remind_days = models.IntegerField(
        default=30,
        verbose_name='提前提醒天数'
    )
    category = models.CharField(
        max_length=50,
        choices=[
            ('BUSINESS', '企业资质'),
            ('QUALITY', '质量认证'),
            ('SAFETY', '安全资质'),
            ('ENVIRONMENT', '环境资质'),
            ('INDUSTRY', '行业资质'),
            ('OTHER', '其他'),
        ],
        default='BUSINESS',
        verbose_name='资质分类'
    )
    description = models.TextField(blank=True, verbose_name='说明')
    is_active = models.BooleanField(default=True, verbose_name='启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'purchase_qualification_type'
        verbose_name = '资质类型'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']
    
    def __str__(self):
        return f'{self.code} - {self.name}'


class SupplierQualification(BaseModel):
    """
    供应商资质
    """
    STATUS_CHOICES = [
        ('PENDING', '待审核'),
        ('VALID', '有效'),
        ('EXPIRING', '即将过期'),
        ('EXPIRED', '已过期'),
        ('REJECTED', '已拒绝'),
    ]
    
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.CASCADE,
        related_name='qualifications',
        verbose_name='供应商'
    )
    qualification_type = models.ForeignKey(
        QualificationType,
        on_delete=models.PROTECT,
        related_name='qualifications',
        verbose_name='资质类型'
    )
    
    # 证书信息
    certificate_no = models.CharField(max_length=100, verbose_name='证书编号')
    certificate_name = models.CharField(max_length=200, verbose_name='证书名称')
    issuing_authority = models.CharField(max_length=200, blank=True, verbose_name='发证机关')
    
    # 有效期
    issue_date = models.DateField(verbose_name='发证日期')
    expiry_date = models.DateField(verbose_name='到期日期')
    
    # 附件
    attachment = models.FileField(
        upload_to='qualifications/',
        blank=True,
        null=True,
        verbose_name='附件'
    )
    attachment_url = models.URLField(blank=True, verbose_name='附件链接')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 审核
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_qualifications',
        verbose_name='审核人'
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    rejection_reason = models.CharField(max_length=500, blank=True, verbose_name='拒绝原因')
    
    # 提醒
    is_reminded = models.BooleanField(default=False, verbose_name='已提醒')
    reminded_at = models.DateTimeField(null=True, blank=True, verbose_name='提醒时间')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_supplier_qualification'
        verbose_name = '供应商资质'
        verbose_name_plural = verbose_name
        ordering = ['-expiry_date']
        unique_together = ['supplier', 'qualification_type', 'certificate_no']
    
    def __str__(self):
        return f'{self.supplier.name} - {self.certificate_name}'
    
    @property
    def days_to_expiry(self):
        """距离过期天数"""
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days
    
    @property
    def is_expiring_soon(self):
        """是否即将过期"""
        days = self.days_to_expiry
        if days is None:
            return False
        return 0 < days <= self.qualification_type.remind_days
    
    @property
    def is_expired(self):
        """是否已过期"""
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()
    
    def update_status(self):
        """更新状态"""
        if self.status in ['PENDING', 'REJECTED']:
            return
        
        if self.is_expired:
            self.status = 'EXPIRED'
        elif self.is_expiring_soon:
            self.status = 'EXPIRING'
        else:
            self.status = 'VALID'
        self.save()


class QualificationReminder(BaseModel):
    """
    资质提醒记录
    """
    qualification = models.ForeignKey(
        SupplierQualification,
        on_delete=models.CASCADE,
        related_name='reminders',
        verbose_name='资质'
    )
    remind_date = models.DateField(verbose_name='提醒日期')
    remind_type = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', '邮件'),
            ('SMS', '短信'),
            ('SYSTEM', '系统消息'),
        ],
        default='SYSTEM',
        verbose_name='提醒方式'
    )
    recipients = models.CharField(max_length=500, blank=True, verbose_name='接收人')
    content = models.TextField(blank=True, verbose_name='提醒内容')
    is_sent = models.BooleanField(default=False, verbose_name='已发送')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    
    class Meta:
        db_table = 'purchase_qualification_reminder'
        verbose_name = '资质提醒'
        verbose_name_plural = verbose_name
        ordering = ['-remind_date']


# =====================
# Serializers
# =====================

class QualificationTypeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = QualificationType
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SupplierQualificationSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    type_name = serializers.CharField(source='qualification_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    
    class Meta:
        model = SupplierQualification
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'verified_by', 'verified_at']


class SupplierQualificationListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    type_name = serializers.CharField(source='qualification_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = SupplierQualification
        fields = [
            'id', 'supplier', 'supplier_name', 'qualification_type', 'type_name',
            'certificate_no', 'certificate_name', 'issue_date', 'expiry_date',
            'status', 'status_display', 'days_to_expiry', 'created_at'
        ]


class QualificationReminderSerializer(serializers.ModelSerializer):
    qualification_name = serializers.CharField(source='qualification.certificate_name', read_only=True)
    supplier_name = serializers.CharField(source='qualification.supplier.name', read_only=True)
    
    class Meta:
        model = QualificationReminder
        fields = '__all__'


# =====================
# ViewSets
# =====================

class QualificationTypeViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """资质类型管理"""
    queryset = QualificationType.objects.filter(is_deleted=False)
    serializer_class = QualificationTypeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_required', 'is_active']
    search_fields = ['code', 'name']
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取资质分类"""
        return Response([
            {'value': 'BUSINESS', 'label': '企业资质'},
            {'value': 'QUALITY', 'label': '质量认证'},
            {'value': 'SAFETY', 'label': '安全资质'},
            {'value': 'ENVIRONMENT', 'label': '环境资质'},
            {'value': 'INDUSTRY', 'label': '行业资质'},
            {'value': 'OTHER', 'label': '其他'},
        ])
    
    @action(detail=False, methods=['post'])
    def init_types(self, request):
        """初始化常用资质类型"""
        types = [
            ('BL', '营业执照', 'BUSINESS', True, 365 * 5),
            ('ISO9001', 'ISO9001质量管理体系', 'QUALITY', False, 365 * 3),
            ('ISO14001', 'ISO14001环境管理体系', 'ENVIRONMENT', False, 365 * 3),
            ('ISO45001', 'ISO45001职业健康安全', 'SAFETY', False, 365 * 3),
            ('IATF16949', 'IATF16949汽车质量', 'QUALITY', False, 365 * 3),
            ('CCC', '3C认证', 'QUALITY', False, 365 * 5),
            ('CE', 'CE认证', 'QUALITY', False, 365 * 5),
            ('TAX', '一般纳税人资格', 'BUSINESS', False, 365 * 99),
            ('BANK', '开户许可证', 'BUSINESS', False, 365 * 99),
        ]
        
        created = 0
        for code, name, category, is_required, validity in types:
            _, c = QualificationType.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'category': category,
                    'is_required': is_required,
                    'validity_period': validity,
                    'created_by': request.user
                }
            )
            if c:
                created += 1
        
        return Response({'success': True, 'created': created})


class SupplierQualificationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """供应商资质管理"""
    queryset = SupplierQualification.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'qualification_type', 'status']
    search_fields = ['certificate_no', 'certificate_name', 'supplier__name']
    ordering_fields = ['expiry_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SupplierQualificationListSerializer
        return SupplierQualificationSerializer
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """审核通过"""
        qualification = self.get_object()
        qualification.status = 'VALID'
        qualification.verified_by = request.user
        qualification.verified_at = timezone.now()
        qualification.save()
        return Response(self.get_serializer(qualification).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审核拒绝"""
        qualification = self.get_object()
        reason = request.data.get('reason', '')
        
        qualification.status = 'REJECTED'
        qualification.rejection_reason = reason
        qualification.verified_by = request.user
        qualification.verified_at = timezone.now()
        qualification.save()
        return Response(self.get_serializer(qualification).data)
    
    @action(detail=False, methods=['get'])
    def expiring(self, request):
        """即将过期的资质"""
        days = int(request.query_params.get('days', 30))
        expiry_date = date.today() + timedelta(days=days)
        
        qualifications = self.get_queryset().filter(
            status='VALID',
            expiry_date__lte=expiry_date,
            expiry_date__gte=date.today()
        ).order_by('expiry_date')
        
        return Response(SupplierQualificationListSerializer(qualifications, many=True).data)
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """已过期的资质"""
        qualifications = self.get_queryset().filter(
            expiry_date__lt=date.today()
        ).exclude(status='REJECTED').order_by('-expiry_date')
        
        return Response(SupplierQualificationListSerializer(qualifications, many=True).data)
    
    @action(detail=False, methods=['get'])
    def by_supplier(self, request):
        """按供应商查询资质"""
        supplier_id = request.query_params.get('supplier_id')
        if not supplier_id:
            return Response({'error': '请提供供应商ID'}, status=400)
        
        qualifications = self.get_queryset().filter(supplier_id=supplier_id)
        return Response(SupplierQualificationListSerializer(qualifications, many=True).data)
    
    @action(detail=False, methods=['post'])
    def update_all_status(self, request):
        """批量更新资质状态"""
        qualifications = self.get_queryset().filter(status__in=['VALID', 'EXPIRING'])
        
        updated = 0
        for q in qualifications:
            old_status = q.status
            q.update_status()
            if q.status != old_status:
                updated += 1
        
        return Response({
            'success': True,
            'updated': updated
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """资质统计"""
        from django.db.models import Count
        
        qs = self.get_queryset()
        
        # 按状态统计
        by_status = qs.values('status').annotate(count=Count('id'))
        
        # 按类型统计
        by_type = qs.values('qualification_type__name').annotate(count=Count('id'))
        
        # 即将过期数量
        expiring_30 = qs.filter(
            status='VALID',
            expiry_date__lte=date.today() + timedelta(days=30),
            expiry_date__gte=date.today()
        ).count()
        
        # 已过期数量
        expired = qs.filter(expiry_date__lt=date.today()).exclude(status='REJECTED').count()
        
        return Response({
            'total': qs.count(),
            'expiring_30_days': expiring_30,
            'expired': expired,
            'by_status': list(by_status),
            'by_type': list(by_type)
        })


class QualificationReminderViewSet(viewsets.ReadOnlyModelViewSet):
    """资质提醒记录"""
    queryset = QualificationReminder.objects.filter(is_deleted=False)
    serializer_class = QualificationReminderSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_sent', 'remind_type']
