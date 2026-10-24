from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.business.models import BOMLine, Item, PurchaseLine, PurchaseOrder, Stock, StockMove
from apps.business.services import bom_import
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class BOMSelectionTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def test_classification_maintenance_and_demand_use_one_source(self):
        self.post('purchaser', 'items/', {'name': '分类件', 'brand': 'SMC', 'part_type': 'standard'}, status=201)
        item = Item.objects.get(name='分类件')
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': item.pk, 'quantity': '2', 'assembly_unit': '上料单元'}],
            },
        )
        response = self.clients['purchaser'].get(f'/api/business/projects/{self.project.pk}/demand/')
        line = response.data['lines'][0]
        self.assertEqual((line['brand'], line['part_type'], line['assembly_unit']), ('SMC', 'standard', '上料单元'))
        response = self.clients['purchaser'].patch(
            f'/api/business/items/{item.pk}/', {'brand': 'FESTO'}, format='json', HTTP_IDEMPOTENCY_KEY='brand-change'
        )
        self.assertEqual(response.status_code, 200, response.data)
        response = self.clients['purchaser'].get(f'/api/business/projects/{self.project.pk}/demand/')
        self.assertEqual(response.data['lines'][0]['brand'], 'FESTO')
        self.post('purchaser', 'items/', {'name': '非法类别', 'part_type': 'invalid'}, status=400)

    def test_subset_purchase_does_not_order_unselected_or_overbuy(self):
        other = Item.objects.create(code='I2', name='非标', part_type='custom')
        first = BOMLine.objects.create(project=self.project, item=self.item, quantity=2, assembly_unit='上料')
        second = BOMLine.objects.create(project=self.project, item=other, quantity=3, assembly_unit='检测')
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'from_demand': True,
            'lines': [{'item': self.item.pk, 'bom_line': first.pk, 'quantity': '2', 'unit_price': '1'}],
        }
        result = self.post('purchaser', 'purchases/', data, status=201)
        order = PurchaseOrder.objects.get(pk=result['id'])
        self.assertEqual(list(order.lines.values_list('bom_line_id', flat=True)), [first.pk])
        self.assertFalse(PurchaseLine.objects.filter(bom_line=second).exists())
        self.post('purchaser', 'purchases/', data, status=409)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        data['lines'][0]['bom_line'] = second.pk
        self.post('purchaser', 'purchases/', data, status=404)

    def test_invalid_bom_reference_shape_does_not_change_existing_purchase(self):
        bom = BOMLine.objects.create(project=self.project, item=self.item, quantity=10, assembly_unit='上料')
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'from_demand': True,
            'lines': [{'item': self.item.pk, 'bom_line': str(bom.pk), 'quantity': '2', 'unit_price': '12.34'}],
        }
        created = self.post('purchaser', 'purchases/', data, status=201)
        order = PurchaseOrder.objects.get(pk=created['id'])
        self.assertEqual(order.status, 'draft')
        self.assertEqual(order.lines.get().bom_line_id, bom.pk)
        orders = list(PurchaseOrder.objects.values())
        lines = list(PurchaseLine.objects.values())
        receipts = ActionReceipt.objects.count()
        audits = AuditLog.objects.count()
        counter = CodeRule.objects.get(key='purchase').counter
        for reference in ([], {}):
            with self.subTest(reference=reference):
                result = self.post(
                    'purchaser',
                    'purchases/',
                    {**data, 'lines': [{**data['lines'][0], 'bom_line': reference}]},
                    status=400,
                )
                self.assertIn('bom_line', result)
                self.assertEqual(list(PurchaseOrder.objects.values()), orders)
                self.assertEqual(list(PurchaseLine.objects.values()), lines)
                self.assertEqual(ActionReceipt.objects.count(), receipts)
                self.assertEqual(AuditLog.objects.count(), audits)
                self.assertEqual(CodeRule.objects.get(key='purchase').counter, counter)

    def test_bom_units_import_legacy_preservation_and_revision(self):
        raw = f'物料编码,数量,变更说明,单元\n{self.item.code},2,初版,上料单元\n'.encode()
        preview = bom_import.preview(self.project, SimpleUploadedFile('bom.csv', raw))
        self.assertTrue(preview['can_import'])
        line = preview['lines'][0]
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': preview['expected_revision'],
                'lines': [{key: line[key] for key in ['item', 'quantity', 'change_note', 'assembly_unit']}],
            },
        )
        old = bom_import.preview(
            self.project, SimpleUploadedFile('bom.csv', f'物料编码,数量,变更说明\n{self.item.code},2,调整\n'.encode())
        )
        self.assertEqual(old['lines'][0]['assembly_unit'], '上料单元')
        previous = self.bom_version(self.project.pk)
        data = {
            'expected_revision': previous,
            'lines': [{'item': self.item.pk, 'quantity': '2', 'change_note': '移至检测', 'assembly_unit': '检测单元'}],
        }
        self.post('manager', f'projects/{self.project.pk}/revise-bom/', data)
        self.assertNotEqual(self.bom_version(self.project.pk), previous)
        self.post('manager', f'projects/{self.project.pk}/revise-bom/', data, status=409)

    def test_revise_bom_with_id_and_omitted_unit_keeps_multi_unit_line_unit(self):
        upper = BOMLine.objects.create(project=self.project, item=self.item, quantity=2, assembly_unit='上料')
        BOMLine.objects.create(project=self.project, item=self.item, quantity=3, assembly_unit='下料')
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'id': upper.pk, 'item': self.item.pk, 'quantity': '4', 'change_note': '只改用量'}],
            },
        )
        upper.refresh_from_db()
        self.assertEqual((upper.quantity, upper.assembly_unit), (4, '上料'))
        self.assertEqual(BOMLine.objects.filter(project=self.project).count(), 2)

    def test_revise_bom_with_id_and_explicit_blank_unit_clears_unit(self):
        upper = BOMLine.objects.create(project=self.project, item=self.item, quantity=2, assembly_unit='上料')
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [
                    {
                        'id': upper.pk,
                        'item': self.item.pk,
                        'quantity': '2',
                        'assembly_unit': '',
                        'change_note': '清空单元',
                    }
                ],
            },
        )
        upper.refresh_from_db()
        self.assertEqual(upper.assembly_unit, '')


class MultiUnitReceiptAttributionTests(BusinessFixtures, TestCase):
    """同物料多单元：关联 BOM 行的已收（扣除退货）先归属原行，单行上限计入已收。"""

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [
                    {'item': self.item.pk, 'quantity': '10', 'assembly_unit': '上料'},
                    {'item': self.item.pk, 'quantity': '10', 'assembly_unit': '检测'},
                ],
            },
        )
        self.feed = BOMLine.objects.get(project=self.project, assembly_unit='上料')
        self.check = BOMLine.objects.get(project=self.project, assembly_unit='检测')

    def demand(self):
        response = self.clients['purchaser'].get(f'/api/business/projects/{self.project.pk}/demand/')
        self.assertEqual(response.status_code, 200, response.data)
        return {row['bom_line']: row for row in response.data['lines']}

    def shortage(self, rows):
        return {unit: Decimal(rows[line.pk]['shortage']) for unit, line in (('上料', self.feed), ('检测', self.check))}

    def buy(self, bom, qty, *, from_demand=True, status=201):
        result = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'from_demand': from_demand,
                'lines': [{'item': self.item.pk, 'bom_line': bom.pk, 'quantity': qty, 'unit_price': '5'}],
            },
            status=status,
        )
        if status != 201:
            return result
        purchase = PurchaseOrder.objects.get(pk=result['id'])
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        self.post('manager', f'purchases/{purchase.pk}/approve/')
        return purchase

    def receive(self, purchase, qty):
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': qty}], 'reason': '到货'},
        )

    def test_receive_then_issue_keeps_received_quantity_on_its_bom_line(self):
        purchase = self.buy(self.check, '10')
        self.assertEqual(self.shortage(self.demand()), {'上料': Decimal('10'), '检测': Decimal('0')})
        self.receive(purchase, '10')
        rows = self.demand()
        self.assertEqual(self.shortage(rows), {'上料': Decimal('10'), '检测': Decimal('0')})
        self.assertEqual(Decimal(rows[self.check.pk]['available']), Decimal('10'))
        # 检测行已收满，再按检测行下单（缺料或手工关联）都被拒绝，不能累计到 20。
        self.buy(self.check, '1', status=409)
        self.buy(self.check, '1', from_demand=False, status=409)
        stock = Stock.objects.get(item=self.item)
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': stock.pk, 'quantity': '10', 'reason': '检测单元装配领料'},
        )
        rows = self.demand()
        self.assertEqual(self.shortage(rows), {'上料': Decimal('10'), '检测': Decimal('0')})
        self.assertEqual(Decimal(rows[self.check.pk]['issued']), Decimal('10'))
        self.buy(self.check, '1', status=409)
        self.buy(self.feed, '11', status=409)
        self.buy(self.feed, '10')
        self.assertEqual(
            sum((line.quantity for line in PurchaseLine.objects.filter(bom_line=self.check)), Decimal('0')),
            Decimal('10'),
        )
        self.assertEqual(sum(self.shortage(self.demand()).values()), Decimal('0'))

    def test_purchase_return_releases_line_limit_for_repurchase(self):
        purchase = self.buy(self.check, '10')
        self.receive(purchase, '10')
        receipt = StockMove.objects.get(kind='receipt', purchase_line__purchase=purchase)
        self.post('warehouse', f'moves/{receipt.pk}/return-purchase/', {'quantity': '4', 'reason': '质量退货'})
        rows = self.demand()
        self.assertEqual(self.shortage(rows), {'上料': Decimal('10'), '检测': Decimal('4')})
        self.assertEqual(Decimal(rows[self.check.pk]['available']), Decimal('6'))
        self.buy(self.check, '5', from_demand=False, status=409)
        self.buy(self.check, '4')
        self.assertEqual(self.shortage(self.demand()), {'上料': Decimal('10'), '检测': Decimal('0')})

    def test_legacy_overreceived_line_shares_excess_and_blocks_more_on_that_line(self):
        purchase = self.buy(self.check, '10')
        self.receive(purchase, '10')
        # 按行校验上线前的历史数据：检测行挂了 15 件且已全部到货。
        PurchaseLine.objects.filter(purchase=purchase).update(quantity=Decimal('15'), received_quantity=Decimal('15'))
        Stock.objects.filter(item=self.item).update(quantity=Decimal('15'))
        rows = self.demand()
        self.assertEqual(self.shortage(rows), {'上料': Decimal('5'), '检测': Decimal('0')})
        self.assertEqual(Decimal(rows[self.check.pk]['available']), Decimal('10'))
        self.assertEqual(Decimal(rows[self.feed.pk]['available']), Decimal('5'))
        conflict = self.buy(self.check, '1', from_demand=False, status=409)
        self.assertIn('检测', str(conflict['detail']))
        self.buy(self.feed, '6', status=409)
        self.buy(self.feed, '5')


class BOMRevisionScopeTests(BusinessFixtures, TestCase):
    """某物料在途/已领超过其 BOM 总量时，只拒绝改动该物料，不连累其他物料的修订与导入。"""

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.other = Item.objects.create(code='Z-01', name='超量气缸')
        self.revise(
            [
                {'item': self.item.pk, 'quantity': '10', 'assembly_unit': '上料'},
                {'item': self.other.pk, 'quantity': '4', 'assembly_unit': '检测'},
            ]
        )
        # 手工采购不关联 BOM 行，数量超过该物料 BOM 总量。
        self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': self.other.pk, 'quantity': '6', 'unit_price': '3'}],
            },
            status=201,
        )
        self.line = BOMLine.objects.get(project=self.project, item=self.item)
        self.over = BOMLine.objects.get(project=self.project, item=self.other)

    def revise(self, lines, status=200):
        return self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(self.project.pk), 'lines': lines},
            status=status,
        )

    def import_preview(self, records):
        import csv
        import io

        from apps.business.services.bom_material_import import HEADERS

        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows([[*row, *[''] * (len(HEADERS) - len(row))] for row in records])
        response = self.clients['manager'].post(
            f'/api/business/projects/{self.project.pk}/import-preview/',
            {'file': SimpleUploadedFile('bom.csv', stream.getvalue().encode())},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_overpurchased_item_only_blocks_its_own_quantity_change(self):
        self.revise([{'id': self.line.pk, 'item': self.item.pk, 'quantity': '12', 'change_note': '增加上料用量'}])
        # 同一次修订带上未改数量的超量物料行，也不阻止其他物料。
        self.revise(
            [
                {'id': self.line.pk, 'item': self.item.pk, 'quantity': '13', 'change_note': '再增加'},
                {'id': self.over.pk, 'item': self.other.pk, 'quantity': '4', 'change_note': '只改说明'},
            ]
        )
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 13)
        for qty in ('3', '5'):
            with self.subTest(quantity=qty):
                result = self.revise(
                    [{'id': self.over.pk, 'item': self.other.pk, 'quantity': qty, 'change_note': '调整'}], status=409
                )
                message = str(result['detail'])
                self.assertIn('Z-01', message)
                self.assertIn('超量气缸', message)
                self.assertIn('最低可改为 6.000', message)
        self.over.refresh_from_db()
        self.assertEqual(self.over.quantity, 4)
        self.revise([{'id': self.over.pk, 'item': self.other.pk, 'quantity': '6', 'change_note': '补足到在途'}])

    def test_bom_import_preview_and_confirm_agree_on_overpurchased_items(self):
        preview = self.import_preview(
            [[self.item.code, '上料', '12', '增加上料用量'], [self.other.code, '检测', '4', '未改数量']]
        )
        self.assertTrue(preview['can_import'], preview['errors'])
        self.post('manager', f'projects/{self.project.pk}/bom-import-confirm/', {'token': preview['token']})
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 12)
        blocked = self.import_preview([[self.other.code, '检测', '3', '减少']])
        self.assertFalse(blocked['can_import'])
        message = '；'.join(error['message'] for error in blocked['errors'])
        self.assertIn('Z-01', message)
        self.assertIn('最低可改为 6.000', message)
        legacy = bom_import.preview(
            self.project, SimpleUploadedFile('bom.csv', f'物料编码,数量,变更说明\n{self.other.code},3,减少\n'.encode())
        )
        self.assertFalse(legacy['can_import'])
        self.assertIn('最低可改为 6.000', legacy['errors'][0]['message'])
