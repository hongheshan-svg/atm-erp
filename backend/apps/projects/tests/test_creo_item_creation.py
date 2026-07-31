"""Creo/CAD BOM 自动建料回归测试（软删编码占用）。"""

from django.test import TestCase

from apps.masterdata.models import Item
from apps.projects.creo_integration import ItemCreationService


class CreoItemCreationTest(TestCase):
    def test_create_from_bom_revives_item_held_by_soft_deleted_sku(self):
        """编码被软删物料占着时，要复活它而不是撞唯一约束报 duplicate key。"""
        item = Item.objects.create(sku='CREO-REVIVE-001', name='原始物料名', unit='PCS')
        item.soft_delete()

        rows = [
            {
                'status': 'NEW',
                'part_number': 'CREO-REVIVE-001',
                'part_name': '复活后的名称',
                'unit': '个',
                'suggested_item_property': 'MANUFACTURED',
            }
        ]
        result = ItemCreationService.create_from_bom(rows)

        self.assertEqual(result['errors'], [])
        self.assertEqual(result['revived'], 1)
        self.assertEqual(result['created'], 0)
        self.assertEqual(rows[0]['status'], 'CREATED')

        item.refresh_from_db()
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)
        self.assertTrue(item.is_active)
        self.assertEqual(item.name, '复活后的名称')
        self.assertEqual(rows[0]['created_item_id'], item.id)
        self.assertEqual(Item.all_objects.filter(sku='CREO-REVIVE-001').count(), 1)

    def test_create_from_bom_reports_existing_live_sku(self):
        """编码被在用物料占着时维持原有语义：报 SKU 已存在，不改数据。"""
        item = Item.objects.create(sku='CREO-LIVE-001', name='在用物料', unit='PCS')

        rows = [{'status': 'NEW', 'part_number': 'CREO-LIVE-001', 'part_name': '不应覆盖'}]
        result = ItemCreationService.create_from_bom(rows)

        self.assertEqual(result['created'], 0)
        self.assertEqual(result['revived'], 0)
        self.assertEqual(result['errors'], ['SKU已存在: CREO-LIVE-001'])
        self.assertEqual(rows[0]['status'], 'ERROR')
        item.refresh_from_db()
        self.assertEqual(item.name, '在用物料')
