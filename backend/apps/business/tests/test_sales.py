import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.business.models import Document, Entry, Project, SalesOrder
from apps.core.models import ActionReceipt, AuditLog, CodeRule

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

    def signed_sale_of_sales_manager(self):
        sale_id = self.sales_manager_order()
        self.post('sales_manager', f'sales/{sale_id}/quote/', {'amount': '100', 'reason': '报价'})
        self.post('sales_manager', f'sales/{sale_id}/sign/', {**self.signing(), 'manager': self.users['manager'].pk})
        return SalesOrder.objects.get(pk=sale_id)

    def test_transfer_signed_sale_owner_changes_scope_and_audits(self):
        from apps.accounts.models import User

        sale = self.signed_sale_of_sales_manager()
        new_owner = User.objects.create_user(username='sm2', role='sales_manager')
        from rest_framework.test import APIClient

        new_client = APIClient()
        new_client.force_authenticate(new_owner)
        url = f'sales/{sale.pk}/transfer/'
        project_before = (sale.project_id, sale.project.manager_id, sale.contract_amount)
        self.assertEqual(new_client.get(f'/api/business/sales/{sale.pk}/').status_code, 404)
        payload = {'manager': new_owner.pk, 'reason': '负责人离岗，交接给同事'}
        result = self.post('manager', url, payload, key='transfer-1')
        self.assertEqual(result, self.post('manager', url, payload, key='transfer-1'))
        sale.refresh_from_db()
        self.assertEqual(sale.manager_id, new_owner.pk)
        self.assertEqual(sale.status, 'signed')
        self.assertEqual(project_before, (sale.project_id, sale.project.manager_id, sale.contract_amount))
        log = AuditLog.objects.get(operation='sale.transfer')
        self.assertEqual(
            (log.detail['before'], log.detail['after'], log.detail['reason']),
            (self.users['sales_manager'].pk, new_owner.pk, payload['reason']),
        )
        self.assertEqual(AuditLog.objects.filter(operation='sale.transfer').count(), 1)
        self.assertEqual(self.clients['sales_manager'].get(f'/api/business/sales/{sale.pk}/').status_code, 404)
        self.assertEqual(new_client.get(f'/api/business/sales/{sale.pk}/').status_code, 200)

    def test_transfer_rejections_leave_no_receipt_or_change(self):
        from apps.accounts.models import User

        sale = self.signed_sale_of_sales_manager()
        other = User.objects.create_user(username='sm2', role='sales_manager')
        inactive = User.objects.create_user(username='sm3', role='sales_manager', is_active=False)
        url = f'sales/{sale.pk}/transfer/'
        good = {'manager': other.pk, 'reason': '交接'}
        receipts = ActionReceipt.objects.count()
        self.post('sales_manager', url, good, status=403)
        self.post('member', url, good, status=403)
        self.post('manager', url, {**good, 'manager': self.users['manager'].pk}, status=400)
        self.post('manager', url, {**good, 'manager': self.users['warehouse'].pk}, status=400)
        self.post('manager', url, {**good, 'manager': inactive.pk}, status=404)
        self.post('manager', url, {**good, 'manager': self.users['sales_manager'].pk}, status=400)
        self.post('manager', url, {**good, 'reason': ''}, status=400)
        self.post('manager', url, {**good, 'reason': 'x' * 501}, status=400)
        self.post('manager', url, {**good, 'extra': 1}, status=400)
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        sale.refresh_from_db()
        self.assertEqual(sale.manager_id, self.users['sales_manager'].pk)
        self.assertFalse(AuditLog.objects.filter(operation='sale.transfer').exists())

    def test_transfer_requires_signed_sale(self):
        from apps.accounts.models import User

        other = User.objects.create_user(username='sm2', role='sales_manager')
        sale = self.sale()
        self.post('manager', f'sales/{sale.pk}/transfer/', {'manager': other.pk, 'reason': '交接'}, status=409)
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '100', 'reason': '报价'})
        self.post('manager', f'sales/{sale.pk}/transfer/', {'manager': other.pk, 'reason': '交接'}, status=409)
        sale.refresh_from_db()
        self.assertEqual(sale.manager_id, self.users['manager'].pk)

    def test_transfer_limited_to_admin_or_project_owner_and_never_to_self(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User

        sale = self.signed_sale_of_sales_manager()
        other = User.objects.create_user(username='sm2', role='sales_manager')
        # 兼任销售经理、未负责该项目的项目经理：转给自己即可借负责人身份读到被隐藏的金额，必须拒绝。
        dual = User.objects.create_user(username='pm2', role='manager', additional_roles=['sales_manager'])
        self.clients['pm2'] = APIClient()
        self.clients['pm2'].force_authenticate(dual)
        url = f'sales/{sale.pk}/transfer/'
        receipts = ActionReceipt.objects.count()
        row = self.clients['pm2'].get(f'/api/business/sales/{sale.pk}/').data
        self.assertEqual((row['amounts_visible'], row['can_transfer']), (False, False))
        self.post('pm2', url, {'manager': dual.pk, 'reason': '转给自己'}, status=403)
        self.post('pm2', url, {'manager': other.pk, 'reason': '代为交接'}, status=403)
        # 参与项目不等于项目负责人。
        sale.project.members.add(dual)
        self.assertFalse(self.clients['pm2'].get(f'/api/business/sales/{sale.pk}/').data['can_transfer'])
        self.post('pm2', url, {'manager': other.pk, 'reason': '代为交接'}, status=403)
        # 项目负责人与管理员兼任销售经理时也不能转给自己。
        for role in ('manager', 'admin'):
            self.users[role].additional_roles = ['sales_manager']
            self.users[role].save()
            self.assertTrue(self.clients[role].get(f'/api/business/sales/{sale.pk}/').data['can_transfer'])
            response = self.post(role, url, {'manager': self.users[role].pk, 'reason': '转给自己'}, status=400)
            self.assertIn('manager', response)
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        sale.refresh_from_db()
        self.assertEqual(sale.manager_id, self.users['sales_manager'].pk)
        self.assertFalse(AuditLog.objects.filter(operation='sale.transfer').exists())
        # 管理员不负责该项目也可以转交；项目负责人换人后，原负责人的旧请求回放被拒绝。
        self.post('admin', url, {'manager': other.pk, 'reason': '管理员交接'})
        payload = {'manager': self.users['sales_manager'].pk, 'reason': '交回原负责人'}
        self.post('manager', url, payload, key='transfer-back')
        Project.objects.filter(pk=sale.project_id).update(manager=dual)
        self.post('manager', url, payload, key='transfer-back', status=403)
        sale.refresh_from_db()
        self.assertEqual(sale.manager_id, self.users['sales_manager'].pk)
        self.assertEqual(AuditLog.objects.filter(operation='sale.transfer').count(), 2)

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


class SalesDateFactTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def quoted_sale(self):
        sale = self.post(
            'manager',
            'sales/',
            {'name': '日期校验', 'customer': self.customer.pk, 'manager': self.users['manager'].pk},
            status=201,
        )['id']
        self.post('manager', f'sales/{sale}/quote/', {'amount': '100', 'reason': '确认'})
        return sale

    def test_future_contract_date_is_rejected_without_side_effects(self):
        sale = self.quoted_sale()
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        counts = (Project.objects.count(), Entry.objects.count(), ActionReceipt.objects.count())
        number = CodeRule.objects.get(key='project').counter
        result = self.post(
            'manager',
            f'sales/{sale}/sign/',
            {
                'date': future,
                'members': [self.users['member'].pk],
                'milestones': [{'title': '合同款', 'amount': '100', 'due_date': future}],
            },
            status=400,
        )
        self.assertIn('date', result)
        self.assertEqual((Project.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()), counts)
        self.assertEqual(CodeRule.objects.get(key='project').counter, number)
        order = SalesOrder.objects.get(pk=sale)
        self.assertEqual((order.status, order.contract_date, order.project_id), ('quoted', None, None))

    def test_same_day_contract_allows_same_day_time_entry(self):
        today = timezone.localdate().isoformat()
        sale = self.quoted_sale()
        project_id = self.post(
            'manager',
            f'sales/{sale}/sign/',
            {
                'date': today,
                'members': [self.users['member'].pk],
                'milestones': [{'title': '合同款', 'amount': '100', 'due_date': today}],
            },
        )['project']
        task = self.post(
            'manager',
            'tasks/',
            {'project': project_id, 'kind': 'design', 'title': '设计', 'assignee': self.users['member'].pk},
            status=201,
        )['id']
        self.post('member', f'tasks/{task}/time/', {'hours': '1', 'date': today, 'reason': '当天工作'})

    def test_future_amendment_date_is_rejected(self):
        project = self.active_project()
        sale = project.sale
        doc = Document.objects.create(
            project=project, category='contract', original_name='a.pdf', size=1, sha256='a' * 64, file='t'
        )
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        audits = AuditLog.objects.count()
        receipts = ActionReceipt.objects.count()
        result = self.post(
            'manager',
            f'sales/{sale.pk}/amend/',
            {
                'expected_updated_at': sale.updated_at.isoformat(),
                'reason': '补充协议',
                'date': future,
                'document': doc.pk,
                'amount': '10000.00',
                'equipment_quantity': 1,
                'warranty_months': 12,
                'credits': [],
                'milestones': [],
            },
            status=400,
        )
        self.assertIn('date', result)
        self.assertFalse(sale.amendments.exists())
        self.assertEqual((AuditLog.objects.count(), ActionReceipt.objects.count()), (audits, receipts))
