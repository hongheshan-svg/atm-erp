"""物料 Excel 导入回归测试（软删编码占用）。"""

from io import BytesIO

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.masterdata.models import Item
from apps.masterdata.views import ItemViewSet


class ItemImportSoftDeletedSkuTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='item_import_admin',
            employee_id='ITEM-IMPORT-ADMIN',
            is_staff=True,
            is_superuser=True,
        )
        self.factory = APIRequestFactory()
        self.import_view = ItemViewSet.as_view({'post': 'import_excel'})

    def import_rows(self, rows):
        output = BytesIO()
        pd.DataFrame(rows).to_excel(output, index=False)
        upload = SimpleUploadedFile(
            'item-import.xlsx',
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        request = self.factory.post('/api/masterdata/items/import_excel/', {'file': upload}, format='multipart')
        force_authenticate(request, user=self.user)
        return self.import_view(request)

    def test_import_revives_item_whose_sku_is_held_by_soft_deleted_row(self):
        """编码被软删物料占着时，要复活它而不是撞唯一约束报 duplicate key。"""
        item = Item.objects.create(
            sku='IMP-REVIVE-001',
            name='原始物料名',
            unit='PCS',
            manufacturer='原厂家',
        )
        item.soft_delete()

        response = self.import_rows([{'物料编码': 'IMP-REVIVE-001', '物料名称': '导入后的名称', '单位': '个'}])

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['errors'], [])
        self.assertEqual(response.data['revived_count'], 1)
        self.assertEqual(response.data['created'], 0)
        self.assertIn('恢复已删除 1 条', response.data['message'])

        item.refresh_from_db()
        self.assertFalse(item.is_deleted)
        self.assertIsNone(item.deleted_at)
        self.assertEqual(item.name, '导入后的名称')
        # Excel 没给"生产厂家"列，不能把主数据里原有的值清空
        self.assertEqual(item.manufacturer, '原厂家')
        # 全表只应有这一条，没有被新建出第二条同编码物料
        self.assertEqual(Item.all_objects.filter(sku='IMP-REVIVE-001').count(), 1)

    def test_import_skips_existing_live_item(self):
        """编码被在用物料占着时维持原有语义：跳过，不复活也不改数据。"""
        item = Item.objects.create(sku='IMP-LIVE-001', name='在用物料', unit='PCS')

        response = self.import_rows([{'物料编码': 'IMP-LIVE-001', '物料名称': '不应覆盖', '单位': '个'}])

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['skip_exist_count'], 1)
        self.assertEqual(response.data['revived_count'], 0)
        item.refresh_from_db()
        self.assertEqual(item.name, '在用物料')
