from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.business.models import BOMLine, Item, PurchaseLine, PurchaseOrder, Stock, StockMove
from apps.business.services import bom_import
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures
from .test_permission_queries import counted_queries


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

    def test_editing_demand_purchase_cannot_buy_stock_already_available(self):
        line = BOMLine.objects.create(project=self.project, item=self.item, quantity=10)
        self.post(
            'admin', 'stocks/opening/', {'item': self.item.pk, 'quantity': '6', 'unit_cost': '1', 'reason': '期初'}
        )
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'from_demand': True,
            'lines': [{'item': self.item.pk, 'bom_line': line.pk, 'quantity': '4', 'unit_price': '1'}],
        }
        order = self.post('purchaser', 'purchases/', data, status=201)['id']

        def edit(quantity, price='1', status=200):
            detail = self.clients['purchaser'].get(f'/api/business/purchases/{order}/').data
            row = {'id': detail['lines'][0]['id'], 'quantity': quantity, 'unit_price': price, 'due_date': TODAY}
            payload = {'expected_updated_at': detail['updated_at'], 'reason': '调整', 'due_date': TODAY, 'lines': [row]}
            return self.post('purchaser', f'purchases/{order}/edit/', payload, status=status)

        # 缺口 = 用量 10 - 在库 6 = 4；改单与按缺料下单同一口径，不能把在库可领的 6 件再买一遍。
        self.assertIn('超过当前缺口', str(edit('10', status=409)))
        edit('4', price='2')
        # 之后又有库存到货，只改单价或调减的草稿仍可保存，调增按最新缺口拒绝。
        Stock.objects.filter(item=self.item).update(quantity=Decimal('8'))
        edit('4', price='3')
        edit('3')
        edit('4', status=409)
        self.assertEqual(PurchaseLine.objects.get(purchase_id=order).quantity, Decimal('3'))

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
                'over_bom_reason': '备件随设备发运',
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


class BOMAuditRemediationTests(BusinessFixtures, TestCase):
    """BOM 审计整改：待批采购单独呈现、留空单元不再静默新增、预览只列改动、导入不变行跳过、替换与批量移除、变更记录。"""

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.project.members.add(self.users['mechanical_engineer'])
        self.other = Item.objects.create(code='I2', name='直线导轨')
        self.third = Item.objects.create(code='I3', name='轴承')
        self.revise(
            [
                {'item': self.other.pk, 'quantity': '2', 'assembly_unit': '01 上料'},
                {'item': self.other.pk, 'quantity': '3', 'assembly_unit': '03 检测'},
                {'item': self.item.pk, 'quantity': '4', 'assembly_unit': '01 上料'},
                {'item': self.third.pk, 'quantity': '1', 'assembly_unit': '03 检测'},
            ]
        )
        self.feed = BOMLine.objects.get(project=self.project, item=self.other, assembly_unit='01 上料')
        self.check = BOMLine.objects.get(project=self.project, item=self.other, assembly_unit='03 检测')

    def revise(self, lines, status=200, role='manager', url='revise-bom'):
        return self.post(
            role,
            f'projects/{self.project.pk}/{url}/',
            {'expected_revision': self.bom_version(self.project.pk), 'lines': lines},
            status=status,
        )

    def demand(self):
        response = self.clients['purchaser'].get(f'/api/business/projects/{self.project.pk}/demand/')
        self.assertEqual(response.status_code, 200, response.data)
        return {row['bom_line']: row for row in response.data['lines']}

    def numbers(self, row):
        return tuple(Decimal(row[key]) for key in ('incoming', 'unapproved', 'shortage'))

    def buy(self, bom, qty, *, submit=False, approve=False):
        result = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'from_demand': bom is not None,
                'lines': [
                    {'item': self.other.pk, 'quantity': qty, 'unit_price': '5', **({'bom_line': bom.pk} if bom else {})}
                ],
            },
            status=201,
        )
        purchase = PurchaseOrder.objects.get(pk=result['id'])
        if submit or approve:
            self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        if approve:
            self.post('manager', f'purchases/{purchase.pk}/approve/')
        return purchase

    def test_draft_and_submitted_purchases_still_cover_shortage_but_are_shown_as_unapproved(self):
        purchase = self.buy(self.feed, '2')
        self.assertEqual(self.numbers(self.demand()[self.feed.pk]), (2, 2, 0))
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        self.assertEqual(self.numbers(self.demand()[self.feed.pk]), (2, 2, 0))
        self.post('manager', f'purchases/{purchase.pk}/approve/')
        self.assertEqual(self.numbers(self.demand()[self.feed.pk]), (2, 0, 0))
        # 未关联 BOM 行的草稿采购按共享在途分摊，同样标为待批。
        self.buy(None, '1')
        self.assertEqual(self.numbers(self.demand()[self.check.pk]), (1, 1, 2))

    def test_blank_unit_for_multi_unit_item_is_rejected_instead_of_adding_a_line(self):
        count = BOMLine.objects.count()
        result = self.revise([{'item': self.other.pk, 'quantity': '3', 'change_note': '改数量'}], status=400)
        self.assertIn('单元不能留空', str(result))
        self.assertIn('01 上料', str(result))
        preview = self.revise([{'item': self.other.pk, 'quantity': '3'}], url='bom-change-preview')
        self.assertFalse(preview['can_apply'])
        self.assertIn('单元不能留空', preview['blockers'][0])
        self.assertEqual(BOMLine.objects.count(), count)
        # 只有一行的物料留空单元仍然沿用原单元修改该行。
        self.revise([{'item': self.item.pk, 'quantity': '5', 'change_note': '加量'}])
        self.assertEqual(BOMLine.objects.get(project=self.project, item=self.item).quantity, 5)
        self.assertEqual(BOMLine.objects.count(), count)

    def test_unit_written_differently_only_by_spaces_is_rejected(self):
        result = self.revise([{'item': self.third.pk, 'quantity': '1', 'assembly_unit': '01上料'}], status=400)
        self.assertIn('与现有单元「01 上料」只差空格', str(result))
        self.revise([{'item': self.third.pk, 'quantity': '1', 'assembly_unit': '０１　上料'}], status=400)
        self.revise([{'item': self.third.pk, 'quantity': '1', 'assembly_unit': '01 上料'}])

    def test_preview_lists_submitted_rows_new_line_warning_and_only_changed_items(self):
        preview = self.revise(
            [{'item': self.other.pk, 'quantity': '4', 'assembly_unit': '05 下料'}], url='bom-change-preview'
        )
        self.assertTrue(preview['can_apply'])
        self.assertEqual(
            [(row['action'], row['assembly_unit'], row['before'], row['after']) for row in preview['changes']],
            [('create', '05 下料', None, '4.000')],
        )
        self.assertIn('已在 2 个单元有用料', preview['warnings'][0])
        self.assertIn('总需求 5.000 → 9.000', preview['warnings'][0])
        self.assertEqual([row['item'] for row in preview['items']], [self.other.pk])
        self.assertEqual((preview['items'][0]['difference'], preview['unchanged_items']), ('4.000', 2))
        dates = self.revise(
            [{'id': self.feed.pk, 'item': self.other.pk, 'quantity': '2', 'required_date': '2026-12-01'}],
            url='bom-change-preview',
        )
        self.assertEqual((dates['items'], dates['changes'][0]['action']), ([], 'update'))

    def test_reduce_below_linked_purchase_names_order_and_minimum(self):
        purchase = self.buy(self.feed, '2', approve=True)
        message = str(
            self.revise([{'id': self.feed.pk, 'item': self.other.pk, 'quantity': '1', 'change_note': '减'}], 409)
        )
        self.assertIn(purchase.code, message)
        self.assertIn('最低可改为 2.000', message)
        removal = str(self.post('mechanical_engineer', f'bom/{self.feed.pk}/remove/', {'reason': '作废'}, status=409))
        self.assertIn(purchase.code, removal)
        self.assertIn('待收货', removal)

    def test_received_surplus_is_warned_when_reducing(self):
        purchase = self.buy(self.feed, '2', approve=True)
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': '2'}], 'reason': '到货'},
        )
        preview = self.revise(
            [{'id': self.check.pk, 'item': self.other.pk, 'quantity': '1', 'change_note': '减'}],
            url='bom-change-preview',
        )
        self.assertTrue(preview['can_apply'])
        self.assertEqual(preview['items'][0]['received_in_stock'], '2.000')
        self.assertFalse(any('多出' in warning for warning in preview['warnings']))
        preview = self.revise(
            [
                {'id': self.check.pk, 'item': self.other.pk, 'quantity': '0.5', 'change_note': '减'},
                {'id': self.feed.pk, 'item': self.other.pk, 'quantity': '1', 'change_note': '减'},
            ],
            url='bom-change-preview',
        )
        self.assertTrue(any('变更后多出 0.500' in warning for warning in preview['warnings']), preview['warnings'])

    def test_replace_material_adds_new_line_and_removes_old_in_one_step(self):
        replacement = Item.objects.create(code='I2-B', name='直线导轨B版')
        url = f'bom/{self.feed.pk}/replace/'
        self.post(
            'mechanical_engineer', url, {'item': self.other.pk, 'quantity': '2', 'change_note': '升版'}, status=400
        )
        self.post('sales_manager', url, {'item': replacement.pk, 'quantity': '2', 'change_note': '升版'}, status=403)
        result = self.post(
            'mechanical_engineer', url, {'item': replacement.pk, 'quantity': '3', 'change_note': '图档B版'}
        )
        new = BOMLine.objects.get(pk=result['id'])
        self.assertEqual((new.item, new.assembly_unit, new.quantity), (replacement, '01 上料', 3))
        self.assertTrue(BOMLine.all_objects.get(pk=self.feed.pk).is_deleted)
        # 原行有在途采购时整步拒绝，新物料行也不落库。
        purchase = self.buy(self.check, '1', approve=True)
        conflict = self.post(
            'mechanical_engineer',
            f'bom/{self.check.pk}/replace/',
            {'item': replacement.pk, 'quantity': '3', 'change_note': '换型'},
            status=409,
        )
        self.assertIn(purchase.code, str(conflict))
        self.assertFalse(BOMLine.objects.filter(item=replacement, assembly_unit='03 检测').exists())

    def test_inactive_material_is_flagged_and_can_only_be_replaced(self):
        Item.objects.filter(pk=self.other.pk).update(is_active=False)
        rows = [row for row in self.demand().values() if row['item'] == self.other.pk]
        self.assertEqual({row['is_active'] for row in rows}, {False})
        # 修改停用物料行被拒，提示里写明物料和「替换物料」入口。
        error = self.revise(
            [
                {
                    'id': self.feed.pk,
                    'item': self.other.pk,
                    'quantity': '5',
                    'assembly_unit': '01 上料',
                    'change_note': '加量',
                }
            ],
            status=400,
        )
        self.assertIn('I2', str(error))
        self.assertIn('替换物料', str(error))
        replacement = Item.objects.create(code='I2-C', name='直线导轨在用版')
        self.post(
            'mechanical_engineer',
            f'bom/{self.feed.pk}/replace/',
            {'item': replacement.pk, 'quantity': '2', 'change_note': '原型号停用'},
        )
        self.assertTrue(
            BOMLine.objects.filter(project=self.project, item=replacement, assembly_unit='01 上料').exists()
        )

    def test_batch_remove_is_all_or_nothing(self):
        bearing = BOMLine.objects.get(project=self.project, item=self.third)
        self.buy(self.check, '1', approve=True)
        payload = {'project': self.project.pk, 'ids': [bearing.pk, self.check.pk], 'reason': '作废'}
        self.post('mechanical_engineer', 'bom/remove-batch/', payload, status=409)
        self.assertTrue(BOMLine.objects.filter(pk=bearing.pk).exists())
        payload['ids'] = [bearing.pk, self.feed.pk]
        self.post('member', 'bom/remove-batch/', payload, status=403)
        self.assertEqual(self.post('mechanical_engineer', 'bom/remove-batch/', payload)['removed'], 2)
        self.assertFalse(BOMLine.objects.filter(pk__in=[bearing.pk, self.feed.pk]).exists())
        self.assertEqual(AuditLog.objects.filter(operation='bom.remove').count(), 2)
        self.post('mechanical_engineer', 'bom/remove-batch/', payload, status=409)

    def test_change_log_is_readable_by_project_members_with_before_and_after(self):
        self.revise([{'id': self.feed.pk, 'item': self.other.pk, 'quantity': '6', 'change_note': '加工位'}])
        self.post('mechanical_engineer', f'bom/{self.check.pk}/remove/', {'reason': '取消检测'})
        url = '/api/business/bom/changes/'
        for role in ('manager', 'purchaser', 'mechanical_engineer'):
            response = self.clients[role].get(url, {'project': self.project.pk})
            self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['results']
        self.assertEqual([row['action'] for row in rows[:2]], ['remove', 'update'])
        self.assertEqual((rows[0]['before'], rows[0]['after'], rows[0]['reason']), ('3.000', None, '取消检测'))
        self.assertEqual((rows[1]['before'], rows[1]['after'], rows[1]['actor']), ('2.000', '6.000', 'manager'))
        searched = self.clients['manager'].get(url, {'project': self.project.pk, 'search': '轴承'}).data
        self.assertEqual([row['action'] for row in searched['results']], ['create'])
        self.assertEqual(self.clients['electrical_engineer'].get(url, {'project': self.project.pk}).status_code, 404)
        self.assertEqual(self.clients['sales_manager'].get(url, {'project': self.project.pk}).status_code, 403)
        self.assertEqual(self.clients['manager'].get(url, {'project': self.project.pk, 'start': 'x'}).status_code, 400)


class BOMQueryBudgetTests(BusinessFixtures, TestCase):
    """缺料、在途与已领按物料一次分组读取：逐行写入之外的查询数不随行数增长，同一请求里前面的行照样计入。"""

    BOM_WRITES = ('apps.business.services.bom.save', 'apps.business.services.bom.audit')
    PURCHASE_WRITES = ('apps.business.services.supply.save', 'apps.business.services.supply.audit')

    def setUp(self):
        self.setup_business()

    def stocked_bom(self, size, *, issued=None, linked='1'):
        """size 种物料各一条 BOM 行（用量 5），本项目已领 issued（为 None 时不建库存），各行挂一张草稿采购在途 linked。"""
        project = self.active_project()
        items = Item.objects.bulk_create([Item(code=f'QB{project.pk}-{i}', name=f'预算件{i}') for i in range(size)])
        lines = BOMLine.objects.bulk_create(
            [BOMLine(project=project, item=item, quantity=5, assembly_unit='上料') for item in items]
        )
        if issued is not None:
            stocks = Stock.objects.bulk_create([Stock(item=item, quantity=10, value=10) for item in items])
            StockMove.objects.bulk_create(
                [
                    StockMove(
                        stock=stock, project=project, kind='issue', quantity=-Decimal(issued), value=-1, reason='领料'
                    )
                    for stock in stocks
                ]
            )
        order = PurchaseOrder.objects.create(
            code=f'QP{project.pk}', project=project, supplier=self.supplier, due_date=TODAY
        )
        PurchaseLine.objects.bulk_create(
            [
                PurchaseLine(purchase=order, item=line.item, bom_line=line, quantity=Decimal(linked), unit_price=1)
                for line in lines
            ]
        )
        return project, items, lines

    def test_bom_import_revision_and_change_preview_reads_do_not_grow_with_rows(self):
        def scenario(size):
            project, items, lines = self.stocked_bom(size, issued='2')
            fresh = Item.objects.bulk_create([Item(code=f'QN{project.pk}-{i}', name=f'新件{i}') for i in range(size)])
            csv = '物料编码,单元,需求数量,变更说明\n' + ''.join(f'{item.code},上料,2,减量\n' for item in items)
            with CaptureQueriesContext(connection) as preview:
                result = bom_import.preview(project, SimpleUploadedFile('bom.csv', csv.encode()))
            reads = {'import_preview': len(preview)}
            # 合计 2 小于已领 2 与在途 1：每种物料一条说明，带上在途采购单号。
            self.assertEqual(len(result['errors']), size, result['errors'])
            self.assertIn(f'QP{project.pk} 草稿', result['errors'][0]['message'])
            revision = self.bom_version(project.pk)
            raised = [{'id': line.pk, 'item': line.item_id, 'quantity': '8', 'change_note': '加量'} for line in lines]
            added = [{'item': item.pk, 'quantity': '1', 'assembly_unit': '检测'} for item in fresh]
            change = {'expected_revision': revision, 'lines': raised + added}
            reads['change_preview'], _ = counted_queries(
                lambda: self.assertTrue(
                    self.post('manager', f'projects/{project.pk}/bom-change-preview/', change)['can_apply']
                ),
                *self.BOM_WRITES,
            )
            reads['revise'], _ = counted_queries(
                lambda: self.post('manager', f'projects/{project.pk}/revise-bom/', change), *self.BOM_WRITES
            )
            self.assertEqual(BOMLine.objects.filter(project=project).count(), size * 2)
            return reads

        small, large = scenario(3), scenario(30)
        self.assertEqual(small, large, f'3/30 行查询数: {small} / {large}')

    def test_batch_bom_removal_reads_do_not_grow_with_rows(self):
        def scenario(size):
            project, items, lines = self.stocked_bom(size)
            payload = {'project': project.pk, 'ids': [line.pk for line in lines], 'reason': '作废'}
            with CaptureQueriesContext(connection) as blocked:
                denied = self.post('manager', 'bom/remove-batch/', payload, status=409)
            blocked = len(blocked)
            self.assertEqual(str(denied).count('关联在途采购 1.000'), size)
            self.assertEqual(str(denied).count('小于已领用 0 与在途采购 1.000'), size)
            PurchaseLine.objects.filter(purchase__project=project).update(cancelled_quantity=1)
            reads, _ = counted_queries(
                lambda: self.post('manager', 'bom/remove-batch/', payload),
                (BOMLine, 'soft_delete'),
                'apps.business.services.corrections.audit',
            )
            self.assertFalse(BOMLine.objects.filter(project=project).exists())
            return blocked, reads

        small, large = scenario(3), scenario(30)
        self.assertEqual(small, large, f'3/30 行查询数: {small} / {large}')

    def test_purchase_create_and_edit_reads_do_not_grow_with_rows(self):
        def scenario(size):
            project, items, lines = self.stocked_bom(size, linked='0.5')
            payload = {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'from_demand': True,
                'lines': [
                    {'item': line.item_id, 'bom_line': line.pk, 'quantity': '2', 'unit_price': '1'} for line in lines
                ],
            }
            reads = {}
            created = {}

            def create():
                created.update(self.post('purchaser', 'purchases/', payload, status=201))

            reads['create'], _ = counted_queries(create, *self.PURCHASE_WRITES)
            detail = self.clients['purchaser'].get(f'/api/business/purchases/{created["id"]}/').data
            edit = {
                'expected_updated_at': detail['updated_at'],
                'reason': '调整',
                'due_date': TODAY,
                'lines': [
                    {'id': row['id'], 'quantity': '3', 'unit_price': '2', 'due_date': TODAY} for row in detail['lines']
                ],
            }
            reads['edit'], _ = counted_queries(
                lambda: self.post('purchaser', f'purchases/{created["id"]}/edit/', edit), *self.PURCHASE_WRITES
            )
            # 未关联 BOM 行的手工采购：缺口 = 5 - 在途 3.5，买 2 超出 0.5，须写明原因并留审计。
            manual = {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'over_bom_reason': '备件',
                'lines': [{'item': item.pk, 'quantity': '2', 'unit_price': '1'} for item in items],
            }
            reads['manual'], _ = counted_queries(
                lambda: created.update(self.post('purchaser', 'purchases/', manual, status=201)),
                *self.PURCHASE_WRITES,
            )
            log = AuditLog.objects.get(operation='purchase.create', resource=f'purchaseorder:{created["id"]}')
            self.assertEqual(len(log.detail['over_bom']), size)
            self.assertEqual(
                {key: log.detail['over_bom'][0][key] for key in ('needed', 'incoming', 'shortage', 'excess')},
                {'needed': '5.000', 'incoming': '3.500', 'shortage': '1.500', 'excess': '0.500'},
            )
            draft = self.clients['purchaser'].get(f'/api/business/purchases/{created["id"]}/').data
            manual_edit = {
                'expected_updated_at': draft['updated_at'],
                'reason': '调整',
                'due_date': TODAY,
                'over_bom_reason': '备件',
                'lines': [
                    {'id': row['id'], 'quantity': '2.5', 'unit_price': '1', 'due_date': TODAY} for row in draft['lines']
                ],
            }
            reads['manual_edit'], _ = counted_queries(
                lambda: self.post('purchaser', f'purchases/{created["id"]}/edit/', manual_edit),
                *self.PURCHASE_WRITES,
            )
            return reads

        small, large = scenario(3), scenario(30)
        self.assertEqual(small, large, f'3/30 行查询数: {small} / {large}')

    def test_earlier_rows_of_the_same_order_count_as_incoming(self):
        """逐行校验时，本单前面已写入的明细计入在途：与逐行查库的结果一致。"""
        project = self.active_project()
        first = BOMLine.objects.create(project=project, item=self.item, quantity=3, assembly_unit='上料')
        second = BOMLine.objects.create(project=project, item=self.item, quantity=3, assembly_unit='检测')
        base = {'project': project.pk, 'supplier': self.supplier.pk, 'due_date': TODAY}
        # 先买 4 件不挂 BOM 行：物料缺口只剩 2，后面的行即使本行还有 3 也只能买 2。
        denied = self.post(
            'purchaser',
            'purchases/',
            {
                **base,
                'over_bom_reason': '备件',
                'lines': [
                    {'item': self.item.pk, 'quantity': '4', 'unit_price': '1'},
                    {'item': self.item.pk, 'bom_line': first.pk, 'quantity': '3', 'unit_price': '1'},
                ],
            },
            status=409,
        )
        self.assertIn('超过当前 BOM 剩余需求', str(denied))
        # 先挂满两行，再买的未关联明细超出缺口 0：说明里的在途含本单前两行。
        denied = self.post(
            'purchaser',
            'purchases/',
            {
                **base,
                'lines': [
                    {'item': self.item.pk, 'bom_line': first.pk, 'quantity': '3', 'unit_price': '1'},
                    {'item': self.item.pk, 'bom_line': second.pk, 'quantity': '3', 'unit_price': '1'},
                    {'item': self.item.pk, 'quantity': '1', 'unit_price': '1'},
                ],
            },
            status=400,
        )
        self.assertIn('在途 6.000，还可采购 0', str(denied))
        self.assertFalse(PurchaseOrder.objects.filter(project=project).exists())
