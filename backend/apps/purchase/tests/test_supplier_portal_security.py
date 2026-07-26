from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope, Permission, RolePermission
from apps.masterdata.models import Supplier
from apps.purchase.supplier_portal import SupplierAccount

User = get_user_model()


class SupplierPortalSecurityTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(code='SUP-PORTAL-1', name='供应商一')
        self.other_supplier = Supplier.objects.create(code='SUP-PORTAL-2', name='供应商二')
        self.account = SupplierAccount.objects.create(
            supplier=self.supplier,
            username='supplier-one',
            password_hash='',
        )
        self.account.set_password('SupplierPassword123!')
        self.account.save(update_fields=['password_hash'])

    def _login(self):
        response = self.client.post(
            '/api/purchase/supplier-portal/login/',
            {'username': 'supplier-one', 'password': 'SupplierPassword123!'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        return response.data['token']

    def test_portal_token_is_verified_and_bound_to_supplier(self):
        token = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Supplier {token}')

        own_response = self.client.get(f'/api/purchase/supplier-portal/{self.supplier.id}/orders/')
        other_response = self.client.get(f'/api/purchase/supplier-portal/{self.other_supplier.id}/orders/')

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 403)

    def test_random_or_erp_credentials_cannot_access_supplier_portal(self):
        self.client.credentials(HTTP_AUTHORIZATION='Supplier random-token')
        random_response = self.client.get(f'/api/purchase/supplier-portal/{self.supplier.id}/orders/')

        erp_user = User.objects.create_user(
            username='erp-user',
            employee_id='erp-user',
            password='test-password',
        )
        self.client.credentials()
        self.client.force_authenticate(erp_user)
        erp_response = self.client.get(f'/api/purchase/supplier-portal/{self.supplier.id}/orders/')

        self.assertEqual(random_response.status_code, 401)
        self.assertEqual(erp_response.status_code, 403)

    def test_password_change_revokes_existing_portal_token(self):
        token = self._login()
        self.account.set_password('ReplacementPassword123!')
        self.account.save(update_fields=['password_hash'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Supplier {token}')

        response = self.client.get(f'/api/purchase/supplier-portal/{self.supplier.id}/orders/')

        self.assertEqual(response.status_code, 401)


class SupplierPortalInternalManagementTests(APITestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(code='SUP-INTERNAL', name='内部管理供应商')
        self.account = SupplierAccount.objects.create(
            supplier=self.supplier,
            username='internal-supplier',
            password_hash='',
        )
        self.account.set_password('SupplierPassword123!')
        self.account.save(update_fields=['password_hash'])
        self.user = User.objects.create_user(
            username='ordinary-user',
            employee_id='ordinary-user',
            password='test-password',
        )
        self.client.force_authenticate(self.user)

    def _grant_supplier_management(self):
        role = Role.objects.create(name='供应商管理员', code='supplier-admin')
        permission = Permission.objects.create(code='supply:supplier', name='供应商管理', type='menu')
        RolePermission.objects.create(role=role, permission=permission)
        DataScope.objects.create(role=role, module='purchase', scope_type='all')
        self.user.roles.add(role)

    def test_supplier_account_management_requires_supplier_menu_permission(self):
        denied = self.client.get('/api/purchase/supplier-accounts/')
        self._grant_supplier_management()
        allowed = self.client.get('/api/purchase/supplier-accounts/')

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)

    def test_password_reset_requires_explicit_password_and_never_echoes_it(self):
        self._grant_supplier_management()
        url = f'/api/purchase/supplier-accounts/{self.account.id}/reset_password/'

        missing = self.client.post(url, {}, format='json')
        password = 'ReplacementPassword123!'
        reset = self.client.post(url, {'password': password}, format='json')

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(reset.status_code, 200)
        self.assertNotIn('new_password', reset.data)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password(password))
