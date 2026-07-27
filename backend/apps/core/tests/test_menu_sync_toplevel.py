import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.core.management.commands.sync_frontend_menu_permissions import (
    PREFIX_PARENT_OVERRIDES,
    TOP_LEVEL_MENUS,
    Command,
)


class MenuTopLevelAlignmentTests(SimpleTestCase):
    """TOP_LEVEL_MENUS 必须与前端路由实际使用的 menuId 前缀对齐。

    一级菜单由同步命令无条件 update_or_create 建出来。前端没有任何 menuId 落在它下面时,
    侧边栏就会多出一个空壳入口 —— 而且因为一级菜单都带 route_path,
    get_menus() 里"跳过没有可见子项的空分组容器"那条过滤也拦不住它。
    """

    def _router_prefixes(self):
        router_path = Command()._find_router_path()
        menu_ids = re.findall(r"menuId:\s*'([^']+)'", Path(router_path).read_text(encoding='utf-8'))
        return {menu_id.split(':', 1)[0] for menu_id in menu_ids}

    def test_every_top_level_menu_is_used_by_the_frontend_router(self):
        prefixes = self._router_prefixes()
        parents_in_use = {PREFIX_PARENT_OVERRIDES.get(prefix, prefix) for prefix in prefixes}

        unused = sorted(set(TOP_LEVEL_MENUS) - parents_in_use)
        self.assertEqual(unused, [], f'一级菜单 {unused} 没有任何前端路由挂载,会在侧边栏留下空壳入口')

    def test_every_router_prefix_resolves_to_a_top_level_menu(self):
        prefixes = self._router_prefixes()
        parents_in_use = {PREFIX_PARENT_OVERRIDES.get(prefix, prefix) for prefix in prefixes}

        missing = sorted(parents_in_use - set(TOP_LEVEL_MENUS))
        self.assertEqual(missing, [], f'前端路由挂在 {missing} 下,但它不是一级菜单,这些页面会被同步命令跳过')

    def test_prefix_overrides_point_to_existing_top_level_menus(self):
        dangling = {
            prefix: parent for prefix, parent in PREFIX_PARENT_OVERRIDES.items() if parent not in TOP_LEVEL_MENUS
        }
        self.assertEqual(dangling, {}, f'PREFIX_PARENT_OVERRIDES 指向了不存在的一级菜单: {dangling}')
