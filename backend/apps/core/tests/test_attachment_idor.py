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

from apps.core.models import Attachment
from apps.core.views import AttachmentViewSet

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
