from django.test import SimpleTestCase

from apps.core.permission_mixin import PermissionMixin
from apps.projects.bom_compare import BOMCompareViewSet
from apps.projects.bom_integration import BOMIntegrationViewSet
from apps.projects.drawing_import import DrawingImportViewSet


class ProjectPermissionArchitectureTests(SimpleTestCase):
    def test_project_integration_endpoints_use_unified_permission_mixin(self):
        resources = {
            BOMIntegrationViewSet: 'bom_integration',
            DrawingImportViewSet: 'drawing_import',
            BOMCompareViewSet: 'bom_compare',
        }

        for viewset, resource in resources.items():
            with self.subTest(viewset=viewset.__name__):
                self.assertTrue(issubclass(viewset, PermissionMixin))
                self.assertEqual(viewset.permission_module, 'projects')
                self.assertEqual(viewset.permission_resource, resource)
