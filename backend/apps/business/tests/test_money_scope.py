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

from .test_commercial_chain import TODAY, BusinessFixtures

GLOBAL_EXTRAS = ('purchaser', 'warehouse', 'purchase_manager')
COST_PATHS = ('cost/', 'cost-analysis/', 'cost-sources/')


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

    def get(self, path, params=None, role='manager'):
        return self.clients[role].get('/api/business/' + path, params or {})

    def act_as(self, *extras):
        self.manager.additional_roles = list(extras)
        self.manager.save()

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
