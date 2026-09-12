import csv
import io
import tempfile
import uuid
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import (
    BOMLine,
    Document,
    Entry,
    Item,
    Payment,
    PurchaseContractVersion,
    PurchaseOrder,
    PurchaseWarranty,
    StockMove,
    Task,
    TimeEntry,
)
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

    def test_warranty_status_shape_is_rejected_without_changing_case_or_history(self):
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
        case = PurchaseWarranty.objects.get(pk=created['id'])
        original_version = case.updated_at
        receipts = ActionReceipt.objects.count()
        audits = AuditLog.objects.count()
        for status in (['repairing'], {'value': 'repairing'}):
            with self.subTest(status=status):
                result = self.post(
                    'purchaser',
                    path,
                    {
                        'case': case.pk,
                        'expected_updated_at': original_version.isoformat().replace('+00:00', 'Z'),
                        'status': status,
                        'response': '不可写入的响应',
                    },
                    status=400,
                )
                self.assertIn('status', result)
                case.refresh_from_db()
                self.assertEqual((case.status, case.response, case.updated_at), ('open', '', original_version))
                self.assertEqual(ActionReceipt.objects.count(), receipts)
                self.assertEqual(AuditLog.objects.count(), audits)
                self.assertEqual(StockMove.objects.count(), 1)

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

    def test_manager_purchaser_own_project_preserves_approval_and_posting_separation(self):
        project = self.active_project()
        user = self.users['manager']
        user.additional_roles = ['purchaser']
        user.save()
        self.assertTrue(self.clients['manager'].get(f'/api/business/projects/{project.pk}/').data['can_manage'])
        created = self.post(
            'manager',
            'purchases/',
            {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': str(timezone.localdate()),
                'lines': [{'item': self.item.pk, 'quantity': '2', 'unit_price': '10'}],
            },
            status=201,
        )
        purchase = PurchaseOrder.objects.get(pk=created['id'])
        self.post('manager', f'purchases/{purchase.pk}/submit/')
        receipts = ActionReceipt.objects.count()
        result = self.post('manager', f'purchases/{purchase.pk}/approve/', status=403)
        self.assertIn('申请人不能审批自己的单据', str(result))
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'submitted')
        self.post('admin', f'purchases/{purchase.pk}/approve/')
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'approved')
        self.assertEqual(purchase.entry.amount, 20)
        receipts = ActionReceipt.objects.count()
        audits = AuditLog.objects.count()
        self.post(
            'manager',
            f'purchases/{purchase.pk}/receive/',
            {'reason': '双岗不能兼作仓管', 'lines': [{'line': purchase.lines.get().pk, 'quantity': '2'}]},
            status=403,
        )
        for entry in [purchase.entry, project.entries.get(kind='receivable')]:
            self.post(
                'manager',
                f'entries/{entry.pk}/pay/',
                {'amount': '1', 'date': str(timezone.localdate()), 'reason': '双岗不能兼作财务'},
                status=403,
            )
        for path in ['reports/', 'reports/?view=aging', 'reports/?file_format=csv']:
            self.assertEqual(self.clients['manager'].get('/api/business/' + path).status_code, 403)
        self.assertFalse(StockMove.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertEqual(AuditLog.objects.count(), audits)

    def test_manager_purchaser_global_read_does_not_expand_other_project_management(self):
        project = self.active_project()
        purchase = self.purchase(project, approve=False)
        user = self.users['purchaser']
        user.additional_roles = ['manager']
        user.save()
        self.assertEqual(self.clients['purchaser'].get(f'/api/business/projects/{project.pk}/').status_code, 200)
        self.assertFalse(self.clients['purchaser'].get(f'/api/business/projects/{project.pk}/').data['can_manage'])
        self.assertFalse(self.clients['purchaser'].get(f'/api/business/purchases/{purchase.pk}/').data['can_manage'])
        receipts = ActionReceipt.objects.count()
        audits = AuditLog.objects.count()
        result = self.post('purchaser', f'purchases/{purchase.pk}/approve/', status=403)
        self.assertIn('无权访问此项目', str(result))
        self.post(
            'purchaser',
            f'projects/{project.pk}/budget/',
            {
                'materials': '100',
                'labor': '100',
                'expenses': '100',
                'reason': '不能扩大项目管理',
                'expected_revision': 0,
            },
            status=403,
        )
        self.post(
            'purchaser',
            'tasks/',
            {'project': project.pk, 'title': '不能越权分配任务', 'kind': 'design', 'assignee': self.users['member'].pk},
            status=403,
        )
        self.post('purchaser', f'projects/{project.pk}/cancel/', {'reason': '不能越权取消项目'}, status=403)
        project.refresh_from_db()
        purchase.refresh_from_db()
        self.assertEqual(project.status, 'active')
        self.assertEqual(project.budget_revision, 0)
        self.assertEqual(purchase.status, 'submitted')
        self.assertFalse(project.tasks.exists())
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertEqual(AuditLog.objects.count(), audits)

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


class RoleResponsibilityTests(BusinessFixtures, TestCase):
    engineers = ('mechanical_engineer', 'electrical_engineer')

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.project.members.add(*(self.users[role] for role in self.engineers))
        self.other_project = self.active_project()

    def get(self, role, path, status=200):
        response = self.clients[role].get('/api/business/' + path)
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def upload(self, role, owner, category='drawing', status=201):
        response = self.clients[role].post(
            '/api/business/documents/',
            {**owner, 'category': category, 'file': SimpleUploadedFile('role-check.txt', b'synthetic role fixture')},
            format='multipart',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def test_purchase_manager_global_purchase_access_keeps_project_money_and_management_separate(self):
        purchase = self.purchase(self.other_project, approve=False)
        detail = self.get('purchase_manager', f'purchases/{purchase.pk}/')
        self.assertTrue(detail['can_approve'])
        self.assertEqual(detail['lines'][0]['unit_price'], '100.00')
        visible = self.get('purchase_manager', 'projects/')['results']
        self.assertEqual({row['id'] for row in visible}, {self.project.pk, self.other_project.pk})
        for row in visible:
            self.assertFalse(row['can_manage'])
            self.assertFalse(row['can_edit_bom'])
            self.assertNotIn('contract_amount', row)
            self.assertNotIn('quote_amount', row)
        workbench = self.get('purchase_manager', 'workbench/')
        self.assertIn(purchase.pk, [row['id'] for row in workbench['approvals']['results']])
        self.assertNotIn('settlements', workbench)
        self.assertNotIn('reconciliations', workbench)
        self.assertNotIn('bank_records', workbench)
        self.get('purchase_manager', f'purchases/{purchase.pk}/contract-preview/')
        self.get('purchase_manager', 'items/import-schema/')
        self.get('purchase_manager', 'partners/import-schema/')
        self.post('purchase_manager', 'items/', {'name': '采购经理维护物料', 'code': 'PM-MATERIAL'}, status=201)
        self.post('purchase_manager', 'partners/', {'name': '采购经理供应商', 'kind': 'supplier'}, status=201)

    def test_purchase_manager_can_reject_and_approve_others_but_cannot_approve_own_submission(self):
        purchase = self.purchase(self.other_project, approve=False)
        self.post('purchase_manager', f'purchases/{purchase.pk}/reject/', {'reason': '采购经理复核交期'})
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'draft')
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        self.post('purchase_manager', f'purchases/{purchase.pk}/approve/')
        self.assertEqual(purchase.entry.amount, 500)
        self.assertEqual(AuditLog.objects.get(operation='purchase.approve').actor_id, self.users['purchase_manager'].pk)
        own = self.post(
            'purchase_manager',
            'purchases/',
            {
                'project': self.other_project.pk,
                'supplier': self.supplier.pk,
                'due_date': str(timezone.localdate()),
                'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': '20'}],
            },
            status=201,
        )
        self.post('purchase_manager', f'purchases/{own["id"]}/submit/')
        before = ActionReceipt.objects.count()
        rejected = self.post('purchase_manager', f'purchases/{own["id"]}/approve/', status=403)
        self.assertIn('申请人不能审批自己的单据', str(rejected))
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertFalse(Entry.objects.filter(purchase_id=own['id']).exists())
        self.assertEqual(PurchaseOrder.objects.get(pk=own['id']).status, 'submitted')

    def test_purchase_manager_material_over_budget_approval_requires_fresh_snapshot_and_not_self(self):
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {'materials': '100', 'labor': '200', 'expenses': '300', 'expected_revision': 0, 'reason': '按岗位验收预算'},
        )
        purchase = self.purchase(self.project, approve=False)
        check = self.get('purchase_manager', f'purchases/{purchase.pk}/budget-check/')
        self.assertTrue(check['over_budget'])
        self.assertEqual(check['scope'], 'purchasing')
        self.assertEqual(check['materials_budget'], '100.00')
        self.assertEqual(check['purchase_amount'], '500.00')
        self.post('purchase_manager', f'purchases/{purchase.pk}/approve/', status=409)
        payload = {'confirmed': True, 'expected_snapshot': check['snapshot'], 'reason': '确认采购超额需求'}
        self.post(
            'purchase_manager',
            f'purchases/{purchase.pk}/approve-over-budget/',
            {**payload, 'expected_snapshot': '0' * 64},
            status=409,
        )
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        self.post('purchase_manager', f'purchases/{purchase.pk}/approve-over-budget/', payload)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'approved')
        self.assertEqual(purchase.entry.amount, 500)
        own = self.post(
            'purchase_manager',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': str(timezone.localdate()),
                'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': '20'}],
            },
            status=201,
        )
        self.post('purchase_manager', f'purchases/{own["id"]}/submit/')
        own_check = self.get('purchase_manager', f'purchases/{own["id"]}/budget-check/')
        self.post(
            'purchase_manager',
            f'purchases/{own["id"]}/approve-over-budget/',
            {**payload, 'expected_snapshot': own_check['snapshot']},
            status=403,
        )
        self.assertFalse(Entry.objects.filter(purchase_id=own['id']).exists())

    def test_purchase_manager_nonmaterial_overrun_does_not_disclose_costs_in_preview_or_rejection(self):
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {
                'materials': '10000',
                'labor': '536.29',
                'expenses': '11',
                'expected_revision': 0,
                'reason': '敏感分项预算',
            },
        )
        self.post(
            'finance',
            'entries/expense/',
            {
                'project': self.project.pk,
                'title': '敏感项目费用',
                'amount': '1379.13',
                'due_date': str(timezone.localdate()),
            },
            status=201,
        )
        purchase = self.purchase(self.project, approve=False)
        check = self.get('purchase_manager', f'purchases/{purchase.pk}/budget-check/')
        self.assertTrue(check['over_budget'])
        self.assertEqual(check['scope'], 'purchasing')
        self.assertLessEqual(
            set(check),
            {
                'scope',
                'materials_budget',
                'materials_occupied',
                'purchase_amount',
                'purchase_net',
                'configured',
                'over_budget',
                'snapshot',
                'purchase',
                'warnings',
            },
        )
        rejected = self.post('purchase_manager', f'purchases/{purchase.pk}/approve/', status=409)
        for sensitive in ('1379.13', '536.29', '1368.13', '1879.13'):
            self.assertNotIn(sensitive, str(check))
            self.assertNotIn(sensitive, str(rejected))
        self.post(
            'purchase_manager',
            f'purchases/{purchase.pk}/approve-over-budget/',
            {'confirmed': True, 'expected_snapshot': check['snapshot'], 'reason': '按采购授权确认例外'},
        )
        self.assertEqual(purchase.entry.amount, 500)

    def test_purchase_manager_cannot_manage_projects_post_money_receive_stock_or_confirm_prepayment(self):
        purchase = self.purchase(self.project)
        for path in (
            'sales/',
            'sales/export/',
            'entries/',
            'entries/export/',
            'payments/',
            'payments/export/',
            'reconciliations/',
            'bank-records/',
            'reports/',
            'reports/?view=aging',
            f'projects/{self.project.pk}/cost/',
            f'projects/{self.project.pk}/cost-analysis/',
            f'projects/{self.project.pk}/cost-sources/',
        ):
            with self.subTest(path=path):
                self.get('purchase_manager', path, status=403)
        before_receipts, before_audits = ActionReceipt.objects.count(), AuditLog.objects.count()
        for path, data in (
            ('projects/', {'name': '不允许新项目', 'customer': self.customer.pk, 'manager': self.users['manager'].pk}),
            (f'projects/{self.project.pk}/cancel/', {'reason': '不能取消项目'}),
            (
                f'projects/{self.project.pk}/budget/',
                {'materials': '1', 'labor': '1', 'expenses': '1', 'expected_revision': 0, 'reason': '不可改预算'},
            ),
            (
                f'projects/{self.project.pk}/revise-bom/',
                {
                    'expected_revision': self.bom_version(self.project.pk),
                    'lines': [{'item': self.item.pk, 'quantity': '1'}],
                },
            ),
            (
                'tasks/',
                {
                    'project': self.project.pk,
                    'kind': 'design',
                    'title': '不能分配技术任务',
                    'assignee': self.users['member'].pk,
                },
            ),
            (
                f'purchases/{purchase.pk}/receive/',
                {'reason': '不能兼作仓管', 'lines': [{'line': purchase.lines.get().pk, 'quantity': '1'}]},
            ),
            (
                f'entries/{purchase.entry.pk}/pay/',
                {'amount': '1', 'date': str(timezone.localdate()), 'reason': '不能兼作财务'},
            ),
        ):
            with self.subTest(path=path):
                self.post('purchase_manager', path, data, status=403)
        self.assertEqual(ActionReceipt.objects.count(), before_receipts)
        self.assertEqual(AuditLog.objects.count(), before_audits)
        self.assertFalse(StockMove.objects.exists())
        self.assertFalse(Payment.objects.exists())
        statement = self.post(
            'finance',
            'reconciliations/',
            {
                'entry': purchase.entry.pk,
                'kind': 'prepayment',
                'counterparty_balance': '500',
                'approved_amount': '100',
                'basis': '合同预付20%',
                'reason': '财务申请',
            },
            status=201,
        )
        self.post(
            'purchase_manager',
            f'reconciliations/{statement["id"]}/confirm/',
            {'reason': '采购审批不能代替预付核准'},
            status=403,
        )
        self.assertEqual(self.get('finance', f'reconciliations/{statement["id"]}/')['status'], 'draft')

    def test_engineers_can_revise_preview_and_remove_only_participating_project_bom(self):
        for role in self.engineers:
            with self.subTest(role=role):
                projects = self.get(role, 'projects/')['results']
                self.assertEqual([project['id'] for project in projects], [self.project.pk])
                self.assertFalse(projects[0]['can_manage'])
                self.assertTrue(projects[0]['can_edit_bom'])
                self.assertNotIn('contract_amount', projects[0])
                self.get(role, f'projects/{self.other_project.pk}/', status=404)
                self.get(role, f'projects/{self.other_project.pk}/demand/', status=404)
                data = {
                    'expected_revision': self.bom_version(self.project.pk),
                    'lines': [
                        {'item': self.item.pk, 'quantity': '2', 'assembly_unit': role, 'change_note': '技术确认'}
                    ],
                }
                self.post(role, f'projects/{self.project.pk}/bom-change-preview/', data)
                self.post(role, f'projects/{self.project.pk}/revise-bom/', data)
                self.get(role, f'projects/{self.project.pk}/bom-impact/')
                line = BOMLine.objects.get(project=self.project)
                self.assertEqual(line.quantity, 2)
                self.assertEqual(line.updated_by_id, self.users[role].pk)
                self.post(role, f'bom/{line.pk}/remove/', {'reason': '撤回技术初版'})
                self.assertFalse(BOMLine.objects.filter(pk=line.pk).exists())
                self.assertTrue(BOMLine.all_objects.get(pk=line.pk).is_deleted)
                self.post(role, f'projects/{self.other_project.pk}/revise-bom/', data, status=404)

    def test_engineers_material_maintenance_and_bom_import_preserve_atomic_numbering(self):
        from apps.business.services.bom_material_import import HEADERS

        for role in self.engineers:
            with self.subTest(role=role):
                item = self.post(role, 'items/', {'name': f'{role}技术物料', 'code': f'ENG-{role}'}, status=201)
                edited = self.clients[role].patch(
                    f'/api/business/items/{item["id"]}/',
                    {'brand': '工程确认品牌'},
                    format='json',
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                )
                self.assertEqual(edited.status_code, 200, edited.data)
                self.assertEqual(Item.objects.get(pk=item['id']).brand, '工程确认品牌')
                self.get(role, 'items/import-schema/')
                self.post(role, 'partners/', {'name': '技术岗位不可维护供应商', 'kind': 'supplier'}, status=403)
                self.post(role, 'partners/', {'name': '技术岗位不可维护客户', 'kind': 'customer'}, status=403)
                template = self.clients[role].get('/api/business/projects/bom-template/')
                self.assertEqual(template.status_code, 200)
                stream = io.StringIO()
                writer = csv.writer(stream)
                writer.writerow(HEADERS)
                writer.writerow(
                    [
                        '',
                        role,
                        '1',
                        '工程新物料',
                        '',
                        '',
                        role,
                        f'{role}导入传感器',
                        'ENG-SPEC',
                        '',
                        '',
                        '21',
                        '工程品牌',
                        'standard',
                        '件',
                    ]
                )
                before = Item.objects.count()
                preview = self.clients[role].post(
                    f'/api/business/projects/{self.project.pk}/import-preview/',
                    {'file': SimpleUploadedFile('engineering-bom.csv', stream.getvalue().encode())},
                    format='multipart',
                )
                self.assertEqual(preview.status_code, 200, preview.data)
                self.assertTrue(preview.data['can_import'], preview.data)
                self.assertEqual(Item.objects.count(), before)
                result = self.post(
                    role, f'projects/{self.project.pk}/bom-import-confirm/', {'token': preview.data['token']}
                )
                self.assertTrue(result)
                self.assertEqual(Item.objects.count(), before + 1)
                imported = Item.objects.get(name=f'{role}导入传感器')
                self.assertRegex(imported.code, r'^2199\d{6}$')
                self.assertTrue(BOMLine.objects.filter(project=self.project, item=imported, quantity=1).exists())

    def test_engineers_own_tasks_and_hours_do_not_grant_project_purchasing_or_money_permissions(self):
        purchase = self.purchase(self.project, approve=False)
        other_task = Task.objects.create(
            project=self.project, kind='design', title='成员任务', assignee=self.users['member']
        )
        for role in self.engineers:
            with self.subTest(role=role):
                task = Task.objects.create(
                    project=self.project, kind='design', title=f'{role}任务', assignee=self.users[role]
                )
                self.post(
                    role,
                    f'tasks/{task.pk}/time/',
                    {'date': str(timezone.localdate()), 'hours': '1', 'reason': '工程设计一小时'},
                )
                self.post(role, f'tasks/{task.pk}/complete/', {'reason': '工程任务完成'})
                task.refresh_from_db()
                self.assertEqual(task.status, 'done')
                self.assertEqual(TimeEntry.objects.get(task=task).user_id, self.users[role].pk)
                self.post(role, f'tasks/{other_task.pk}/complete/', {'reason': '不能代办他人任务'}, status=403)
                self.post(
                    role,
                    f'tasks/{other_task.pk}/time/',
                    {'date': str(timezone.localdate()), 'hours': '1', 'reason': '不能代报他人工时'},
                    status=403,
                )
                for path in (
                    'sales/',
                    'purchases/',
                    'purchases/export/',
                    f'purchases/{purchase.pk}/',
                    'entries/',
                    'payments/',
                    'reconciliations/',
                    'bank-records/',
                    'reports/',
                    f'projects/{self.project.pk}/cost/',
                    f'projects/{self.project.pk}/cost-analysis/',
                ):
                    self.get(role, path, status=403)
                self.post(
                    role,
                    'tasks/',
                    {
                        'project': self.project.pk,
                        'kind': 'design',
                        'title': '不能分配任务',
                        'assignee': self.users[role].pk,
                    },
                    status=403,
                )
                self.post(role, f'projects/{self.project.pk}/cancel/', {'reason': '不能管理项目'}, status=403)
                self.post(role, f'purchases/{purchase.pk}/approve/', status=403)
                self.post(
                    role,
                    'purchases/',
                    {
                        'project': self.project.pk,
                        'supplier': self.supplier.pk,
                        'due_date': str(timezone.localdate()),
                        'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': '1'}],
                    },
                    status=403,
                )
                self.assertNotIn('approvals', self.get(role, 'workbench/'))
        self.assertFalse(TimeEntry.objects.filter(task=other_task).exists())
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())

    def test_engineers_technical_attachments_are_project_scoped_and_exclude_contracts(self):
        with tempfile.TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
            technical = self.upload('manager', {'project': self.project.pk})
            contract = self.upload('manager', {'project': self.project.pk}, 'contract')
            receipt = self.upload('finance', {'project': self.project.pk}, 'receipt')
            other = self.upload('manager', {'project': self.other_project.pk})
            purchase = self.purchase(self.project)
            purchase_contract = self.upload('purchaser', {'purchase': purchase.pk}, 'contract')
            for role in self.engineers:
                with self.subTest(role=role):
                    own = self.upload(role, {'project': self.project.pk}, 'drawing')
                    self.upload(role, {'project': self.project.pk}, 'other')
                    listed = self.get(role, f'documents/?project={self.project.pk}')['results']
                    ids = {row['id'] for row in listed}
                    self.assertIn(technical['id'], ids)
                    self.assertIn(own['id'], ids)
                    self.assertTrue(ids.isdisjoint({contract['id'], receipt['id'], purchase_contract['id']}))
                    downloaded = self.clients[role].get(f'/api/business/documents/{own["id"]}/download/')
                    self.assertEqual(downloaded.status_code, 200)
                    self.assertEqual(b''.join(downloaded.streaming_content), b'synthetic role fixture')
                    for denied in (contract, receipt, purchase_contract, other):
                        self.get(role, f'documents/{denied["id"]}/download/', status=404)
                    before = Document.objects.count()
                    self.upload(role, {'project': self.project.pk}, 'contract', status=403)
                    self.upload(role, {'project': self.project.pk}, 'receipt', status=403)
                    self.upload(role, {'purchase': purchase.pk}, 'contract', status=403)
                    self.upload(role, {'project': self.other_project.pk}, status=403)
                    self.assertEqual(Document.objects.count(), before)

    def test_purchase_manager_engineer_union_does_not_expand_bom_writes_to_unassigned_projects(self):
        for engineer in self.engineers:
            with self.subTest(engineer=engineer):
                user = self.users['purchase_manager']
                user.additional_roles = [engineer]
                user.save()
                self.project.members.add(user)
                own = self.get('purchase_manager', f'projects/{self.project.pk}/')
                outside = self.get('purchase_manager', f'projects/{self.other_project.pk}/')
                self.assertTrue(own['can_edit_bom'])
                self.assertFalse(outside['can_edit_bom'])
                self.assertFalse(own['can_manage'])
                self.assertFalse(outside['can_manage'])
                data = {
                    'expected_revision': self.bom_version(self.project.pk),
                    'lines': [{'item': self.item.pk, 'quantity': '1', 'change_note': '参与项目技术维护'}],
                }
                self.post('purchase_manager', f'projects/{self.project.pk}/revise-bom/', data)
                before = ActionReceipt.objects.count()
                self.post(
                    'purchase_manager',
                    f'projects/{self.other_project.pk}/revise-bom/',
                    {**data, 'expected_revision': self.bom_version(self.other_project.pk)},
                    status=403,
                )
                self.assertFalse(BOMLine.objects.filter(project=self.other_project).exists())
                self.assertEqual(ActionReceipt.objects.count(), before)

    def test_revoked_engineering_membership_and_purchase_manager_role_reject_action_replay(self):
        user = self.users['mechanical_engineer']
        data = {
            'expected_revision': self.bom_version(self.project.pk),
            'lines': [{'item': self.item.pk, 'quantity': '1'}],
        }
        key = str(uuid.uuid4())
        self.post('mechanical_engineer', f'projects/{self.project.pk}/revise-bom/', data, key=key)
        self.project.members.remove(user)
        before = ActionReceipt.objects.count()
        self.post('mechanical_engineer', f'projects/{self.project.pk}/revise-bom/', data, key=key, status=404)
        self.assertEqual(ActionReceipt.objects.count(), before)
        purchase = self.purchase(self.other_project, approve=False)
        key = str(uuid.uuid4())
        self.post('purchase_manager', f'purchases/{purchase.pk}/approve/', key=key)
        user = self.users['purchase_manager']
        user.role, user.additional_roles = 'purchaser', []
        user.save()
        before = ActionReceipt.objects.count()
        self.post('purchase_manager', f'purchases/{purchase.pk}/approve/', key=key, status=403)
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertEqual(Entry.objects.filter(purchase=purchase).count(), 1)
