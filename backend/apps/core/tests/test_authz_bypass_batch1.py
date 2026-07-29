"""审计批次1:授权旁路回归测试。

锁定修复:
- 非标准端点(裸 @api_view / APIView)必须经模块菜单授权,不能只挂 IsAuthenticated —
  仅持无关模块菜单的登录用户访问财务导出/利润报表应 403。
- SystemConfig list 对未认证请求只返回公开公司信息,不泄露银行账号/税号/法人/注册资本。
- 用户管理序列化器不得让非系统管理员写入 is_staff/is_superuser(垂直提权)。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.core.permission_models_new import Permission, RolePermission

User = get_user_model()


def _make_user(username, menu_codes=(), is_superuser=False):
    user = User.objects.create_user(
        username=username,
        password='x',
        employee_id=username,
        is_superuser=is_superuser,
        is_staff=is_superuser,
    )
    if menu_codes:
        role = Role.objects.create(name=f'{username}_role', code=f'{username}_role')
        for code in menu_codes:
            perm, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'type': 'menu'})
            RolePermission.objects.get_or_create(role=role, permission=perm)
        user.role = role
        user.save()
    return user


class AuthzBypassBatch1Test(TestCase):
    def setUp(self):
        cache.clear()
        # 仅持库存菜单的普通用户(无 finance / reports 菜单)
        self.warehouse = _make_user('wh_u', menu_codes=['supply', 'inventory'])
        self.superuser = _make_user('root_u', is_superuser=True)

    def test_financial_export_denied_without_module_menu(self):
        client = APIClient()
        client.force_authenticate(self.warehouse)
        resp = client.get(reverse('export-ar'))
        self.assertEqual(resp.status_code, 403, '仅持库存菜单者导出应收应被 403')

    def test_financial_export_allowed_for_superuser(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        resp = client.get(reverse('export-ar'))
        self.assertEqual(resp.status_code, 200, '超管导出应收应放行')

    def test_reports_profitability_denied_without_module_menu(self):
        client = APIClient()
        client.force_authenticate(self.warehouse)
        resp = client.get(reverse('project-profitability'))
        self.assertEqual(resp.status_code, 403, '仅持库存菜单者读全项目利润应被 403')

    def test_system_config_public_list_hides_sensitive_fields(self):
        from apps.core.models import SystemConfig

        cfg = SystemConfig.get_config()
        cfg.company_name = '测试公司'
        cfg.bank_account = '6222001234567890'
        cfg.company_tax_no = '91310000XXXXXXXX'
        cfg.legal_representative = '张三'
        cfg.registered_capital = '10000000.00'
        cfg.save()

        client = APIClient()  # 未认证
        resp = client.get('/api/core/system-config/')
        self.assertEqual(resp.status_code, 200, '登录页需读公司名,list 保持公开')
        data = resp.json()
        self.assertEqual(data.get('company_name'), '测试公司', '公开信息公司名应可见')
        for leaked in ('bank_account', 'company_tax_no', 'legal_representative', 'registered_capital'):
            self.assertNotIn(leaked, data, f'未认证不应看到敏感字段 {leaked}')

    def test_system_config_authenticated_admin_sees_full(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        resp = client.get('/api/core/system-config/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('bank_account', resp.json(), '系统管理员应能读到完整配置')

    def test_non_admin_cannot_set_is_staff_via_user_update(self):
        from apps.accounts.serializers import UserUpdateSerializer

        hr = _make_user('hr_u', menu_codes=['system:user'])
        target = _make_user('victim_u')
        factory_req = APIClient()
        factory_req.force_authenticate(hr)
        # 直接跑序列化器 validate:模拟 HR 提交 is_staff=True
        from rest_framework.test import APIRequestFactory

        req = APIRequestFactory().patch('/x/')
        req.user = hr
        ser = UserUpdateSerializer(instance=target, data={'is_staff': True}, partial=True, context={'request': req})
        self.assertFalse(
            ser.is_valid() and ser.validated_data.get('is_staff') is True,
            'HR(非系统管理员)不应能经用户序列化器写入 is_staff=True',
        )

    def test_non_admin_user_list_uses_picker_serializer(self):
        """非管理员列取用户走精简 picker 序列化器,不含 is_superuser/is_staff/role/PII(审计 batch1 #19)。

        直接断言 get_serializer_class 的选择 + picker 字段集,避开数据范围过滤对返回行数的干扰
        (合成用户无 DataScope → self 范围 → 列表可能为空,无法据此断言字段)。
        """
        from rest_framework.test import APIRequestFactory

        from apps.accounts.serializers import UserPickerSerializer, UserSerializer
        from apps.accounts.views import UserViewSet

        viewer = _make_user('viewer_u', menu_codes=['oa:announcement'])
        req = APIRequestFactory().get('/api/accounts/users/')
        req.user = viewer
        vs = UserViewSet()
        vs.request = req
        vs.action = 'list'
        self.assertIs(vs.get_serializer_class(), UserPickerSerializer, '非管理员列表应用 picker 序列化器')

        # picker 序列化实际用户,确认特权/PII 字段不出现
        data = UserPickerSerializer(viewer).data
        for leaked in ('is_superuser', 'is_staff', 'role', 'phone', 'email', 'birth_date', 'hire_date'):
            self.assertNotIn(leaked, data, f'picker 不应暴露字段 {leaked}')

        # 超管仍走完整序列化器
        req2 = APIRequestFactory().get('/api/accounts/users/')
        req2.user = self.superuser
        vs2 = UserViewSet()
        vs2.request = req2
        vs2.action = 'list'
        self.assertIs(vs2.get_serializer_class(), UserSerializer, '超管列表应用完整序列化器')

    def test_admin_user_list_keeps_full_fields(self):
        client = APIClient()
        client.force_authenticate(self.superuser)
        resp = client.get('/api/accounts/users/')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        rows = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
        self.assertIn('is_superuser', rows[0], '管理员应看到完整用户字段')


class BackupPathSafetyTest(TestCase):
    """审计 batch1 #17:备份文件名路径穿越/绝对路径防护。"""

    def test_rejects_absolute_and_traversal(self):
        from apps.core.backup_service import safe_backup_path

        for bad in ('/tmp/evil.sql', '../../etc/passwd', '../secret.sql', ''):
            with self.assertRaises(ValueError, msg=f'{bad!r} 应被拒绝'):
                safe_backup_path(bad)

    def test_accepts_plain_name_inside_dir(self):
        import os

        from apps.core.backup_service import BACKUP_DIR, safe_backup_path

        p = safe_backup_path('erp_backup_20260101.sql.gz')
        self.assertTrue(p.startswith(os.path.realpath(BACKUP_DIR) + os.sep))
