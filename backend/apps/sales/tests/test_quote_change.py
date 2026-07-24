"""报价改版数据保全 + 版本谱系 + 销售订单变更单 回归测试。

覆盖审计整改点:
1. create_new_version 改版必须完整复制非标明细字段 (custom_name/custom_spec/custom_unit),
   不再丢失产品名称/规格/单位; 并记录版本谱系 parent_quote。
2. SalesOrderChange 审批 (approve) 后在同一事务内 guarded 地作用到销售订单,
   并写入变更前/后快照与生效时间。

风格对齐 apps/sales/tests/test_invoice_chain.py (TestCase + 关 ES 同步 + APIClient)。
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class QuotationNewVersionTest(TestCase):
    """报价改版: 非标明细字段保全 + 版本谱系。"""

    def setUp(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User
        from apps.masterdata.models import Customer
        from apps.sales.models import SalesQuotation, SalesQuotationLine

        self.user = User.objects.create(
            username='qtver', employee_id='QTVER1', is_staff=True, is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.customer = Customer.objects.create(code='QVC1', name='改版报价客户')
        self.quote = SalesQuotation.objects.create(
            customer=self.customer,
            valid_until=date.today() + timedelta(days=30),
            tax_rate=13,
            version=1,
            notes='首版报价',
            created_by=self.user,
        )
        # 非标定制明细: 无物料, 全靠 custom_* 承载产品信息
        self.line = SalesQuotationLine.objects.create(
            quotation=self.quote,
            item=None,
            custom_name='定制夹具组件',
            custom_spec='按图纸 ABC-001 加工',
            custom_unit='套',
            qty=Decimal('2'),
            unit_price=Decimal('5000.00'),
            notes='含表面处理',
            created_by=self.user,
        )
        # 触发金额汇总
        self.quote.total_amount = Decimal('10000.00')
        self.quote.save()

    def test_create_new_version_preserves_custom_fields_and_sets_parent(self):
        from apps.sales.models import SalesQuotation

        resp = self.client.post(f'/api/sales/quotations/{self.quote.id}/create_new_version/')
        self.assertEqual(resp.status_code, 201, resp.data)

        new_id = resp.data['id']
        self.assertNotEqual(new_id, self.quote.id)

        new_quote = SalesQuotation.objects.get(id=new_id)
        # 版本谱系
        self.assertEqual(new_quote.parent_quote_id, self.quote.id)
        self.assertEqual(new_quote.version, 2)
        # 从父版本继承税率/备注, 金额/税额重算
        self.assertEqual(new_quote.tax_rate, 13)
        self.assertEqual(new_quote.total_amount, Decimal('10000.00'))
        self.assertEqual(new_quote.tax_amount, Decimal('1300.00'))
        self.assertEqual(new_quote.total_with_tax, Decimal('11300.00'))

        # 关键: 非标字段完整复制, 不丢名称/规格/单位
        new_line = new_quote.lines.filter(is_deleted=False).first()
        self.assertIsNotNone(new_line)
        self.assertIsNone(new_line.item)
        self.assertEqual(new_line.custom_name, '定制夹具组件')
        self.assertEqual(new_line.custom_spec, '按图纸 ABC-001 加工')
        self.assertEqual(new_line.custom_unit, '套')
        self.assertEqual(new_line.qty, Decimal('2'))
        self.assertEqual(new_line.unit_price, Decimal('5000.00'))
        self.assertEqual(new_line.line_amount, Decimal('10000.00'))

        # 父版本 child_versions 反向可达
        self.assertIn(new_quote.id, self.quote.child_versions.values_list('id', flat=True))


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class SalesOrderChangeApplyTest(TestCase):
    """销售订单变更单: 审批作用到订单 + guard。

    通过 APIRequestFactory 直接驱动 SalesOrderChangeViewSet 的 submit/approve action,
    不依赖 urls.py 的路由注册 (路由注册由集成方按 integration_notes 完成)。
    """

    def setUp(self):
        from apps.accounts.models import User
        from apps.masterdata.models import Customer
        from apps.sales.models import SalesOrder, SalesOrderLine

        self.user = User.objects.create(
            username='socusr', employee_id='SOC1', is_staff=True, is_superuser=True
        )

        self.customer = Customer.objects.create(code='SOCC1', name='变更单客户')
        self.so = SalesOrder.objects.create(
            customer=self.customer,
            delivery_date=date.today() + timedelta(days=20),
            status='CONFIRMED',
            tax_rate=13,
            total_amount=Decimal('10000.00'),
            tax_amount=Decimal('1300.00'),
            total_with_tax=Decimal('11300.00'),
            created_by=self.user,
        )
        self.line = SalesOrderLine.objects.create(
            so=self.so,
            item=None,
            custom_name='定制机架',
            custom_spec='SPEC-XYZ',
            custom_unit='台',
            qty=Decimal('2'),
            unit_price=Decimal('5000.00'),
            line_amount=Decimal('10000.00'),
            created_by=self.user,
        )

    def _call(self, action_name, change_id):
        """经 ViewSet action 调用 (submit/approve/reject),返回 DRF Response。"""
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.sales.change_order import SalesOrderChangeViewSet

        factory = APIRequestFactory()
        request = factory.post(f'/_/{change_id}/{action_name}/')
        force_authenticate(request, user=self.user)
        view = SalesOrderChangeViewSet.as_view({'post': action_name})
        return view(request, pk=change_id)

    def test_price_change_approve_applies_to_order(self):
        from apps.sales.change_order import SalesOrderChange

        change = SalesOrderChange.objects.create(
            sales_order=self.so,
            change_type='PRICE',
            reason='客户议价',
            change_data={'so_line': self.line.id, 'unit_price': '6000.00'},
            created_by=self.user,
        )
        self.assertTrue(change.change_no.startswith('SOC'))

        # 先提交再审批
        r_submit = self._call('submit', change.id)
        self.assertEqual(r_submit.status_code, 200, getattr(r_submit, 'data', None))
        change.refresh_from_db()
        self.assertEqual(change.status, 'PENDING')

        r_approve = self._call('approve', change.id)
        self.assertEqual(r_approve.status_code, 200, getattr(r_approve, 'data', None))

        change.refresh_from_db()
        self.assertEqual(change.status, 'APPROVED')
        self.assertIsNotNone(change.applied_at)
        # 前后快照均已写入
        self.assertTrue(change.before_data)
        self.assertTrue(change.after_data)

        # 订单明细单价 + 行金额被改写, 订单金额重算
        self.line.refresh_from_db()
        self.assertEqual(self.line.unit_price, Decimal('6000.00'))
        self.assertEqual(self.line.line_amount, Decimal('12000.00'))

        self.so.refresh_from_db()
        self.assertEqual(self.so.total_amount, Decimal('12000.00'))
        self.assertEqual(self.so.tax_amount, Decimal('1560.00'))
        self.assertEqual(self.so.total_with_tax, Decimal('13560.00'))

    def test_add_change_creates_line(self):
        from apps.sales.change_order import SalesOrderChange

        change = SalesOrderChange.objects.create(
            sales_order=self.so,
            change_type='ADD',
            change_data={
                'custom_name': '追加配件',
                'custom_spec': 'PART-9',
                'custom_unit': '件',
                'qty': '3',
                'unit_price': '1000.00',
            },
            created_by=self.user,
        )
        r = self._call('approve', change.id)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))

        self.so.refresh_from_db()
        # 原 10000 + 新增 3000 = 13000
        self.assertEqual(self.so.total_amount, Decimal('13000.00'))
        names = list(self.so.lines.filter(is_deleted=False).values_list('custom_name', flat=True))
        self.assertIn('追加配件', names)

    def test_qty_change_below_delivered_is_rejected(self):
        from apps.sales.change_order import SalesOrderChange

        # 该明细已发货 1 台
        self.line.delivered_qty = Decimal('1')
        self.line.save()

        change = SalesOrderChange.objects.create(
            sales_order=self.so,
            change_type='QTY',
            change_data={'so_line': self.line.id, 'qty': '0.5'},
            created_by=self.user,
        )
        r = self._call('approve', change.id)
        self.assertEqual(r.status_code, 400, getattr(r, 'data', None))

        change.refresh_from_db()
        self.assertNotEqual(change.status, 'APPROVED')
        # 订单明细数量未被改写
        self.line.refresh_from_db()
        self.assertEqual(self.line.qty, Decimal('2'))

    def test_change_on_draft_order_is_rejected(self):
        from apps.sales.change_order import SalesOrderChange

        self.so.status = 'DRAFT'
        self.so.save()

        change = SalesOrderChange.objects.create(
            sales_order=self.so,
            change_type='PRICE',
            change_data={'so_line': self.line.id, 'unit_price': '7000.00'},
            created_by=self.user,
        )
        r = self._call('approve', change.id)
        self.assertEqual(r.status_code, 400, getattr(r, 'data', None))
