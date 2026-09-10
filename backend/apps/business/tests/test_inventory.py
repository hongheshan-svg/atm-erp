from decimal import Decimal

from django.test import TestCase

from apps.business.models import Entry, Stock, StockMove, Task

from .test_commercial_chain import BusinessFixtures


class InventoryTests(BusinessFixtures, TestCase):
    def test_stock_search_and_material_filters_preserve_money_permissions(self):
        self.item.specification = '750W'
        self.item.brand = '伺服品牌'
        self.item.part_type = 'standard'
        self.item.save()
        stock = self.open_stock()
        response = self.clients['warehouse'].get(
            '/api/business/stocks/',
            {'search': '750W', 'item__brand': '伺服品牌', 'item__part_type': 'standard', 'location': stock.location},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['specification'], '750W')
        self.assertEqual(row['brand'], '伺服品牌')
        self.assertEqual(row['unit'], self.item.unit)
        self.assertNotIn('value', row)
        self.assertEqual(
            self.clients['warehouse'].get('/api/business/stocks/', {'item__part_type': 'custom'}).data['count'], 0
        )

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '5'}],
            },
        )

    def open_stock(self, quantity='5', unit_cost='20'):
        self.post(
            'admin',
            'stocks/opening/',
            {'item': self.item.pk, 'quantity': quantity, 'unit_cost': unit_cost, 'reason': '期初确认'},
        )
        return Stock.objects.get(item=self.item)

    def issue(self, stock, quantity, status=200):
        return self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': stock.pk, 'quantity': quantity, 'reason': '生产领料'},
            status=status,
        )

    def test_moving_average_returns_and_supplier_credit_are_distinct(self):
        stock = self.open_stock()
        purchase = self.purchase(self.project)
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': '5'}], 'reason': '采购入库'},
        )
        issue_id = self.issue(stock, '4')['id']
        self.post('warehouse', f'moves/{issue_id}/return-material/', {'quantity': '1', 'reason': '余料退仓'})
        receipt = StockMove.objects.get(kind='receipt')
        return_id = self.post(
            'warehouse', f'moves/{receipt.pk}/return-purchase/', {'quantity': '2', 'reason': '供应商确认退货'}
        )['id']
        returned = StockMove.objects.get(pk=return_id)
        self.assertEqual(returned.value, Decimal('-120.00'))
        self.assertEqual(returned.supplier_credit, Decimal('200.00'))
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, stock.value), (Decimal('5'), Decimal('300')))
        self.assertEqual(Entry.objects.get(purchase=purchase).credit_amount, Decimal('200'))
        cost = self.clients['finance'].get(f'/api/business/projects/{self.project.pk}/cost/').data
        self.assertEqual(
            cost,
            {
                'materials': '180.00',
                'purchase_return_variance': '-80.00',
                'labor': '0.00',
                'expenses': '0.00',
                'total': '100.00',
            },
        )
        self.post(
            'warehouse',
            f'moves/{receipt.pk}/return-purchase/',
            {'quantity': '4', 'reason': '超过原可退余量'},
            status=409,
        )

    def test_issue_is_bounded_by_stock_and_bom(self):
        stock = self.open_stock(quantity='3')
        self.issue(stock, '4', status=409)
        self.assertFalse(StockMove.objects.filter(kind='issue').exists())
        self.issue(stock, '3')
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, stock.value), (Decimal('0'), Decimal('0')))
        self.issue(stock, '3', status=409)

    def test_material_return_cannot_exceed_original_issue(self):
        stock = self.open_stock()
        issue_id = self.issue(stock, '3')['id']
        self.post('warehouse', f'moves/{issue_id}/return-material/', {'quantity': '2', 'reason': '退料'})
        self.post('warehouse', f'moves/{issue_id}/return-material/', {'quantity': '2', 'reason': '超退'}, status=409)
        self.post('warehouse', f'moves/{issue_id}/return-material/', {'quantity': '1', 'reason': '剩余退料'})
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, stock.value), (Decimal('5'), Decimal('100')))

    def test_opening_is_admin_only_and_cannot_be_repeated(self):
        self.post(
            'warehouse',
            'stocks/opening/',
            {'item': self.item.pk, 'quantity': '5', 'unit_cost': '20', 'reason': '越权'},
            status=403,
        )
        self.open_stock()
        self.post(
            'admin',
            'stocks/opening/',
            {'item': self.item.pk, 'quantity': '5', 'unit_cost': '20', 'reason': '重复期初'},
            status=409,
        )
        self.assertEqual(StockMove.objects.count(), 1)

    def test_count_rejects_stale_snapshot_and_preserves_average_cost(self):
        stock = self.open_stock()
        before = stock.updated_at.isoformat()
        self.issue(stock, '1')
        self.post(
            'warehouse',
            f'stocks/{stock.pk}/count/',
            {'quantity': '3', 'expected_quantity': '5', 'expected_updated_at': before, 'reason': '旧盘点'},
            status=409,
        )
        stock.refresh_from_db()
        self.post(
            'warehouse',
            f'stocks/{stock.pk}/count/',
            {
                'quantity': '3',
                'expected_quantity': '4',
                'expected_updated_at': stock.updated_at.isoformat(),
                'reason': '实盘三件',
            },
        )
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, stock.value), (Decimal('3'), Decimal('60')))
        move = StockMove.objects.get(kind='count')
        self.assertEqual((move.quantity, move.value), (Decimal('-1'), Decimal('-20')))

    def test_zero_stock_gain_requires_admin_cost(self):
        stock = Stock.objects.create(item=self.item)
        payload = {
            'quantity': '1',
            'expected_quantity': '0',
            'expected_updated_at': stock.updated_at.isoformat(),
            'unit_cost': '25',
            'reason': '发现未登记物料',
        }
        self.post('warehouse', f'stocks/{stock.pk}/count/', payload, status=403)
        self.post('admin', f'stocks/{stock.pk}/count/', payload)
        stock.refresh_from_db()
        self.assertEqual(stock.value, Decimal('25'))

    def test_warranty_issue_requires_own_active_service_task(self):
        stock = self.open_stock()
        self.project.status = 'warranty'
        self.project.save()
        self.issue(stock, '1', status=400)
        task = Task.objects.create(
            project=self.project, title='现场维修', kind='service', assignee=self.users['member']
        )
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': stock.pk, 'task': task.pk, 'quantity': '1', 'reason': '售后换件'},
        )
        self.assertEqual(StockMove.objects.get(kind='issue').task_id, task.pk)

    def test_warehouse_stock_responses_do_not_expose_costs(self):
        stock = self.open_stock()
        response = self.clients['warehouse'].get(f'/api/business/stocks/{stock.pk}/')
        self.assertNotIn('value', response.data)
        response = self.clients['warehouse'].get('/api/business/moves/')
        self.assertNotIn('value', response.data['results'][0])
        self.assertNotIn('supplier_credit', response.data['results'][0])
