"""图纸 Excel 导入回归测试（软删物料 / 软删图纸占用唯一键）。"""

from io import BytesIO

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.masterdata.models import Customer, Item
from apps.projects.models import Drawing, Project
from apps.projects.views import DrawingViewSet


class DrawingImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='drawing_import_admin',
            employee_id='DWG-IMPORT-ADMIN',
            is_staff=True,
            is_superuser=True,
        )
        self.customer = Customer.objects.create(code='DWG-IMPORT-CUSTOMER', name='图纸导入测试客户')
        self.project = Project.objects.create(
            code='DWG-IMPORT-PROJECT',
            name='图纸导入测试项目',
            customer=self.customer,
            manager=self.user,
            start_date='2026-07-01',
            end_date='2026-12-31',
        )
        self.factory = APIRequestFactory()
        self.import_view = DrawingViewSet.as_view({'post': 'import_excel'})

    def import_rows(self, rows, *, project=None, update_existing=False):
        output = BytesIO()
        pd.DataFrame(rows).to_excel(output, index=False)
        upload = SimpleUploadedFile(
            'drawing-import.xlsx',
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        request = self.factory.post(
            '/api/projects/drawings/import_excel/',
            {
                'file': upload,
                'project': str((project or self.project).id),
                'update_existing': str(update_existing).lower(),
            },
            format='multipart',
        )
        force_authenticate(request, user=self.user)
        return self.import_view(request)

    def test_import_reports_soft_deleted_item_instead_of_silently_skipping(self):
        """关联物料被软删时，图纸照常导入，但必须说出来没关联上，不能静默吞掉。"""
        item = Item.objects.create(sku='DWG-DELETED-ITEM', name='已删除物料', unit='PCS')
        item.soft_delete()

        response = self.import_rows(
            [{'图纸号': 'DWG-ITEM-001', '图纸名称': '关联已删除物料的图纸', '物料编码': 'DWG-DELETED-ITEM'}]
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(len(response.data['errors']), 1)
        self.assertIn('已被删除', response.data['errors'][0]['error'])

        drawing = Drawing.objects.get(drawing_no='DWG-ITEM-001')
        self.assertIsNone(drawing.item)

    def test_import_revives_soft_deleted_drawing_in_same_project(self):
        """唯一键 (图纸号,版本,修订) 被本项目软删图纸占着时，复活它而不是撞唯一约束。"""
        drawing = Drawing.objects.create(
            project=self.project,
            drawing_no='DWG-REVIVE-001',
            name='原始图纸名',
            version='A0',
            file_type='PDF',
        )
        drawing.soft_delete()

        response = self.import_rows([{'图纸号': 'DWG-REVIVE-001', '图纸名称': '导入后的图纸名'}])

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['errors'], [])
        self.assertEqual(response.data['revived'], 1)
        self.assertEqual(response.data['created'], 0)
        self.assertIn('恢复已删除1条', response.data['message'])

        drawing.refresh_from_db()
        self.assertFalse(drawing.is_deleted)
        self.assertIsNone(drawing.deleted_at)
        self.assertEqual(drawing.name, '导入后的图纸名')
        self.assertEqual(Drawing.all_objects.filter(drawing_no='DWG-REVIVE-001').count(), 1)

    def test_import_reports_drawing_no_taken_by_another_project(self):
        """唯一键被别的项目占着时，给一句能照着做的报错，而不是 duplicate key 报文。"""
        other_project = Project.objects.create(
            code='DWG-OTHER-PROJECT',
            name='占用图纸号的项目',
            customer=self.customer,
            manager=self.user,
            start_date='2026-07-01',
            end_date='2026-12-31',
        )
        Drawing.objects.create(
            project=other_project,
            drawing_no='DWG-TAKEN-001',
            name='别的项目的图纸',
            version='A0',
            file_type='PDF',
        )

        response = self.import_rows([{'图纸号': 'DWG-TAKEN-001', '图纸名称': '想用同一个图纸号'}])

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['created'], 0)
        self.assertEqual(len(response.data['errors']), 1)
        error = response.data['errors'][0]['error']
        self.assertIn('已被占用', error)
        self.assertIn(other_project.code, error)
        self.assertNotIn('duplicate key', error)
