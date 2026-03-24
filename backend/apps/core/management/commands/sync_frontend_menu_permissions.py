import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.permission_models_new import Permission


TOP_LEVEL_MENUS = {
    # 非标自动化行业(100人规模)优化菜单
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

# 将前端细分业务前缀收敛到既有一级菜单
PREFIX_PARENT_OVERRIDES = {
    'aftersales': 'sales',
    'equipment':  'production',
    'knowledge':  'design',
    'plm':        'design',
    'mes':        'production',
    'accounts':   'oa',
    'workflow':   'oa',
    'analytics':  'reports',
}

LEGACY_TOP_LEVEL_CODES = tuple(PREFIX_PARENT_OVERRIDES.keys())

# ── 二级分组：将扁平子菜单按业务场景分组，降低视觉复杂度 ──
# 格式: { '一级code': [ ('分组后缀', '分组名', [menuId ...]), ... ] }
MENU_GROUPS = {
    'projects': [
        ('exec',     '项目执行', ['projects:list', 'projects:dashboard', 'projects:tasks', 'projects:gantt', 'projects:milestones', 'projects:members']),
        ('delivery', '项目交付', ['projects:bom', 'projects:work-orders', 'projects:acceptances', 'projects:bugs']),
        ('analysis', '项目分析', ['projects:time-logs', 'projects:cost', 'projects:archives', 'projects:alerts']),
    ],
    'design': [
        ('manage',    '设计管理', ['design:ecn', 'design:drawings', 'design:batch-drawing', 'design:drawing-bom-link', 'design:documents']),
        ('plm',       'PLM',     ['plm:requirements', 'plm:proposals', 'plm:agreements', 'plm:model-viewer', 'plm:cad-bom', 'plm:bom-compare']),
        ('knowledge', '知识库',   ['knowledge:articles', 'knowledge:issues', 'knowledge:components']),
    ],
    'sales': [
        ('crm',        '客户管理', ['sales:crm-dashboard', 'sales:leads', 'sales:opportunities', 'sales:performance', 'sales:analysis']),
        ('order',      '报价合同', ['sales:quotations', 'sales:quote-estimation', 'sales:quote', 'sales:orders', 'sales:contracts', 'sales:contract-templates', 'sales:quote-templates']),
        ('aftersales', '发货售后', ['sales:delivery-orders', 'sales:training', 'sales:service', 'aftersales:orders', 'aftersales:service']),
        ('reconcile',  '销售对账', ['finance:sales-reconciliation']),
    ],
    'purchase': [
        ('business', '采购业务',   ['purchase:requests', 'purchase:orders', 'purchase:goods-receipts', 'purchase:budgets']),
        ('reconcile', '采购对账',  ['finance:purchase-reconciliation']),
        ('supplier', '供应商管理', ['purchase:comparisons', 'purchase:evaluations', 'purchase:blacklist']),
        ('collab',   '委外协同',   ['purchase:outsource', 'purchase:collaboration', 'purchase:portal']),
    ],
    'production': [
        ('process',   '工艺管理', ['production:processes', 'production:routing', 'production:workstations', 'production:capacity', 'production:resources']),
        ('execute',   '生产执行', ['production:plans', 'production:assembly', 'production:debug-records', 'production:serial-numbers', 'production:inspections']),
        ('equipment', '设备管理', ['equipment:list', 'equipment:fixtures', 'equipment:inspection', 'equipment:archives', 'equipment:maintenance', 'equipment:oee', 'equipment:monitoring']),
        ('mes',       'MES',     ['mes:scheduling', 'mes:kanban', 'mes:andon', 'mes:data-acquisition']),
    ],
    'inventory': [
        ('inout',   '出入库',   ['inventory:stocks', 'inventory:moves', 'inventory:requisitions', 'inventory:returns', 'inventory:transfer']),
        ('manage',  '库存管理', ['inventory:batches', 'inventory:adjustment', 'inventory:alerts', 'inventory:cost-accounting']),
        ('plan',    '物料计划', ['inventory:mrp', 'inventory:spare-parts', 'inventory:data-accuracy']),
    ],
    'finance': [
        ('cashflow',  '费用管理', ['finance:expenses', 'finance:shared-expenses', 'finance:collection']),
        ('reconcile', '对账结算', ['finance:ar', 'finance:ap', 'finance:invoices']),
        ('assets',    '资产成本', ['finance:project-costs', 'finance:assets']),
    ],
    'masterdata': [
        ('base',    '物料仓库',   ['masterdata:items', 'masterdata:warehouses', 'masterdata:locations']),
        ('partner', '客户供应商', ['masterdata:customers', 'masterdata:suppliers', 'masterdata:customer-followups', 'masterdata:customer-contacts', 'masterdata:credit']),
    ],
    'reports': [
        ('finance',   '财务报表', ['reports:profitability', 'reports:aging', 'reports:cash-flow', 'reports:cost-analysis', 'reports:project-profitability']),
        ('operation', '运营报表', ['reports:timelog', 'reports:slow-moving', 'reports:equipment-lifecycle', 'reports:capacity-utilization', 'reports:customer-value']),
        ('bi',        '综合分析', ['analytics:project', 'analytics:inventory']),
    ],
    'oa': [
        ('office',     '日常办公', ['oa:schedule', 'oa:meeting', 'oa:im', 'oa:announcement']),
        ('attendance', '考勤假期', ['oa:attendance', 'oa:attendance-import', 'oa:leave', 'accounts:attendance']),
        ('workflow',   '审批流程', ['workflow:tasks', 'workflow:my-submissions', 'workflow:config']),
        ('admin',      '行政管理', ['oa:vehicles', 'oa:vehicle-request', 'oa:assets']),
    ],
    'system': [
        ('auth',   '组织权限', ['system:users', 'system:roles', 'system:departments']),
        ('config', '基础配置', ['system:code-rules', 'system:config', 'system:dashboard-config', 'system:data-dictionary', 'system:custom-fields']),
        ('notify', '消息通知', ['system:notification-settings', 'system:email-templates', 'system:notifications', 'system:announcements']),
        ('audit',  '安全审计', ['system:audit-log', 'system:login-logs', 'system:webhooks', 'system:audit-analytics']),
        ('ops',    '运维管理', ['system:monitor', 'system:backup']),
    ],
}


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
        redirect_paths = set(re.findall(r"path:\s*'([^']+)'\s*,\s*redirect:", route_text))
        # 排除注释掉的路由: 查找被 // 注释的 path 行
        commented_paths = set(re.findall(r"//\s*path:\s*'([^']+)'", route_text))
        raw_routes = [(p, t, m) for p, t, m in raw_routes if p not in redirect_paths and p not in commented_paths]
        selected_routes = self._select_routes(raw_routes)

        created = 0
        updated = 0

        # ── 1. 一级菜单 ──
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

        # ── 2. 二级分组容器 ──
        group_parent_map = {}  # menuId → group Permission
        for top_code, groups in MENU_GROUPS.items():
            top_perm = Permission.objects.filter(code=top_code).first()
            if not top_perm:
                continue
            for idx, (suffix, name, items) in enumerate(groups):
                grp_code = f'{top_code}:g-{suffix}'
                grp_perm, was_created = Permission.objects.update_or_create(
                    code=grp_code,
                    defaults={
                        'name': name,
                        'type': 'menu',
                        'icon': '',
                        'route_path': '',
                        'sort_order': top_perm.sort_order * 10 + idx + 1,
                        'is_active': True,
                        'parent': top_perm,
                    },
                )
                created += int(was_created)
                updated += int(not was_created)
                for item_code in items:
                    group_parent_map[item_code] = grp_perm

        # ── 3. 三级叶子菜单 ──
        for menu_id, route in selected_routes.items():
            if ':' not in menu_id:
                continue

            if menu_id in group_parent_map:
                parent = group_parent_map[menu_id]
            else:
                prefix = menu_id.split(':', 1)[0]
                parent_code = PREFIX_PARENT_OVERRIDES.get(prefix, prefix)
                parent = Permission.objects.filter(code=parent_code).first()
                if not parent:
                    self.stdout.write(self.style.WARNING(f'跳过 {menu_id}: 缺少父菜单 {parent_code}'))
                    continue

            defaults = {
                'name': route['title'],
                'type': 'menu',
                'icon': '',
                'route_path': route['route_path'],
                'sort_order': route['sort_order'],
                'is_active': True,
                'parent': parent,
            }
            _, was_created = Permission.objects.update_or_create(code=menu_id, defaults=defaults)
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
