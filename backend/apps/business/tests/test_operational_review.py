import uuid

from django.test import TestCase

from apps.business.models import BOMLine, Document, Entry, Payment, PaymentEvidence, PurchaseOrder, StockMove
from apps.business.services import finance
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY
from .test_execution import ExecutionFixtures


class OperationalReviewTests(ExecutionFixtures, TestCase):
    def setUp(self):
        self.setup_execution()

    def test_cost_sources_match_original_cost_and_reject_member(self):
        project = self.ready_project()
        self.stock_and_issue(project)
        result = (
            self.clients['manager'].get(f'/api/business/projects/{project.pk}/cost-sources/?category=materials').data
        )
        self.assertEqual(result['count'], 1)
        self.assertEqual(float(result['results'][0]['amount']), float(finance.cost(project)['materials']))
        self.assertEqual(
            self.clients['member'].get(f'/api/business/projects/{project.pk}/cost-sources/').status_code, 403
        )

    def test_workbench_pagination_keeps_assignee_and_open_filter(self):
        project = self.active_project()
        for index in range(23):
            self.task(project, title=f'任务{index}')
        first = self.clients['member'].get('/api/business/workbench/').data['tasks']
        second = self.clients['member'].get('/api/business/workbench/?tasks_page=2').data['tasks']
        self.assertEqual(first['count'], 23)
        self.assertEqual(len(first['results']), 20)
        self.assertEqual(len(second['results']), 3)
        self.assertFalse({row['id'] for row in first['results']} & {row['id'] for row in second['results']})

    def test_forecast_missing_material_is_incomplete_and_complete_estimate_keeps_actuals(self):
        project = self.active_project()
        body = {'remaining_labor': '20', 'remaining_expenses': '30', 'reason': '重新评估', 'expected_revision': 0}
        self.post('manager', f'projects/{project.pk}/forecast/', body)
        report = self.clients['manager'].get(f'/api/business/projects/{project.pk}/cost-analysis/').data
        self.assertIsNone(report['forecast_total'])
        body.update(remaining_materials='100', expected_revision=1)
        self.post('manager', f'projects/{project.pk}/forecast/', body)
        report = self.clients['manager'].get(f'/api/business/projects/{project.pk}/cost-analysis/').data
        self.assertEqual(report['forecast_total'], '150.00')
        self.assertIsNotNone(report['forecast_at'])
        self.assertFalse(report['forecast_stale'])
        self.assertEqual(finance.cost(project)['total'], '0.00')

    def test_purchase_payment_deadline_is_independent_of_delivery(self):
        project = self.active_project()
        purchase = self.post(
            'purchaser',
            'purchases/',
            {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'payment_due_date': '2026-12-31',
                'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': '10'}],
            },
            status=201,
        )
        pk = purchase['id']
        self.post('purchaser', f'purchases/{pk}/submit/')
        self.post('manager', f'purchases/{pk}/approve/')
        self.assertEqual(str(Entry.objects.get(purchase_id=pk).due_date), '2026-12-31')
        detail = PurchaseOrder.objects.get(pk=pk)
        self.post(
            'purchaser',
            f'purchases/{pk}/delivery-plan/',
            {
                'expected_updated_at': detail.updated_at.isoformat(),
                'reason': '供应商改期',
                'lines': [{'id': detail.lines.get().pk, 'due_date': '2026-01-01'}],
            },
        )
        result = self.clients['warehouse'].get(f'/api/business/purchases/{pk}/').data
        self.assertEqual(str(result['next_delivery_date']), '2026-01-01')
        self.assertEqual(str(Entry.objects.get(purchase_id=pk).due_date), '2026-12-31')

    def test_evidence_append_is_idempotent_authorized_and_preserves_payment(self):
        project = self.active_project()
        entry = Entry.objects.get(project=project)
        pk = self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '10', 'date': TODAY, 'reason': '付款'})['id']
        doc = Document.objects.create(
            project=project, category='receipt', original_name='回单.pdf', file='isolated/receipt.pdf', size=1
        )
        body = {'document': doc.pk, 'reason': '回单补录'}
        key = str(uuid.uuid4())
        self.post('finance', f'payments/{pk}/attach-evidence/', body, key=key)
        self.post('finance', f'payments/{pk}/attach-evidence/', body, key=key)
        self.assertEqual(PaymentEvidence.objects.count(), 1)
        self.assertEqual(Payment.objects.get(pk=pk).amount, 10)
        self.assertIsNone(Payment.objects.get(pk=pk).document_id)
        self.post('manager', f'payments/{pk}/attach-evidence/', body, status=403)
        other = self.active_project()
        wrong = Document.objects.create(
            project=other, category='receipt', original_name='其他.pdf', file='isolated/other.pdf', size=1
        )
        self.post(
            'finance', f'payments/{pk}/attach-evidence/', {'document': wrong.pk, 'reason': '错误项目'}, status=404
        )
        self.assertEqual(PaymentEvidence.objects.count(), 1)

    def test_explicit_delivery_kit_and_returns_use_snapshot(self):
        project = self.ready_project(equipment=2)
        self.stock_and_issue(project)
        BOMLine.objects.filter(project=project).update(assembly_unit='设备A')
        data = {
            'date': TODAY,
            'quantity': 1,
            'installer': self.users['member'].pk,
            'acceptor': self.users['manager'].pk,
            'materials': [{'item': self.item.pk, 'quantity': '3'}],
        }
        self.post('manager', f'projects/{project.pk}/ship/', data)
        move = StockMove.objects.get(kind='issue')
        self.post(
            'warehouse', f'moves/{move.pk}/return-material/', {'quantity': '2', 'reason': '不可退已交付'}, status=409
        )
        data['materials'][0]['quantity'] = '2'
        self.post('manager', f'projects/{project.pk}/ship/', data, status=409)
        data['materials'][0]['quantity'] = '1'
        self.post('manager', f'projects/{project.pk}/ship/', data)
        self.assertEqual(project.deliveries.count(), 2)

    def test_bom_preview_returns_difference_without_mutation_or_receipt(self):
        project = self.ready_project()
        count, logs = ActionReceipt.objects.count(), AuditLog.objects.count()
        data = {
            'expected_revision': self.bom_version(project.pk),
            'lines': [{'item': self.item.pk, 'quantity': '3', 'change_note': '计划减量'}],
        }
        result = self.post('manager', f'projects/{project.pk}/bom-change-preview/', data)
        self.assertTrue(result['can_apply'])
        self.assertEqual(result['items'][0]['difference'], '-1.000')
        self.assertEqual(BOMLine.objects.get(project=project).quantity, 4)
        self.assertEqual(ActionReceipt.objects.count(), count)
        self.assertEqual(AuditLog.objects.count(), logs)
