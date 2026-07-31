"""采购申请 Excel 导入回归测试（软删物料的报错口径）。"""

from io import BytesIO

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.masterdata.models import Item
from apps.purchase.views import PurchaseRequestViewSet


class PurchaseRequestImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='pr_import_admin',
            employee_id='PR-IMPORT-ADMIN',
            is_staff=True,
            is_superuser=True,
        )
        self.factory = APIRequestFactory()
        self.import_view = PurchaseRequestViewSet.as_view({'post': 'import_excel'})

    def import_rows(self, rows):
        output = BytesIO()
        pd.DataFrame(rows).to_excel(output, index=False)
        upload = SimpleUploadedFile(
            'pr-import.xlsx',
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        request = self.factory.post('/api/purchase/requests/import_excel/', {'file': upload}, format='multipart')
        force_authenticate(request, user=self.user)
        return self.import_view(request)

    def test_import_distinguishes_soft_deleted_item_from_missing_item(self):
        """软删物料要报"已被删除"并指路去恢复，不能和"不存在"混为一谈。

        报"不存在"会把用户引去新建同编码物料，而唯一索引 item_sku_key 不区分软删，
        新建必然撞约束 —— 用户照着提示做反而走进死路。
        """
        item = Item.objects.create(sku='PR-DELETED-001', name='已删除物料', unit='PCS')
        item.soft_delete()

        response = self.import_rows(
            [
                {'物料编码': 'PR-DELETED-001', '数量': 2},
                {'物料编码': 'PR-MISSING-001', '数量': 1},
            ]
        )

        self.assertEqual(response.status_code, 400, response.data)
        errors = {e['sku']: e['error'] for e in response.data['errors']}
        self.assertIn('已被删除', errors['PR-DELETED-001'])
        self.assertIn('物料主数据中恢复', errors['PR-DELETED-001'])
        self.assertIn('不存在', errors['PR-MISSING-001'])
        self.assertNotIn('已被删除', errors['PR-MISSING-001'])
        # 软删行不能被顺手复活
        self.assertTrue(Item.all_objects.get(pk=item.pk).is_deleted)
