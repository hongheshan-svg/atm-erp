import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import Document, Entry, Item, PurchaseContractVersion, PurchaseWarranty, StockMove
from apps.core.models import ActionReceipt, AuditLog, Company

from .test_commercial_chain import BusinessFixtures


class HardeningTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def test_archived_contract_survives_masterdata_changes_and_preserves_versions(self):
        purchase = self.purchase(self.active_project())
        company = Company.objects.create(pk=1, name='采购方', address='甲方地址', phone='123')
        self.supplier.address, self.supplier.phone = '供应商地址', '456'
        self.supplier.save()
        doc = Document.objects.create(
            purchase=purchase, category='contract', original_name='signed.pdf', file='fixture', size=1, sha256='a' * 64
        )
        path = f'/api/business/purchases/{purchase.pk}/contract-preview/'
        preview = self.clients['purchaser'].get(path).data
        data = {
            'expected_snapshot': preview['snapshot_hash'],
            'document': doc.pk,
            'delivery_address': '约定收货地点',
            'reason': '双方签署确认',
            'confirmed': True,
        }
        key = str(uuid.uuid4())
        first = self.post('purchaser', f'purchases/{purchase.pk}/archive-contract/', data, key=key, status=201)
        self.post('purchaser', f'purchases/{purchase.pk}/archive-contract/', data, key=key, status=201)
        self.assertEqual(PurchaseContractVersion.objects.count(), 1)
        company.name = '采购方新名称'
        company.save()
        self.item.name = '后来修改物料名称'
        self.item.save()
        frozen = self.clients['purchaser'].get(path).data
        self.assertEqual(frozen['buyer']['name'], '采购方')
        self.assertEqual(frozen['lines'][0]['name'], '伺服电机')
        self.assertEqual(frozen['signed_document'], doc.pk)
        self.post('purchaser', f'purchases/{purchase.pk}/archive-contract/', data, status=409)
        fresh = self.clients['purchaser'].get(path, {'version': 'current'}).data
        second = self.post(
            'purchaser',
            f'purchases/{purchase.pk}/archive-contract/',
            {**data, 'expected_snapshot': fresh['snapshot_hash']},
            status=201,
        )
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.clients['purchaser'].get(path, {'version': '1'}).data['buyer']['name'], '采购方')
        self.assertEqual(self.clients['warehouse'].get(path).status_code, 403)
        self.assertEqual(self.clients['purchaser'].get(path, {'version': 'invalid'}).status_code, 400)

    def test_monthly_partial_receipt_authorizes_only_received_amount_and_replays_once(self):
        purchase = self.purchase(self.active_project())
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'reason': '部分收货', 'lines': [{'line': purchase.lines.get().pk, 'quantity': '2'}]},
        )
        path = 'reconciliations/supplier-monthly/'
        report = (
            self.clients['finance']
            .get('/api/business/' + path, {'supplier': self.supplier.pk, 'month': str(timezone.localdate())[:7]})
            .data
        )
        self.assertEqual(report['totals']['closing'], '200.00')
        data = {
            'supplier': self.supplier.pk,
            'month': report['month'],
            'expected_snapshot': report['snapshot_hash'],
            'counterparty_balance': '199.00',
            'reason': '供应商账单核对',
        }
        self.post('finance', path, data, status=409)

        data['counterparty_balance'] = '200.00'
        key = str(uuid.uuid4())
        result = self.post('finance', path, data, key=key)
        self.assertEqual(self.post('finance', path, data, key=key), result)
        statement = result['reconciliations'][0]
        payload = {'amount': '201.00', 'date': str(timezone.localdate()), 'reason': '付款', 'reconciliation': statement}
        self.post('finance', f'entries/{purchase.entry.pk}/pay/', payload, status=409)
        self.post('finance', f'entries/{purchase.entry.pk}/pay/', {**payload, 'amount': '100.00'})
        self.post('finance', f'entries/{purchase.entry.pk}/pay/', {**payload, 'amount': '100.00'})
        self.post('finance', path, data, status=409)

    def test_monthly_invalid_supplier_is_validation_error(self):
        self.post(
            'finance',
            'reconciliations/supplier-monthly/',
            {
                'supplier': 'invalid',
                'month': '2026-08',
                'reason': '检查异常输入',
                'counterparty_balance': '0.00',
                'expected_snapshot': 'x',
            },
            status=400,
        )

    def test_duplicate_material_requires_reason_and_custom_code_is_preserved(self):
        data = {'code': 'CUSTOM-A', 'name': '  Ｍotor ', 'specification': 'X1', 'brand': 'Brand', 'unit': '件'}
        first = self.post('purchaser', 'items/', data, status=201)
        self.assertEqual(Item.objects.get(pk=first['id']).name, 'Motor')
        self.post('purchaser', 'items/', {**data, 'code': 'CUSTOM-B', 'name': 'motor'}, status=400)
        second = self.post(
            'purchaser',
            'items/',
            {**data, 'code': 'CUSTOM-B', 'name': 'motor', 'duplicate_reason': '不同客户专用内部编码'},
            status=201,
        )
        self.assertEqual(Item.objects.get(pk=second['id']).code, 'CUSTOM-B')
        self.assertIn(
            first['id'],
            [r['id'] for r in self.clients['purchaser'].get('/api/business/items/similar/', {'name': 'Motor'}).data],
        )

    def test_warranty_reuses_receipt_and_requires_real_replacement(self):
        purchase = self.purchase(self.active_project())
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'reason': '收货', 'lines': [{'line': purchase.lines.get().pk, 'quantity': '2'}]},
        )
        receipt = StockMove.objects.get(kind='receipt')
        path = f'purchases/{purchase.pk}/warranty/'
        created = self.post(
            'warehouse',
            path,
            {'receipt': receipt.pk, 'date': str(timezone.localdate()), 'quantity': '1', 'description': '电机异常'},
        )
        info = self.clients['purchaser'].get('/api/business/' + path).data['cases'][0]
        # DRF Response still contains datetime before rendering in APIClient.data.
        updated = info['updated_at'].isoformat().replace('+00:00', 'Z')
        data = {'case': created['id'], 'expected_updated_at': updated, 'status': 'replaced', 'response': '供应商换货'}
        self.post('purchaser', path, data, status=400)
        self.post('purchaser', path, {**data, 'status': 'repairing'})
        self.post('purchaser', path, {**data, 'status': 'closed'}, status=409)
        self.assertEqual(PurchaseWarranty.objects.get().status, 'repairing')
        self.assertEqual(StockMove.objects.count(), 1)
        self.assertFalse(Entry.objects.filter(kind='expense').exists())

    def test_attention_report_requires_separate_report_permission(self):
        self.active_project()
        path = '/api/business/reports/?view=aging'
        self.assertEqual(self.clients['manager'].get(path).status_code, 403)
        self.assertEqual(self.clients['admin'].get(path).status_code, 200)
        self.assertTrue(self.clients['admin'].get(path).data['results'])
        self.assertEqual(self.clients['admin'].get('/api/business/reports/?view=bad').status_code, 400)

    def test_manager_scope_covers_detail_exports_workbench_and_replay(self):
        project = self.active_project()
        purchase = self.purchase(project, approve=False)
        outsider = User.objects.create_user(username='other-manager', role='manager', management_reports=True)
        client = APIClient()
        client.force_authenticate(outsider)
        for url in (
            f'projects/{project.pk}/',
            f'purchases/{purchase.pk}/',
            f'purchases/{purchase.pk}/contract-preview/',
        ):
            self.assertEqual(client.get('/api/business/' + url).status_code, 404)
        self.assertEqual(client.get('/api/business/purchases/').data['count'], 0)
        self.assertNotIn(purchase.code.encode(), client.get('/api/business/purchases/export/').content)
        self.assertEqual(client.get('/api/business/workbench/').data['approvals']['count'], 0)
        self.assertEqual(client.get('/api/business/reports/').status_code, 200)
        project.members.add(outsider)
        self.assertEqual(client.get(f'/api/business/purchases/{purchase.pk}/').status_code, 200)
        key = str(uuid.uuid4())
        self.assertEqual(
            client.post(
                f'/api/business/purchases/{purchase.pk}/approve/', {}, format='json', HTTP_IDEMPOTENCY_KEY=key
            ).status_code,
            200,
        )
        project.members.remove(outsider)
        self.assertEqual(
            client.post(
                f'/api/business/purchases/{purchase.pk}/approve/', {}, format='json', HTTP_IDEMPOTENCY_KEY=key
            ).status_code,
            404,
        )

    def test_creator_or_submitter_cannot_approve_with_multiple_roles(self):
        project = self.active_project()
        purchase = self.purchase(project, approve=False)
        user = self.users['purchaser']
        user.additional_roles = ['manager']
        user.save()
        before = ActionReceipt.objects.count()
        self.post('purchaser', f'purchases/{purchase.pk}/approve/', status=403)
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        self.post('manager', f'purchases/{purchase.pk}/reject/', {'reason': '重新复核'})
        self.post('manager', f'purchases/{purchase.pk}/submit/')
        self.post('manager', f'purchases/{purchase.pk}/approve/', status=403)
        self.post('admin', f'purchases/{purchase.pk}/approve/')

    def test_finance_global_read_does_not_expand_manager_approval_scope(self):
        project = self.active_project()
        purchase = self.purchase(project, approve=False)
        user = self.users['finance']
        user.additional_roles = ['manager']
        user.save()
        self.assertEqual(self.clients['finance'].get(f'/api/business/projects/{project.pk}/').status_code, 200)
        self.assertFalse(self.clients['finance'].get(f'/api/business/projects/{project.pk}/').data['can_manage'])
        self.post('finance', f'purchases/{purchase.pk}/approve/', status=403)
        project.members.add(user)
        self.post('finance', f'purchases/{purchase.pk}/approve/')

    def test_admin_self_approval_requires_reason_and_audit(self):
        project = self.active_project()
        purchase = self.purchase(project, approve=False)
        self.post('admin', f'purchases/{purchase.pk}/reject/', {'reason': '更正'})
        self.post('admin', f'purchases/{purchase.pk}/submit/')
        self.post('admin', f'purchases/{purchase.pk}/approve/', status=400)
        self.post('admin', f'purchases/{purchase.pk}/approve/', {'reason': '负责人出差，管理员承担例外审批责任'})
        self.assertTrue(AuditLog.objects.get(operation='purchase.approve').detail['self_approval'])

    def test_period_rejects_backdated_receipt_then_audited_reopening(self):
        project = self.active_project()
        purchase = self.purchase(project)
        cutoff = timezone.localdate() - timedelta(days=1)
        Company.objects.create(pk=1)
        path = '/api/core/company/1/period-lock/'
        data = {'locked_through': str(cutoff), 'expected_revision': 0, 'reason': '核对完成'}
        self.assertEqual(
            self.clients['finance'].post(path, data, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,
            403,
        )
        self.assertEqual(
            self.clients['admin'].post(path, data, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,
            200,
        )
        receipt = {
            'received_date': str(cutoff),
            'reason': '实际到货',
            'lines': [{'line': purchase.lines.get().pk, 'quantity': '1'}],
        }
        self.post('warehouse', f'purchases/{purchase.pk}/receive/', receipt, status=409)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'approved')
        self.assertEqual(
            self.clients['admin']
            .post(
                path,
                {**data, 'locked_through': None, 'expected_revision': 1, 'reason': '补齐漏记收货后重新核对'},
                format='json',
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            )
            .status_code,
            200,
        )
        self.post('warehouse', f'purchases/{purchase.pk}/receive/', receipt)
        self.assertEqual(AuditLog.objects.filter(operation='period.lock').count(), 2)

    def test_prepayment_applicant_cannot_confirm_own_request(self):
        project = self.active_project()
        purchase = self.purchase(project)
        self.users['finance'].additional_roles = ['manager']
        self.users['finance'].save()
        result = self.post(
            'finance',
            'reconciliations/',
            {
                'entry': purchase.entry.pk,
                'kind': 'prepayment',
                'counterparty_balance': '500.00',
                'approved_amount': '100.00',
                'basis': '合同预付20%',
                'reason': '申请预付',
            },
            status=201,
        )
        self.post('finance', f'reconciliations/{result["id"]}/confirm/', {'reason': '兼任经理'}, status=403)
        self.post('manager', f'reconciliations/{result["id"]}/confirm/', {'reason': '独立审核合同预付条款'})
