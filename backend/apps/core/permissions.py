"""
Custom permission classes for the ERP system.

Most permission enforcement is handled by PermissionMixin in permission_mixin.py
(menu-level granularity bridged by MODULE_MENU_MAP). The classes here add a
*hard* gate, independent of and stricter than that menu fallback, for the
security/RBAC machinery and system-level configuration.

Why this is needed
------------------
PermissionMixin grants module access to anyone holding a mapped menu prefix
(``_has_module_menu_access``). Because many sensitive ViewSets share
``permission_module='system'``, that fallback would let a holder of *any*
``system:*`` leaf (e.g. ``system:report``, held by every manager) — or, before
the accompanying MODULE_MENU_MAP fix, any ``oa:*`` leaf held by ordinary
employees — read or write the permission tree, data scopes, code rules,
webhooks, audit logs, etc. (privilege escalation, audit finding C1).

These classes require either a Django superuser or a holder of the *top-level*
``system`` permission grant (only the ``admin`` role holds it via ``*``). They
run inside ``super().check_permissions()`` — i.e. before PermissionMixin's menu
fallback — so attaching them to a ViewSet closes the escalation regardless of
the menu fallback.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

# Aliased to avoid confusion with BasePermission.has_permission (the DRF method).
from apps.core.permission_service import has_permission as user_has_permission

# Top-level menu grant that designates a full system administrator.
SYSTEM_ADMIN_CODE = 'system'


class HasModuleMenuAccess(BasePermission):
    """Module-menu authorization gate for endpoints that cannot inherit
    ``PermissionMixin`` — function-based views (``@api_view``) and bare
    ``APIView`` subclasses (exports, reports, dashboards, kanban).

    Mirrors ``PermissionMixin._has_module_menu_access``: a user is authorized
    when they hold any menu code mapped to ``module`` via ``MODULE_MENU_MAP``
    (exact match or ``prefix:`` descendant). Superusers always pass; anonymous
    users never do. Without this gate such endpoints fall back to a bare
    ``IsAuthenticated``/``AllowAny`` and leak cross-module data (audit batch 1).

    Bind to a module with the ``module_menu_permission`` factory:

        @permission_classes([module_menu_permission('finance')])
        def export_ar(request): ...

        class ProductionKanbanView(APIView):
            permission_classes = [module_menu_permission('production')]
    """

    module = None

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        module = self.module or getattr(view, 'permission_module', None)
        if not module:
            return False
        # Lazy import avoids a circular import (permission_mixin imports this module's siblings).
        from apps.core.permission_mixin import MODULE_MENU_MAP
        from apps.core.permission_service import get_user_menu_permissions

        menu_prefixes = MODULE_MENU_MAP.get(module, [])
        if not menu_prefixes:
            return False
        user_perms = get_user_menu_permissions(user)
        return any(p == prefix or p.startswith(prefix + ':') for prefix in menu_prefixes for p in user_perms)


def module_menu_permission(module):
    """Return a ``HasModuleMenuAccess`` subclass bound to ``module``.

    Produces a distinct DRF permission class per module so it can be dropped
    into ``permission_classes`` on FBVs/APIViews.
    """
    return type(f'HasModuleMenuAccess_{module}', (HasModuleMenuAccess,), {'module': module})


def _is_system_admin(user) -> bool:
    """True for Django superusers and holders of the top-level ``system`` grant."""
    return bool(user and user.is_authenticated and (user.is_superuser or user_has_permission(user, SYSTEM_ADMIN_CODE)))


class IsSystemAdmin(BasePermission):
    """
    Restrict every method (read and write) to system administrators.

    Use on resources that ordinary users never need via the API: the permission
    tree, data scopes, code rules, webhooks, audit/email logs.
    """

    message = '仅系统管理员可访问该资源'

    def has_permission(self, request, view):
        return _is_system_admin(request.user)


class IsSystemAdminOrReadOnly(BasePermission):
    """
    Allow safe (read) methods through to the ViewSet's own rules, but require a
    system administrator for any write (POST/PUT/PATCH/DELETE).

    Use on system configuration that business users/UIs must still *read*
    (data dictionaries, custom-field definitions, email templates, roles) but
    only administrators may modify.
    """

    message = '仅系统管理员可修改该资源'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _is_system_admin(request.user)
