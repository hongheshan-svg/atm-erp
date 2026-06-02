"""
对账单视图
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.permission_mixin import PermissionMixin

from .models import AccountPayable, AccountReceivable, Invoice, Payment
from .reconciliation_models import (
    InvoiceReconciliation,
    InvoiceReconciliationLine,
    PurchaseReconciliation,
    PurchaseReconciliationLine,
    SalesReconciliation,
    SalesReconciliationLine,
)
from .reconciliation_serializers import (
    InvoiceReconciliationListSerializer,
    InvoiceReconciliationSerializer,
    PurchaseReconciliationLineSerializer,
    PurchaseReconciliationListSerializer,
    PurchaseReconciliationSerializer,
    SalesReconciliationLineSerializer,
    SalesReconciliationListSerializer,
    SalesReconciliationSerializer,
)


class PurchaseReconciliationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    采购付款对账单视图

    支持操作：
    - 创建对账单
    - 生成对账明细（从采购订单、发票、付款记录）
    - 确认对账
    """

    queryset = PurchaseReconciliation.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['supplier', 'status']
    search_fields = ['reconciliation_no', 'supplier__name']
    ordering_fields = ['period_start', 'created_at']
    ordering = ['-created_at']

    permission_module = 'finance'
    permission_resource = 'purchase_reconciliation'
    module_name = 'finance'

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseReconciliationListSerializer
        return PurchaseReconciliationSerializer

    @action(detail=True, methods=['post'])
    def generate_lines(self, request, pk=None):
        """
        生成对账明细
        自动从采购订单、收货单、发票、付款记录中生成对账明细
        """
        reconciliation = self.get_object()

        if reconciliation.status not in ['DRAFT', 'PENDING']:
            return Response({'error': '只能对草稿或待确认状态的对账单生成明细'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.purchase.models import GoodsReceipt, PurchaseOrder

        with transaction.atomic():
            # 清除现有明细
            reconciliation.lines.all().delete()

            running_balance = reconciliation.opening_balance
            total_order = Decimal('0')
            total_received = Decimal('0')
            total_invoice = Decimal('0')
            total_paid = Decimal('0')

            # 1. 获取期间内的采购订单
            orders = PurchaseOrder.objects.filter(
                supplier=reconciliation.supplier,
                order_date__gte=reconciliation.period_start,
                order_date__lte=reconciliation.period_end,
                status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED'],
                is_deleted=False,
            ).order_by('order_date')

            for po in orders:
                order_amount = po.total_with_tax or po.total_amount or Decimal('0')
                total_order += order_amount

                # 计算订单数量和已收货数量
                order_qty = sum(line.qty for line in po.lines.filter(is_deleted=False))
                received_qty = Decimal('0')
                for receipt in po.receipts.filter(status__in=['CONFIRMED', 'COMPLETED'], is_deleted=False):
                    for line in receipt.lines.filter(is_deleted=False):
                        received_qty += line.qty

                # 确定收货状态
                if received_qty == 0:
                    receipt_status = 'NOT_RECEIVED'
                elif received_qty >= order_qty:
                    receipt_status = 'RECEIVED'
                else:
                    receipt_status = 'PARTIAL'

                # 计算付款进度
                payable_amount = order_amount
                paid_amount = Decimal('0')
                # 从应付账款中获取该订单的付款情况
                for ap in AccountPayable.objects.filter(po=po, is_deleted=False):
                    paid_amount += ap.amount_paid or Decimal('0')

                payment_progress = Decimal('0')
                if payable_amount > 0:
                    payment_progress = (paid_amount / payable_amount * 100).quantize(Decimal('0.01'))

                PurchaseReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='ORDER',
                    po=po,
                    reference_no=po.order_no,
                    reference_date=po.order_date,
                    debit_amount=order_amount,
                    credit_amount=0,
                    balance=running_balance + order_amount,
                    order_qty=order_qty,
                    received_qty=received_qty,
                    receipt_status=receipt_status,
                    payable_amount=payable_amount,
                    paid_amount=paid_amount,
                    payment_progress=payment_progress,
                    notes=f'采购订单 - {po.get_status_display()}',
                    created_by=request.user,
                )

            # 2. 获取期间内的收货单
            receipts = GoodsReceipt.objects.filter(
                po__supplier=reconciliation.supplier,
                receipt_date__gte=reconciliation.period_start,
                receipt_date__lte=reconciliation.period_end,
                status__in=['CONFIRMED', 'COMPLETED'],
                is_deleted=False,
            ).order_by('receipt_date')

            for receipt in receipts:
                # 计算收货金额 (数量 * 采购订单行单价)
                receipt_amount = Decimal('0')
                for line in receipt.lines.filter(is_deleted=False):
                    if hasattr(line, 'po_line') and line.po_line:
                        receipt_amount += line.qty * line.po_line.unit_price
                total_received += receipt_amount

                PurchaseReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='RECEIPT',
                    po=receipt.po,
                    reference_no=receipt.receipt_no,
                    reference_date=receipt.receipt_date,
                    debit_amount=receipt_amount,
                    credit_amount=0,
                    balance=running_balance,
                    notes='收货确认',
                    created_by=request.user,
                )

            # 3. 获取期间内的应付账款（发票）
            payables = AccountPayable.objects.filter(
                supplier=reconciliation.supplier,
                invoice_date__gte=reconciliation.period_start,
                invoice_date__lte=reconciliation.period_end,
                is_deleted=False,
            ).order_by('invoice_date')

            for ap in payables:
                running_balance += ap.amount_due
                total_invoice += ap.amount_due

                PurchaseReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='INVOICE',
                    po=ap.po,
                    reference_no=ap.invoice_no or ap.ap_no,
                    reference_date=ap.invoice_date,
                    debit_amount=ap.amount_due,
                    credit_amount=0,
                    balance=running_balance,
                    notes='发票/应付',
                    created_by=request.user,
                )

            # 4. 获取期间内的付款记录
            payments = Payment.objects.filter(
                payment_type='AP',
                ap__supplier=reconciliation.supplier,
                payment_date__gte=reconciliation.period_start,
                payment_date__lte=reconciliation.period_end,
                is_deleted=False,
            ).order_by('payment_date')

            for payment in payments:
                running_balance -= payment.amount
                total_paid += payment.amount

                PurchaseReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='PAYMENT',
                    reference_no=payment.payment_no,
                    reference_date=payment.payment_date,
                    debit_amount=0,
                    credit_amount=payment.amount,
                    balance=running_balance,
                    notes=f'付款 - {payment.get_payment_method_display()}',
                    created_by=request.user,
                )

            # 更新汇总金额
            reconciliation.total_order_amount = total_order
            reconciliation.total_received_amount = total_received
            reconciliation.total_invoice_amount = total_invoice
            reconciliation.total_paid_amount = total_paid
            reconciliation.reconciled_by = request.user
            reconciliation.reconciled_at = timezone.now()
            reconciliation.status = 'PENDING'
            reconciliation.save()

        return Response(PurchaseReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交对账单"""
        reconciliation = self.get_object()

        if reconciliation.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的对账单'}, status=status.HTTP_400_BAD_REQUEST)

        reconciliation.status = 'PENDING'
        reconciliation.save()

        return Response(PurchaseReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认对账单"""
        reconciliation = self.get_object()

        if reconciliation.status != 'PENDING':
            return Response({'error': '只能确认待确认状态的对账单'}, status=status.HTTP_400_BAD_REQUEST)

        reconciliation.status = 'CONFIRMED'
        reconciliation.confirmed_by = request.user
        reconciliation.confirmed_at = timezone.now()
        reconciliation.save()

        return Response(PurchaseReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'])
    def dispute(self, request, pk=None):
        """标记有争议"""
        reconciliation = self.get_object()

        if reconciliation.status not in ['PENDING', 'CONFIRMED']:
            return Response({'error': '只能对待确认或已确认的对账单标记争议'}, status=status.HTTP_400_BAD_REQUEST)

        reconciliation.status = 'DISPUTED'
        reconciliation.notes = f"争议说明：{request.data.get('reason', '')}\n" + reconciliation.notes
        reconciliation.save()

        return Response(PurchaseReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'], url_path='confirm_receipt/(?P<line_id>[^/.]+)')
    def confirm_receipt(self, request, pk=None, line_id=None):
        """确认收货状态"""
        reconciliation = self.get_object()

        try:
            line = reconciliation.lines.get(id=line_id)
        except PurchaseReconciliationLine.DoesNotExist:
            return Response({'error': '明细不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 更新收货状态
        new_status = request.data.get('receipt_status')
        if new_status and new_status in ['NOT_RECEIVED', 'PARTIAL', 'RECEIVED', 'VERIFIED']:
            line.receipt_status = new_status

        line.receipt_confirmed = True
        line.receipt_confirmed_at = timezone.now()

        # 可以更新收货数量
        if 'received_qty' in request.data:
            line.received_qty = Decimal(str(request.data.get('received_qty', 0)))

        line.save()

        return Response(PurchaseReconciliationLineSerializer(line).data)

    @action(detail=True, methods=['post'])
    def batch_confirm_receipt(self, request, pk=None):
        """批量确认收货状态"""
        reconciliation = self.get_object()

        line_ids = request.data.get('line_ids', [])
        if not line_ids:
            return Response({'error': '请选择要确认的明细'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            lines = reconciliation.lines.filter(id__in=line_ids, line_type='ORDER')
            for line in lines:
                line.receipt_confirmed = True
                line.receipt_confirmed_at = timezone.now()
                if line.receipt_status == 'NOT_RECEIVED':
                    line.receipt_status = 'RECEIVED'
                line.save()

        return Response({'message': f'已确认 {lines.count()} 条明细'})

    @action(detail=False, methods=['get'])
    def get_opening_balance(self, request):
        """
        获取供应商期初余额
        计算逻辑：
        1. 如果有上期已确认对账单，以上期期末余额为基础
        2. 减去上期对账单期末日期之后的所有付款金额
        3. 如果没有历史对账单，则计算应付账款余额（应付-已付）

        口径说明：期初/结转一律以 AccountPayable.amount_due（应付净额）为基础，而非税务 Invoice.total_amount
        （Invoice 无供应商 FK，无法按供应商汇总，旧实现据此查询是坏的）。amount_due 才是按供应商做账龄结转的
        正确口径；若财务要求改用发票毛额口径，请同步调整此处与对账明细的取数。
        """
        supplier_id = request.query_params.get('supplier')
        if not supplier_id:
            return Response({'error': '请提供供应商ID'}, status=status.HTTP_400_BAD_REQUEST)

        # 查找该供应商最近一期已确认的对账单
        last_reconciliation = (
            PurchaseReconciliation.objects.filter(supplier_id=supplier_id, status='CONFIRMED', is_deleted=False)
            .order_by('-period_end')
            .first()
        )

        if last_reconciliation:
            # 使用上期对账单的期末余额
            opening_balance = last_reconciliation.closing_balance or Decimal('0')

            # 减去上期对账单之后的付款金额（付款经 AP→供应商 关联，Payment 无 supplier/status 字段）
            payments_after = Payment.objects.filter(
                ap__supplier_id=supplier_id,
                payment_type='AP',
                payment_date__gt=last_reconciliation.period_end,
                is_deleted=False,
            ).aggregate(total=Sum('amount'))
            payments_after_amount = payments_after['total'] or Decimal('0')
            opening_balance = opening_balance - payments_after_amount

            # 加上上期对账单之后新增的应付金额（以 AccountPayable 为准，含真实供应商 FK 与发票日期；
            # 税务 Invoice 表无供应商关联，无法据以按供应商汇总）
            invoices_after = AccountPayable.objects.filter(
                supplier_id=supplier_id,
                invoice_date__gt=last_reconciliation.period_end,
                is_deleted=False,
            ).aggregate(total=Sum('amount_due'))
            invoices_after_amount = invoices_after['total'] or Decimal('0')
            opening_balance = opening_balance + invoices_after_amount

            source = 'last_reconciliation'
            last_period = f'{last_reconciliation.period_start} ~ {last_reconciliation.period_end}'
            details = {
                'last_closing_balance': float(last_reconciliation.closing_balance or 0),
                'payments_after': float(payments_after_amount),
                'invoices_after': float(invoices_after_amount),
            }
        else:
            # 没有历史对账单，计算应付账款余额
            payable = AccountPayable.objects.filter(supplier_id=supplier_id, is_deleted=False).aggregate(
                total_due=Sum('amount_due'), total_paid=Sum('amount_paid')
            )
            total_due = payable['total_due'] or Decimal('0')
            total_paid = payable['total_paid'] or Decimal('0')
            opening_balance = total_due - total_paid
            source = 'account_payable'
            last_period = None
            details = {'total_due': float(total_due), 'total_paid': float(total_paid)}

        return Response(
            {
                'opening_balance': float(opening_balance),
                'source': source,
                'last_period': last_period,
                'details': details,
            }
        )

    @action(detail=False, methods=['get'])
    def supplier_summary(self, request):
        """
        获取供应商对账汇总
        按供应商汇总应付账款、已付款、余额
        """
        from apps.masterdata.models import Supplier

        suppliers = (
            Supplier.objects.filter(is_deleted=False)
            .annotate(
                total_payable=Sum('payables__amount_due', filter=Q(payables__is_deleted=False)),
                total_paid=Sum('payables__amount_paid', filter=Q(payables__is_deleted=False)),
            )
            .values('id', 'name', 'code', 'total_payable', 'total_paid')
            .order_by('name')
        )

        result = []
        for s in suppliers:
            payable = s['total_payable'] or 0
            paid = s['total_paid'] or 0
            result.append(
                {
                    'id': s['id'],
                    'name': s['name'],
                    'code': s['code'],
                    'total_payable': float(payable),
                    'total_paid': float(paid),
                    'balance': float(payable - paid),
                }
            )

        return Response(result)


class SalesReconciliationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    销售收款对账单视图
    """

    queryset = SalesReconciliation.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'status']
    search_fields = ['reconciliation_no', 'customer__name']
    ordering_fields = ['period_start', 'created_at']
    ordering = ['-created_at']

    permission_module = 'finance'
    permission_resource = 'sales_reconciliation'

    def get_serializer_class(self):
        if self.action == 'list':
            return SalesReconciliationListSerializer
        return SalesReconciliationSerializer

    @action(detail=True, methods=['post'])
    def generate_lines(self, request, pk=None):
        """
        生成对账明细
        自动从销售订单、发货单、发票、收款记录中生成对账明细
        """
        reconciliation = self.get_object()

        if reconciliation.status not in ['DRAFT', 'PENDING']:
            return Response({'error': '只能对草稿或待确认状态的对账单生成明细'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.sales.models import DeliveryOrder, SalesOrder

        with transaction.atomic():
            reconciliation.lines.all().delete()

            running_balance = reconciliation.opening_balance
            total_order = Decimal('0')
            total_delivered = Decimal('0')
            total_invoice = Decimal('0')
            total_received = Decimal('0')

            # 1. 获取期间内的销售订单
            orders = SalesOrder.objects.filter(
                customer=reconciliation.customer,
                order_date__gte=reconciliation.period_start,
                order_date__lte=reconciliation.period_end,
                status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED'],
                is_deleted=False,
            ).order_by('order_date')

            for so in orders:
                order_amount = so.total_with_tax or so.total_amount or Decimal('0')
                total_order += order_amount

                # 计算订单数量和已发货数量
                order_qty = sum(line.qty for line in so.lines.filter(is_deleted=False))
                delivered_qty = Decimal('0')
                for delivery in so.deliveries.filter(status__in=['CONFIRMED', 'COMPLETED'], is_deleted=False):
                    for line in delivery.lines.filter(is_deleted=False):
                        delivered_qty += line.qty

                # 确定发货状态
                if delivered_qty == 0:
                    delivery_status = 'NOT_DELIVERED'
                elif delivered_qty >= order_qty:
                    delivery_status = 'DELIVERED'
                else:
                    delivery_status = 'PARTIAL'

                # 计算收款进度
                receivable_amount = order_amount
                received_amount = Decimal('0')
                # 从应收账款中获取该订单的收款情况
                for ar in AccountReceivable.objects.filter(so=so, is_deleted=False):
                    received_amount += ar.amount_paid or Decimal('0')

                collection_progress = Decimal('0')
                if receivable_amount > 0:
                    collection_progress = (received_amount / receivable_amount * 100).quantize(Decimal('0.01'))

                SalesReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='ORDER',
                    so=so,
                    reference_no=so.order_no,
                    reference_date=so.order_date,
                    debit_amount=order_amount,
                    credit_amount=0,
                    balance=running_balance + order_amount,
                    order_qty=order_qty,
                    delivered_qty=delivered_qty,
                    delivery_status=delivery_status,
                    receivable_amount=receivable_amount,
                    received_amount=received_amount,
                    collection_progress=collection_progress,
                    notes=f'销售订单 - {so.get_status_display()}',
                    created_by=request.user,
                )

            # 2. 获取期间内的发货单
            deliveries = DeliveryOrder.objects.filter(
                so__customer=reconciliation.customer,
                delivery_date__gte=reconciliation.period_start,
                delivery_date__lte=reconciliation.period_end,
                status__in=['CONFIRMED', 'COMPLETED'],
                is_deleted=False,
            ).order_by('delivery_date')

            for delivery in deliveries:
                # 计算发货金额 (数量 * 销售订单行单价)
                delivery_amount = Decimal('0')
                for line in delivery.lines.filter(is_deleted=False):
                    if hasattr(line, 'so_line') and line.so_line:
                        delivery_amount += line.qty * line.so_line.unit_price
                total_delivered += delivery_amount

                SalesReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='DELIVERY',
                    so=delivery.so,
                    reference_no=delivery.delivery_no,
                    reference_date=delivery.delivery_date,
                    debit_amount=delivery_amount,
                    credit_amount=0,
                    balance=running_balance,
                    notes='发货确认',
                    created_by=request.user,
                )

            # 3. 获取期间内的应收账款（发票）
            receivables = AccountReceivable.objects.filter(
                customer=reconciliation.customer,
                invoice_date__gte=reconciliation.period_start,
                invoice_date__lte=reconciliation.period_end,
                is_deleted=False,
            ).order_by('invoice_date')

            for ar in receivables:
                running_balance += ar.amount_due
                total_invoice += ar.amount_due

                SalesReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='INVOICE',
                    so=ar.so,
                    reference_no=ar.invoice_no or ar.ar_no,
                    reference_date=ar.invoice_date,
                    debit_amount=ar.amount_due,
                    credit_amount=0,
                    balance=running_balance,
                    notes='发票/应收',
                    created_by=request.user,
                )

            # 4. 获取期间内的收款记录
            payments = Payment.objects.filter(
                payment_type='AR',
                ar__customer=reconciliation.customer,
                payment_date__gte=reconciliation.period_start,
                payment_date__lte=reconciliation.period_end,
                is_deleted=False,
            ).order_by('payment_date')

            for payment in payments:
                running_balance -= payment.amount
                total_received += payment.amount

                SalesReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    line_type='RECEIPT',
                    reference_no=payment.payment_no,
                    reference_date=payment.payment_date,
                    debit_amount=0,
                    credit_amount=payment.amount,
                    balance=running_balance,
                    notes=f'收款 - {payment.get_payment_method_display()}',
                    created_by=request.user,
                )

            # 更新汇总金额
            reconciliation.total_order_amount = total_order
            reconciliation.total_delivered_amount = total_delivered
            reconciliation.total_invoice_amount = total_invoice
            reconciliation.total_received_amount = total_received
            reconciliation.reconciled_by = request.user
            reconciliation.reconciled_at = timezone.now()
            reconciliation.status = 'PENDING'
            reconciliation.save()

        return Response(SalesReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交对账单"""
        reconciliation = self.get_object()

        if reconciliation.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的对账单'}, status=status.HTTP_400_BAD_REQUEST)

        reconciliation.status = 'PENDING'
        reconciliation.save()

        return Response(SalesReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认对账单"""
        reconciliation = self.get_object()

        if reconciliation.status != 'PENDING':
            return Response({'error': '只能确认待确认状态的对账单'}, status=status.HTTP_400_BAD_REQUEST)

        reconciliation.status = 'CONFIRMED'
        reconciliation.confirmed_by = request.user
        reconciliation.confirmed_at = timezone.now()
        reconciliation.save()

        return Response(SalesReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'], url_path='confirm_delivery/(?P<line_id>[^/.]+)')
    def confirm_delivery(self, request, pk=None, line_id=None):
        """确认发货状态"""
        reconciliation = self.get_object()

        try:
            line = reconciliation.lines.get(id=line_id)
        except SalesReconciliationLine.DoesNotExist:
            return Response({'error': '明细不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 更新发货状态
        new_status = request.data.get('delivery_status')
        if new_status and new_status in ['NOT_DELIVERED', 'PARTIAL', 'DELIVERED', 'SIGNED']:
            line.delivery_status = new_status

        line.delivery_confirmed = True
        line.delivery_confirmed_at = timezone.now()

        # 可以更新发货数量
        if 'delivered_qty' in request.data:
            line.delivered_qty = Decimal(str(request.data.get('delivered_qty', 0)))

        line.save()

        return Response(SalesReconciliationLineSerializer(line).data)

    @action(detail=True, methods=['post'])
    def batch_confirm_delivery(self, request, pk=None):
        """批量确认发货状态"""
        reconciliation = self.get_object()

        line_ids = request.data.get('line_ids', [])
        if not line_ids:
            return Response({'error': '请选择要确认的明细'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            lines = reconciliation.lines.filter(id__in=line_ids, line_type='ORDER')
            for line in lines:
                line.delivery_confirmed = True
                line.delivery_confirmed_at = timezone.now()
                if line.delivery_status == 'NOT_DELIVERED':
                    line.delivery_status = 'DELIVERED'
                line.save()

        return Response({'message': f'已确认 {lines.count()} 条明细'})

    @action(detail=False, methods=['get'])
    def get_opening_balance(self, request):
        """
        获取客户期初余额
        计算逻辑：
        1. 如果有上期已确认对账单，以上期期末余额为基础
        2. 减去上期对账单期末日期之后的所有收款金额
        3. 如果没有历史对账单，则计算应收账款余额（应收-已收）
        """
        customer_id = request.query_params.get('customer')
        if not customer_id:
            return Response({'error': '请提供客户ID'}, status=status.HTTP_400_BAD_REQUEST)

        # 查找该客户最近一期已确认的对账单
        last_reconciliation = (
            SalesReconciliation.objects.filter(customer_id=customer_id, status='CONFIRMED', is_deleted=False)
            .order_by('-period_end')
            .first()
        )

        if last_reconciliation:
            # 使用上期对账单的期末余额
            opening_balance = last_reconciliation.closing_balance or Decimal('0')

            # 减去上期对账单之后的收款金额（收款经 AR→客户 关联，Payment 无 customer/status 字段）
            receipts_after = Payment.objects.filter(
                ar__customer_id=customer_id,
                payment_type='AR',
                payment_date__gt=last_reconciliation.period_end,
                is_deleted=False,
            ).aggregate(total=Sum('amount'))
            receipts_after_amount = receipts_after['total'] or Decimal('0')
            opening_balance = opening_balance - receipts_after_amount

            # 加上上期对账单之后新增的应收金额（以 AccountReceivable 为准，含真实客户 FK 与发票日期；
            # 税务 Invoice 表无客户关联，无法据以按客户汇总）
            invoices_after = AccountReceivable.objects.filter(
                customer_id=customer_id,
                invoice_date__gt=last_reconciliation.period_end,
                is_deleted=False,
            ).aggregate(total=Sum('amount_due'))
            invoices_after_amount = invoices_after['total'] or Decimal('0')
            opening_balance = opening_balance + invoices_after_amount

            source = 'last_reconciliation'
            last_period = f'{last_reconciliation.period_start} ~ {last_reconciliation.period_end}'
            details = {
                'last_closing_balance': float(last_reconciliation.closing_balance or 0),
                'receipts_after': float(receipts_after_amount),
                'invoices_after': float(invoices_after_amount),
            }
        else:
            # 没有历史对账单，计算应收账款余额
            receivable = AccountReceivable.objects.filter(customer_id=customer_id, is_deleted=False).aggregate(
                total_due=Sum('amount_due'), total_received=Sum('amount_paid')
            )
            total_due = receivable['total_due'] or Decimal('0')
            total_received = receivable['total_received'] or Decimal('0')
            opening_balance = total_due - total_received
            source = 'account_receivable'
            last_period = None
            details = {'total_due': float(total_due), 'total_received': float(total_received)}

        return Response(
            {
                'opening_balance': float(opening_balance),
                'source': source,
                'last_period': last_period,
                'details': details,
            }
        )

    @action(detail=False, methods=['get'])
    def customer_summary(self, request):
        """
        获取客户对账汇总
        """
        from apps.masterdata.models import Customer

        customers = (
            Customer.objects.filter(is_deleted=False)
            .annotate(
                total_receivable=Sum('receivables__amount_due', filter=Q(receivables__is_deleted=False)),
                total_received=Sum('receivables__amount_paid', filter=Q(receivables__is_deleted=False)),
            )
            .values('id', 'name', 'code', 'total_receivable', 'total_received')
            .order_by('name')
        )

        result = []
        for c in customers:
            receivable = c['total_receivable'] or 0
            received = c['total_received'] or 0
            result.append(
                {
                    'id': c['id'],
                    'name': c['name'],
                    'code': c['code'],
                    'total_receivable': float(receivable),
                    'total_received': float(received),
                    'balance': float(receivable - received),
                }
            )

        return Response(result)


class InvoiceReconciliationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    发票对账单视图
    """

    queryset = InvoiceReconciliation.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['invoice_type', 'status']
    search_fields = ['reconciliation_no']
    ordering_fields = ['period_start', 'created_at']
    ordering = ['-created_at']

    permission_module = 'finance'
    permission_resource = 'invoice_reconciliation'
    module_name = 'finance'

    def get_serializer_class(self):
        if self.action == 'list':
            return InvoiceReconciliationListSerializer
        return InvoiceReconciliationSerializer

    @action(detail=True, methods=['post'])
    def generate_lines(self, request, pk=None):
        """生成发票对账明细"""
        reconciliation = self.get_object()

        if reconciliation.status not in ['DRAFT', 'UNMATCHED', 'PARTIAL']:
            return Response({'error': '当前状态不允许生成明细'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            reconciliation.lines.all().delete()

            # 获取期间内的发票
            invoices = Invoice.objects.filter(
                invoice_type=reconciliation.invoice_type,
                invoice_date__gte=reconciliation.period_start,
                invoice_date__lte=reconciliation.period_end,
                is_deleted=False,
            ).order_by('invoice_date')

            total_count = 0
            total_amount = Decimal('0')
            total_tax = Decimal('0')
            matched_count = 0
            matched_amount = Decimal('0')

            for invoice in invoices:
                total_count += 1
                total_amount += invoice.total_amount
                total_tax += invoice.tax_amount

                # 尝试匹配订单
                matched_order_no = ''
                matched_order_amount = Decimal('0')
                match_status = 'UNMATCHED'

                if invoice.reference_id:
                    if reconciliation.invoice_type == 'INPUT':
                        # 进项发票匹配采购订单
                        from apps.purchase.models import PurchaseOrder

                        try:
                            po = PurchaseOrder.objects.get(id=invoice.reference_id)
                            matched_order_no = po.order_no
                            matched_order_amount = po.total_with_tax

                            diff = abs(invoice.total_amount - matched_order_amount)
                            if diff < Decimal('0.01'):
                                match_status = 'MATCHED'
                                matched_count += 1
                                matched_amount += invoice.total_amount
                            else:
                                match_status = 'PARTIAL'
                        except PurchaseOrder.DoesNotExist:
                            pass
                    else:
                        # 销项发票匹配销售订单
                        from apps.sales.models import SalesOrder

                        try:
                            so = SalesOrder.objects.get(id=invoice.reference_id)
                            matched_order_no = so.order_no
                            matched_order_amount = so.total_with_tax

                            diff = abs(invoice.total_amount - matched_order_amount)
                            if diff < Decimal('0.01'):
                                match_status = 'MATCHED'
                                matched_count += 1
                                matched_amount += invoice.total_amount
                            else:
                                match_status = 'PARTIAL'
                        except SalesOrder.DoesNotExist:
                            pass

                InvoiceReconciliationLine.objects.create(
                    reconciliation=reconciliation,
                    invoice_no=invoice.invoice_no,
                    invoice_date=invoice.invoice_date,
                    party_name=invoice.party_name,
                    tax_number=invoice.tax_number,
                    amount_before_tax=invoice.amount_before_tax,
                    tax_amount=invoice.tax_amount,
                    total_amount=invoice.total_amount,
                    matched_order_no=matched_order_no,
                    matched_order_amount=matched_order_amount,
                    match_status=match_status,
                    created_by=request.user,
                )

            # 更新汇总
            reconciliation.total_invoice_count = total_count
            reconciliation.total_invoice_amount = total_amount
            reconciliation.total_tax_amount = total_tax
            reconciliation.matched_count = matched_count
            reconciliation.matched_amount = matched_amount
            reconciliation.unmatched_count = total_count - matched_count
            reconciliation.unmatched_amount = total_amount - matched_amount

            if matched_count == total_count:
                reconciliation.status = 'MATCHED'
            elif matched_count > 0:
                reconciliation.status = 'PARTIAL'
            else:
                reconciliation.status = 'UNMATCHED'

            reconciliation.reconciled_by = request.user
            reconciliation.reconciled_at = timezone.now()
            reconciliation.save()

        return Response(InvoiceReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认对账单"""
        reconciliation = self.get_object()

        if reconciliation.status not in ['MATCHED', 'PARTIAL']:
            return Response({'error': '只能确认已匹配或部分匹配的对账单'}, status=status.HTTP_400_BAD_REQUEST)

        reconciliation.status = 'CONFIRMED'
        reconciliation.save()

        return Response(InvoiceReconciliationSerializer(reconciliation).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        获取发票汇总
        """
        invoice_type = request.query_params.get('invoice_type', 'INPUT')
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        filters = Q(is_deleted=False, invoice_type=invoice_type)
        if year:
            filters &= Q(invoice_date__year=year)
        if month:
            filters &= Q(invoice_date__month=month)

        invoices = Invoice.objects.filter(filters)

        summary = invoices.aggregate(
            total_count=Sum('id', filter=Q()),  # 使用 Count 更准确
            total_amount=Sum('total_amount'),
            total_tax=Sum('tax_amount'),
        )

        return Response(
            {
                'invoice_type': invoice_type,
                'total_count': invoices.count(),
                'total_amount': float(summary['total_amount'] or 0),
                'total_tax': float(summary['total_tax'] or 0),
            }
        )
