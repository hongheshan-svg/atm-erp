import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import BOMLine, Entry, IssueSlip, Item, Stock, StockMove, Task
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import BusinessFixtures
from .test_permission_queries import counted_queries


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
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count())
        response = self.post('warehouse', f'stocks/{stock.pk}/count/', payload, status=403)
        self.assertIn('零库存盘盈需管理员填写单位成本', str(response))
        self.assertIn('库存页面', str(response))
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, stock.value), (0, 0))
        self.assertFalse(stock.moves.exists())
        self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), counts)
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

    def test_stock_value_is_limited_to_cost_roles_and_authorized_general_manager(self):
        stock = self.open_stock()
        self.issue(stock, '1')
        general = User.objects.create_user(username='general', role='manager', management_reports=True)
        self.clients['general'] = APIClient()
        self.clients['general'].force_authenticate(general)
        readers = {'admin', 'finance', 'purchaser', 'purchase_manager', 'general'}
        global_moves = {'admin', 'finance', 'purchaser', 'purchase_manager', 'warehouse'}
        for role in ('admin', 'finance', 'purchaser', 'purchase_manager', 'general', 'manager', 'warehouse'):
            with self.subTest(role=role):
                client = self.clients[role]
                listed = client.get('/api/business/stocks/').data['results'][0]
                detail = client.get(f'/api/business/stocks/{stock.pk}/').data
                header = client.get('/api/business/stocks/export/').content.decode('utf-8-sig').splitlines()[0]
                # 库存结存没有项目归属，按库存金额口径；项目经理即便负责领料项目也看不到。
                self.assertEqual('value' in listed, role in readers)
                self.assertEqual('value' in detail, role in readers)
                self.assertEqual('库存金额' in header, role in readers)
                moves = {row['kind']: row for row in client.get('/api/business/moves/').data['results']}
                # 期初流水同样没有项目归属（只有全局岗位读得到流水本身），金额与库存结存同口径。
                self.assertEqual('opening' in moves, role in global_moves)
                if role in global_moves:
                    self.assertEqual('value' in moves['opening'], role in readers)
                # 关联项目的领料流水仍按项目金额范围：负责项目的经理可见，采购岗位不因此看到项目成本。
                self.assertEqual('issue' in moves, role != 'general')
                if role != 'general':
                    self.assertEqual('value' in moves['issue'], role in {'admin', 'finance', 'manager'})
        self.assertEqual(Decimal(self.clients['finance'].get('/api/business/stocks/').data['results'][0]['value']), 80)
        general.management_reports = False
        general.save(update_fields=['management_reports'])
        self.clients['general'].force_authenticate(general)
        self.assertNotIn('value', self.clients['general'].get(f'/api/business/stocks/{stock.pk}/').data)


class IssueSlipTests(BusinessFixtures, TestCase):
    """领料单：单行、库存勾选批量、按 BOM 领料都各开一张；批量可带任务，规则与单行领料相同。"""

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.cylinder = Item.objects.create(code='I2', name='气缸', specification='SC63', unit='个')
        self.spare = Item.objects.create(code='I3', name='密封圈', unit='个')
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '5'}, {'item': self.cylinder.pk, 'quantity': '2'}],
            },
        )
        self.motor = self.opening(self.item, '6')
        self.cylinders = self.opening(self.cylinder, '4', location='二号仓')
        self.seals = self.opening(self.spare, '10')

    def opening(self, item, quantity, location='主仓'):
        self.post(
            'admin',
            'stocks/opening/',
            {'item': item.pk, 'location': location, 'quantity': quantity, 'unit_cost': '10', 'reason': '期初'},
        )
        return Stock.objects.get(item=item, location=location)

    def batch(self, lines, status=200, **extra):
        payload = {'project': self.project.pk, 'lines': lines, **extra}
        return self.post('warehouse', 'stocks/bom-issue/', payload, status=status)

    def task(self, kind='service', project=None, title='现场换件'):
        return Task.objects.create(
            project=project or self.project, title=title, kind=kind, assignee=self.users['member']
        )

    def warranty(self):
        self.project.status = 'warranty'
        self.project.save()

    def test_single_issue_opens_one_line_slip_with_sequential_code(self):
        first = self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': self.motor.pk, 'quantity': '2', 'remark': '一号工位'},
        )
        second = self.post(
            'warehouse', 'stocks/issue/', {'project': self.project.pk, 'stock': self.motor.pk, 'quantity': '1'}
        )
        self.assertEqual((first['slip_code'], second['slip_code']), ('LL000001', 'LL000002'))
        slip = IssueSlip.objects.get(pk=first['slip'])
        self.assertEqual(
            (slip.project_id, slip.task_id, slip.reason, slip.created_by),
            (self.project.pk, None, '项目领料', self.users['warehouse']),
        )
        self.assertEqual(list(slip.moves.values_list('pk', flat=True)), [first['id']])
        self.assertEqual(StockMove.objects.get(pk=first['id']).remark, '一号工位')
        move = self.clients['warehouse'].get(f'/api/business/moves/{first["id"]}/').data
        self.assertEqual((move['slip'], move['slip_code']), (slip.pk, 'LL000001'))
        self.assertEqual(self.clients['warehouse'].get('/api/business/moves/', {'slip': slip.pk}).data['count'], 1)

    def test_stock_batch_issue_is_one_slip_and_replays_without_a_second_slip(self):
        key = str(uuid.uuid4())
        payload = {
            'project': self.project.pk,
            'reason': '装配一线领料',
            'lines': [
                {'stock': self.cylinders.pk, 'quantity': '2', 'remark': '夹爪'},
                {'stock': self.motor.pk, 'quantity': '5'},
            ],
        }
        result = self.post('warehouse', 'stocks/bom-issue/', payload, key=key)
        self.assertEqual(self.post('warehouse', 'stocks/bom-issue/', payload, key=key), result)
        slip = IssueSlip.objects.get()
        self.assertEqual((result['slip'], result['slip_code'], result['count']), (slip.pk, 'LL000001', 2))
        self.assertEqual(set(slip.moves.values_list('pk', flat=True)), set(result['moves']))
        self.assertEqual(set(slip.moves.values_list('reason', flat=True)), {'装配一线领料'})
        self.motor.refresh_from_db()
        self.assertEqual(self.motor.quantity, Decimal('1'))

    def test_batch_with_service_task_allowed_in_warranty_and_skips_bom(self):
        self.warranty()
        service = self.task()
        # 密封圈不在 BOM、电机超出 BOM 剩余：售后领料不占 BOM 剩余，均可领。
        result = self.batch(
            [{'stock': self.seals.pk, 'quantity': '3'}, {'stock': self.motor.pk, 'quantity': '6'}], task=service.pk
        )
        slip = IssueSlip.objects.get(pk=result['slip'])
        self.assertEqual((slip.task_id, slip.reason), (service.pk, '售后领料'))
        self.assertEqual(set(slip.moves.values_list('task_id', flat=True)), {service.pk})
        self.assertEqual(slip.moves.count(), 2)

    def test_batch_task_rules_match_single_issue(self):
        line = [{'stock': self.motor.pk, 'quantity': '1'}]
        other = self.active_project()
        self.batch(line, status=404, task=self.task(project=other).pk)
        done = self.task(title='已完成售后')
        done.status = 'done'
        done.save()
        self.batch(line, status=404, task=done.pk)
        self.warranty()
        assembly = self.task(kind='assembly', title='装配')
        self.assertIn('task', self.batch(line, status=400, task=assembly.pk))
        # 按 BOM 领料不带任务时仍按原规则拒绝（409），并提示改用勾选领料选售后任务。
        self.assertIn('售后任务', str(self.batch(line, status=409)))
        self.assertFalse(IssueSlip.objects.exists())
        self.assertFalse(StockMove.objects.filter(kind='issue').exists())

    def test_bom_overrun_still_rejected_without_service_task(self):
        assembly = self.task(kind='assembly', title='装配')
        response = self.batch([{'stock': self.motor.pk, 'quantity': '6'}], status=409, task=assembly.pk)
        self.assertIn('伺服电机', str(response))
        response = self.batch([{'stock': self.seals.pk, 'quantity': '1'}], status=409)
        self.assertIn('密封圈', str(response))
        result = self.batch([{'stock': self.motor.pk, 'quantity': '5'}], task=assembly.pk)
        self.assertEqual(IssueSlip.objects.get(pk=result['slip']).task_id, assembly.pk)
        # 执行中项目选售后任务同样不占 BOM 剩余。
        self.batch([{'stock': self.motor.pk, 'quantity': '1'}], task=self.task().pk)

    def test_failed_line_rolls_back_whole_slip_and_its_number(self):
        response = self.batch(
            [{'stock': self.cylinders.pk, 'quantity': '1'}, {'stock': self.motor.pk, 'quantity': '7'}], status=409
        )
        self.assertIn('伺服电机', str(response))
        self.assertFalse(IssueSlip.objects.exists())
        self.assertFalse(StockMove.objects.filter(kind='issue').exists())
        self.cylinders.refresh_from_db()
        self.assertEqual(self.cylinders.quantity, Decimal('4'))
        self.assertFalse(CodeRule.objects.filter(key='issue_slip', counter__gt=0).exists())
        self.assertEqual(self.batch([{'stock': self.cylinders.pk, 'quantity': '1'}])['slip_code'], 'LL000001')

    def test_bom_issue_opens_one_slip_for_all_lines(self):
        lines = self.clients['warehouse'].get('/api/business/stocks/bom-issue/', {'project': self.project.pk}).data
        payload = [{'stock': row['stock'], 'quantity': row['quantity']} for row in lines['lines']]
        result = self.batch(payload)
        self.assertEqual(IssueSlip.objects.get().moves.count(), len(payload), result)
        self.assertEqual(result['count'], 2)

    def test_batch_issue_reads_do_not_grow_with_lines(self):
        """BOM 剩余、全库位在库与其他项目到货在锁物料后一次读取，逐行出库在内存里扣减（同一物料前面的库位照样计入）。"""
        other = self.active_project()

        def scenario(size):
            project = self.active_project()
            items = Item.objects.bulk_create([Item(code=f'QI{project.pk}-{i}', name=f'领料件{i}') for i in range(size)])
            BOMLine.objects.bulk_create(
                [BOMLine(project=owner, item=item, quantity=5) for owner in (project, other) for item in items]
            )
            stocks = Stock.objects.bulk_create(
                [
                    Stock(item=item, location=place, quantity=3, value=30)
                    for item in items
                    for place in ('主仓', '二号仓')
                ]
            )
            # 另一个在执行项目各到货 4 件未领：主仓领 2 后在库 4 仍够，二号仓再领 2 就会占用对方到货。
            StockMove.objects.bulk_create(
                [
                    StockMove(stock=stock, project=other, kind='receipt', quantity=2, value=20, reason='到货')
                    for stock in stocks
                ]
            )
            payload = {
                'project': project.pk,
                'confirm_shared': True,
                'lines': [{'stock': stock.pk, 'quantity': '2'} for stock in stocks],
            }
            result = {}
            reads, _ = counted_queries(
                lambda: result.update(self.post('warehouse', 'stocks/bom-issue/', payload)),
                'apps.business.services.inventory.save',
                'apps.business.services.inventory.audit',
            )
            self.assertEqual(result['count'], size * 2)
            shared = {
                move.stock.location: AuditLog.objects.get(resource=f'stockmove:{move.pk}').detail['shared_from']
                for move in StockMove.objects.filter(pk__in=result['moves'], stock__item=items[0]).select_related(
                    'stock'
                )
            }
            self.assertEqual(shared, {'主仓': [], '二号仓': [{'project': other.code, 'quantity': '4.000'}]})
            # 同一物料两个库位各领 1，合计超出 BOM 剩余 1：第二行按本单前一行扣减后的剩余拒绝，整单不出库。
            payload['lines'] = [{'stock': stocks[0].pk, 'quantity': '1'}, {'stock': stocks[1].pk, 'quantity': '1'}]
            denied = self.post('warehouse', 'stocks/bom-issue/', payload, status=409)
            self.assertIn(f'{items[0].name}：领料超过 BOM 剩余需求', str(denied))
            self.assertEqual(StockMove.objects.filter(project=project, kind='issue').count(), size * 2)
            return reads

        small, large = scenario(3), scenario(30)
        self.assertEqual(small, large, f'3/30 种物料查询数: {small} / {large}')

    def test_slip_reads_follow_stock_move_scope(self):
        result = self.batch(
            [
                {'stock': self.cylinders.pk, 'quantity': '2', 'remark': '夹爪'},
                {'stock': self.motor.pk, 'quantity': '1'},
            ],
            reason='装配领料',
        )
        slip = IssueSlip.objects.get(pk=result['slip'])
        detail = self.clients['warehouse'].get(f'/api/business/issue-slips/{slip.pk}/').data
        self.assertEqual(
            (detail['code'], detail['project_code'], detail['reason']), (slip.code, self.project.code, '装配领料')
        )
        self.assertEqual(detail['created_by_name'], 'warehouse')
        self.assertEqual(detail['line_count'], 2)
        line = next(row for row in detail['lines'] if row['item_code'] == 'I2')
        self.assertEqual(
            {key: line[key] for key in ('item_name', 'specification', 'location', 'quantity', 'unit', 'remark')},
            {
                'item_name': '气缸',
                'specification': 'SC63',
                'location': '二号仓',
                'quantity': '2.000',
                'unit': '个',
                'remark': '夹爪',
            },
        )
        self.assertNotIn('value', line)
        self.assertIn('company_name', detail)
        listed = self.clients['finance'].get('/api/business/issue-slips/', {'project': self.project.pk}).data
        self.assertEqual(listed['count'], 1)
        self.assertEqual(listed['results'][0]['items_summary'], '伺服电机、气缸')
        for search in (slip.code, '气缸', 'I1'):
            self.assertEqual(
                self.clients['purchaser'].get('/api/business/issue-slips/', {'search': search}).data['count'], 1
            )
        self.assertEqual(
            self.clients['purchaser'].get('/api/business/issue-slips/', {'search': '密封圈'}).data['count'], 0
        )
        today = slip.created_at.astimezone().date().isoformat()
        dated = self.clients['warehouse'].get('/api/business/issue-slips/', {'date_from': today, 'date_to': today})
        self.assertEqual(dated.data['count'], 1)
        self.assertEqual(
            self.clients['warehouse'].get('/api/business/issue-slips/', {'date_from': '2999-01-01'}).data['count'], 0
        )
        self.assertEqual(self.clients['manager'].get(f'/api/business/issue-slips/{slip.pk}/').status_code, 200)
        outsider = User.objects.create_user(username='other_manager', role='manager')
        client = APIClient()
        client.force_authenticate(outsider)
        self.assertEqual(client.get('/api/business/issue-slips/').data['count'], 0)
        self.assertEqual(client.get(f'/api/business/issue-slips/{slip.pk}/').status_code, 404)
        for role in ('member', 'sales_manager', 'mechanical_engineer', 'production_manager'):
            self.assertEqual(self.clients[role].get('/api/business/issue-slips/').status_code, 403, role)
        self.assertEqual(
            self.clients['warehouse'].post('/api/business/issue-slips/', {}, format='json').status_code, 405
        )
