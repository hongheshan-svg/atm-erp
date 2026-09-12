from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.business.models import BOMLine, Item, PurchaseLine, PurchaseOrder
from apps.business.services import bom_import
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class BOMSelectionTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def test_classification_maintenance_and_demand_use_one_source(self):
        self.post('purchaser', 'items/', {'name': '分类件', 'brand': 'SMC', 'part_type': 'standard'}, status=201)
        item = Item.objects.get(name='分类件')
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': item.pk, 'quantity': '2', 'assembly_unit': '上料单元'}],
            },
        )
        response = self.clients['purchaser'].get(f'/api/business/projects/{self.project.pk}/demand/')
        line = response.data['lines'][0]
        self.assertEqual((line['brand'], line['part_type'], line['assembly_unit']), ('SMC', 'standard', '上料单元'))
        response = self.clients['purchaser'].patch(
            f'/api/business/items/{item.pk}/', {'brand': 'FESTO'}, format='json', HTTP_IDEMPOTENCY_KEY='brand-change'
        )
        self.assertEqual(response.status_code, 200, response.data)
        response = self.clients['purchaser'].get(f'/api/business/projects/{self.project.pk}/demand/')
        self.assertEqual(response.data['lines'][0]['brand'], 'FESTO')
        self.post('purchaser', 'items/', {'name': '非法类别', 'part_type': 'invalid'}, status=400)

    def test_subset_purchase_does_not_order_unselected_or_overbuy(self):
        other = Item.objects.create(code='I2', name='非标', part_type='custom')
        first = BOMLine.objects.create(project=self.project, item=self.item, quantity=2, assembly_unit='上料')
        second = BOMLine.objects.create(project=self.project, item=other, quantity=3, assembly_unit='检测')
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'from_demand': True,
            'lines': [{'item': self.item.pk, 'bom_line': first.pk, 'quantity': '2', 'unit_price': '1'}],
        }
        result = self.post('purchaser', 'purchases/', data, status=201)
        order = PurchaseOrder.objects.get(pk=result['id'])
        self.assertEqual(list(order.lines.values_list('bom_line_id', flat=True)), [first.pk])
        self.assertFalse(PurchaseLine.objects.filter(bom_line=second).exists())
        self.post('purchaser', 'purchases/', data, status=409)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        data['lines'][0]['bom_line'] = second.pk
        self.post('purchaser', 'purchases/', data, status=404)

    def test_invalid_bom_reference_shape_does_not_change_existing_purchase(self):
        bom = BOMLine.objects.create(project=self.project, item=self.item, quantity=10, assembly_unit='上料')
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'from_demand': True,
            'lines': [{'item': self.item.pk, 'bom_line': str(bom.pk), 'quantity': '2', 'unit_price': '12.34'}],
        }
        created = self.post('purchaser', 'purchases/', data, status=201)
        order = PurchaseOrder.objects.get(pk=created['id'])
        self.assertEqual(order.status, 'draft')
        self.assertEqual(order.lines.get().bom_line_id, bom.pk)
        orders = list(PurchaseOrder.objects.values())
        lines = list(PurchaseLine.objects.values())
        receipts = ActionReceipt.objects.count()
        audits = AuditLog.objects.count()
        counter = CodeRule.objects.get(key='purchase').counter
        for reference in ([], {}):
            with self.subTest(reference=reference):
                result = self.post(
                    'purchaser',
                    'purchases/',
                    {**data, 'lines': [{**data['lines'][0], 'bom_line': reference}]},
                    status=400,
                )
                self.assertIn('bom_line', result)
                self.assertEqual(list(PurchaseOrder.objects.values()), orders)
                self.assertEqual(list(PurchaseLine.objects.values()), lines)
                self.assertEqual(ActionReceipt.objects.count(), receipts)
                self.assertEqual(AuditLog.objects.count(), audits)
                self.assertEqual(CodeRule.objects.get(key='purchase').counter, counter)

    def test_bom_units_import_legacy_preservation_and_revision(self):
        raw = f'物料编码,数量,变更说明,单元\n{self.item.code},2,初版,上料单元\n'.encode()
        preview = bom_import.preview(self.project, SimpleUploadedFile('bom.csv', raw))
        self.assertTrue(preview['can_import'])
        line = preview['lines'][0]
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': preview['expected_revision'],
                'lines': [{key: line[key] for key in ['item', 'quantity', 'change_note', 'assembly_unit']}],
            },
        )
        old = bom_import.preview(
            self.project, SimpleUploadedFile('bom.csv', f'物料编码,数量,变更说明\n{self.item.code},2,调整\n'.encode())
        )
        self.assertEqual(old['lines'][0]['assembly_unit'], '上料单元')
        previous = self.bom_version(self.project.pk)
        data = {
            'expected_revision': previous,
            'lines': [{'item': self.item.pk, 'quantity': '2', 'change_note': '移至检测', 'assembly_unit': '检测单元'}],
        }
        self.post('manager', f'projects/{self.project.pk}/revise-bom/', data)
        self.assertNotEqual(self.bom_version(self.project.pk), previous)
        self.post('manager', f'projects/{self.project.pk}/revise-bom/', data, status=409)
