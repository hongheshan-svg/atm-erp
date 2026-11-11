from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

ADMIN = {'admin'}
MANAGERS = {'admin', 'manager'}
PRODUCTION_MANAGERS = MANAGERS | {'production_manager'}
PRODUCTION_TASK_KINDS = ('assembly', 'test', 'install', 'service')
ENGINEERS = {'mechanical_engineer', 'electrical_engineer'}
BOM_WRITERS = MANAGERS | ENGINEERS
PURCHASE_APPROVERS = MANAGERS | {'purchase_manager'}
PURCHASERS = PURCHASE_APPROVERS | {'purchaser'}
ITEM_WRITERS = PURCHASERS | ENGINEERS
WAREHOUSE = {'admin', 'warehouse'}
FINANCE = {'admin', 'finance'}
MONEY_READERS = {'admin', 'manager', 'finance'}
PURCHASE_READERS = PURCHASERS | WAREHOUSE | FINANCE
OPERATION_ROLES = PURCHASE_READERS | {'member', 'production_manager'} | ENGINEERS
ALL_ROLES = OPERATION_ROLES | {'sales_manager'}
SALES = MANAGERS | {'sales_manager'}
SALES_READERS = MONEY_READERS | {'sales_manager'}
GLOBAL_PROJECT_ROLES = {'admin', 'purchaser', 'purchase_manager', 'warehouse', 'finance'}
# 没有项目归属的库存金额（库存结存、期初与盘点流水）汇总了各项目的采购成本：只对管理员、财务和采购岗位开放，
# 外加获授权的总经理（见 can_read_stock_value）；普通项目经理只看负责或参与项目的金额，仓管不可见成本。
STOCK_VALUE_READERS = {'admin', 'finance', 'purchaser', 'purchase_manager'}


def sales_for(user, queryset):
    require_role(user, SALES_READERS)
    return queryset if has_role(user, MONEY_READERS) else queryset.filter(manager=user)


def require_sale(user, sale):
    require_role(user, SALES)
    if not has_role(user, MANAGERS) and sale.manager_id != user.pk:
        raise PermissionDenied('仅能操作自己负责的销售单。')


def role(user):
    return 'admin' if user.is_superuser else user.role


def roles(user):
    return {role(user), *getattr(user, 'additional_roles', [])} & ALL_ROLES


def has_role(user, allowed):
    return bool(roles(user) & allowed)


def require_role(user, allowed):
    if not user.is_authenticated or not user.is_active or not has_role(user, allowed):
        raise PermissionDenied('没有此操作权限。')


def reports_allowed(user):
    """经营报表：管理员默认可看；总经理沿用 manager 角色，由管理员显式开启 management_reports。"""
    return has_role(user, ADMIN) or (has_role(user, MANAGERS) and user.management_reports)


def require_reports(user):
    require_role(user, MANAGERS)
    if not reports_allowed(user):
        raise PermissionDenied('未获得总经理报表授权。')


def can_read_stock_value(user):
    return has_role(user, STOCK_VALUE_READERS) or reports_allowed(user)


def projects_for(user, queryset, allowed=OPERATION_ROLES):
    require_role(user, allowed & OPERATION_ROLES)
    if not has_role(user, GLOBAL_PROJECT_ROLES & allowed):
        return queryset.filter(Q(members=user) | Q(manager=user)).distinct()
    return queryset


def project_allowed(user, project, allowed=OPERATION_ROLES):
    members = getattr(project, '_prefetched_objects_cache', {}).get('members')
    return has_role(user, allowed & OPERATION_ROLES) and (
        has_role(user, GLOBAL_PROJECT_ROLES & allowed)
        or project.manager_id == user.pk
        or (
            any(member.pk == user.pk for member in members)
            if members is not None
            else project.members.filter(pk=user.pk).exists()
        )
    )


def project_read_allowed(request, project_id, allowed=MONEY_READERS):
    """Resolve sensitive read scope once per request, never cache a write authorization."""
    user = request.user
    if not has_role(user, allowed):
        return False
    if project_id is None or has_role(user, GLOBAL_PROJECT_ROLES & allowed):
        return True
    from apps.business.models import Project

    cache = getattr(request, '_project_read_scopes', None)
    if cache is None:
        cache = request._project_read_scopes = {}
    scope = frozenset(allowed)
    if scope not in cache:
        cache[scope] = set(projects_for(user, Project.objects.all(), allowed).values_list('pk', flat=True))
    return project_id in cache[scope]


def require_project(user, project, allowed=OPERATION_ROLES):
    require_role(user, allowed & OPERATION_ROLES)
    if not project_allowed(user, project, allowed):
        raise PermissionDenied('无权访问此项目。')


def task_management_roles(kind):
    return PRODUCTION_MANAGERS if kind in PRODUCTION_TASK_KINDS else MANAGERS


def can_manage_task(user, task):
    return project_allowed(user, task.project, task_management_roles(task.kind))


class RolePermission(BasePermission):
    def has_permission(self, request, view):
        # 未登录返回 False，由 DRF 转成 401「请先登录」；require_role 直接抛 403 会让前端误以为是权限不足。
        if not request.user or not request.user.is_authenticated:
            return False
        allowed = view.read_roles if request.method in ('GET', 'HEAD', 'OPTIONS') else view.write_roles
        require_role(request.user, allowed)
        return True


class PermissionMixin:
    permission_classes = [RolePermission]
    read_roles = OPERATION_ROLES
    write_roles = ADMIN
