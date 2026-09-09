from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

ADMIN = {'admin'}
MANAGERS = {'admin', 'manager'}
PURCHASERS = {'admin', 'manager', 'purchaser'}
WAREHOUSE = {'admin', 'warehouse'}
FINANCE = {'admin', 'finance'}
MONEY_READERS = {'admin', 'manager', 'finance'}
PURCHASE_READERS = {'admin', 'manager', 'purchaser', 'warehouse', 'finance'}
OPERATION_ROLES = PURCHASE_READERS | {'member'}
ALL_ROLES = OPERATION_ROLES | {'sales_manager'}
SALES = MANAGERS | {'sales_manager'}
SALES_READERS = MONEY_READERS | {'sales_manager'}


def sales_for(user, queryset):
    require_role(user, SALES_READERS)
    return queryset.filter(manager=user) if role(user) == 'sales_manager' else queryset


def require_sale(user, sale):
    require_role(user, SALES)
    if role(user) == 'sales_manager' and sale.manager_id != user.pk:
        raise PermissionDenied('仅能操作自己负责的销售单。')


def role(user):
    return 'admin' if user.is_superuser else user.role


def require_role(user, allowed):
    if not user.is_authenticated or not user.is_active or role(user) not in allowed:
        raise PermissionDenied('没有此操作权限。')


def require_reports(user):
    require_role(user, MANAGERS)
    if role(user) != 'admin' and not user.management_reports:
        raise PermissionDenied('未获得总经理报表授权。')


def projects_for(user, queryset):
    require_role(user, OPERATION_ROLES)
    if role(user) == 'member':
        return queryset.filter(Q(members=user) | Q(manager=user)).distinct()
    return queryset


def require_project(user, project):
    require_role(user, OPERATION_ROLES)
    if role(user) == 'member' and project.manager_id != user.pk and not project.members.filter(pk=user.pk).exists():
        raise PermissionDenied('无权访问此项目。')


class RolePermission(BasePermission):
    def has_permission(self, request, view):
        allowed = view.read_roles if request.method in ('GET', 'HEAD', 'OPTIONS') else view.write_roles
        require_role(request.user, allowed)
        return True


class PermissionMixin:
    permission_classes = [RolePermission]
    read_roles = OPERATION_ROLES
    write_roles = ADMIN
