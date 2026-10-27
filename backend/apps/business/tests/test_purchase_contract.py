import copy
import json
from unittest.mock import patch

from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase

from apps.business.models import Document, Entry, Item, PurchaseContractVersion, PurchaseLine, PurchaseOrder, StockMove
from apps.business.services.contract_clauses import clauses
from apps.core.models import ActionReceipt, AuditLog, Company

from .test_commercial_chain import TODAY, BusinessFixtures


class PurchaseContractTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.purchase_order = self.purchase(self.project)
        self.url = f'purchases/{self.purchase_order.pk}/'
        Company.objects.create(pk=1, name='采购方', address='采购方地址', phone='123')
        self.supplier.address, self.supplier.phone = '供应商地址', '456'
        self.supplier.save()

    def preview(self, version='current', role='purchaser', status=200):
        response = self.clients[role].get('/api/business/' + self.url + 'contract-preview/', {'version': version})
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def document(self):
        return Document.objects.create(
            purchase=self.purchase_order,
            category='contract',
            original_name='签署合同.pdf',
            file='fixture',
            size=1,
            sha256='a' * 64,
        )

    def test_current_template_contains_automation_terms_and_order_warranty(self):
        self.purchase_order.warranty_months = 24
        self.purchase_order.save()
        current = self.preview()
        self.assertEqual(current['template_version'], 2)
        self.assertEqual(set(current['clauses']), {'technical', 'quality', 'automation', 'liability'})
        self.assertIn('验收合格之日起24个月', ''.join(current['clauses']['quality']))
        for subject in ['图纸', '公差', '关键工艺', '替代型号']:
            self.assertIn(subject, ''.join(current['clauses']['technical']))
        for subject in ['节拍', '精度', '变更', '参数备份', '现场安全']:
            self.assertIn(subject, ''.join(current['clauses']['automation']))
        # Each preview gets its own clause collection, never mutating the shared template.
        current['clauses']['technical'].clear()
        self.assertTrue(clauses(12)['technical'])

    def test_legacy_snapshot_keeps_its_exact_terms_and_version(self):
        legacy = copy.deepcopy(self.preview())
        for key in ['snapshot_hash', 'archived_version', 'signed_document', 'versions']:
            legacy.pop(key, None)
        legacy['template_version'] = 1
        legacy['clauses'] = {'quality': ['已签署旧版质量条款'], 'liability': ['已签署旧版责任条款']}
        archived = PurchaseContractVersion.objects.create(
            purchase=self.purchase_order,
            version=1,
            document=self.document(),
            reason='历史归档夹具',
            snapshot=json.loads(json.dumps(legacy, cls=DjangoJSONEncoder)),
        )
        for version in ['', '1']:
            current = self.preview(version)
            self.assertEqual(current['clauses'], legacy['clauses'])
            self.assertEqual(current['template_version'], 1)
        self.assertTrue(self.preview()['clauses']['technical'])
        archived.refresh_from_db()
        self.assertEqual(archived.snapshot['clauses'], legacy['clauses'])

    def test_new_signed_snapshot_freezes_industry_terms_and_stale_template_is_rejected(self):
        current = self.preview()
        data = {
            'expected_snapshot': current['snapshot_hash'],
            'document': self.document().pk,
            'delivery_address': '确认的交付地点',
            'reason': '双方签署完整合同',
            'confirmed': True,
        }
        self.post('purchaser', self.url + 'archive-contract/', data, status=201)
        with patch('apps.business.services.purchase_contract.clauses', return_value={'quality': ['后来条款']}):
            self.assertEqual(self.preview('1')['clauses'], current['clauses'])
            self.post('purchaser', self.url + 'archive-contract/', data, status=409)
        self.assertEqual(PurchaseContractVersion.objects.count(), 1)

    def test_preview_preserves_all_lines_long_details_and_has_no_business_writes(self):
        order = PurchaseOrder.objects.create(
            code='PO-LONG',
            supplier=self.supplier,
            project=self.project,
            due_date=TODAY,
            note='长补充约定\n' * 60,
        )
        items = Item.objects.bulk_create(
            [
                Item(
                    code=f'CONTRACT-{i}',
                    name=f'非标零件{i}',
                    specification='详细材质与公差' * 20,
                    drawing_number=f'DRW-{i}',
                    drawing_revision='B',
                )
                for i in range(32)
            ]
        )
        PurchaseLine.objects.bulk_create(
            [PurchaseLine(purchase=order, item=item, quantity=1, unit_price=10) for item in items]
        )
        self.url = f'purchases/{order.pk}/'
        before = (AuditLog.objects.count(), ActionReceipt.objects.count(), Entry.objects.count())
        detail = self.preview()
        self.assertEqual(len(detail['lines']), 32)
        self.assertEqual({row['code'] for row in detail['lines']}, {item.code for item in items})
        self.assertEqual(detail['lines'][-1]['drawing_revision'], 'B')
        self.assertEqual(detail['note'], order.note)
        self.assertEqual(detail['total'], '320.00')
        self.assertEqual((AuditLog.objects.count(), ActionReceipt.objects.count(), Entry.objects.count()), before)
        self.assertFalse(StockMove.objects.exists())
        self.preview(role='warehouse', status=403)
        self.preview(role='member', status=403)
