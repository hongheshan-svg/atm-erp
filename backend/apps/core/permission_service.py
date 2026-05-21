"""
Permission service functions for checking user permissions.

Provides caching and wildcard support for permission checks.
"""
from typing import Set, Tuple, List
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db.models import QuerySet, Q
from apps.core.permission_models_new import DataScope, Permission
from apps.accounts.models import Department

User = get_user_model()

SCOPE_ALIAS_TO_PUBLIC = {
    'ALL': 'all',
    'all': 'all',
    'GLOBAL': 'all',
    'global': 'all',
    'DEPARTMENT': 'dept_tree',
    'department_and_below': 'dept_tree',
    'DEPT_TREE': 'dept_tree',
    'dept_tree': 'dept_tree',
    'DEPT': 'dept',
    'dept': 'dept',
    'department': 'dept',
    'SELF': 'self',
    'self': 'self',
    'CUSTOM': 'custom',
    'custom': 'custom',
}

PUBLIC_SCOPE_TO_MODEL = {
    'all': 'all',
    'dept_tree': 'dept_tree',
    'dept': 'dept',
    'self': 'self',
    'custom': 'custom',
}

# Cache timeout in seconds (5 minutes)
PERMISSION_CACHE_TIMEOUT = 300

# Scope priority for determining widest scope
SCOPE_PRIORITY = {
    'all': 5,
    'custom': 4,
    'dept_tree': 4,
    'dept': 3,
    'self': 2,
}


def normalize_scope_type(scope_type: str, target: str = 'public') -> str:
    canonical = SCOPE_ALIAS_TO_PUBLIC.get(scope_type, scope_type)
    if target == 'public':
        return canonical
    if target == 'model':
        return PUBLIC_SCOPE_TO_MODEL.get(canonical, canonical)
    raise ValueError(f'Unsupported target: {target}')


def get_active_user_roles(user):
    role_model = user.roles.model
    role_filter = Q(users_m2m=user)
    if getattr(user, 'role_id', None):
        role_filter |= Q(pk=user.role_id)

    return role_model.objects.filter(role_filter, is_active=True, is_deleted=False).distinct()


def get_user_permissions(user) -> Set[str]:
    """
    Get all permission codes for a user.

    Returns a set of permission codes that the user has access to.
    Results are cached for performance.

    Args:
        user: User instance

    Returns:
        Set of permission code strings

    Notes:
        - Superusers get all active permissions
        - Only active permissions from active roles are returned
        - Results are cached with key 'user_permissions:{user_id}'
    """
    # Handle None/unauthenticated user
    if user is None or not user.is_authenticated:
        return set()

    # Check cache first
    cache_key = f'user_permissions:{user.id}'
    cached_permissions = cache.get(cache_key)
    if cached_permissions is not None:
        return cached_permissions

    permissions = set()

    if user.is_superuser:
        # Superuser gets all active permissions
        permissions = set(
            Permission.objects.filter(
                is_active=True,
                is_deleted=False
            ).values_list('code', flat=True)
        )
    else:
        # Get permissions from all user's roles (兼容旧 role FK 和新 roles M2M)
        user_roles = get_active_user_roles(user)
        if user_roles.exists():
            permissions = set(
                Permission.objects.filter(
                    role_permissions__role__in=user_roles,
                    is_active=True,
                    is_deleted=False
                ).values_list('code', flat=True)
            )

    # Cache the result
    cache.set(cache_key, permissions, PERMISSION_CACHE_TIMEOUT)

    return permissions


def has_permission(user, permission_code: str) -> bool:
    """
    Check if user has a specific permission.

    Supports parent node wildcard matching:
    - Having 'purchase:order' grants 'purchase:order:*'
    - Having 'purchase:order:create' does NOT grant 'purchase:order:edit'

    Args:
        user: User instance
        permission_code: Permission code to check (e.g., 'purchase:order:create')

    Returns:
        True if user has the permission, False otherwise

    Notes:
        - Superusers always return True
        - Uses get_user_permissions() which is cached
    """
    # Handle None/unauthenticated user
    if user is None or not user.is_authenticated:
        return False

    # Superuser always has permission
    if user.is_superuser:
        return True

    # Get user's permissions (cached)
    user_permissions = get_user_permissions(user)

    # Direct match
    if permission_code in user_permissions:
        return True

    # Check parent node wildcard
    # If user has 'purchase:order', they have 'purchase:order:*'
    parts = permission_code.split(':')
    for i in range(len(parts) - 1, 0, -1):
        parent_code = ':'.join(parts[:i])
        if parent_code in user_permissions:
            return True

    return False


def _get_role_user_ids(role) -> set:
    """Get all user IDs associated with a role (兼容旧 role FK 和新 roles M2M)."""
    user_ids = set(role.users.filter(is_deleted=False).values_list('id', flat=True))
    user_ids.update(role.users_m2m.filter(is_deleted=False).values_list('id', flat=True))
    return user_ids


def on_role_permission_change(role):
    """
    Invalidate permission and data scope caches when role permissions change.

    Call this function after adding/removing permissions from a role.
    """
    user_ids = _get_role_user_ids(role)
    for user_id in user_ids:
        cache.delete(f'user_permissions:{user_id}')
        cache.delete_pattern(f'user_data_scope:{user_id}:*')


def on_user_role_change(user):
    """
    Invalidate permission and data scope caches when user's role changes.
    """
    cache.delete(f'user_permissions:{user.id}')
    cache.delete_pattern(f'user_data_scope:{user.id}:*')


def resolve_data_scope(user, module: str) -> Tuple[str, List[int]]:
    """
    Resolve data scope for a user in a specific module.

    查询 DataScope 表获取用户所有角色中最宽的数据范围。
    无 DataScope 配置时默认返回 'all'（信息透明，促进协作）。

    Args:
        user: User instance
        module: Module name (e.g., 'projects', 'sales', 'purchase')

    Returns:
        Tuple of (scope_type, custom_dept_ids)
    """
    if user is None or not user.is_authenticated:
        return ('self', [])

    if user.is_superuser:
        return ('all', [])

    cache_key = f'user_data_scope:{user.id}:{module}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    user_roles = get_active_user_roles(user)
    if not user_roles.exists():
        result = ('all', [])
        cache.set(cache_key, result, PERMISSION_CACHE_TIMEOUT)
        return result

    scopes = DataScope.objects.filter(
        role__in=user_roles,
        module__in=[module, '']
    )

    if not scopes.exists():
        result = ('all', [])
        cache.set(cache_key, result, PERMISSION_CACHE_TIMEOUT)
        return result

    best_scope = max(scopes, key=lambda s: SCOPE_PRIORITY.get(s.scope_type, 0))
    custom_dept_ids = []
    if best_scope.scope_type == 'custom':
        custom_dept_ids = list(best_scope.custom_departments.values_list('id', flat=True))

    result = (best_scope.scope_type, custom_dept_ids)
    cache.set(cache_key, result, PERMISSION_CACHE_TIMEOUT)
    return result


def get_department_tree_ids(dept_id: int) -> List[int]:
    """
    Get department ID and all its children IDs recursively.

    Args:
        dept_id: Department ID

    Returns:
        List of department IDs including the department itself and all descendants

    Notes:
        - Returns empty list if department doesn't exist
        - Excludes soft-deleted departments
    """
    try:
        dept = Department.objects.get(id=dept_id, is_deleted=False)
    except Department.DoesNotExist:
        return []

    # Start with the department itself
    dept_ids = [dept_id]

    # Get all children recursively
    children = Department.objects.filter(
        parent_id=dept_id,
        is_deleted=False
    )

    for child in children:
        # Recursively get child's tree
        dept_ids.extend(get_department_tree_ids(child.id))

    return dept_ids


def apply_scope_filter(queryset: QuerySet, user, scope_result: Tuple[str, List[int]]) -> QuerySet:
    """
    Apply data scope filter to a queryset.

    Args:
        queryset: Django QuerySet to filter
        user: User instance
        scope_result: Tuple from resolve_data_scope (scope_type, custom_dept_ids)

    Returns:
        Filtered QuerySet

    Notes:
        - Assumes queryset model has 'created_by' and/or 'department' fields
        - For 'all' scope, returns queryset unchanged
        - For 'self' scope, filters by created_by=user
        - For 'dept' scope, filters by user's department
        - For 'dept_tree' scope, filters by user's department tree
        - For 'custom' scope, filters by custom department list
    """
    scope_type, custom_dept_ids = scope_result
    scope_type = normalize_scope_type(scope_type)

    # All scope - no filtering
    if scope_type == 'all':
        return queryset

    # Self scope - only user's own data
    if scope_type == 'self':
        # Try to filter by created_by if field exists
        if hasattr(queryset.model, 'created_by'):
            return queryset.filter(created_by=user)
        return queryset.none()

    # Department scope - user's department only
    if scope_type == 'dept':
        if not user.department:
            return queryset.none()
        if hasattr(queryset.model, 'department'):
            return queryset.filter(department=user.department)
        return queryset.none()

    # Department and below scope - user's department tree
    if scope_type == 'dept_tree':
        if not user.department:
            return queryset.none()
        dept_ids = get_department_tree_ids(user.department.id)
        if hasattr(queryset.model, 'department'):
            return queryset.filter(department_id__in=dept_ids)
        return queryset.none()

    # Custom scope - specific departments
    if scope_type == 'custom':
        if not custom_dept_ids:
            return queryset.none()
        if hasattr(queryset.model, 'department'):
            return queryset.filter(department_id__in=custom_dept_ids)
        return queryset.none()

    # Unknown scope type - return empty queryset
    return queryset.none()


def collect_permission_ids(selected_codes: List[str]) -> List[int]:
    """
    Collect permission IDs for a list of codes, including all descendants and ancestors.

    For each code, finds the permission and collects:
    - The node itself
    - All descendant nodes (so granting 'purchase' also grants 'purchase:orders:view' etc.)
    - All ancestor nodes (so the menu tree path is navigable)

    Special case: ['*'] returns all active permission IDs.

    Args:
        selected_codes: List of permission codes (e.g., ['purchase:orders', 'finance'])

    Returns:
        List of permission IDs (deduplicated)
    """
    if not selected_codes:
        return []

    if selected_codes == ['*']:
        return list(Permission.objects.filter(is_active=True, is_deleted=False).values_list('id', flat=True))

    permissions = list(Permission.objects.filter(is_active=True, is_deleted=False).select_related('parent'))
    permissions_by_code = {p.code: p for p in permissions}
    permissions_by_id = {p.id: p for p in permissions}
    children_by_parent = {}

    for p in permissions:
        children_by_parent.setdefault(p.parent_id, []).append(p)

    collected_ids = set()
    stack = [permissions_by_code[code] for code in selected_codes if code in permissions_by_code]

    while stack:
        perm = stack.pop()
        if perm.id in collected_ids:
            continue
        collected_ids.add(perm.id)
        if perm.parent_id and perm.parent_id in permissions_by_id:
            stack.append(permissions_by_id[perm.parent_id])
        stack.extend(children_by_parent.get(perm.id, []))

    return list(collected_ids)


def get_hidden_fields(user, module: str, resource: str) -> List[str]:
    """
    Get list of field names that should be hidden for the user.

    Args:
        user: User instance
        module: Module name (e.g., 'projects', 'sales')
        resource: Resource identifier (e.g., 'purchase_order', 'project')

    Returns:
        List of field names that should be hidden

    Notes:
        - Returns empty list for superusers
        - Checks field-level permissions for all user's roles
        - Only returns fields where user does NOT have permission
    """
    # Handle None/unauthenticated user - hide all fields
    if user is None or not user.is_authenticated:
        return []

    # Superuser sees all fields
    if user.is_superuser:
        return []

    # Get user's roles (兼容旧 role FK 和新 roles M2M)
    user_roles = get_active_user_roles(user)
    if not user_roles.exists():
        return []

    # Get all field permissions for this resource
    field_permissions = Permission.objects.filter(
        type='field',
        resource=resource,
        is_active=True,
        is_deleted=False
    )

    # Get user's field permissions from all roles
    user_field_permissions = set(
        Permission.objects.filter(
            role_permissions__role__in=user_roles,
            type='field',
            resource=resource,
            is_active=True,
            is_deleted=False
        ).values_list('field_name', flat=True)
    )

    # Fields that user does NOT have permission to see
    hidden_fields = []
    for perm in field_permissions:
        if perm.field_name and perm.field_name not in user_field_permissions:
            hidden_fields.append(perm.field_name)

    return hidden_fields

