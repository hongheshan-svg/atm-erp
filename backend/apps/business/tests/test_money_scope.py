"""兼任全局作业岗位只扩展该岗位动作的范围，不把项目经理的金额读取扩大到非参与项目。

依据 docs/OPERATIONAL_HARDENING.md「兼任全局作业岗位只扩展该岗位动作的范围」与 docs/ROLE_RESPONSIBILITIES.md：
采购员跨项目可见采购单价；仓管看不到采购价格、合同与项目成本；采购经理不自动获得完整项目成本；
项目经理的合同、成本、款项和人员费率读取限负责或参与的项目；管理员、财务全局读取不变。
"""

import tempfile
import uuid
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.business.models import BOMLine, Entry, Project, PurchaseOrder, Task, TimeEntry
from apps.core.permissions import MONEY_READERS, project_allowed

from .test_commercial_chain import TODAY, BusinessFixtures

GLOBAL_EXTRAS = ('purchaser', 'warehouse', 'purchase_manager')
COST_PATHS = ('cost/', 'cost-analysis/', 'cost-sources/')
SALE_MONEY = {'quote_amount', 'contract_amount', 'original_contract_amount'}


class MoneyScopeTests(BusinessFixtures, TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.setup_business()
        self.today = str(timezone.localdate())
        self.manager = self.users['manager']
        self.own = self.active_project()
        self.outsider = User.objects.create_user(username='manager2', role='manager')
        sale = self.post(
            'manager',
            'sales/',
            {
                'name': '外部项目',
                'customer': self.customer.pk,
                'manager': self.outsider.pk,
                'equipment_quantity': 1,
                'warranty_months': 12,
            },
            status=201,
        )
        self.post('manager', f'sales/{sale["id"]}/quote/', {'amount': '20000.00', 'reason': '外部项目报价'})
        signed = self.post(
            'manager',
            f'sales/{sale["id"]}/sign/',
            {
                'date': TODAY,
                'manager': self.outsider.pk,
                'members': [],
                'milestones': [{'title': '合同款', 'amount': '20000.00', 'due_date': TODAY}],
            },
        )
        self.other = Project.objects.get(pk=signed['project'])
        self.sale_id = sale['id']
        self.assertFalse(self.other.members.filter(pk=self.manager.pk).exists())
        self.assertNotEqual(self.other.manager_id, self.manager.pk)

        self.approved = self.order(self.other, '5.000', '100.00', approver='admin')
        self.submitted = self.order(self.other, '1.000', '50.00')
        self.own_approved = self.order(self.own, '2.000', '30.00', approver='admin')
        self.own_submitted = self.order(self.own, '1.000', '20.00')
        self.statement = self.post(
            'finance',
            'reconciliations/',
            {
                'entry': Entry.objects.get(purchase=self.approved).pk,
                'kind': 'prepayment',
                'counterparty_balance': '500.00',
                'approved_amount': '100.00',
                'basis': '合同预付20%',
                'reason': '外部项目预付申请',
            },
            status=201,
        )['id']
        self.receive(self.approved)
        self.receive(self.own_approved)
        receivable = Entry.objects.get(project=self.other, kind='receivable')
        self.post(
            'finance', f'entries/{receivable.pk}/pay/', {'amount': '1000.00', 'date': self.today, 'reason': '外部回款'}
        )
        other_task = Task.objects.create(project=self.other, kind='design', title='外部设计', assignee=self.outsider)
        TimeEntry.objects.create(
            task=other_task,
            user=self.outsider,
            date=timezone.localdate(),
            hours=2,
            hourly_cost=80,
            cost=160,
            reason='外部工时',
        )
        own_task = Task.objects.create(project=self.own, kind='design', title='本项目设计', assignee=self.manager)
        TimeEntry.objects.create(
            task=own_task,
            user=self.manager,
            date=timezone.localdate(),
            hours=1,
            hourly_cost=55,
            cost=55,
            reason='本项目工时',
        )
        BOMLine.objects.create(project=self.other, item=self.item, quantity=5)
        self.contract = self.upload(self.other, 'contract')
        self.technical = self.upload(self.other, 'other')
        self.own_contract = self.upload(self.own, 'contract')
        self.sale_contract = self.upload_sale(self.sale_id, 'contract')
        self.sale_technical = self.upload_sale(self.sale_id, 'other')

    def order(self, project, quantity, price, *, approver=None):
        created = self.post(
            'purchaser',
            'purchases/',
            {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': self.item.pk, 'quantity': quantity, 'unit_price': price}],
            },
            status=201,
        )
        self.post('purchaser', f'purchases/{created["id"]}/submit/')
        if approver:
            self.post(approver, f'purchases/{created["id"]}/approve/')
        return PurchaseOrder.objects.get(pk=created['id'])

    def receive(self, purchase, quantity='1'):
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {
                'received_date': self.today,
                'reason': '实际到货',
                'lines': [{'line': purchase.lines.get().pk, 'quantity': quantity}],
            },
        )

    def upload(self, project, category):
        response = self.clients['admin'].post(
            '/api/business/documents/',
            {'project': project.pk, 'category': category, 'file': SimpleUploadedFile(f'{category}.txt', b'fixture')},
            format='multipart',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def upload_sale(self, sale_id, category):
        response = self.clients['admin'].post(
            '/api/business/documents/',
            {'sale': sale_id, 'category': category, 'file': SimpleUploadedFile(f'sale-{category}.txt', b'fixture')},
            format='multipart',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def get(self, path, params=None, role='manager'):
        return self.clients[role].get('/api/business/' + path, params or {})

    def act_as(self, *extras):
        self.manager.additional_roles = list(extras)
        self.manager.save()

    def sales_money_leaks(self, role='manager'):
        """已签约且关联非参与项目的销售单：行可见，合同额、回款、补充协议金额及合同附件按项目金额范围隐藏。"""
        leaks = []
        listed = {row['id']: row for row in self.get('sales/', {'page_size': 200}, role).data['results']}
        self.assertIn(self.sale_id, listed, '销售单行可见性不变')
        row = listed[self.sale_id]
        if SALE_MONEY & set(row) or row.get('amounts_visible') is not False:
            leaks.append(f'销售列表含非参与项目合同额 {row.get("contract_amount")}')
        own = listed[self.own.sale.pk]
        if not SALE_MONEY <= set(own) or own['amounts_visible'] is not True:
            leaks.append('销售列表误隐藏本人负责项目合同额')
        detail = self.get(f'sales/{self.sale_id}/', role=role).data
        self.assertEqual(detail['project'], self.other.pk)
        if SALE_MONEY & set(detail):
            leaks.append(f'销售详情含非参与项目合同额 {detail.get("contract_amount")}')
        progress = self.get(f'sales/{self.sale_id}/progress/', role=role).data
        if progress['receivables'] or progress.get('amounts_visible') is not False:
            leaks.append(f'销售交付与回款含非参与项目回款 {progress["receivables"]}')
        export = self.get('sales/export/', {'file_format': 'csv'}, role).content.decode('utf-8-sig')
        if '20000' in export or self.other.sale.code not in export:
            leaks.append('销售导出含非参与项目合同额或误删销售行')
        history = self.get(f'sales/{self.sale_id}/amendments/', role=role).data
        if any('amount' in {*record['before'], *record['after']} or record['document'] for record in history):
            leaks.append(f'补充协议记录含非参与项目金额或合同附件 {history}')
        sale_docs = {row['id'] for row in self.get('documents/', {'sale': self.sale_id}, role).data['results']}
        project_docs = {row['id'] for row in self.get('documents/', {'project': self.other.pk}, role).data['results']}
        if self.sale_contract in sale_docs | project_docs:
            leaks.append('附件列表含非参与项目销售合同')
        if self.sale_technical not in sale_docs:
            leaks.append('附件列表误隐藏销售技术附件')
        for path in (f'documents/{self.sale_contract}/', f'documents/{self.sale_contract}/download/'):
            if self.get(path, role=role).status_code != 404:
                leaks.append(f'非参与项目销售合同附件可读 {path}')
        return leaks

    def money_leaks(self, extra):
        """逐个金额读取入口核对非参与项目；返回越界项，便于一次看到全部泄露。"""
        other = self.other.pk
        leaks = []
        detail = self.get(f'projects/{other}/')
        self.assertEqual(detail.status_code, 200, '兼任全局岗位后仍可查看项目基本信息')
        self.assertFalse(detail.data['can_manage'])
        if {'quote_amount', 'contract_amount'} & set(detail.data):
            leaks.append(f'项目详情含合同金额 {detail.data.get("contract_amount")}')
        listed = {row['id']: row for row in self.get('projects/').data['results']}
        if 'contract_amount' in listed[other]:
            leaks.append('项目列表含非参与项目合同金额')
        if 'contract_amount' not in listed[self.own.pk]:
            leaks.append('项目列表误隐藏本人负责项目合同金额')
        for path in COST_PATHS:
            response = self.get(f'projects/{other}/{path}')
            if response.status_code not in (403, 404):
                leaks.append(f'{path} -> {response.status_code}')
        if self.get('entries/', {'project': other}).data['count']:
            leaks.append('entries 列表含非参与项目款项')
        export = self.get('entries/export/', {'project': other})
        if export.status_code != 200 or self.approved.code.encode() in export.content:
            leaks.append(f'entries 导出含非参与项目款项 ({export.status_code})')
        summary = self.get('entries/summary/', {'project': other}).data
        if any(Decimal(value) for value in summary.values()):
            leaks.append(f'entries/summary 非零 {summary}')
        if self.get('payments/', {'entry__project': other}).data['count']:
            leaks.append('payments 列表含非参与项目收付款')
        if self.get('reconciliations/', {'entry__project': other}).data['count']:
            leaks.append('对账单列表含非参与项目')
        if self.get(f'reconciliations/{self.statement}/').status_code not in (403, 404):
            leaks.append('非参与项目对账单详情可读')
        monthly = self.get('reconciliations/supplier-monthly/', {'supplier': self.supplier.pk, 'month': self.today[:7]})
        self.assertEqual(monthly.status_code, 200, monthly.data)
        if other in {row['project'] for row in monthly.data['rows']}:
            leaks.append('供应商月度对账含非参与项目应付')
        rows = self.get('time/', {'task__project': other}).data['results']
        self.assertEqual(len(rows), 1, '兼任全局岗位后工时行仍按原范围可见')
        if {'hourly_cost', 'cost'} & set(rows[0]):
            leaks.append(f'工时含费率/成本 {rows[0].get("hourly_cost")}/{rows[0].get("cost")}')
        exported = self.get('time/export/', {'task__project': other}).content.decode('utf-8-sig')
        if '160.00' in exported or '80.00' in exported:
            leaks.append('工时导出含费率/成本')
        documents = {row['id'] for row in self.get('documents/', {'project': other}).data['results']}
        if self.contract in documents:
            leaks.append('附件列表含非参与项目合同')
        if self.technical not in documents:
            leaks.append('附件列表误隐藏非金额技术附件')
        if self.get(f'documents/{self.contract}/download/').status_code != 404:
            leaks.append('非参与项目合同附件可下载')
        leaks.extend(self.sales_money_leaks())
        settlements = self.get('workbench/').data.get('settlements', {'results': []})['results']
        if other in {row['project'] for row in settlements}:
            leaks.append('工作台 settlements 含非参与项目款项')
        moves = self.get('moves/', {'project': other}).data['results']
        if any({'value', 'supplier_credit'} & set(row) for row in moves):
            leaks.append('库存流水含非参与项目金额')
        line = self.get(f'purchases/{self.approved.pk}/').data['lines'][0]
        if extra == 'warehouse' and 'unit_price' in line:
            leaks.append('兼任仓管后可见非参与项目采购单价')
        if extra == 'warehouse' and self.get(f'purchases/{self.approved.pk}/contract-preview/').status_code != 403:
            leaks.append('兼任仓管后可见非参与项目采购合同金额')
        check = self.get(f'purchases/{self.submitted.pk}/budget-check/')
        if extra == 'purchase_manager':
            if check.status_code != 200 or check.data.get('scope') != 'purchasing' or 'rows' in check.data:
                leaks.append(f'budget-check 未限为材料摘要 {check.status_code} {sorted(check.data)}')
        elif check.status_code not in (403, 404):
            leaks.append(f'budget-check -> {check.status_code} {sorted(check.data)}')
        return leaks

    def test_manager_alone_stays_within_participating_projects(self):
        other = self.other.pk
        self.assertEqual(self.get(f'projects/{other}/').status_code, 404)
        for path in COST_PATHS:
            self.assertEqual(self.get(f'projects/{other}/{path}').status_code, 404, path)
        self.assertEqual(self.get('entries/', {'project': other}).data['count'], 0)
        self.assertEqual(self.get('payments/', {'entry__project': other}).data['count'], 0)
        self.assertEqual(self.get('time/', {'task__project': other}).data['count'], 0)
        self.assertEqual(self.get(f'documents/{self.contract}/download/').status_code, 404)
        self.assertEqual(self.get(f'purchases/{self.submitted.pk}/budget-check/').status_code, 404)
        self.assertEqual(self.get(f'documents/{self.own_contract}/download/').status_code, 200)
        self.assertIn('rows', self.get(f'purchases/{self.own_submitted.pk}/budget-check/').data)
        self.assertEqual(self.sales_money_leaks(), [])

    def test_global_operational_roles_do_not_extend_manager_money_scope(self):
        for extra in GLOBAL_EXTRAS:
            with self.subTest(extra=extra):
                self.act_as(extra)
                self.assertEqual(self.money_leaks(extra), [])
                self.assertTrue(Entry.objects.filter(project=self.other).exists())

    def test_joining_project_restores_manager_money_access(self):
        self.other.members.add(self.manager)
        other = self.other.pk
        for extra in GLOBAL_EXTRAS:
            with self.subTest(extra=extra):
                self.act_as(extra)
                self.assertEqual(self.get(f'projects/{other}/').data['contract_amount'], '20000.00')
                for path in COST_PATHS:
                    self.assertEqual(self.get(f'projects/{other}/{path}').status_code, 200, path)
                self.assertEqual(self.get('entries/', {'project': other}).data['count'], 2)
                self.assertIn(self.approved.code.encode(), self.get('entries/export/', {'project': other}).content)
                self.assertEqual(self.get('payments/', {'entry__project': other}).data['count'], 1)
                self.assertEqual(self.get('reconciliations/', {'entry__project': other}).data['count'], 1)
                row = self.get('time/', {'task__project': other}).data['results'][0]
                self.assertEqual((row['hourly_cost'], row['cost']), ('80.00', '160.00'))
                self.assertEqual(self.get(f'documents/{self.contract}/download/').status_code, 200)
                settlements = self.get('workbench/').data['settlements']['results']
                self.assertIn(other, {row['project'] for row in settlements})
                self.assertIn('value', self.get('moves/', {'project': other}).data['results'][0])
                self.assertEqual(self.get(f'purchases/{self.approved.pk}/').data['lines'][0]['unit_price'], '100.00')
                self.assertIn('rows', self.get(f'purchases/{self.submitted.pk}/budget-check/').data)
                self.assert_sale_money_visible()

    def assert_sale_money_visible(self, role='manager', sale_id=None, document=None):
        sale_id = sale_id or self.sale_id
        listed = {row['id']: row for row in self.get('sales/', {'page_size': 200}, role).data['results']}
        self.assertTrue(listed[sale_id]['amounts_visible'])
        self.assertTrue(SALE_MONEY <= set(listed[sale_id]))
        detail = self.get(f'sales/{sale_id}/', role=role).data
        self.assertEqual(detail['contract_amount'], detail['quote_amount'])
        progress = self.get(f'sales/{sale_id}/progress/', role=role).data
        self.assertTrue(progress['amounts_visible'])
        self.assertTrue(progress['receivables'])
        self.assertTrue({'amount', 'credit_amount', 'paid', 'balance'} <= set(progress['receivables'][0]))
        exported = self.get('sales/export/', {'file_format': 'csv'}, role).content.decode('utf-8-sig')
        self.assertIn(detail['contract_amount'].split('.')[0], exported)
        self.assertEqual(self.get(f'documents/{document or self.sale_contract}/download/', role=role).status_code, 200)
        return detail, progress

    def test_finance_and_admin_keep_global_money_access(self):
        other = self.other.pk
        for role in ('finance', 'admin'):
            with self.subTest(role=role):
                self.assertEqual(self.get(f'projects/{other}/', role=role).data['contract_amount'], '20000.00')
                for path in COST_PATHS:
                    self.assertEqual(self.get(f'projects/{other}/{path}', role=role).status_code, 200, path)
                self.assertEqual(self.get('entries/', {'project': other}, role=role).data['count'], 2)
                self.assertEqual(self.get('payments/', {'entry__project': other}, role=role).data['count'], 1)
                self.assertEqual(self.get('reconciliations/', {'entry__project': other}, role=role).data['count'], 1)
                row = self.get('time/', {'task__project': other}, role=role).data['results'][0]
                self.assertEqual(row['cost'], '160.00')
                self.assertEqual(self.get(f'documents/{self.contract}/download/', role=role).status_code, 200)
                self.assertIn('value', self.get('moves/', {'project': other}, role=role).data['results'][0])
                self.assertIn('rows', self.get(f'purchases/{self.submitted.pk}/budget-check/', role=role).data)
                monthly = self.get(
                    'reconciliations/supplier-monthly/', {'supplier': self.supplier.pk, 'month': self.today[:7]}, role
                ).data
                self.assertIn(other, {row['project'] for row in monthly['rows']})
                _, progress = self.assert_sale_money_visible(role)
                self.assertEqual(progress['receivables'][0]['paid'], '1000.00')

    def test_revoked_membership_is_not_reused_by_later_requests(self):
        self.act_as('warehouse')
        self.other.members.add(self.manager)
        self.assertIn('contract_amount', self.get(f'projects/{self.other.pk}/').data)
        self.other.members.remove(self.manager)
        self.assertNotIn('contract_amount', self.get(f'projects/{self.other.pk}/').data)
        self.assertEqual(self.get(f'projects/{self.other.pk}/cost/').status_code, 403)
        self.assertEqual(self.get('entries/', {'project': self.other.pk}).data['count'], 0)
        self.assertEqual(self.get(f'documents/{self.contract}/download/').status_code, 404)

    def test_purchase_document_uses_purchase_scope_not_warehouse_scope(self):
        response = self.clients['admin'].post(
            '/api/business/documents/',
            {
                'purchase': self.approved.pk,
                'category': 'contract',
                'file': SimpleUploadedFile('purchase-contract.txt', b'contract fixture'),
            },
            format='multipart',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201, response.data)
        document = response.data['id']
        for extra, expected in [('warehouse', 404), ('purchaser', 200), ('purchase_manager', 200)]:
            with self.subTest(extra=extra):
                self.act_as(extra)
                self.assertEqual(self.get(f'documents/{document}/download/').status_code, expected)
                visible = self.get('documents/', {'purchase': self.approved.pk}).data['results']
                self.assertEqual(document in {row['id'] for row in visible}, expected == 200)

    def test_global_operational_roles_keep_their_own_cross_project_reads(self):
        other = self.other.pk
        self.act_as('purchaser')
        line = self.get(f'purchases/{self.approved.pk}/').data['lines'][0]
        self.assertEqual(line['unit_price'], '100.00')
        exported = self.get('purchases/export/', {'project': other}).content.decode('utf-8-sig')
        self.assertIn(self.approved.code, exported)
        self.assertIn('100.00', exported)
        self.assertEqual(self.get('bom/', {'project': other}).data['count'], 1)
        self.assertEqual(self.get(f'projects/{other}/demand/').status_code, 200)
        self.assertEqual(self.get('tasks/', {'project': other}).data['count'], 1)

        self.act_as('warehouse')
        purchase = self.get(f'purchases/{self.approved.pk}/').data
        self.assertEqual(purchase['lines'][0]['received_quantity'], '1.000')
        self.assertNotIn('unit_price', purchase['lines'][0])
        own_line = self.get(f'purchases/{self.own_approved.pk}/').data['lines'][0]
        self.assertEqual(own_line['unit_price'], '30.00')
        moves = self.get('moves/', {'project': other}).data['results']
        self.assertEqual([row['quantity'] for row in moves], ['1.000'])
        self.assertIn('value', self.get('moves/', {'project': self.own.pk}).data['results'][0])

        self.act_as('purchase_manager')
        summary = self.get(f'purchases/{self.submitted.pk}/budget-check/').data
        self.assertEqual(summary['scope'], 'purchasing')
        self.assertEqual(summary['purchase_amount'], '50.00')
        self.assertIn('rows', self.get(f'purchases/{self.own_submitted.pk}/budget-check/').data)

        self.act_as('purchaser', 'warehouse')
        self.assertEqual(self.get(f'purchases/{self.approved.pk}/').data['lines'][0]['unit_price'], '100.00')

    def test_money_scope_is_resolved_once_per_list(self):
        self.act_as('warehouse')

        def queries():
            with CaptureQueriesContext(connection) as captured:
                response = self.get('moves/')
            self.assertEqual(response.status_code, 200)
            return len(captured), response.data['count']

        before, rows = queries()
        self.receive(self.approved)
        self.receive(self.own_approved)
        after, more = queries()
        self.assertEqual(more, rows + 2)
        self.assertEqual(after, before)

    def test_unsigned_and_own_sales_keep_amounts_for_managers(self):
        draft = self.post(
            'admin',
            'sales/',
            {
                'name': '外部需求',
                'customer': self.customer.pk,
                'manager': self.outsider.pk,
                'equipment_quantity': 1,
                'warranty_months': 12,
            },
            status=201,
        )
        self.post('admin', f'sales/{draft["id"]}/quote/', {'amount': '3000.00', 'reason': '外部初步报价'})
        owned = {}
        for owner in ('manager', 'sales_manager'):
            sale = self.post(
                'admin',
                'sales/',
                {
                    'name': f'{owner}负责的销售',
                    'customer': self.customer.pk,
                    'manager': self.users[owner].pk,
                    'equipment_quantity': 1,
                    'warranty_months': 12,
                },
                status=201,
            )
            self.post('admin', f'sales/{sale["id"]}/quote/', {'amount': '7000.00', 'reason': '本人报价'})
            signed = self.post(
                'admin',
                f'sales/{sale["id"]}/sign/',
                {
                    'date': TODAY,
                    'manager': self.outsider.pk,
                    'members': [],
                    'milestones': [{'title': '合同款', 'amount': '7000.00', 'due_date': TODAY}],
                },
            )
            project = Project.objects.get(pk=signed['project'])
            self.assertFalse(project_allowed(self.users[owner], project, MONEY_READERS))
            owned[owner] = (sale['id'], self.upload_sale(sale['id'], 'contract'))
        for extras in ([], ['sales_manager'], ['purchaser']):
            with self.subTest(extras=extras):
                self.act_as(*extras)
                draft_detail = self.get(f'sales/{draft["id"]}/').data
                self.assertEqual(draft_detail['quote_amount'], '3000.00')
                self.assertTrue(draft_detail['amounts_visible'])
                sale_id, document = owned['manager']
                detail, _ = self.assert_sale_money_visible(sale_id=sale_id, document=document)
                self.assertEqual(detail['contract_amount'], '7000.00')
                self.assertEqual(self.sales_money_leaks(), [])
                if extras == ['sales_manager']:
                    bucket = {row['id']: row for row in self.get('workbench/').data['sales']['results']}
                    self.assertFalse(SALE_MONEY & set(bucket[self.sale_id]))
                    self.assertEqual(bucket[sale_id]['contract_amount'], '7000.00')
        sale_id, document = owned['sales_manager']
        detail, _ = self.assert_sale_money_visible('sales_manager', sale_id, document)
        self.assertEqual(detail['contract_amount'], '7000.00')

    def test_amendment_amounts_follow_project_money_scope(self):
        detail = self.get(f'sales/{self.sale_id}/', role='admin').data
        self.post(
            'admin',
            f'sales/{self.sale_id}/amend/',
            {
                'expected_updated_at': detail['updated_at'],
                'reason': '增加调试范围',
                'document': self.sale_contract,
                'date': TODAY,
                'amount': '25000.00',
                'equipment_quantity': 1,
                'warranty_months': 12,
                'milestones': [{'title': '增补款', 'amount': '5000.00', 'due_date': TODAY}],
                'credits': [],
            },
        )
        self.act_as('purchaser')
        history = self.get(f'sales/{self.sale_id}/amendments/').data
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['before'], {'equipment_quantity': 1, 'warranty_months': 12})
        self.assertEqual(history[0]['after'], {'equipment_quantity': 1, 'warranty_months': 12})
        self.assertIsNone(history[0]['document'])
        self.assertIsNone(history[0]['document__original_name'])
        self.assertEqual(history[0]['reason'], '增加调试范围')
        self.assertEqual(self.sales_money_leaks(), [])
        self.assertNotIn('25000', self.get('sales/export/', {'file_format': 'csv'}).content.decode('utf-8-sig'))

        self.other.members.add(self.manager)
        history = self.get(f'sales/{self.sale_id}/amendments/').data
        self.assertEqual((history[0]['before']['amount'], history[0]['after']['amount']), ('20000.00', '25000.00'))
        self.assertEqual(history[0]['document'], self.sale_contract)
        detail = self.get(f'sales/{self.sale_id}/').data
        self.assertEqual((detail['contract_amount'], detail['original_contract_amount']), ('25000.00', '20000.00'))
        self.assertEqual(len(self.get(f'sales/{self.sale_id}/progress/').data['receivables']), 2)
