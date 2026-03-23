import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.permission_models_new import Permission


TOP_LEVEL_MENUS = {
    # 非标自动化行业(100人规模)优化菜单: 商务→项目→研发→采购→生产→仓储→财务
    'dashboard':  {'name': '工作台',   'icon': 'DataAnalysis',    'route_path': '/dashboard',              'sort_order': 0},
    'projects':   {'name': '项目管理', 'icon': 'Folder',          'route_path': '/projects',               'sort_order': 10},
    'design':     {'name': '研发设计', 'icon': 'EditPen',         'route_path': '/plm/requirements',       'sort_order': 15},
    'sales':      {'name': '商务销售', 'icon': 'TrendCharts',     'route_path': '/sales/crm-dashboard',    'sort_order': 20},
    'purchase':   {'name': '采购供应', 'icon': 'ShoppingCart',    'route_path': '/purchase/requests',      'sort_order': 30},
    'production': {'name': '生产制造', 'icon': 'Operation',       'route_path': '/production/processes',   'sort_order': 40},
    'inventory':  {'name': '仓储物料', 'icon': 'Goods',           'route_path': '/inventory/stocks',       'sort_order': 50},
    'finance':    {'name': '财务管理', 'icon': 'Money',           'route_path': '/finance/expenses',       'sort_order': 60},
    'masterdata': {'name': '基础数据', 'icon': 'Box',             'route_path': '/masterdata/items',       'sort_order': 70},
    'reports':    {'name': '经营分析', 'icon': 'PieChart',        'route_path': '/reports/profitability',  'sort_order': 80},
    'oa':         {'name': '协同办公', 'icon': 'OfficeBuilding',  'route_path': '/oa/schedule',            'sort_order': 90},
    'system':     {'name': '系统设置', 'icon': 'Setting',         'route_path': '/system/users',           'sort_order': 999},
}

# 将前端细分业务前缀收敛到既有一级菜单，避免改变原始菜单结构。
PREFIX_PARENT_OVERRIDES = {
    'aftersales': 'sales',       # 售后归入商务销售
    'equipment':  'production',  # 设备管理归入生产制造
    'knowledge':  'design',      # 知识库归入研发设计
    'plm':        'design',      # PLM归入研发设计
    'mes':        'production',  # MES归入生产制造
    'accounts':   'oa',          # 考勤归入协同办公
    'workflow':   'oa',          # 审批归入协同办公
    'analytics':  'reports',     # 分析看板归入经营分析
}

LEGACY_TOP_LEVEL_CODES = tuple(PREFIX_PARENT_OVERRIDES.keys())


class Command(BaseCommand):
    help = '从前端路由同步菜单权限到 core_permission'

    route_pattern = re.compile(
        r"path:\s*'([^']+)'[\s\S]{0,20}?(?:name|component)[\s\S]{0,200}?meta:\s*\{[^}]*title:\s*'([^']+)'[^}]*menuId:\s*'([^']+)'",
        re.M,
    )

    def handle(self, *args, **options):
        router_path = self._find_router_path()
        if not router_path.exists():
            raise CommandError(f'找不到前端路由文件: {router_path}')

        route_text = router_path.read_text(encoding='utf-8')
        raw_routes = self.route_pattern.findall(route_text)
        # 排除 redirect 路由路径，防止正则跨路由对象边界误匹配
        redirect_paths = set(re.findall(r"path:\s*'([^']+)'\s*,\s*redirect:", route_text))
        raw_routes = [(p, t, m) for p, t, m in raw_routes if p not in redirect_paths]
        selected_routes = self._select_routes(raw_routes)

        created = 0
        updated = 0

        for code, meta in TOP_LEVEL_MENUS.items():
            _, was_created = Permission.objects.update_or_create(
                code=code,
                defaults={
                    'name': meta['name'],
                    'type': 'menu',
                    'icon': meta['icon'],
                    'route_path': meta['route_path'],
                    'sort_order': meta['sort_order'],
                    'is_active': True,
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        Permission.objects.filter(code__in=LEGACY_TOP_LEVEL_CODES, parent__isnull=True).update(is_active=False)

        for menu_id, route in selected_routes.items():
            if ':' not in menu_id:
                # 顶级菜单已由映射表维护
                continue

            prefix = menu_id.split(':', 1)[0]
            parent_code = PREFIX_PARENT_OVERRIDES.get(prefix, prefix)
            parent = Permission.objects.filter(code=parent_code).first()
            if not parent:
                self.stdout.write(self.style.WARNING(f'跳过 {menu_id}: 缺少父菜单 {parent_code}'))
                continue

            defaults = {
                'name': route['title'],
                'type': 'menu',
                'route_path': route['route_path'],
                'sort_order': route['sort_order'],
                'is_active': True,
                'parent': parent,
            }
            permission, was_created = Permission.objects.update_or_create(code=menu_id, defaults=defaults)
            if permission.icon != parent.icon:
                permission.icon = parent.icon
                permission.save(update_fields=['icon'])
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f'菜单同步完成: 创建 {created} 条, 更新 {updated} 条'))

    def _find_router_path(self):
        candidates = [
            Path.cwd().parent / 'frontend' / 'src' / 'router' / 'index.js',
            Path.cwd() / 'frontend' / 'src' / 'router' / 'index.js',
            Path(__file__).resolve().parents[4] / 'frontend' / 'src' / 'router' / 'index.js',
            Path('/frontend/src/router/index.js'),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1]

    def _select_routes(self, raw_routes):
        grouped = {}

        for path, title, menu_id in raw_routes:
            route = {
                'title': title,
                'route_path': self._normalize_route_path(path),
                'sort_order': self._sort_order(menu_id, path),
                'score': self._score_candidate(menu_id, path),
            }
            current = grouped.get(menu_id)
            if current is None or route['score'] > current['score']:
                grouped[menu_id] = route

        return grouped

    @staticmethod
    def _normalize_route_path(path):
        return path if path.startswith('/') else f'/{path}'

    @staticmethod
    def _sort_order(menu_id, path):
        parts = menu_id.split(':')
        base = TOP_LEVEL_MENUS.get(parts[0], {}).get('sort_order', 900)
        depth = path.count('/')
        return base * 10 + depth

    @staticmethod
    def _score_candidate(menu_id, path):
        score = 0
        if ':' not in path:
            score += 2
        if '/:' not in path:
            score += 20
        prefix, _, tail = menu_id.partition(':')
        if path.startswith(prefix + '/') or path == prefix:
            score += 10
        tail_token = tail.split(':')[-1] if tail else prefix
        if tail_token.replace('-', '/') in path or tail_token in path:
            score += 6
        score -= path.count('/:') * 5
        score -= path.count('/')
        return score