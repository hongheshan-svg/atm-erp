"""销售订单变更单 (Sales Order Change / SOC)。

审计 P1：已确认/发货中的销售订单不允许直接改明细（序列化器 update 已拦截）。
本模块提供受控的"变更单"作为唯一合法修订路径：变更单记录变更类型、原因、
变更前/后快照，经审批 (approve) 后在同一事务内 guarded 地作用到销售订单，
并留下可追溯的审计轨迹。

模型 / 序列化器 / 视图集集中在本文件，遵循 win_loss_analysis.py 的组织约定。
为避免与 apps.sales.models / apps.sales.serializers 之间的循环导入，
本文件的所有跨模块引用（SalesOrder / SalesOrderLine）均在方法内惰性导入。
"""

from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin
from apps.core.utils import generate_code


def _to_decimal(value, field_name):
    """安全转 Decimal，非法值抛业务异常（由视图转 400）。"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{field_name} 数值非法：{value!r}')


def _snapshot_order(order):
    """对销售订单及其有效明细做结构化快照（金额用字符串保留 Decimal 精度）。"""
    return {
        'order_no': order.order_no,
        'status': order.status,
        'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
        'tax_rate': order.tax_rate,
        'total_amount': str(order.total_amount),
        'tax_amount': str(order.tax_amount),
        'total_with_tax': str(order.total_with_tax),
        'lines': [
            {
                'id': line.id,
                'item': line.item_id,
                'custom_name': line.custom_name,
                'custom_spec': line.custom_spec,
                'custom_unit': line.custom_unit,
                'qty': str(line.qty),
                'unit_price': str(line.unit_price),
                'line_amount': str(line.line_amount),
                'delivered_qty': str(line.delivered_qty),
            }
            for line in order.lines.filter(is_deleted=False)
        ],
    }


class SalesOrderChange(BaseModel):
    """销售订单变更单 - 已确认/发货中订单修订的唯一合法路径。"""

    CHANGE_TYPE_CHOICES = [
        ('ADD', '新增明细'),
        ('REMOVE', '删除明细'),
        ('PRICE', '单价调整'),
        ('QTY', '数量调整'),
        ('DELIVERY', '交期调整'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('REJECTED', '已拒绝'),
    ]

    # 变更单挂靠订单；订单软删不级联，变更单作为审计轨迹长期保留
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.CASCADE,
        related_name='changes',
        verbose_name='销售订单',
    )
    change_no = models.CharField(max_length=50, unique=True, verbose_name='变更单号')
    change_type = models.CharField(
        max_length=20, choices=CHANGE_TYPE_CHOICES, verbose_name='变更类型'
    )
    reason = models.TextField(blank=True, verbose_name='变更原因')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态'
    )
    # 结构化变更指令，形如：
    #   PRICE/QTY: {'so_line': <id>, 'unit_price'|'qty': <值>}
    #   ADD:       {'item': <id|null>, 'custom_name', 'custom_spec', 'custom_unit', 'qty', 'unit_price', 'notes'}
    #   REMOVE:    {'so_line': <id>}
    #   DELIVERY:  {'delivery_date': 'YYYY-MM-DD'}
    #   OTHER:     {'notes': <str>}
    change_data = models.JSONField(default=dict, blank=True, verbose_name='变更指令')
    before_data = models.JSONField(default=dict, blank=True, verbose_name='变更前快照')
    after_data = models.JSONField(default=dict, blank=True, verbose_name='变更后快照')
    applied_at = models.DateTimeField(null=True, blank=True, verbose_name='生效时间')

    class Meta:
        db_table = 'sales_order_change'
        verbose_name = '销售订单变更单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.change_no} ({self.get_change_type_display()})'

    def save(self, *args, **kwargs):
        if not self.change_no:
            self.change_no = generate_code('SOC', rule_type='SALES_ORDER_CHANGE')
        super().save(*args, **kwargs)

    def _get_target_line(self, order, data):
        line_id = data.get('so_line') or data.get('line') or data.get('so_line_id')
        if not line_id:
            raise ValueError('请指定要变更的订单明细 so_line')
        try:
            return order.lines.get(id=line_id, is_deleted=False)
        except Exception:
            raise ValueError(f'订单明细 {line_id} 不存在或不属于本订单')

    def apply(self, user):
        """将变更 guarded 地作用到销售订单，写入前/后快照并置为已审批。

        必须在 transaction.atomic() 内调用；对订单加行锁避免并发变更竞争。
        guard 校验失败抛 ValueError，由视图转 400。
        """
        from datetime import datetime

        from django.db.models import Sum
        from django.utils import timezone

        from .models import SalesOrder, SalesOrderLine

        order = SalesOrder.objects.select_for_update().get(pk=self.sales_order_id)

        # 仅已确认/部分发货订单需要走变更单；草稿可直接编辑
        if order.status not in ('CONFIRMED', 'PARTIAL'):
            raise ValueError(
                f'仅已确认/部分发货状态的订单可执行变更，当前状态：{order.get_status_display()}'
            )

        self.before_data = _snapshot_order(order)
        data = self.change_data or {}
        ct = self.change_type

        if ct == 'PRICE':
            line = self._get_target_line(order, data)
            if 'unit_price' not in data:
                raise ValueError('单价调整需提供 unit_price')
            new_price = _to_decimal(data['unit_price'], '单价')
            if new_price < 0:
                raise ValueError('单价不能为负数')
            line.unit_price = new_price
            line.save()  # SalesOrderLine.save() 重算 line_amount

        elif ct == 'QTY':
            line = self._get_target_line(order, data)
            if 'qty' not in data:
                raise ValueError('数量调整需提供 qty')
            new_qty = _to_decimal(data['qty'], '数量')
            if new_qty <= 0:
                raise ValueError('数量必须大于0')
            if new_qty < (line.delivered_qty or Decimal('0')):
                raise ValueError(
                    f'变更数量 {new_qty} 不能小于已发货数量 {line.delivered_qty}'
                )
            line.qty = new_qty
            line.save()

        elif ct == 'ADD':
            qty = _to_decimal(data.get('qty', '0'), '数量')
            unit_price = _to_decimal(data.get('unit_price', '0'), '单价')
            if qty <= 0:
                raise ValueError('新增明细数量必须大于0')
            if unit_price < 0:
                raise ValueError('单价不能为负数')
            if not data.get('item') and not data.get('custom_name'):
                raise ValueError('新增明细需选择物料或填写产品名称')
            SalesOrderLine.objects.create(
                so=order,
                item_id=data.get('item'),
                custom_name=data.get('custom_name', ''),
                custom_spec=data.get('custom_spec', ''),
                custom_unit=data.get('custom_unit', '件'),
                qty=qty,
                unit_price=unit_price,
                notes=data.get('notes', ''),
                created_by=user,
            )

        elif ct == 'REMOVE':
            line = self._get_target_line(order, data)
            if (line.delivered_qty or Decimal('0')) > 0:
                raise ValueError('已发货明细不能删除，请走退货流程')
            line.is_deleted = True
            line.deleted_at = timezone.now()
            line.updated_by = user
            line.save(update_fields=['is_deleted', 'deleted_at', 'updated_by'])

        elif ct == 'DELIVERY':
            raw = data.get('delivery_date')
            if not raw:
                raise ValueError('交期调整需提供 delivery_date')
            if isinstance(raw, str):
                try:
                    new_date = datetime.strptime(raw.strip(), '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError(f'交货日期格式错误（应为 YYYY-MM-DD）：{raw}')
            else:
                new_date = raw
            order.delivery_date = new_date

        elif ct == 'OTHER':
            if 'notes' in data:
                order.notes = data.get('notes', '') or ''

        else:
            raise ValueError(f'未知变更类型：{ct}')

        # 重算订单金额（明细金额可能因增删改变化）
        total = order.lines.filter(is_deleted=False).aggregate(
            s=Sum('line_amount')
        )['s'] or Decimal('0')
        order.total_amount = total
        order.tax_amount = total * order.tax_rate / 100
        order.total_with_tax = total + order.tax_amount
        order.updated_by = user
        order.save()

        self.after_data = _snapshot_order(order)
        self.status = 'APPROVED'
        self.applied_at = timezone.now()
        self.updated_by = user
        self.save()
        return order


class SalesOrderChangeSerializer(serializers.ModelSerializer):
    """SalesOrderChange serializer。"""

    order_no = serializers.CharField(source='sales_order.order_no', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrderChange
        fields = [
            'id',
            'sales_order',
            'order_no',
            'change_no',
            'change_type',
            'change_type_display',
            'reason',
            'status',
            'status_display',
            'change_data',
            'before_data',
            'after_data',
            'applied_at',
            'is_deleted',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'change_no',
            'status',
            'before_data',
            'after_data',
            'applied_at',
            'created_at',
            'updated_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''


class SalesOrderChangeViewSet(
    PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet
):
    """销售订单变更单 ViewSet。

    受控修订流程：create(DRAFT) → submit(PENDING) → approve(APPROVED, 作用到订单) / reject。
    """

    queryset = SalesOrderChange.objects.all()
    serializer_class = SalesOrderChangeSerializer
    filterset_fields = ['sales_order', 'change_type', 'status', 'is_deleted']
    search_fields = ['change_no', 'reason']
    ordering_fields = ['created_at', 'applied_at']

    permission_module = 'sales'
    permission_resource = 'order_change'

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交变更单审批 (DRAFT/REJECTED → PENDING)。"""
        change = self.get_object()
        if change.status not in ('DRAFT', 'REJECTED'):
            return Response(
                {'error': '只能提交草稿或已拒绝状态的变更单'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        change.status = 'PENDING'
        change.updated_by = request.user
        change.save(update_fields=['status', 'updated_by', 'updated_at'])
        return Response(SalesOrderChangeSerializer(change).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批变更单并作用到销售订单 (DRAFT/PENDING → APPROVED)。"""
        change = self.get_object()
        if change.status not in ('DRAFT', 'PENDING'):
            return Response(
                {'error': '只能审批草稿或待审批状态的变更单'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                change.apply(request.user)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(SalesOrderChangeSerializer(change).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝变更单 (DRAFT/PENDING → REJECTED)。"""
        change = self.get_object()
        if change.status not in ('DRAFT', 'PENDING'):
            return Response(
                {'error': '只能拒绝草稿或待审批状态的变更单'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        change.status = 'REJECTED'
        change.reason = request.data.get('reason', change.reason)
        change.updated_by = request.user
        change.save(update_fields=['status', 'reason', 'updated_by', 'updated_at'])
        return Response(SalesOrderChangeSerializer(change).data)
