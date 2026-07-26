from django.test import SimpleTestCase

from apps.core.permission_mixin import PermissionMixin
from apps.purchase.rfq_views import (
    RFQAttachmentViewSet,
    RFQSupplierViewSet,
    RFQTemplateViewSet,
    SupplierCapabilityMappingViewSet,
    SupplierCapabilityViewSet,
)


class PurchasePermissionArchitectureTests(SimpleTestCase):
    def test_rfq_child_resources_use_unified_permission_mixin(self):
        resources = {
            RFQSupplierViewSet: 'rfq_supplier',
            RFQTemplateViewSet: 'rfq_template',
            SupplierCapabilityViewSet: 'supplier_capability',
            SupplierCapabilityMappingViewSet: 'supplier_capability_mapping',
            RFQAttachmentViewSet: 'rfq_attachment',
        }

        for viewset, resource in resources.items():
            with self.subTest(viewset=viewset.__name__):
                self.assertTrue(issubclass(viewset, PermissionMixin))
                self.assertEqual(viewset.permission_module, 'purchase')
                self.assertEqual(viewset.permission_resource, resource)
