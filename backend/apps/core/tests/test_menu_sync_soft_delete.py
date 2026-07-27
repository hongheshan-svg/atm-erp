from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.core.permission_models_new import Permission


class MenuSyncSoftDeleteTests(TestCase):
    """重跑菜单同步时,此前被软删的菜单节点必须复活。

    菜单树由 UserProfileSerializer.get_menus() 经 Permission.active 递归构建,
    父节点带着 is_deleted=True 就会被过滤掉,其下所有子菜单随之变成永远遍历不到的孤儿。
    """

    def test_sync_revives_soft_deleted_menu_nodes(self):
        call_command('sync_frontend_menu_permissions', verbosity=0)

        # 一级菜单 / 二级分组容器 / 三级叶子 各取一个
        codes = ['projects', 'projects:g-delivery', 'projects:bom']
        self.assertEqual(Permission.objects.filter(code__in=codes).count(), len(codes))
        Permission.objects.filter(code__in=codes).update(is_deleted=True, deleted_at=timezone.now())

        call_command('sync_frontend_menu_permissions', verbosity=0)

        for code in codes:
            perm = Permission.objects.get(code=code)
            self.assertFalse(perm.is_deleted, f'{code} 仍是软删状态,其子菜单会成为孤儿')
            self.assertIsNone(perm.deleted_at, f'{code} 的 deleted_at 未复位')
            self.assertTrue(Permission.active.filter(code=code).exists(), f'{code} 未回到 active 菜单集合')
