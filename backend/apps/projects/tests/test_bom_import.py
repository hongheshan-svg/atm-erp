"""Project BOM Excel import regression tests."""

from io import BytesIO

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.masterdata.models import Customer, Item
from apps.projects.models import Project, ProjectBOM
from apps.projects.views import ProjectBOMViewSet


class ProjectBOMImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='bom_import_admin',
            employee_id='BOM-IMPORT-ADMIN',
            is_staff=True,
            is_superuser=True,
        )
        self.customer = Customer.objects.create(code='BOM-IMPORT-CUSTOMER', name='BOM导入测试客户')
        self.project = Project.objects.create(
            code='BOM-IMPORT-PROJECT',
            name='BOM导入测试项目',
            customer=self.customer,
            manager=self.user,
            start_date='2026-07-01',
            end_date='2026-12-31',
        )
        self.factory = APIRequestFactory()
        self.import_view = ProjectBOMViewSet.as_view({'post': 'import_excel'})

    def import_rows(self, rows, *, auto_create_items=False):
        output = BytesIO()
        pd.DataFrame(rows).to_excel(output, index=False)
        upload = SimpleUploadedFile(
            'bom-import.xlsx',
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        request = self.factory.post(
            '/api/projects/bom/import_excel/',
            {
                'file': upload,
                'project': str(self.project.id),
                'auto_create_items': str(auto_create_items).lower(),
            },
            format='multipart',
        )
        force_authenticate(request, user=self.user)
        return self.import_view(request)

    def test_import_accepts_template_minimum_required_columns(self):
        item = Item.objects.create(sku='BOM-MINIMUM-001', name='最小模板物料', unit='PCS')

        response = self.import_rows([{'物料编码*': item.sku, '数量*': 2}])

        self.assertEqual(response.status_code, 200, response.data)
        bom = ProjectBOM.objects.get(project=self.project, item=item)
        self.assertEqual(bom.planned_qty, 2)
        self.assertIsNone(bom.required_date)
        self.assertIsNone(bom.requester)

    def test_failed_auto_create_import_rolls_back_created_items(self):
        response = self.import_rows(
            [
                {
                    '物料编码': 'BOM-ROLLBACK-001',
                    '物料名称': '不应残留的物料',
                    '单位': 'PCS',
                    '计划数量': 1,
                    '需求日期': '2026-08-31',
                    '申请人': self.user.username,
                },
                {
                    '物料编码': 'BOM-ROLLBACK-002',
                    '物料名称': '触发整批失败',
                    '单位': 'PCS',
                    '计划数量': 0,
                    '需求日期': '2026-08-31',
                    '申请人': self.user.username,
                },
            ],
            auto_create_items=True,
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Item.objects.filter(sku__in=['BOM-ROLLBACK-001', 'BOM-ROLLBACK-002']).exists())
        self.assertFalse(ProjectBOM.objects.filter(project=self.project).exists())
