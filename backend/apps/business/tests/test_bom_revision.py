"""非标件换版：在途按新图改单、已领与在库旧版待处理（报废、留作备件、返修改制）、一步升版和导入换版列。"""

import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.business.models import (
    BOMLine,
    Entry,
    Item,
    Project,
    PurchaseLine,
    PurchaseOrder,
    RevisionChange,
    RevisionDisposition,
    Stock,
    StockMove,
)
from apps.business.services import finance
from apps.core.models import AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


class RevisionFixtures(BusinessFixtures):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.project.members.add(self.users['mechanical_engineer'])
        self.old = Item.objects.create(
            code='JG-001',
            name='夹爪安装板',
            specification='6061 200x80',
            drawing_number='DWG-001',
            drawing_revision='A',
        )
        self.new = Item.objects.create(
            code='JG-001B',
            name='夹爪安装板',
            specification='6061 200x80',
            drawing_number='DWG-001',
            drawing_revision='B',
        )
        self.revise([{'item': self.old.pk, 'quantity': '10', 'assembly_unit': '01 上料'}])
        self.line = BOMLine.objects.get(project=self.project, item=self.old)

    def revise(self, lines, status=200, project=None):
        project = project or self.project
        return self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': lines},
            status=status,
        )

    def buy(
        self, line, qty, *, approve=True, price='5', item=None, project=None, buyer='purchaser', approver='manager'
    ):
        project = project or self.project
        result = self.post(
            buyer,
            'purchases/',
            {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': (item or line.item).pk, 'bom_line': line.pk, 'quantity': qty, 'unit_price': price}],
            },
            status=201,
        )
        purchase = PurchaseOrder.objects.get(pk=result['id'])
        if approve:
            self.post(buyer, f'purchases/{purchase.pk}/submit/')
            self.post(approver, f'purchases/{purchase.pk}/approve/')
            purchase.refresh_from_db()
        return purchase

    def receive(self, purchase, line, qty, status=200):
        return self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': line.pk, 'quantity': qty}], 'reason': '到货'},
            status=status,
        )

    def issue(self, qty):
        stock = Stock.objects.get(item=self.old)
        return self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': stock.pk, 'quantity': qty, 'reason': '装配领料'},
        )

    def replace(self, qty='10', status=200, role='mechanical_engineer'):
        return self.post(
            role,
            f'bom/{self.line.pk}/replace/',
            {'item': self.new.pk, 'quantity': qty, 'change_note': 'ECN-01 孔位调整'},
            status=status,
        )

    def parts(self, role='warehouse'):
        return {
            row['old_item_code']: row for row in self.get(role, f'projects/{self.project.pk}/obsolete-parts/')['parts']
        }

    def shortage(self, line_id):
        rows = self.get('purchaser', f'projects/{self.project.pk}/demand/')['lines']
        return Decimal(next(row['shortage'] for row in rows if row['bom_line'] == line_id))


class RevisionInTransitTests(RevisionFixtures, TestCase):
    def test_in_transit_old_revision_is_converted_instead_of_blocking(self):
        approved = self.buy(self.line, '4')
        draft = self.buy(self.line, '3', approve=False)
        old_line = approved.lines.get()
        self.receive(approved, old_line, '2')
        entry = Entry.objects.get(purchase=approved)
        self.assertEqual(entry.amount, Decimal('20.00'))

        result = self.replace()
        new_line = BOMLine.objects.get(pk=result['id'])
        self.assertEqual((new_line.item, new_line.assembly_unit, new_line.quantity), (self.new, '01 上料', 10))
        self.assertTrue(BOMLine.all_objects.get(pk=self.line.pk).is_deleted)
        self.assertEqual(
            {row['code']: row['pending'] for row in result['converted']}, {approved.code: True, draft.code: False}
        )

        # 草稿直接改成新版，审批人批准的就是新图。
        draft_line = draft.lines.get()
        self.assertEqual(
            (draft_line.item, draft_line.bom_line, draft_line.revision_role), (self.new, new_line, 'converted')
        )
        # 已批准：旧版余量取消并冲减应付，同单新增新版明细，待采购确认。
        old_line.refresh_from_db()
        self.assertEqual((old_line.received_quantity, old_line.cancelled_quantity), (2, 2))
        converted = approved.lines.get(item=self.new)
        self.assertEqual((converted.quantity, converted.bom_line, converted.revision_pending), (2, new_line, True))
        entry.refresh_from_db()
        self.assertEqual((entry.amount, entry.credit_amount), (Decimal('30.00'), Decimal('10.00')))
        change = RevisionChange.objects.get(project=self.project)
        self.assertEqual((change.old_item, change.new_item, change.converted_quantity), (self.old, self.new, 5))
        self.assertTrue(
            AuditLog.objects.filter(
                operation='purchase.revision_convert', resource=f'purchaseorder:{approved.pk}'
            ).exists()
        )

        # 在途已转成新版，新版缺料不重复计算：10 − 转来的 2（已批准）− 3（草稿）。
        self.assertEqual(self.shortage(new_line.pk), 5)
        # 确认前仓库不能收新版；采购按新图确认并调价，应付同步调整。
        self.assertIn('确认新图', str(self.receive(approved, converted, '2', status=409)))
        workbench = self.get('purchaser', 'workbench/')
        self.assertEqual([row['id'] for row in workbench['revision_reviews']['results']], [approved.pk])
        self.post(
            'warehouse',
            f'purchases/{approved.pk}/revision-review/',
            {'line': converted.pk, 'decision': 'confirm', 'reason': '供应商确认'},
            status=403,
        )
        # 调高单价会增加已批准应付，普通采购员不能自行确认；由独立采购审批人确认并同步调整应付。
        self.post(
            'purchaser',
            f'purchases/{approved.pk}/revision-review/',
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '6', 'reason': '供应商按B版报价'},
            status=403,
        )
        self.post(
            'purchase_manager',
            f'purchases/{approved.pk}/revision-review/',
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '6', 'reason': '供应商按B版报价'},
        )
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal('32.00'))
        history = self.get('purchaser', f'purchases/{approved.pk}/handling-history/')['results']
        self.assertTrue(
            {'purchase.revision_convert', 'purchase.revision_confirm'} <= {row['operation'] for row in history}
        )
        self.receive(approved, converted, '2')
        self.assertNotIn('revision_reviews', self.get('purchaser', 'workbench/'))
        # 已到货的 2 件旧版超出现 BOM 需求，进入在库待处理。
        self.assertEqual(self.parts()['JG-001']['pending_stock'], '2.000')

    def test_revision_price_hike_enforces_approval_sod_and_budget(self):
        # 1) 维持原价或降价：普通采购员可以直接确认。
        po_drop = self.buy(self.line, '2', price='10')
        self.replace()
        converted_drop = po_drop.lines.get(item=self.new)
        self.post(
            'purchaser',
            f'purchases/{po_drop.pk}/revision-review/',
            {'line': converted_drop.pk, 'decision': 'confirm', 'unit_price': '8', 'reason': '供应商降价'},
        )
        self.assertEqual(Entry.objects.get(purchase=po_drop).amount, Decimal('36.00'))

        # 2) 采购经理自己创建并提交的采购单，换版调高单价触发申请人分离（403），需其他审批人或管理员确认。
        item_c = Item.objects.create(
            code='JG-001C', name='夹爪安装板', drawing_number='DWG-JG-001', drawing_revision='C', unit='件'
        )
        new_line = BOMLine.objects.get(project=self.project, item=self.new)
        po_self = self.buy(new_line, '2', price='10', buyer='purchase_manager', approver='manager')
        self.project.budget_materials = Decimal('40.00')
        self.project.budget_labor = Decimal('0.00')
        self.project.budget_expenses = Decimal('0.00')
        self.project.budget_changed_by = self.users['manager']
        self.project.save(update_fields=['budget_materials', 'budget_labor', 'budget_expenses', 'budget_changed_by'])
        self.post(
            'mechanical_engineer',
            f'bom/{new_line.pk}/replace/',
            {'item': item_c.pk, 'quantity': '10', 'change_note': 'ECN-03 升C版'},
        )
        converted_self = po_self.lines.get(item=item_c)
        # 采购员调高单价 -> 403
        self.post(
            'purchaser',
            f'purchases/{po_self.pk}/revision-review/',
            {'line': converted_self.pk, 'decision': 'confirm', 'unit_price': '15', 'reason': '涨价'},
            status=403,
        )
        # 申请人（purchase_manager）不能自批调高单价 -> 403
        self.post(
            'purchase_manager',
            f'purchases/{po_self.pk}/revision-review/',
            {'line': converted_self.pk, 'decision': 'confirm', 'unit_price': '15', 'reason': '涨价'},
            status=403,
        )
        # 独立审批人（manager）调价超预算但未勾选 confirm_over_budget -> 409；且 manager 是预算调整人 -> 403
        self.post(
            'manager',
            f'purchases/{po_self.pk}/revision-review/',
            {'line': converted_self.pk, 'decision': 'confirm', 'unit_price': '15', 'reason': '涨价'},
            status=403,
        )
        # 管理员未勾选 confirm_over_budget -> 409
        conflict = self.post(
            'admin',
            f'purchases/{po_self.pk}/revision-review/',
            {'line': converted_self.pk, 'decision': 'confirm', 'unit_price': '15', 'reason': '涨价'},
            status=409,
        )
        self.assertIn('确认承担超预算调价', str(conflict))
        # 管理员勾选 confirm_over_budget -> 200 且记录超预算审计
        self.post(
            'admin',
            f'purchases/{po_self.pk}/revision-review/',
            {
                'line': converted_self.pk,
                'decision': 'confirm',
                'unit_price': '15',
                'confirm_over_budget': True,
                'reason': '涨价特批',
            },
        )
        log = AuditLog.objects.filter(
            operation='purchase.revision_confirm', resource=f'purchaseorder:{po_self.pk}'
        ).last()
        self.assertTrue(log.detail['over_budget'])
        self.assertEqual(log.detail['delta'], '10.00')

    def test_revision_convert_fractional_rounding_preserves_accounting_invariant(self):
        po = self.buy(self.line, '1.000', price='1.01')
        old_line = po.lines.get(item=self.old)
        self.receive(po, old_line, '0.500')
        self.replace()
        entry = Entry.objects.get(purchase=po)
        preview = self.get('purchaser', f'purchases/{po.pk}/contract-preview/', {'version': 'current'})
        self.assertEqual(entry.amount - entry.credit_amount, Decimal(preview['effective_total']))
        self.assertEqual(Decimal(preview['effective_total']), Decimal('1.02'))
        log = AuditLog.objects.filter(operation='purchase.revision_convert', resource=f'purchaseorder:{po.pk}').last()
        self.assertEqual(log.detail.get('rounding_delta'), '0.01')

    def test_open_parts_and_scope_query_counts_do_not_scale_with_projects(self):
        from apps.business.services import revisions

        extras = []
        for idx in range(3):
            proj = self.active_project()
            proj.members.add(self.users['mechanical_engineer'])
            line = BOMLine.objects.create(project=proj, item=self.old, quantity=Decimal('2.000'), assembly_unit='U1')
            po = self.buy(line, '2', project=proj)
            self.receive(po, po.lines.get(item=self.old), '2')
            self.post(
                'mechanical_engineer',
                f'bom/{line.pk}/replace/',
                {'item': self.new.pk, 'quantity': '2', 'change_note': f'ECN-{idx}'},
            )
            extras.append(proj)
        with self.assertNumQueries(8):
            opened = revisions.open_parts(Project.objects.filter(pk__in=[p.pk for p in extras]))
        self.assertEqual(len(opened), 3)
        # scope 批量聚合：即使有多个项目共用同物料也不按行查库。
        for proj in extras:
            BOMLine.objects.create(project=proj, item=self.old, quantity=Decimal('1.000'), assembly_unit='U2')
        with self.assertNumQueries(4):
            scoped = revisions.scope(self.users['mechanical_engineer'], self.line)
        self.assertEqual(len(scoped), 3)

    def test_purchaser_can_cancel_converted_remainder(self):
        approved = self.buy(self.line, '4')
        self.replace()
        converted = approved.lines.get(item=self.new)
        self.post(
            'purchaser',
            f'purchases/{approved.pk}/revision-review/',
            {'line': converted.pk, 'decision': 'cancel', 'reason': '供应商不接受改图'},
        )
        converted.refresh_from_db()
        approved.refresh_from_db()
        self.assertEqual(
            (converted.cancelled_quantity, converted.revision_pending, approved.status), (4, False, 'cancelled')
        )
        entry = Entry.objects.get(purchase=approved)
        self.assertEqual(entry.amount - entry.credit_amount, Decimal('0.00'))

    def test_new_quantity_must_cover_converted_in_transit(self):
        self.buy(self.line, '6')
        message = str(self.replace(qty='4', status=409))
        self.assertIn('至少为 6', message)
        self.assertFalse(BOMLine.objects.filter(item=self.new).exists())
        self.assertTrue(BOMLine.objects.filter(pk=self.line.pk).exists())


class ObsoletePartsTests(RevisionFixtures, TestCase):
    def setUp(self):
        super().setUp()
        purchase = self.buy(self.line, '6', price='10')
        self.receive(purchase, purchase.lines.get(), '6')
        self.issue('3')
        self.replace()
        self.change = RevisionChange.objects.get(project=self.project)

    def dispose(self, role, source, kind, qty, status=200):
        return self.post(
            role,
            f'revision-changes/{self.change.pk}/dispose/',
            {'source': source, 'kind': kind, 'quantity': qty, 'reason': '旧版孔位不对'},
            status=status,
        )

    def test_issued_and_received_old_parts_become_pending_and_are_disposed(self):
        row = self.parts()['JG-001']
        self.assertEqual((row['pending_issued'], row['pending_stock'], row['open']), ('3.000', '3.000', True))
        self.assertEqual(row['new_item_code'], 'JG-001B')
        workbench = self.get('warehouse', 'workbench/')
        self.assertEqual(workbench['obsolete_parts']['results'][0]['project'], self.project.pk)

        before = Decimal(finance.cost(self.project)['materials'])
        self.dispose('warehouse', 'stock', 'scrap', '1')
        scrap = StockMove.objects.get(kind='scrap')
        self.assertEqual((scrap.project, scrap.quantity, scrap.value), (self.project, -1, Decimal('-10.00')))
        self.assertEqual(Stock.objects.get(item=self.old).quantity, 2)
        self.assertEqual(Decimal(finance.cost(self.project)['materials']), before + 10)
        self.dispose('warehouse', 'stock', 'keep', '1')
        self.assertEqual(Stock.objects.get(item=self.old).quantity, 2)
        # 在库旧版只由仓管出库或留用；已装机的可由工程师登记报废，且不能留作备件。
        self.dispose('mechanical_engineer', 'stock', 'scrap', '1', status=403)
        self.dispose('mechanical_engineer', 'issued', 'keep', '1', status=400)
        self.dispose('mechanical_engineer', 'issued', 'scrap', '1')
        self.dispose('sales_manager', 'issued', 'scrap', '1', status=403)
        row = self.parts()['JG-001']
        self.assertEqual((row['pending_issued'], row['pending_stock']), ('2.000', '1.000'))
        self.assertIn('只有 1.000', str(self.dispose('warehouse', 'stock', 'scrap', '2', status=409)))
        self.assertEqual(RevisionDisposition.objects.count(), 3)

    def test_rework_purchase_converts_stock_on_receipt(self):
        result = self.post(
            'purchaser',
            f'revision-changes/{self.change.pk}/rework/',
            {
                'source': 'stock',
                'quantity': '2',
                'supplier': self.supplier.pk,
                'unit_price': '3',
                'due_date': TODAY,
                'note': '扩孔',
            },
        )
        purchase = PurchaseOrder.objects.get(pk=result['id'])
        line = purchase.lines.get()
        new_line = BOMLine.objects.get(project=self.project, item=self.new)
        self.assertEqual(
            (purchase.status, line.item, line.bom_line, line.revision_role),
            ('draft', self.new, new_line, 'rework_stock'),
        )
        self.assertIn('返修改制', purchase.note)
        self.assertEqual(self.parts()['JG-001']['pending_stock'], '1.000')
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        self.post('manager', f'purchases/{purchase.pk}/approve/')
        self.receive(purchase, line, '2')
        rework = StockMove.objects.filter(kind='rework')
        self.assertEqual(sum(move.quantity for move in rework), -2)
        self.assertEqual(Stock.objects.get(item=self.old).quantity, 1)
        self.assertEqual(Stock.objects.get(item=self.new).quantity, 2)
        row = self.parts()['JG-001']
        self.assertEqual((row['pending_stock'], row['rework_stock_received']), ('1.000', '2.000'))
        # 已装机旧版返修：拆下送修，收货只入新版；返修数量不能超过新版剩余需求和待处理数量。
        self.post(
            'purchaser',
            f'revision-changes/{self.change.pk}/rework/',
            {'source': 'issued', 'quantity': '4', 'supplier': self.supplier.pk, 'unit_price': '3', 'due_date': TODAY},
            status=409,
        )
        self.post(
            'warehouse',
            f'revision-changes/{self.change.pk}/rework/',
            {'source': 'issued', 'quantity': '3', 'supplier': self.supplier.pk, 'unit_price': '3', 'due_date': TODAY},
            status=403,
        )
        self.post(
            'purchaser',
            f'revision-changes/{self.change.pk}/rework/',
            {'source': 'issued', 'quantity': '3', 'supplier': self.supplier.pk, 'unit_price': '3', 'due_date': TODAY},
        )
        self.assertEqual(self.parts()['JG-001']['pending_issued'], '0.000')
        self.assertEqual(
            PurchaseLine.objects.filter(revision=self.change, revision_role='rework_issued').get().quantity, 3
        )


class UpgradeTests(RevisionFixtures, TestCase):
    def test_one_step_upgrade_creates_next_revision_and_optionally_other_projects(self):
        other = self.active_project()
        other.members.add(self.users['mechanical_engineer'])
        self.revise([{'item': self.old.pk, 'quantity': '2', 'assembly_unit': '02 搬运'}], project=other)
        Item.objects.filter(pk=self.new.pk).update(is_active=False)
        url = f'bom/{self.line.pk}/upgrade/'
        scope = self.get('mechanical_engineer', f'bom/{self.line.pk}/upgrade-scope/')
        self.assertEqual([(row['id'], row['writable']) for row in scope], [(other.pk, True)])
        self.post('mechanical_engineer', url, {'drawing_revision': 'A', 'change_note': 'ECN-02'}, status=400)
        result = self.post(
            'mechanical_engineer',
            url,
            {'drawing_revision': 'C', 'change_note': 'ECN-02 加强筋', 'projects': [other.pk]},
        )
        item = Item.objects.get(pk=result['item'])
        self.assertTrue(result['created_item'])
        self.assertEqual(
            (item.name, item.specification, item.drawing_number, item.drawing_revision),
            ('夹爪安装板', '6061 200x80', 'DWG-001', 'C'),
        )
        self.assertNotEqual(item.code, self.old.code)
        self.assertEqual(BOMLine.objects.get(project=self.project, item=item).quantity, 10)
        self.assertEqual(BOMLine.objects.get(project=other, item=item).assembly_unit, '02 搬运')
        self.assertFalse(BOMLine.objects.filter(item=self.old).exists())
        self.assertEqual(RevisionChange.objects.filter(new_item=item).count(), 2)
        line = BOMLine.objects.get(project=other, item=item)
        same = self.post(
            'mechanical_engineer',
            f'bom/{line.pk}/upgrade/',
            {'drawing_revision': 'c', 'change_note': '同版'},
            status=400,
        )
        self.assertIn('相同', str(same))
        # 同图号、同版本的在用物料已存在时直接复用，不再新建。
        reused = self.post(
            'mechanical_engineer', f'bom/{line.pk}/upgrade/', {'drawing_revision': 'a', 'change_note': '回到A版'}
        )
        self.assertEqual((reused['item'], reused['created_item']), (self.old.pk, False))

    def test_upgrade_requires_drawing_number_and_bom_writer(self):
        plain = Item.objects.create(code='STD-1', name='螺钉')
        self.revise([{'item': plain.pk, 'quantity': '4', 'assembly_unit': '01 上料'}])
        line = BOMLine.objects.get(item=plain)
        self.get('mechanical_engineer', f'bom/{line.pk}/upgrade-scope/', status=400)
        self.post(
            'mechanical_engineer', f'bom/{line.pk}/upgrade/', {'drawing_revision': 'B', 'change_note': '改'}, status=400
        )
        self.post(
            'purchaser', f'bom/{self.line.pk}/upgrade/', {'drawing_revision': 'B', 'change_note': '改'}, status=403
        )

    def test_upgrade_scope_redacts_inaccessible_projects_and_hides_confidential_codes(self):
        from apps.accounts.models import User
        from apps.business.models import Project

        other_manager = User.objects.create_user(username='scope-pm', role='manager')
        secret = Project.objects.create(
            code='SECRET-PRJ', name='保密产线', customer=self.customer, manager=other_manager, status='active'
        )
        BOMLine.objects.create(project=secret, item=self.old, quantity=7, assembly_unit='保密单元')
        # 机械工程师未参与保密项目：upgrade-scope 不得泄露其编号、名称、单元、用量、在途或已领。
        rows = self.get('mechanical_engineer', f'bom/{self.line.pk}/upgrade-scope/')
        self.assertEqual(rows, [{'writable': False}])
        denied = self.post(
            'mechanical_engineer',
            f'bom/{self.line.pk}/upgrade/',
            {'drawing_revision': 'C', 'change_note': '尝试越权换版', 'projects': [secret.pk]},
            status=403,
        )
        self.assertNotIn('SECRET-PRJ', str(denied))
        # 本就有该项目读取权但无 BOM 写权限（例如兼仓管）时，只返回项目编号，不返回详情。
        self.users['mechanical_engineer'].additional_roles = ['warehouse']
        self.users['mechanical_engineer'].save(update_fields=['additional_roles'])
        rows = self.get('mechanical_engineer', f'bom/{self.line.pk}/upgrade-scope/')
        self.assertEqual(rows, [{'writable': False, 'code': 'SECRET-PRJ'}])

    def test_revision_price_hike_enforces_approver_separation_and_budget_gate(self):
        from apps.accounts.models import User
        from apps.business.models import Project

        approved = self.buy(self.line, '4', price='10')
        # 预算设置：材料预算 50 元（原单已占 40 元，最多再涨 10 元），人工/费用预算 0。
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {'materials': '50', 'labor': '0', 'expenses': '0', 'expected_revision': 0, 'reason': '初始预算'},
        )
        self.replace()
        converted = approved.lines.get(item=self.new)
        url = f'purchases/{approved.pk}/revision-review/'

        # 普通采购员涨价被拒（即使未超预算）。
        self.post(
            'purchaser',
            url,
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '11', 'reason': '涨价'},
            status=403,
        )
        # 兼任其他项目经理的采购员也不能越权审批非参与项目的换版涨价。
        other_pm = User.objects.create_user(username='foreign-pm-buyer', role='manager', additional_roles=['purchaser'])
        from rest_framework.test import APIClient

        foreign_client = APIClient()
        foreign_client.force_authenticate(other_pm)
        self.assertEqual(
            foreign_client.post(
                f'/api/business/{url}',
                {'line': converted.pk, 'decision': 'confirm', 'unit_price': '11', 'reason': '越权涨价'},
                format='json',
                HTTP_IDEMPOTENCY_KEY='foreign-rev-hike',
            ).status_code,
            403,
        )
        # 原单申请人（即便是采购经理）也不能自批涨价。
        self.users['purchaser'].additional_roles = ['purchase_manager']
        self.users['purchaser'].save(update_fields=['additional_roles'])
        self.post(
            'purchaser',
            url,
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '11', 'reason': '自批涨价'},
            status=403,
        )
        # 超预算涨价（4*20=80，增量 +40 > 剩余预算 10）：未勾选 confirm_over_budget 返回 409。
        conflict = self.post(
            'purchase_manager',
            url,
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '20', 'reason': '供应商涨价'},
            status=409,
        )
        self.assertIn('确认承担超预算调价', str(conflict))
        # 预算调整人（manager）不能批准超预算调价。
        self.post(
            'manager',
            url,
            {
                'line': converted.pk,
                'decision': 'confirm',
                'unit_price': '20',
                'confirm_over_budget': True,
                'reason': '经理自批超预算',
            },
            status=403,
        )
        # 非申请人且非预算调整人的采购经理勾选 confirm_over_budget 后可批准超预算调价。
        self.post(
            'purchase_manager',
            url,
            {
                'line': converted.pk,
                'decision': 'confirm',
                'unit_price': '20',
                'confirm_over_budget': True,
                'reason': '核准涨价',
            },
        )
        entry = Entry.objects.get(purchase=approved)
        self.assertEqual(entry.amount - entry.credit_amount, Decimal('80.00'))

        # 验证降价仍可由普通采购员直接确认。
        other = Project.objects.create(
            code='DROP-PRJ', name='降价项目', customer=self.customer, manager=self.users['manager'], status='active'
        )
        other.members.add(self.users['mechanical_engineer'])
        self.revise([{'item': self.old.pk, 'quantity': '4', 'assembly_unit': '01'}], project=other)
        line2 = BOMLine.objects.get(project=other, item=self.old)
        self.users['purchaser'].additional_roles = []
        self.users['purchaser'].save(update_fields=['additional_roles'])
        order2 = self.buy(line2, '4', price='10', project=other)
        self.post(
            'mechanical_engineer',
            f'bom/{line2.pk}/replace/',
            {'item': self.new.pk, 'quantity': '4', 'change_note': 'ECN-降价'},
        )
        conv2 = order2.lines.get(item=self.new)
        self.post(
            'purchaser',
            f'purchases/{order2.pk}/revision-review/',
            {'line': conv2.pk, 'decision': 'confirm', 'unit_price': '8', 'reason': '供应商降价'},
        )
        entry2 = Entry.objects.get(purchase=order2)
        self.assertEqual(entry2.amount - entry2.credit_amount, Decimal('32.00'))


class ImportRevisionTests(RevisionFixtures, TestCase):
    HEADERS = [
        '物料编码', '单元', '需求数量', '变更说明', '需求日期', '申请日期', '申请人', '物料名称', '规格', '图号',
        '图档版本', '产品编码类别', '品牌', '物料类别', '单位', '替换原编码',
    ]  # fmt: skip

    def upload(self, rows, headers=None):
        stream = io.StringIO()
        import csv

        writer = csv.writer(stream)
        writer.writerow(headers or self.HEADERS)
        writer.writerows(rows)
        response = self.clients['mechanical_engineer'].post(
            f'/api/business/projects/{self.project.pk}/import-preview/',
            {'file': SimpleUploadedFile('bom.csv', stream.getvalue().encode('utf-8-sig'))},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def row(self, code, replaces='', note='ECN-03', unit='01 上料', qty='10', **material):
        values = [code, unit, qty, note, '', '', '', '', '', '', '', '', '', '', '', replaces]
        for index, key in enumerate(('name', 'specification', 'drawing_number', 'drawing_revision'), 7):
            values[index] = material.get(key, '')
        return values

    def test_replace_column_changes_revision_and_converts_in_transit(self):
        purchase = self.buy(self.line, '4')
        preview = self.upload([self.row('JG-001B', replaces='JG-001')])
        self.assertTrue(preview['can_import'], preview['errors'])
        line = preview['lines'][0]
        self.assertEqual(
            (line['bom_action'], line['replaces'], line['before_quantity']), ('replace', 'JG-001', '10.000')
        )
        self.assertEqual(preview['summary']['replace'], 1)
        self.assertEqual(preview['untouched'], [])
        result = self.post(
            'mechanical_engineer', f'projects/{self.project.pk}/bom-import-confirm/', {'token': preview['token']}
        )
        self.assertEqual(len(result['changes']), 1)
        self.assertEqual(BOMLine.objects.get(project=self.project, item=self.new).quantity, 10)
        self.assertFalse(BOMLine.objects.filter(item=self.old).exists())
        self.assertTrue(purchase.lines.filter(item=self.new, revision_pending=True).exists())

    def test_replace_column_with_blank_code_upgrades_from_old_material(self):
        # 原物料版本为空：新版与原物料名称、型号都相同，也按不同图档新建，不会被当成同一物料复用。
        Item.objects.filter(pk=self.old.pk).update(drawing_revision='')
        Item.objects.filter(pk=self.new.pk).update(is_active=False)
        missing = self.upload([self.row('', replaces='JG-001')])
        self.assertIn('新的图档版本', missing['errors'][0]['message'])
        preview = self.upload([self.row('', replaces='JG-001', specification='6061 200x80 加厚', drawing_revision='C')])
        self.assertTrue(preview['can_import'], preview['errors'])
        line = preview['lines'][0]
        self.assertEqual(
            (line['bom_action'], line['material_action'], line['item_code']),
            ('replace', '升版新建物料', '确认时自动生成'),
        )
        self.post('mechanical_engineer', f'projects/{self.project.pk}/bom-import-confirm/', {'token': preview['token']})
        item = BOMLine.objects.get(project=self.project, assembly_unit='01 上料').item
        self.assertEqual(
            (item.name, item.specification, item.drawing_number, item.drawing_revision),
            ('夹爪安装板', '6061 200x80 加厚', 'DWG-001', 'C'),
        )

    def test_previous_template_without_replace_column_still_imports(self):
        # 旧的 15 列模板照常接受，按不换版处理。
        legacy = self.upload([self.row('JG-001', qty='12', note='加量')[:15]], headers=self.HEADERS[:15])
        self.assertTrue(legacy['can_import'], legacy['errors'])
        self.assertEqual(legacy['lines'][0]['bom_action'], 'update')

    def test_replace_column_errors(self):
        errors = self.upload(
            [
                self.row('JG-001B', replaces='NOPE'),
                self.row('JG-001B', replaces='JG-001', unit='09 不存在'),
                self.row('JG-001B', replaces='JG-001', note=''),
            ]
        )['errors']
        messages = ' '.join(error['message'] for error in errors)
        self.assertIn('不在本项目 BOM 中', messages)
        self.assertIn('没有原物料 JG-001', messages)
        self.assertIn('换版必须填写变更说明', messages)
        conflict = self.upload([self.row('JG-001B', replaces='JG-001'), self.row('JG-001', qty='12')])['errors']
        self.assertIn('已由第 2 行换版', ' '.join(error['message'] for error in conflict))
        self.buy(self.line, '8')
        short = self.upload([self.row('JG-001B', replaces='JG-001', qty='5')])['errors']
        self.assertIn('至少 8', ' '.join(error['message'] for error in short))


class RevisionChainTests(RevisionFixtures, TestCase):
    """版本链：同图号换版把旧版指向新版；别的项目仍用旧版时在物料、BOM 和导入里提示「该图已有新版」。"""

    def setUp(self):
        super().setUp()
        self.other = self.active_project()
        self.other.members.add(self.users['mechanical_engineer'])
        self.revise([{'item': self.old.pk, 'quantity': '2', 'assembly_unit': '02 搬运'}], project=self.other)

    def newer(self, item, role='purchaser'):
        return self.get(role, f'items/{item.pk}/')['newer_revision']

    def upgrade(self, line, revision, status=200):
        return self.post(
            'mechanical_engineer',
            f'bom/{line.pk}/upgrade/',
            {'drawing_revision': revision, 'change_note': f'ECN 升 {revision}'},
            status=status,
        )

    def test_newer_revision_follows_chain_and_falls_back_when_latest_is_disabled(self):
        self.assertIsNone(self.newer(self.old))
        self.replace()
        self.assertEqual(self.newer(self.old)['code'], 'JG-001B')
        self.assertIsNone(self.newer(self.new))
        listed = {
            row['code']: row['newer_revision']
            for row in self.get('purchaser', 'items/', {'search': 'JG-001'})['results']
        }
        self.assertEqual((listed['JG-001']['drawing_revision'], listed['JG-001B']), ('B', None))
        # 另一个项目仍用 A 版：BOM 行标出新版，工程师自己决定是否跟着升版。
        rows = self.get('mechanical_engineer', f'projects/{self.other.pk}/demand/')['lines']
        self.assertEqual(rows[0]['newer_revision']['code'], 'JG-001B')

        third = self.upgrade(BOMLine.objects.get(project=self.project, item=self.new), 'C')
        latest = Item.objects.get(pk=third['item'])
        self.assertEqual((self.newer(self.old)['code'], self.newer(self.new)['code']), (latest.code, latest.code))
        Item.objects.filter(pk=latest.pk).update(is_active=False)
        self.assertEqual((self.newer(self.old)['code'], self.newer(self.new)), ('JG-001B', None))

        # 导出与删除快照不带提示列。
        export = self.clients['purchaser'].get('/api/business/items/export/', {'file_format': 'csv'})
        self.assertEqual(export.status_code, 200)
        self.assertNotIn('newer', export.content.decode('utf-8-sig'))

    def test_rollback_to_old_revision_and_model_replacement(self):
        self.replace()
        line = BOMLine.objects.get(project=self.project, item=self.new)
        back = self.upgrade(line, 'A')
        self.assertEqual((back['item'], back['created_item']), (self.old.pk, False))
        # A→B 之后又改回 A：最近一次换版的新版 A 是当前版本，B 才是旧版。
        self.assertIsNone(self.newer(self.old))
        self.assertEqual(self.newer(self.new)['code'], 'JG-001')
        # 换成另一个型号（不同图号）只是该项目的替代，原物料不算过时。
        bolt = Item.objects.create(code='STD-1', name='螺钉', specification='M6')
        other_bolt = Item.objects.create(code='STD-2', name='螺钉', specification='M8')
        self.revise([{'item': bolt.pk, 'quantity': '4', 'assembly_unit': '03 检测'}])
        self.post(
            'mechanical_engineer',
            f'bom/{BOMLine.objects.get(item=bolt).pk}/replace/',
            {'item': other_bolt.pk, 'quantity': '4', 'change_note': '换型'},
        )
        self.assertIsNone(self.newer(bolt))

    def test_item_history_lists_versions_and_only_visible_project_changes(self):
        self.replace()
        other_line = BOMLine.objects.get(project=self.other, item=self.old)
        self.post(
            'mechanical_engineer',
            f'bom/{other_line.pk}/replace/',
            {'item': self.new.pk, 'quantity': '2', 'change_note': 'ECN-01 跟进'},
        )
        self.other.members.remove(self.users['member'])
        plain = Item.objects.create(code='STD-9', name='垫片')
        self.assertEqual(self.get('purchaser', f'items/{plain.pk}/revisions/')['versions'], [])
        history = self.get('purchaser', f'items/{self.old.pk}/revisions/')
        self.assertEqual(
            [(row['code'], row['superseded_by'], row['latest']) for row in history['versions']],
            [('JG-001', 'JG-001B', False), ('JG-001B', '', True)],
        )
        self.assertEqual({row['project'] for row in history['changes']}, {self.project.pk, self.other.pk})
        # 成员只看到自己参与项目的换版记录；物料版本本身是公共资料。
        member = self.get('member', f'items/{self.new.pk}/revisions/')
        self.assertEqual(len(member['versions']), 2)
        self.assertEqual([row['project'] for row in member['changes']], [self.project.pk])
        self.assertEqual(member['changes'][0]['reason'], 'ECN-01 孔位调整')


class RevisionImpactTests(RevisionFixtures, TestCase):
    """换版前的影响预估与实际换版结果一致：在途怎么转、旧版待处理多少。"""

    def setUp(self):
        super().setUp()
        self.approved = self.buy(self.line, '6', price='10')
        self.receive(self.approved, self.approved.lines.get(), '4')
        self.issue('2')
        self.draft = self.buy(self.line, '3', approve=False)

    def test_dialog_impact_matches_the_change(self):
        impact = self.get('mechanical_engineer', f'bom/{self.line.pk}/revision-impact/')
        self.assertEqual(
            [(row['code'], row['quantity'], row['pending'], row['blocked']) for row in impact['in_transit']],
            [(self.approved.code, '2.000', True, False), (self.draft.code, '3.000', False, False)],
        )
        self.assertEqual(
            (impact['issued'], impact['received_unissued'], impact['need_after']), ('2.000', '2.000', '0.000')
        )
        self.assertEqual((impact['pending_issued'], impact['pending_stock']), ('2.000', '2.000'))
        self.get('purchaser', f'bom/{self.line.pk}/revision-impact/', status=403)
        self.replace()
        row = self.parts()['JG-001']
        self.assertEqual((row['pending_issued'], row['pending_stock']), ('2.000', '2.000'))

    def test_other_unit_still_needing_old_revision_reduces_the_estimate(self):
        self.revise([{'item': self.old.pk, 'quantity': '3', 'assembly_unit': '02 搬运', 'change_note': '增加搬运单元'}])
        impact = self.get('mechanical_engineer', f'bom/{self.line.pk}/revision-impact/')
        # 换掉 01 单元后旧版仍需 3：已领 2 全部留用，到货未领 2 里 1 件补足 02 单元，只有 1 件进入待处理。
        self.assertEqual(
            (impact['need_after'], impact['pending_issued'], impact['pending_stock']), ('3.000', '0.000', '1.000')
        )

    def test_scope_shows_in_transit_and_issued_of_other_projects(self):
        other = self.active_project()
        other.members.add(self.users['mechanical_engineer'])
        self.revise([{'item': self.old.pk, 'quantity': '5', 'assembly_unit': '02 搬运'}], project=other)
        other_line = BOMLine.objects.get(project=other, item=self.old)
        self.buy(other_line, '4', project=other)
        [row] = self.get('mechanical_engineer', f'bom/{self.line.pk}/upgrade-scope/')
        self.assertEqual(
            (row['id'], row['quantity'], row['in_transit'], row['issued']), (other.pk, '5.000', '4.000', '0.000')
        )


class ImportRevisionHintTests(ImportRevisionTests):
    def test_preview_marks_old_revision_rows_and_estimates_replace_impact(self):
        approved = self.buy(self.line, '6', price='10')
        self.receive(approved, approved.lines.get(), '4')
        self.issue('2')
        other = self.active_project()
        self.revise([{'item': self.old.pk, 'quantity': '1', 'assembly_unit': '09 备件'}], project=other)
        self.post(
            'manager',
            f'bom/{BOMLine.objects.get(project=other, item=self.old).pk}/replace/',
            {'item': self.new.pk, 'quantity': '1', 'change_note': '别的项目先升版'},
        )
        preview = self.upload(
            [
                self.row('JG-001B', replaces='JG-001'),
                self.row('JG-001', unit='03 检测', qty='1', note='新增'),
            ]
        )
        self.assertTrue(preview['can_import'], preview['errors'])
        replace, added = preview['lines']
        self.assertEqual(replace['bom_action'], 'replace')
        impact = replace['replace_impact']
        self.assertEqual([(row['code'], row['quantity']) for row in impact['in_transit']], [(approved.code, '2.000')])
        # 03 单元新增 1 件旧版：换版后旧版仍需 1，已领 2 里 1 件留用。
        self.assertEqual(
            (impact['need_after'], impact['pending_issued'], impact['pending_stock']), ('1.000', '1.000', '2.000')
        )
        self.assertEqual(added['bom_action'], 'create')
        self.assertEqual(added['newer_revision']['code'], 'JG-001B')
        self.assertIn('物料编码改为 JG-001B', added['revision_hint'])
        self.assertNotIn('revision_hint', replace)


class ContractUpdateTests(RevisionFixtures, TestCase):
    """已归档合同的采购单按新图改单后，提醒采购与供应商确认并归档新版本合同。"""

    def setUp(self):
        super().setUp()
        from apps.core.models import Company

        Company.objects.create(pk=1, name='采购方', address='采购方地址', phone='123')
        self.supplier.address, self.supplier.phone = '供应商地址', '456'
        self.supplier.save()
        self.purchase = self.buy(self.line, '4', price='10')
        self.archive()

    def archive(self):
        from apps.business.models import Document

        url = f'purchases/{self.purchase.pk}/'
        current = self.get('purchaser', url + 'contract-preview/', {'version': 'current'})
        document = Document.objects.create(
            purchase=self.purchase, category='contract', original_name='签署.pdf', file='f', size=1, sha256='b' * 64
        )
        self.post(
            'purchaser',
            url + 'archive-contract/',
            {
                'expected_snapshot': current['snapshot_hash'],
                'document': document.pk,
                'delivery_address': '工厂',
                'confirmed': True,
            },
            status=201,
        )

    def test_confirmed_revision_flags_contract_until_new_version_is_archived(self):
        url = f'purchases/{self.purchase.pk}/'
        self.assertEqual(self.get('purchaser', url + 'contract-preview/')['changes_since_archive'], [])
        self.replace()
        converted = self.purchase.lines.get(item=self.new)
        # 待确认期间只在「换版改单待确认」里，不重复提醒重签。
        self.assertNotIn('contract_updates', self.get('purchaser', 'workbench/'))
        self.post(
            'purchaser',
            url + 'revision-review/',
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '12', 'reason': '供应商按 B 版报价'},
            status=403,
        )
        result = self.post(
            'purchase_manager',
            url + 'revision-review/',
            {'line': converted.pk, 'decision': 'confirm', 'unit_price': '12', 'reason': '供应商按 B 版报价'},
        )
        self.assertEqual(result['contract_version'], 1)
        preview = self.get('purchaser', url + 'contract-preview/')
        current = self.get('purchaser', url + 'contract-preview/', {'version': 'current'})
        self.assertEqual(current['effective_total'], '48.00')
        self.assertEqual(current['cancelled_amount'], '40.00')
        self.assertEqual(preview['latest_archived_version'], 1)
        self.assertEqual(
            preview['changes_since_archive'],
            ['JG-001（A 版） 数量 4 → 0', '新增 JG-001B（B 版） 夹爪安装板 4 件，单价 12.00'],
        )
        workbench = self.get('purchaser', 'workbench/')
        self.assertEqual([row['id'] for row in workbench['contract_updates']['results']], [self.purchase.pk])
        self.assertNotIn('contract_updates', self.get('warehouse', 'workbench/'))
        self.archive()
        self.assertEqual(self.get('purchaser', url + 'contract-preview/')['changes_since_archive'], [])
        self.assertNotIn('contract_updates', self.get('purchaser', 'workbench/'))

    def test_cancelled_converted_line_also_flags_stale_contract(self):
        from apps.business.models import Document

        other = Item.objects.create(code='JG-OTHER', name='辅件', unit='件')
        other_bom = BOMLine.objects.create(
            project=self.project, item=other, quantity=Decimal('2.000'), assembly_unit='U2'
        )
        created = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [
                    {'item': self.old.pk, 'bom_line': self.line.pk, 'quantity': '4', 'unit_price': '10'},
                    {'item': other.pk, 'bom_line': other_bom.pk, 'quantity': '2', 'unit_price': '15'},
                ],
            },
            status=201,
        )
        po = PurchaseOrder.objects.get(pk=created['id'])
        self.post('purchaser', f'purchases/{po.pk}/submit/')
        self.post('manager', f'purchases/{po.pk}/approve/')
        po.refresh_from_db()
        url = f'purchases/{po.pk}/'
        current = self.get('purchaser', url + 'contract-preview/', {'version': 'current'})
        doc = Document.objects.create(
            purchase=po, category='contract', original_name='双行签署.pdf', file='f2', size=1, sha256='c' * 64
        )
        self.post(
            'purchaser',
            url + 'archive-contract/',
            {
                'expected_snapshot': current['snapshot_hash'],
                'document': doc.pk,
                'delivery_address': '工厂',
                'confirmed': True,
            },
            status=201,
        )
        self.replace()
        converted = po.lines.get(item=self.new)
        self.post(
            'purchaser',
            url + 'revision-review/',
            {'line': converted.pk, 'decision': 'cancel', 'reason': '供应商不做新版'},
        )
        workbench = self.get('purchaser', 'workbench/')
        self.assertIn(po.pk, [row['id'] for row in workbench['contract_updates']['results']])
        updated = self.get('purchaser', url + 'contract-preview/', {'version': 'current'})
        self.assertEqual(updated['effective_total'], '30.00')
