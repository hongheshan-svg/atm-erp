import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.business.models import Entry, Project, SalesOrder
from apps.core.models import ActionReceipt, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class SalesTests(BusinessFixtures, TestCase):
    def test_sales_member_cannot_be_removed_with_open_work(self):
        from apps.business.models import Task

        actor = self.users['sales_manager']
        actor.additional_roles = ['member']
        actor.save()
        project = self.active_project()
        project.members.add(actor)
        Task.objects.create(project=project, title='兼岗设计任务', kind='design', assignee=actor)
        self.post('manager', f'projects/{project.pk}/edit/', {'members': [], 'reason': '移除兼岗成员'}, status=409)
        self.assertTrue(project.members.filter(pk=actor.pk).exists())

    def test_sales_purchaser_roles_union_without_sales_scope_leak(self):
        actor = self.users['sales_manager']
        actor.additional_roles = ['purchaser']
        actor.save()
        own = self.sales_manager_order()
        other = self.sale()
        client = self.clients['sales_manager']
        self.assertEqual(client.get('/api/business/sales/').data['count'], 1)
        self.assertEqual(client.get(f'/api/business/sales/{other.pk}/').status_code, 404)
        self.assertEqual(client.get('/api/business/purchases/').status_code, 200)
        self.assertEqual(client.get('/api/business/entries/').status_code, 403)
        self.post('sales_manager', 'partners/', {'name': '兼岗供应商', 'kind': 'supplier'}, status=201)
        self.post('sales_manager', f'sales/{own}/quote/', {'amount': '100', 'reason': '兼岗报价'})
        work = client.get('/api/business/workbench/').data
        self.assertIn('sales', work)
        self.assertIn('drafts', work)
        actor.additional_roles = []
        actor.save()
        self.assertEqual(client.get('/api/business/purchases/').status_code, 403)

    def test_sales_member_project_scope_and_finance_write_scope(self):
        actor = self.users['sales_manager']
        actor.additional_roles = ['member']
        actor.save()
        project = self.active_project()
        client = self.clients['sales_manager']
        self.assertEqual(client.get(f'/api/business/projects/{project.pk}/').status_code, 404)
        project.members.add(actor)
        response = client.get(f'/api/business/projects/{project.pk}/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn('contract_amount', response.data)
        other = self.sale()
        actor.additional_roles = ['finance']
        actor.save()
        self.assertEqual(client.get(f'/api/business/sales/{other.pk}/').status_code, 200)
        self.post('sales_manager', f'sales/{other.pk}/quote/', {'amount': '100', 'reason': '越权'}, status=403)

    def sales_manager_order(self):
        data = {'name': '销售经理订单', 'customer': self.customer.pk, 'manager': self.users['sales_manager'].pk}
        return self.post('sales_manager', 'sales/', data, status=201)['id']

    def test_sales_manager_scope_and_handoff(self):
        own = self.sales_manager_order()
        other = self.sale()
        client = self.clients['sales_manager']
        self.assertEqual(client.get('/api/business/sales/').data['count'], 1)
        self.assertEqual(client.get(f'/api/business/sales/{other.pk}/').status_code, 404)
        self.assertEqual(client.get(f'/api/business/sales/{other.pk}/progress/').status_code, 404)
        export = client.get('/api/business/sales/export/?file_format=csv')
        self.assertEqual(export.status_code, 200)
        self.assertNotIn(other.code, export.content.decode('utf-8-sig'))
        self.post('sales_manager', f'sales/{other.pk}/quote/', {'amount': '100', 'reason': '越权'}, status=404)
        self.post('sales_manager', f'sales/{own}/quote/', {'amount': '100', 'reason': '报价'})
        self.post('sales_manager', f'sales/{own}/sign/', self.signing(), status=400)
        payload = {**self.signing(), 'manager': self.users['manager'].pk}
        result = self.post('sales_manager', f'sales/{own}/sign/', payload, key='sales-sign')
        self.assertEqual(result, self.post('sales_manager', f'sales/{own}/sign/', payload, key='sales-sign'))
        project = Project.objects.get(pk=result['project'])
        self.assertEqual(project.manager_id, self.users['manager'].pk)
        entry = Entry.objects.get(project=project)
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '25', 'date': TODAY, 'reason': '回款'})
        detail = client.get(f'/api/business/sales/{own}/progress/').data
        self.assertEqual(detail['receivables'][0]['paid'], '25.00')
        self.assertEqual(detail['receivables'][0]['balance'], '75.00')
        self.assertNotIn('cost', detail)
        self.assertEqual(client.get('/api/business/workbench/').data['sales']['count'], 1)

    def test_sales_manager_cannot_access_operational_or_financial_interfaces(self):
        project = self.active_project()
        client = self.clients['sales_manager']
        for path in (
            'projects/',
            f'projects/{project.pk}/cost/',
            'bom/',
            'purchases/',
            'stocks/',
            'moves/',
            'entries/',
            'payments/',
            'tasks/',
            'time/',
            'deliveries/',
            'items/',
            'reports/',
        ):
            self.assertEqual(client.get('/api/business/' + path).status_code, 403, path)
        self.assertEqual(client.get('/api/business/documents/').data['count'], 0)
        self.post('sales_manager', 'purchases/', {}, status=403)
        self.post('sales_manager', 'entries/expense/', {}, status=403)
        self.post('sales_manager', 'projects/', {}, status=403)
        self.assertEqual(client.get('/api/auth/users/').status_code, 403)
        self.assertEqual(client.get('/api/core/upgrade/').status_code, 403)

    def test_sales_manager_cannot_assign_others_or_replay_after_transfer(self):
        from rest_framework.exceptions import PermissionDenied

        from apps.business.services import sales

        self.post(
            'sales_manager',
            'sales/',
            {'name': '越权', 'customer': self.customer.pk, 'manager': self.users['manager'].pk},
            status=403,
        )
        own = self.sales_manager_order()
        payload = {'amount': '100', 'reason': '报价'}
        self.post('sales_manager', f'sales/{own}/quote/', payload, key='old-quote')
        SalesOrder.objects.filter(pk=own).update(manager=self.users['manager'])
        with self.assertRaises(PermissionDenied):
            sales.quote(self.users['sales_manager'], 'old-quote', own, payload)

    def test_sales_manager_customer_and_import_permissions(self):
        client = self.clients['sales_manager']
        self.assertEqual(client.get('/api/business/partners/').data['count'], 1)
        self.assertEqual(client.get(f'/api/business/partners/{self.supplier.pk}/').status_code, 404)
        self.post('sales_manager', 'partners/', {'name': '新增客户', 'kind': 'customer'}, status=201)
        self.post('sales_manager', 'partners/', {'name': '供应商', 'kind': 'supplier'}, status=403)
        for resource in ('sales', 'partners'):
            self.assertEqual(client.get(f'/api/business/{resource}/import-template/').status_code, 200)
        self.assertEqual(client.get('/api/business/projects/import-template/').status_code, 403)

    def test_downgraded_sales_manager_cannot_replay_previous_supplier_or_assignment(self):
        from rest_framework.exceptions import PermissionDenied

        from apps.business.models import Partner
        from apps.business.services import masterdata, sales

        actor = self.users['manager']
        customer = {'name': '旧供应商', 'kind': 'supplier'}
        order = {'name': '转交订单', 'customer': self.customer.pk, 'manager': self.users['admin'].pk}
        masterdata.masterdata(actor, 'old-supplier', Partner, customer)
        sales.create(actor, 'old-assignment', order)
        actor.role = 'sales_manager'
        actor.save()
        with self.assertRaises(PermissionDenied):
            masterdata.masterdata(actor, 'old-supplier', Partner, customer)
        with self.assertRaises(PermissionDenied):
            sales.create(actor, 'old-assignment', order)

    def test_contract_number_unique_searchable_and_immutable_after_signing(self):
        first, second = self.sale(), self.sale()
        for sale in (first, second):
            self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '确认'})
        data = {**self.signing(), 'contract_number': ' HT-2026-001 '}
        self.post('manager', f'sales/{first.pk}/sign/', data, key='sign-custom')
        self.post('manager', f'sales/{first.pk}/sign/', data, key='sign-custom')
        self.post('manager', f'sales/{second.pk}/sign/', data, status=400)
        second.refresh_from_db()
        self.assertIsNone(second.project_id)
        self.assertEqual(Entry.objects.count(), 1)
        self.assertEqual(self.clients['manager'].get('/api/business/sales/?search=HT-2026-001').data['count'], 1)
        self.post('manager', f'sales/{first.pk}/sign/', {**data, 'contract_number': 'OTHER'}, status=409)
        first.refresh_from_db()
        self.assertEqual(first.contract_number, 'HT-2026-001')
        self.post('manager', f'sales/{second.pk}/sign/', self.signing())

    def setUp(self):
        self.setup_business()

    def sale(self):
        result = self.post(
            'manager',
            'sales/',
            {
                'name': '独立销售',
                'customer': self.customer.pk,
                'manager': self.users['manager'].pk,
            },
            status=201,
        )
        return SalesOrder.objects.get(pk=result['id'])

    def signing(self):
        return {'date': TODAY, 'milestones': [{'title': '合同款', 'amount': '100', 'due_date': TODAY}]}

    def test_edit_requires_requote_and_replay_does_not_invalidate_new_quote(self):
        sale = self.sale()
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '确认'})
        sale.refresh_from_db()
        payload = {'equipment_quantity': 2, 'reason': '数量更正', 'expected_updated_at': sale.updated_at.isoformat()}
        key = str(uuid.uuid4())
        result = self.post('manager', f'sales/{sale.pk}/edit/', payload, key=key)
        sale.refresh_from_db()
        self.assertEqual((sale.status, sale.equipment_quantity, sale.quote_amount), ('draft', 2, 0))
        self.post('manager', f'sales/{sale.pk}/sign/', self.signing(), status=409)
        self.post('manager', f'sales/{sale.pk}/edit/', {**payload, 'equipment_quantity': 3}, status=409)
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '重新确认'})
        self.assertEqual(result, self.post('manager', f'sales/{sale.pk}/edit/', payload, key=key))
        sale.refresh_from_db()
        self.assertEqual((sale.status, sale.quote_amount), ('quoted', 100))
        result = self.post('manager', f'sales/{sale.pk}/sign/', self.signing())
        self.assertEqual(Project.objects.get(pk=result['project']).equipment_quantity, 2)
        self.post('manager', f'sales/{sale.pk}/edit/', payload, status=409)

    def test_invalid_or_unauthorized_edit_leaves_quote_unchanged(self):
        sale = self.sale()
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '确认'})
        sale.refresh_from_db()
        payload = {'reason': '更正', 'expected_updated_at': sale.updated_at.isoformat()}
        for extra in [
            {'equipment_quantity': 0},
            {'quote_amount': '999'},
            {'manager': self.users['member'].pk},
            {'expected_updated_at': None},
            {},
        ]:
            self.post('manager', f'sales/{sale.pk}/edit/', {**payload, **extra}, status=400)
        self.post('finance', f'sales/{sale.pk}/edit/', {**payload, 'name': '越权修改'}, status=403)
        sale.refresh_from_db()
        self.assertEqual((sale.status, sale.quote_amount, sale.equipment_quantity), ('quoted', 100, 1))

    def test_legacy_project_receives_corrected_sales_details_on_sign(self):
        sale = self.sale()
        project = Project.objects.create(
            code='OLD-P', name='原项目', customer=self.customer, manager=self.users['manager']
        )
        project.members.add(self.users['member'])
        sale.project = project
        sale.save()
        self.post(
            'manager',
            f'sales/{sale.pk}/edit/',
            {
                'name': '更正项目',
                'equipment_quantity': 2,
                'reason': '更正',
                'expected_updated_at': sale.updated_at.isoformat(),
            },
        )
        project.refresh_from_db()
        self.assertEqual(project.name, '原项目')
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '确认'})
        result = self.post('manager', f'sales/{sale.pk}/sign/', self.signing())
        self.assertEqual(result['project'], project.pk)
        project.refresh_from_db()
        self.assertEqual((project.name, project.equipment_quantity), ('更正项目', 2))
        self.assertEqual(list(project.members.all()), [self.users['member']])

    def test_quote_is_independent_and_sign_handoff_is_idempotent(self):
        sale = self.sale()
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '确认'})
        self.assertFalse(Project.objects.exists())
        self.assertFalse(Entry.objects.exists())
        key = str(uuid.uuid4())
        result = self.post('manager', f'sales/{sale.pk}/sign/', self.signing(), key=key)
        self.assertEqual(result, self.post('manager', f'sales/{sale.pk}/sign/', self.signing(), key=key))
        self.post('manager', f'sales/{sale.pk}/sign/', self.signing(), status=409)
        self.assertEqual((Project.objects.count(), Entry.objects.count()), (1, 1))
        sale.refresh_from_db()
        self.assertEqual((sale.status, sale.project_id), ('signed', result['project']))
        self.assertEqual(sale.project.contract_amount, sale.contract_amount)
        self.assertEqual(sale.project.status, 'active')
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '200', 'reason': '不允许改合同'}, status=409)

    def test_failed_finance_handoff_rolls_back_project_sale_and_number(self):
        sale = self.sale()
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '确认'})
        key = str(uuid.uuid4())
        with patch('apps.business.services.sales.finance.record_contract', side_effect=ValidationError('交接失败')):
            self.post('manager', f'sales/{sale.pk}/sign/', self.signing(), key=key, status=400)
        sale.refresh_from_db()
        self.assertEqual((sale.status, sale.project_id, sale.contract_date), ('quoted', None, None))
        self.assertFalse(Project.objects.exists())
        self.assertFalse(Entry.objects.exists())
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.assertEqual(CodeRule.objects.get(key='project').counter, 0)
        self.post('manager', f'sales/{sale.pk}/sign/', self.signing(), key=key)

    def test_sales_roles_and_replayed_request_reauthorize(self):
        sale = self.sale()
        key = str(uuid.uuid4())
        payload = {'amount': '100', 'reason': '确认'}
        self.post('manager', f'sales/{sale.pk}/quote/', payload, key=key)
        for role in ['member', 'purchaser', 'warehouse']:
            self.assertEqual(self.clients[role].get('/api/business/sales/').status_code, 403)
            self.assertEqual(self.clients[role].get(f'/api/business/sales/{sale.pk}/').status_code, 403)
        self.assertEqual(self.clients['finance'].get('/api/business/sales/').status_code, 200)
        self.post('finance', f'sales/{sale.pk}/sign/', self.signing(), status=403)
        user = self.users['manager']
        user.role = 'member'
        user.save()
        self.post('manager', f'sales/{sale.pk}/quote/', payload, key=key, status=403)

    def test_standalone_project_and_sale_cancellation_do_not_create_finance(self):
        sale = self.sale()
        self.post('manager', f'sales/{sale.pk}/cancel/', {'reason': '需求撤回'})
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '拒绝'}, status=409)
        self.post(
            'manager',
            'projects/',
            {
                'name': '内部项目',
                'customer': self.customer.pk,
                'manager': self.users['manager'].pk,
            },
            status=201,
        )
        project = Project.objects.get()
        self.assertEqual((project.status, project.contract_amount, project.contract_date), ('active', 0, None))
        self.assertFalse(Entry.objects.exists())
        self.assertEqual(SalesOrder.objects.count(), 1)
