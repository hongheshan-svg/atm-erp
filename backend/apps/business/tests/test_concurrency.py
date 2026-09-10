import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import Delivery, Entry, Payment, Stock, StockMove, Task, TimeEntry

from .test_commercial_chain import TODAY, BusinessFixtures


class BusinessConcurrencyTests(BusinessFixtures, TransactionTestCase):
    def test_concurrent_bank_allocations_cannot_overclaim(self):
        from apps.business.models import BankMatch, BankRecord
        from apps.business.services.banking import remaining

        bank = self.post(
            'finance',
            'bank-records/',
            {
                'amount': '500',
                'date': TODAY,
                'account': 'BANK-A',
                'reference': 'B-001',
                'counterparty': '客户',
                'reason': '实际到账',
            },
            status=201,
        )['id']
        entry = self.project.entries.get(kind='receivable')
        payload = {'entry': entry.pk, 'amount': '400', 'reason': '并发认领'}
        results = self.together([('finance', f'bank-records/{bank}/allocate/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(BankMatch.objects.count(), 1)
        self.assertEqual(remaining(BankRecord.objects.get(pk=bank)), 100)

    def test_concurrent_bank_matches_cannot_match_same_payment_twice(self):
        from apps.business.models import BankMatch

        bank = self.post(
            'finance',
            'bank-records/',
            {
                'amount': '1000',
                'date': TODAY,
                'account': 'BANK-A',
                'reference': 'B-002',
                'counterparty': '客户',
                'reason': '实际到账',
            },
            status=201,
        )['id']
        entry = self.project.entries.get(kind='receivable')
        payment = self.post(
            'finance',
            f'entries/{entry.pk}/pay/',
            {'amount': '400', 'date': TODAY, 'method': 'bank', 'account': 'BANK-A', 'reason': '已登记收款'},
        )['id']
        results = self.together(
            [('finance', f'bank-records/{bank}/match/', {'payment': payment, 'reason': '并发匹配'})] * 2
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(BankMatch.objects.count(), 1)

    def test_concurrent_payments_cannot_overrun_confirmed_limit(self):
        entry = self.purchase(self.project).entry
        statement = self.post(
            'finance',
            'reconciliations/',
            {
                'entry': entry.pk,
                'kind': 'prepayment',
                'counterparty_balance': '500',
                'approved_amount': '100',
                'basis': '合同预付20%',
                'reason': '预付核准',
            },
            status=201,
        )['id']
        self.post('manager', f'reconciliations/{statement}/confirm/', {'reason': '按合同确认'})
        payload = {'amount': '80', 'date': TODAY, 'reason': '并发付款', 'reconciliation': statement}
        results = self.together([('finance', f'entries/{entry.pk}/pay/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Payment.objects.get().amount, 80)

    def test_concurrent_quarantine_release_cannot_double_stock(self):
        purchase = self.purchase(self.project, qty='1')
        line = purchase.lines.get()
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {
                'location': '主仓',
                'reason': '隔离',
                'lines': [{'line': line.pk, 'quantity': '0', 'pending_quantity': '1'}],
            },
        )
        payload = {'location': '主仓', 'reason': '复检合格', 'lines': [{'line': line.pk, 'quantity': '1'}]}
        results = self.together([('warehouse', f'purchases/{purchase.pk}/quality-accept/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Stock.objects.get().quantity, 1)

    def test_concurrent_contract_amendments_preserve_one_version(self):
        from apps.business.models import ContractAmendment, Document

        sale = self.project.sale
        doc = Document.objects.create(
            project=self.project,
            category='contract',
            original_name='agreement.pdf',
            file='test',
            size=1,
            sha256='a' * 64,
        )
        payload = {
            'expected_updated_at': sale.updated_at.isoformat(),
            'reason': '追加设备费用',
            'date': TODAY,
            'document': doc.pk,
            'amount': '10100',
            'equipment_quantity': 1,
            'warranty_months': 12,
            'milestones': [{'title': '追加', 'amount': '100', 'due_date': TODAY}],
        }
        results = self.together([('manager', f'sales/{sale.pk}/amend/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(ContractAmendment.objects.count(), 1)
        self.assertEqual(Entry.objects.filter(title='追加').count(), 1)

    def test_concurrent_import_confirmation_creates_one_batch(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.business.models import Item
        from apps.business.services.transfers import preview

        batch = preview(
            self.users['admin'],
            'items',
            SimpleUploadedFile('items.csv', '物料编码,名称,规格,单位\nBATCH1,批量物料,,件\n'.encode()),
        )
        results = self.together([('admin', 'items/import-confirm/', {'token': batch['token']})] * 2)
        self.assertEqual([status for status, _ in results], [200, 200], results)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(Item.objects.filter(code='BATCH1').count(), 1)

    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.setup_business()
        self.project = self.active_project()
        clock = patch('apps.business.services.execution.timezone.localdate', return_value=date.fromisoformat(TODAY))
        clock.start()
        self.addCleanup(clock.stop)

    def together(self, requests):
        barrier = Barrier(len(requests))

        def perform(spec):
            role, url, data = spec
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=self.users[role].pk))
                barrier.wait(timeout=10)
                response = client.post(
                    '/api/business/' + url, data, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
                )
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(perform, requests))

    def test_concurrent_approvals_create_one_payable(self):
        purchase = self.purchase(self.project, approve=False)
        results = self.together([('manager', f'purchases/{purchase.pk}/approve/', {})] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Entry.objects.filter(purchase=purchase).count(), 1)

    def test_manual_and_automatic_material_codes_cannot_collide(self):
        from apps.business.models import Item

        results = self.together(
            [
                ('purchaser', 'items/', {'name': '手工', 'code': 'MAT000001'}),
                ('purchaser', 'items/', {'name': '自动'}),
            ]
        )
        self.assertIn(sorted(status for status, _ in results), [[201, 201], [201, 400]])
        codes = list(Item.objects.filter(name__in=['手工', '自动']).values_list('code', flat=True))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(Item.objects.filter(name='自动').exists())

    def test_two_sales_cannot_sign_with_same_contract_number(self):
        from apps.business.models import SalesOrder

        sales = [
            self.post(
                'manager',
                'sales/',
                {'name': name, 'customer': self.customer.pk, 'manager': self.users['manager'].pk},
                status=201,
            )
            for name in ['合同甲', '合同乙']
        ]
        for sale in sales:
            self.post('manager', f'sales/{sale["id"]}/quote/', {'amount': '100', 'reason': '确认'})
        data = {
            'date': TODAY,
            'contract_number': 'HT-CONCURRENT',
            'milestones': [{'title': '款项', 'amount': '100', 'due_date': TODAY}],
        }
        results = self.together([('manager', f'sales/{sale["id"]}/sign/', data) for sale in sales])
        self.assertEqual(sorted(status for status, _ in results), [200, 400])
        self.assertEqual(SalesOrder.objects.filter(contract_number='HT-CONCURRENT').count(), 1)

    def test_two_purchase_approvals_cannot_both_consume_remaining_budget(self):
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {'materials': '500', 'labor': '0', 'expenses': '0', 'expected_revision': 0, 'reason': '限额'},
        )
        purchases = [self.purchase(self.project, qty='3', approve=False) for _ in range(2)]
        results = self.together([('manager', f'purchases/{p.pk}/approve/', {}) for p in purchases])
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Entry.objects.filter(purchase__in=purchases).count(), 1)

    def test_concurrent_bom_revisions_do_not_overwrite_same_snapshot(self):
        from apps.business.models import BOMLine

        version = self.bom_version(self.project.pk)
        results = self.together(
            [
                (
                    'manager',
                    f'projects/{self.project.pk}/revise-bom/',
                    {'expected_revision': version, 'lines': [{'item': self.item.pk, 'quantity': quantity}]},
                )
                for quantity in ['1', '2']
            ]
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(BOMLine.objects.count(), 1)

    def test_concurrent_sales_edits_reject_stale_version(self):
        from apps.business.models import SalesOrder

        result = self.post(
            'manager',
            'sales/',
            {'name': '原需求', 'customer': self.customer.pk, 'manager': self.users['manager'].pk},
            status=201,
        )
        sale = SalesOrder.objects.get(pk=result['id'])
        payload = {'expected_updated_at': sale.updated_at.isoformat(), 'reason': '更正'}
        results = self.together(
            [('manager', f'sales/{sale.pk}/edit/', {**payload, 'name': name}) for name in ['需求甲', '需求乙']]
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        sale.refresh_from_db()
        self.assertIn(sale.name, ['需求甲', '需求乙'])

    def test_concurrent_signing_creates_one_project_and_receivable(self):
        sale = self.post(
            'manager',
            'sales/',
            {
                'name': '并发签约',
                'customer': self.customer.pk,
                'manager': self.users['manager'].pk,
            },
            status=201,
        )
        self.post('manager', f'sales/{sale["id"]}/quote/', {'amount': '100', 'reason': '确认'})
        payload = {'date': TODAY, 'milestones': [{'title': '首款', 'amount': '100', 'due_date': TODAY}]}
        results = self.together([('manager', f'sales/{sale["id"]}/sign/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        project_id = next(data['project'] for status, data in results if status == 200)
        self.assertEqual(Entry.objects.filter(project_id=project_id).count(), 1)
        self.assertEqual(self.project.__class__.objects.count(), 2)

    def test_concurrent_receipts_cannot_exceed_purchase(self):
        purchase = self.purchase(self.project)
        payload = {'lines': [{'line': purchase.lines.get().pk, 'quantity': '4'}], 'reason': '并发收货'}
        results = self.together([('warehouse', f'purchases/{purchase.pk}/receive/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Stock.objects.get().quantity, Decimal('4'))
        self.assertEqual(StockMove.objects.count(), 1)

    def test_concurrent_payments_cannot_exceed_balance(self):
        purchase = self.purchase(self.project)
        entry = Entry.objects.get(purchase=purchase)
        payload = {
            'amount': '400',
            'date': TODAY,
            'reason': '并发付款',
            **self.reconciliation_data(entry, prepayment=True),
        }
        results = self.together([('finance', f'entries/{entry.pk}/pay/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Payment.objects.get(entry=entry).amount, Decimal('400'))

    def test_concurrent_refunds_cannot_exceed_overpayment(self):
        from apps.business.services.finance import balance, paid

        purchase = self.purchase(self.project)
        entry = Entry.objects.get(purchase=purchase)
        self.post(
            'finance',
            f'entries/{entry.pk}/pay/',
            {'amount': '500', 'date': TODAY, 'reason': '预付款', **self.reconciliation_data(entry, prepayment=True)},
        )
        self.post('purchaser', f'purchases/{purchase.pk}/cancel-remainder/', {'reason': '供应商取消'})
        payload = {'amount': '500', 'date': TODAY, 'reason': '退款到账', **self.reconciliation_data(entry)}
        results = self.together([('finance', f'entries/{entry.pk}/refund/', payload)] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        entry.refresh_from_db()
        self.assertEqual((paid(entry), balance(entry)), (Decimal('0'), Decimal('0')))
        self.assertEqual(
            list(Payment.objects.filter(entry=entry).order_by('id').values_list('amount', flat=True)),
            [Decimal('500'), Decimal('-500')],
        )

    def test_receipts_from_different_projects_share_stock_safely(self):
        second_project = self.active_project()
        first = self.purchase(self.project)
        second = self.purchase(second_project, price='20')
        requests = [
            (
                'warehouse',
                f'purchases/{purchase.pk}/receive/',
                {'lines': [{'line': purchase.lines.get().pk, 'quantity': '5'}], 'reason': '不同项目并发入库'},
            )
            for purchase in (first, second)
        ]
        results = self.together(requests)
        self.assertEqual([status for status, _ in results], [200, 200], results)
        stock = Stock.objects.get()
        self.assertEqual((stock.quantity, stock.value), (Decimal('10'), Decimal('600')))

    def test_issues_from_different_projects_cannot_make_stock_negative(self):
        second_project = self.active_project()
        self.post(
            'admin', 'stocks/opening/', {'item': self.item.pk, 'quantity': '5', 'unit_cost': '20', 'reason': '共享库存'}
        )
        stock = Stock.objects.get()
        for project in (self.project, second_project):
            self.post(
                'manager',
                f'projects/{project.pk}/revise-bom/',
                {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '5'}]},
            )
        requests = [
            (
                'warehouse',
                'stocks/issue/',
                {'project': project.pk, 'stock': stock.pk, 'quantity': '4', 'reason': '并发领料'},
            )
            for project in (self.project, second_project)
        ]
        results = self.together(requests)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, stock.value), (Decimal('1'), Decimal('20')))

    def test_time_across_projects_cannot_exceed_daily_person_limit(self):
        second = self.active_project()
        tasks = [
            self.post(
                'manager',
                'tasks/',
                {'project': project.pk, 'kind': 'design', 'title': '跨项目设计', 'assignee': self.users['member'].pk},
                status=201,
            )['id']
            for project in (self.project, second)
        ]
        results = self.together(
            [('member', f'tasks/{task}/time/', {'date': TODAY, 'hours': '15', 'reason': '并发填报'}) for task in tasks]
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(sum(TimeEntry.objects.values_list('hours', flat=True)), Decimal('15'))

    def test_concurrent_shipments_cannot_exceed_equipment_quantity(self):
        for kind in ('design', 'assembly', 'test'):
            task = self.post(
                'manager',
                'tasks/',
                {'project': self.project.pk, 'kind': kind, 'title': kind, 'assignee': self.users['member'].pk},
                status=201,
            )['id']
            self.post('member', f'tasks/{task}/complete/', {'reason': '检查完成'})
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '1'}],
            },
        )
        self.post(
            'admin', 'stocks/opening/', {'item': self.item.pk, 'quantity': '1', 'unit_cost': '20', 'reason': '期初'}
        )
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': Stock.objects.get().pk, 'quantity': '1', 'reason': '领料'},
        )
        results = self.together([('manager', f'projects/{self.project.pk}/ship/', {'quantity': 1, 'date': TODAY})] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(Delivery.objects.count(), 1)
        self.assertEqual(Task.objects.filter(kind__in=['install', 'acceptance']).count(), 2)

    def test_concurrent_time_corrections_reverse_original_once(self):
        task = self.post(
            'manager',
            'tasks/',
            {'project': self.project.pk, 'kind': 'design', 'title': '设计', 'assignee': self.users['member'].pk},
            status=201,
        )['id']
        entry = self.post('member', f'tasks/{task}/time/', {'date': TODAY, 'hours': '3', 'reason': '原填报'})['id']
        results = self.together(
            [('member', f'time/{entry}/amend/', {'date': TODAY, 'hours': '2', 'reason': '并发更正'})] * 2
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(TimeEntry.objects.count(), 3)
        self.assertEqual(sum(TimeEntry.objects.values_list('hours', flat=True)), Decimal('2'))
