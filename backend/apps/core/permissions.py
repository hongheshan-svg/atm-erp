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


def require_reports(user):
    require_role(user, MANAGERS)
    if not has_role(user, ADMIN) and not user.management_reports:
        raise PermissionDenied('未获得总经理报表授权。')


def projects_for(user, queryset, allowed=OPERATION_ROLES):
    require_role(user, allowed & OPERATION_ROLES)
    if not has_role(user, GLOBAL_PROJECT_ROLES & allowed):
        return queryset.filter(Q(members=user) | Q(manager=user)).distinct()
    return queryset


def project_allowed(user, project, allowed=OPERATION_ROLES):
    return has_role(user, allowed & OPERATION_ROLES) and (
        has_role(user, GLOBAL_PROJECT_ROLES & allowed)
        or project.manager_id == user.pk
        or project.members.filter(pk=user.pk).exists()
    )


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
        allowed = view.read_roles if request.method in ('GET', 'HEAD', 'OPTIONS') else view.write_roles
        require_role(request.user, allowed)
        return True


class PermissionMixin:
    permission_classes = [RolePermission]
    read_roles = OPERATION_ROLES
    write_roles = ADMIN
