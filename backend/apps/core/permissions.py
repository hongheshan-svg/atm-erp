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
ALL_ROLES = PURCHASE_READERS | {'member'}


def role(user):
    return 'admin' if user.is_superuser else user.role


def require_role(user, allowed):
    if not user.is_authenticated or not user.is_active or role(user) not in allowed:
        raise PermissionDenied('没有此操作权限。')


def projects_for(user, queryset):
    require_role(user, ALL_ROLES)
    if role(user) == 'member':
        return queryset.filter(Q(members=user) | Q(manager=user)).distinct()
    return queryset


def require_project(user, project):
    require_role(user, ALL_ROLES)
    if role(user) == 'member' and project.manager_id != user.pk and not project.members.filter(pk=user.pk).exists():
        raise PermissionDenied('无权访问此项目。')


class RolePermission(BasePermission):
    def has_permission(self, request, view):
        allowed = view.read_roles if request.method in ('GET', 'HEAD', 'OPTIONS') else view.write_roles
        require_role(request.user, allowed)
        return True


class PermissionMixin:
    permission_classes = [RolePermission]
    read_roles = ALL_ROLES
    write_roles = ADMIN
