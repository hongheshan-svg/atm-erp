"""
附件越权枚举回归测试（审计 IDOR）。

AttachmentViewSet 原先对 'all' 数据范围用户返回全部附件(可批量枚举他人附件);且 Attachment
非 BaseModel、无 created_by，self 范围会被 apply_scope_filter 误判为 none()(self 范围用户看不到)。
修复:skip_data_scope=True（可见性随父对象，而非 created_by）+ 列表操作要求非管理员限定
related_model+related_id（否则空，防批量枚举）。
"""

import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Role
from apps.core.models import Attachment
from apps.core.permission_models_new import Permission, RolePermission
from apps.core.views import AttachmentViewSet, _user_can_access_attachment

User = get_user_model()
factory = APIRequestFactory()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AttachmentIDORTest(TestCase):
    def setUp(self):
        cache.clear()
        self.emp = User.objects.create_user(username='att_emp', password='x', employee_id='att_emp')
        self.root = User.objects.create_user(
            username='att_root', password='x', employee_id='att_root', is_superuser=True
        )
        Attachment.objects.create(
            related_model='Project', related_id=5,
            file=SimpleUploadedFile('a.txt', b'x'), original_name='a.txt',
        )
        Attachment.objects.create(
            related_model='Order', related_id=7,
            file=SimpleUploadedFile('b.txt', b'y'), original_name='b.txt',
        )

    def _list_qs(self, user, params):
        request = factory.get('/x/', params)
        request.user = user
        request.query_params = request.GET  # DRF Request 才有 query_params，这里手动桥接
        viewset = AttachmentViewSet()
        viewset.request = request
        viewset.action = 'list'
        return viewset.get_queryset()

    def test_nonadmin_unscoped_list_is_empty(self):
        # 非管理员未限定关联对象 → 空，禁止批量枚举全部附件（审计 IDOR）
        self.assertEqual(self._list_qs(self.emp, {}).count(), 0)

    def test_nonadmin_scoped_list_returns_object_attachments(self):
        # 限定具体对象 → 可见该对象的附件（不含其它对象）
        qs = self._list_qs(self.emp, {'related_model': 'Project', 'related_id': '5'})
        self.assertEqual(qs.count(), 1)

    def test_admin_can_list_all(self):
        # 系统管理员（超管/持顶层 system）可列全部
        self.assertEqual(self._list_qs(self.root, {}).count(), 2)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AttachmentAccessControlTest(TestCase):
    """retrieve/download/update/destroy 经 get_object 的模块级访问校验（审计越权收紧 #38）。"""

    def setUp(self):
        cache.clear()
        self.proj_perm = Permission.objects.create(
            code='projects:list', name='项目列表', type='menu', is_active=True
        )
        self.proj_role = Role.objects.create(name='项目角色', code='proj', is_active=True)
        RolePermission.objects.create(role=self.proj_role, permission=self.proj_perm)

        self.proj_user = User.objects.create_user(username='pu', password='x', employee_id='pu', role=self.proj_role)
        self.outsider = User.objects.create_user(username='out', password='x', employee_id='out')
        self.uploader = User.objects.create_user(username='up', password='x', employee_id='up')
        self.root = User.objects.create_superuser(username='r3', password='x', employee_id='r3')

        # Project 属 app 'projects'（强制校验模块）
        self.proj_att = Attachment.objects.create(
            related_model='Project',
            related_id=1,
            file=SimpleUploadedFile('p.txt', b'x'),
            original_name='p.txt',
            uploaded_by=self.uploader,
        )

    def test_module_user_can_access(self):
        self.assertTrue(_user_can_access_attachment(self.proj_user, self.proj_att))

    def test_outsider_denied_on_enforced_module(self):
        self.assertFalse(_user_can_access_attachment(self.outsider, self.proj_att))

    def test_uploader_always_allowed(self):
        self.assertTrue(_user_can_access_attachment(self.uploader, self.proj_att))

    def test_unknown_related_model_failopen(self):
        att = Attachment.objects.create(
            related_model='NoSuchModelXYZ',
            related_id=1,
            file=SimpleUploadedFile('u.txt', b'x'),
            original_name='u.txt',
        )
        self.assertTrue(_user_can_access_attachment(self.outsider, att))

    def test_non_enforced_module_failopen(self):
        # Customer 属 masterdata（未纳入强制模块）/ 或无此模型 → 一律放行
        att = Attachment.objects.create(
            related_model='Customer',
            related_id=1,
            file=SimpleUploadedFile('c.txt', b'x'),
            original_name='c.txt',
        )
        self.assertTrue(_user_can_access_attachment(self.outsider, att))

    def _viewset(self, user):
        request = factory.get('/x/')
        request.user = user
        request.query_params = request.GET
        request.authenticators = []
        request.successful_authenticator = None
        vs = AttachmentViewSet()
        vs.request = request
        vs.action = 'retrieve'
        vs.kwargs = {'pk': str(self.proj_att.pk)}
        vs.format_kwarg = None
        return vs

    def test_get_object_denies_outsider(self):
        from rest_framework.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            self._viewset(self.outsider).get_object()

    def test_get_object_allows_admin(self):
        self.assertEqual(self._viewset(self.root).get_object().pk, self.proj_att.pk)

    def _delete_req(self, user, ids):
        request = factory.delete('/x/')
        request.user = user
        request.data = {'ids': ids}
        return request

    def test_batch_delete_skips_unauthorized(self):
        resp = AttachmentViewSet().batch_delete(self._delete_req(self.outsider, [self.proj_att.id]))
        self.assertEqual(resp.data.get('deleted'), 0)
        self.assertEqual(resp.data.get('denied'), 1)
        self.assertTrue(Attachment.objects.filter(id=self.proj_att.id).exists())  # 越权未删成

    def test_batch_delete_allows_authorized(self):
        resp = AttachmentViewSet().batch_delete(self._delete_req(self.proj_user, [self.proj_att.id]))
        self.assertEqual(resp.data.get('deleted'), 1)
        self.assertFalse(Attachment.objects.filter(id=self.proj_att.id).exists())

    def test_batch_delete_admin_deletes_all(self):
        resp = AttachmentViewSet().batch_delete(self._delete_req(self.root, [self.proj_att.id]))
        self.assertEqual(resp.data.get('deleted'), 1)
