"""
来料检验 (IQC - Incoming Quality Control) 单据化模块。

审计缺口整改：历史收货质检仅在 GoodsReceiptLine.quality_status 单字段上打标，
缺少独立的来料检验单据(送检/抽样/不良/AQL/处置)与"合格才入库"的门禁。

本模块提供：
- IncomingInspection: 来料检验单模型(继承 BaseModel，软删除/审计齐全)。
- IncomingInspectionSerializer / IncomingInspectionViewSet: 单据 CRUD + submit。
- evaluate_line_inspection(): 收货入库门禁判定，供 GoodsReceiptViewSet.confirm 调用。

门禁默认防御性设计(见 evaluate_line_inspection)：
- 已提交且判 FAIL/REJECT 的检验单 -> 该收货行不入库(路由不良/退货)。
- PASS/CONDITIONAL(让步) -> 允许入库。
- 无检验单时，仅当 settings.IQC_ENFORCE_INSPECTION=True 且物料需检才硬拦截；
  默认(False)不阻断既有收货流程，避免对存量数据/流程造成破坏。
"""

from django.db import models
from django.utils import timezone
from rest_framework import serializers, status as drf_status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin
from apps.core.utils import generate_code

from .models import GoodsReceipt, GoodsReceiptLine

# 允许入库的检验结果
STOCK_IN_OK_RESULTS = ('PASS', 'CONDITIONAL')


class IncomingInspection(BaseModel):
    """来料检验单 (IQC)."""

    RESULT_CHOICES = [
        ('PASS', '合格'),
        ('FAIL', '不合格'),
        ('CONDITIONAL', '让步接收(有条件合格)'),
    ]

    DISPOSITION_CHOICES = [
        ('ACCEPT', '接收入库'),
        ('REJECT', '拒收/退货'),
        ('CONCESSION', '让步接收'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
    ]

    inspection_no = models.CharField(max_length=50, unique=True, verbose_name='检验单号')
    goods_receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name='inspections', verbose_name='收货单'
    )
    receipt_line = models.ForeignKey(
        GoodsReceiptLine,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='inspections',
        verbose_name='收货明细',
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='incoming_inspections', verbose_name='物料'
    )

    inspected_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='送检数量')
    sample_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='抽样数量')
    defect_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='不良数量')

    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='PASS', verbose_name='检验结果')
    disposition = models.CharField(
        max_length=20, choices=DISPOSITION_CHOICES, default='ACCEPT', verbose_name='处置方式'
    )

    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_inspections',
        verbose_name='检验员',
    )
    inspection_date = models.DateField(default=timezone.localdate, verbose_name='检验日期')
    aql = models.CharField(max_length=50, blank=True, verbose_name='AQL/抽样标准')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'incoming_inspection'
        verbose_name = '来料检验单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['goods_receipt', 'result']),
            models.Index(fields=['receipt_line']),
            models.Index(fields=['status', 'result']),
        ]

    def __str__(self):
        return f'{self.inspection_no}'

    def save(self, *args, **kwargs):
        if not self.inspection_no:
            self.inspection_no = generate_code('IQC', rule_type='INCOMING_INSPECTION')
        super().save(*args, **kwargs)


# ==========================================================================
# 入库门禁判定
# ==========================================================================


def item_requires_inspection(item):
    """物料是否需要来料检验。

    读取 masterdata.Item.inspection_type：'NONE'(免检) 视为无需检验；
    'INCOMING'/'SAMPLE'/'FULL' 视为需检。字段缺失时保守返回 False(不阻断收货)。
    """
    if item is None:
        return False
    itype = getattr(item, 'inspection_type', None)
    if itype is None:
        return False
    return itype != 'NONE'


def _resolve_inspection(receipt_line):
    """解析收货行对应的最新一张"已提交"检验单。

    优先匹配 receipt_line 精确关联；否则回退到同收货单同物料的单据级检验单
    (支持只做整单级 IQC、未拆到行的用法)。
    """
    inspection = (
        IncomingInspection.objects.filter(receipt_line=receipt_line, status='SUBMITTED', is_deleted=False)
        .order_by('-created_at', '-id')
        .first()
    )
    if inspection is not None:
        return inspection
    return (
        IncomingInspection.objects.filter(
            goods_receipt=receipt_line.receipt_id,
            item=receipt_line.item_id,
            status='SUBMITTED',
            is_deleted=False,
        )
        .order_by('-created_at', '-id')
        .first()
    )


def evaluate_line_inspection(receipt_line, enforce=None):
    """收货行入库处置判定。

    返回 (decision, reason)，decision ∈ {'ALLOW', 'FAIL_SKIP', 'MISSING_BLOCK'}：
    - FAIL_SKIP: 已提交检验单判 FAIL 或处置 REJECT -> 该行不入库(走不良/退货)。
    - MISSING_BLOCK: 需检物料且无合格检验单，且强制门禁开启 -> 硬拦截整单确认。
    - ALLOW: 允许入库(PASS/CONDITIONAL，或未开启强制门禁时无单放行)。

    enforce 缺省读取 settings.IQC_ENFORCE_INSPECTION(默认 False)。
    默认关闭强制门禁以避免破坏既有收货流程；FAIL 检验单在任何情况下都会拦截入库。
    """
    from django.conf import settings

    if enforce is None:
        enforce = getattr(settings, 'IQC_ENFORCE_INSPECTION', False)

    item = receipt_line.item
    inspection = _resolve_inspection(receipt_line)

    if inspection is not None:
        if inspection.result == 'FAIL' or inspection.disposition == 'REJECT':
            return 'FAIL_SKIP', f'物料 {item.sku} 来料检验不合格({inspection.inspection_no})，不予入库'
        if inspection.result in STOCK_IN_OK_RESULTS:
            return 'ALLOW', ''
        # 未知结果保守拦截该行
        return 'FAIL_SKIP', f'物料 {item.sku} 来料检验结果 {inspection.result} 不允许入库'

    # 无已提交检验单
    if enforce and item_requires_inspection(item):
        return 'MISSING_BLOCK', f'物料 {item.sku} 需来料检验(IQC)，缺少已提交的合格检验单，不能入库'
    return 'ALLOW', ''


# ==========================================================================
# Serializer / ViewSet
# ==========================================================================


class IncomingInspectionSerializer(serializers.ModelSerializer):
    """来料检验单序列化器."""

    item_sku = serializers.CharField(source='item.sku', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    receipt_no = serializers.CharField(source='goods_receipt.receipt_no', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    disposition_display = serializers.CharField(source='get_disposition_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    inspector_name = serializers.SerializerMethodField()

    def get_inspector_name(self, obj):
        if obj.inspector:
            return obj.inspector.get_full_name() or obj.inspector.username
        return ''

    class Meta:
        model = IncomingInspection
        fields = [
            'id',
            'inspection_no',
            'goods_receipt',
            'receipt_no',
            'receipt_line',
            'item',
            'item_sku',
            'item_name',
            'inspected_qty',
            'sample_qty',
            'defect_qty',
            'result',
            'result_display',
            'disposition',
            'disposition_display',
            'inspector',
            'inspector_name',
            'inspection_date',
            'aql',
            'status',
            'status_display',
            'notes',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['inspection_no', 'status', 'created_at', 'updated_at']
        extra_kwargs = {
            'item': {'required': False},
            'inspector': {'required': False},
        }


class IncomingInspectionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """来料检验单 ViewSet."""

    queryset = IncomingInspection.objects.all()
    serializer_class = IncomingInspectionSerializer
    filterset_fields = ['goods_receipt', 'receipt_line', 'item', 'result', 'disposition', 'status', 'is_deleted']
    search_fields = ['inspection_no', 'item__sku', 'item__name']
    ordering_fields = ['inspection_date', 'created_at']

    permission_module = 'purchase'
    permission_resource = 'inspection'

    def perform_create(self, serializer):
        """自动回填物料(从收货行)与检验员(当前用户)，并保留审计字段。"""
        validated = serializer.validated_data
        kwargs = {}
        model_fields = {f.name for f in IncomingInspection._meta.get_fields()}
        if 'created_by' in model_fields:
            kwargs['created_by'] = self.request.user
        if 'updated_by' in model_fields:
            kwargs['updated_by'] = self.request.user

        receipt_line = validated.get('receipt_line')
        if not validated.get('item') and receipt_line is not None:
            kwargs['item'] = receipt_line.item
        if not validated.get('inspector'):
            kwargs['inspector'] = self.request.user

        serializer.save(**kwargs)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交检验单：DRAFT -> SUBMITTED，提交后方参与入库门禁判定。"""
        inspection = self.get_object()
        if inspection.status == 'SUBMITTED':
            return Response({'error': '检验单已提交'}, status=drf_status.HTTP_400_BAD_REQUEST)
        inspection.status = 'SUBMITTED'
        inspection.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(inspection).data)
