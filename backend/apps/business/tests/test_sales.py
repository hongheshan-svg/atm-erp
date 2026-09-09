import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.business.models import Entry, Project, SalesOrder
from apps.core.models import ActionReceipt, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class SalesTests(BusinessFixtures, TestCase):
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
