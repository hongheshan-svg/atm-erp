"""发货 → 开票 → 应收 事件驱动勾稽链 回归测试。

覆盖审计整改点:
1. 发货完成触发销项发票草稿生成(Invoice 勾稽 SO + 发货单),金额/明细正确。
2. 开票幂等:同一发货单重复触发只生成一张发票。
3. 发票开出/确认激活 '发货款'(ON_DELIVERY) 付款节点:应收到位 + 节点 due_date=今天,
   以事件驱动替代纯日期偏移;应收不重复创建。

风格对齐 apps/finance/tests/test_p1_finance_fixes.py(TestCase + 关 ES 同步)。
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class DeliveryInvoiceChainServiceTest(TestCase):
    """服务层:create_invoice_from_delivery / ensure_ar_and_activate_milestone。"""

    def setUp(self):
        from apps.accounts.models import User
        from apps.masterdata.models import Customer, Item, Warehouse
        from apps.sales.models import (
            DeliveryOrder,
            DeliveryOrderLine,
            SalesOrder,
            SalesOrderLine,
        )

        self.user = User.objects.create(username='invchain', employee_id='INV1')
        self.customer = Customer.objects.create(code='INVC1', name='开票客户', tax_number='TAX123456')
        self.warehouse = Warehouse.objects.create(code='INVWH1', name='开票仓库')
        self.item = Item.objects.create(sku='INV-ITEM-1', name='联轴器', specification='D=20')

        # 未来交期:证明激活后 ON_DELIVERY 节点 due_date 由 delivery_date 改为今天
        self.future_delivery = timezone.now().date() + timedelta(days=30)
        self.so = SalesOrder.objects.create(
            customer=self.customer,
            delivery_date=self.future_delivery,
            status='CONFIRMED',
            tax_rate=13,
            total_amount=Decimal('200.00'),
            tax_amount=Decimal('26.00'),
            total_with_tax=Decimal('226.00'),
            payment_terms='M_30_30_40',
            created_by=self.user,
        )
        self.so_line = SalesOrderLine.objects.create(
            so=self.so,
            item=self.item,
            qty=Decimal('2'),
            unit_price=Decimal('100.00'),
            delivered_qty=Decimal('2'),
            created_by=self.user,
        )
        self.delivery = DeliveryOrder.objects.create(
            so=self.so,
            warehouse=self.warehouse,
            delivery_date=self.future_delivery,
            status='PROJECT_CONFIRMING',
            created_by=self.user,
        )
        self.delivery_line = DeliveryOrderLine.objects.create(
            delivery=self.delivery,
            so_line=self.so_line,
            item=self.item,
            qty=Decimal('2'),
            created_by=self.user,
        )

    def test_create_invoice_links_so_delivery_and_amounts(self):
        from apps.finance.services import create_invoice_from_delivery

        invoice = create_invoice_from_delivery(self.delivery, self.user)

        self.assertIsNotNone(invoice)
        # 结构化勾稽
        self.assertEqual(invoice.sales_order_id, self.so.id)
        self.assertEqual(invoice.delivery_order_id, self.delivery.id)
        self.assertEqual(invoice.reference_type, 'SALES_ORDER')
        self.assertEqual(invoice.reference_id, self.so.id)
        self.assertEqual(invoice.invoice_type, 'OUTPUT')
        # 金额(Decimal):2 * 100 = 200 不含税,13% 税 = 26,价税合计 226
        self.assertEqual(invoice.amount_before_tax, Decimal('200.00'))
        self.assertEqual(invoice.tax_amount, Decimal('26.00'))
        self.assertEqual(invoice.total_amount, Decimal('226.00'))
        self.assertEqual(invoice.buyer_tax_no, 'TAX123456')
        # 明细:一条,数量/单价取自发货 + SO 明细
        items = list(invoice.items.filter(is_deleted=False))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].quantity, Decimal('2'))
        self.assertEqual(items[0].unit_price, Decimal('100.00'))
        self.assertEqual(items[0].amount, Decimal('200.00'))
        self.assertEqual(items[0].item_name, '联轴器')

    def test_create_invoice_is_idempotent(self):
        from apps.finance.models import Invoice
        from apps.finance.services import create_invoice_from_delivery

        first = create_invoice_from_delivery(self.delivery, self.user)
        second = create_invoice_from_delivery(self.delivery, self.user)

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            Invoice.objects.filter(delivery_order=self.delivery, is_deleted=False).count(),
            1,
        )

    def test_no_lines_returns_none(self):
        from apps.finance.services import create_invoice_from_delivery
        from apps.sales.models import DeliveryOrder

        empty = DeliveryOrder.objects.create(
            so=self.so,
            warehouse=self.warehouse,
            delivery_date=self.future_delivery,
            status='PROJECT_CONFIRMING',
            created_by=self.user,
        )
        self.assertIsNone(create_invoice_from_delivery(empty, self.user))

    def test_issue_activates_delivery_milestone_and_reuses_ar(self):
        from apps.finance.models import AccountReceivable, PaymentSchedule
        from apps.finance.services import (
            create_invoice_from_delivery,
            ensure_ar_and_activate_milestone,
        )
        from apps.sales.services import create_sales_order_receivables

        # 模拟 SO 确认:已建应收 + 付款计划(含 ON_DELIVERY 节点)
        create_sales_order_receivables(self.so, self.user)
        ar_before = AccountReceivable.objects.filter(so=self.so, is_deleted=False).count()
        self.assertEqual(ar_before, 1)

        milestone = PaymentSchedule.objects.get(
            sales_order=self.so, milestone_type='ON_DELIVERY', is_deleted=False
        )
        # 激活前:due_date 来自 delivery_date(纯日期偏移),不是今天
        self.assertEqual(milestone.due_date, self.future_delivery)

        invoice = create_invoice_from_delivery(self.delivery, self.user)
        ar = ensure_ar_and_activate_milestone(invoice, self.user)

        # 应收未被重复创建,发票号已回填
        self.assertEqual(
            AccountReceivable.objects.filter(so=self.so, is_deleted=False).count(), 1
        )
        self.assertEqual(ar.invoice_no, invoice.invoice_no)

        # '发货款' 节点被事件驱动激活:due_date=今天,并挂接应收
        milestone.refresh_from_db()
        self.assertEqual(milestone.due_date, timezone.now().date())
        self.assertEqual(milestone.account_receivable_id, ar.id)

    def test_ensure_creates_ar_when_absent(self):
        from apps.finance.models import AccountReceivable
        from apps.finance.services import (
            create_invoice_from_delivery,
            ensure_ar_and_activate_milestone,
        )

        # 未预先建应收:ensure 应补建一张(不依赖 SO 确认已跑过)
        self.assertFalse(AccountReceivable.objects.filter(so=self.so, is_deleted=False).exists())
        invoice = create_invoice_from_delivery(self.delivery, self.user)
        ar = ensure_ar_and_activate_milestone(invoice, self.user)

        self.assertIsNotNone(ar)
        self.assertEqual(AccountReceivable.objects.filter(so=self.so, is_deleted=False).count(), 1)
        self.assertEqual(ar.so_id, self.so.id)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class DeliveryCompletionInvoiceApiTest(TestCase):
    """API 层:项目确认完成 → 自动生成开票草稿;create_invoice 手动动作幂等。"""

    def setUp(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User
        from apps.masterdata.models import Customer, Item, Warehouse
        from apps.sales.models import (
            DeliveryOrder,
            DeliveryOrderLine,
            SalesOrder,
            SalesOrderLine,
        )

        self.user = User.objects.create(
            username='invapi', employee_id='INVAPI1', is_staff=True, is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.customer = Customer.objects.create(code='INVAPIC', name='API开票客户')
        self.warehouse = Warehouse.objects.create(code='INVAPIWH', name='API仓库')
        self.item = Item.objects.create(sku='INVAPI-ITEM', name='API物料')
        self.so = SalesOrder.objects.create(
            customer=self.customer,
            delivery_date=timezone.now().date() + timedelta(days=10),
            status='CONFIRMED',
            tax_rate=13,
            total_amount=Decimal('300.00'),
            tax_amount=Decimal('39.00'),
            total_with_tax=Decimal('339.00'),
            created_by=self.user,
        )
        self.so_line = SalesOrderLine.objects.create(
            so=self.so, item=self.item, qty=Decimal('3'), unit_price=Decimal('100.00'),
            delivered_qty=Decimal('3'), created_by=self.user,
        )
        self.delivery = DeliveryOrder.objects.create(
            so=self.so, warehouse=self.warehouse,
            delivery_date=timezone.now().date() + timedelta(days=10),
            status='PROJECT_CONFIRMING', created_by=self.user,
        )
        DeliveryOrderLine.objects.create(
            delivery=self.delivery, so_line=self.so_line, item=self.item,
            qty=Decimal('3'), created_by=self.user,
        )

    def test_project_confirm_generates_draft_invoice(self):
        from apps.finance.models import Invoice

        resp = self.client.post(f'/api/sales/deliveries/{self.delivery.id}/project_confirm/')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, 'COMPLETED')

        invoices = Invoice.objects.filter(delivery_order=self.delivery, is_deleted=False)
        self.assertEqual(invoices.count(), 1)
        self.assertEqual(invoices.first().sales_order_id, self.so.id)
        self.assertEqual(invoices.first().total_amount, Decimal('339.00'))

    def test_create_invoice_action_is_idempotent(self):
        from apps.finance.models import Invoice

        r1 = self.client.post(f'/api/sales/deliveries/{self.delivery.id}/create_invoice/')
        r2 = self.client.post(f'/api/sales/deliveries/{self.delivery.id}/create_invoice/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r1.data['invoice_id'], r2.data['invoice_id'])
        self.assertEqual(
            Invoice.objects.filter(delivery_order=self.delivery, is_deleted=False).count(), 1
        )
