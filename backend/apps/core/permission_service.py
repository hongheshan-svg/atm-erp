"""
Permission service functions for checking user permissions.

Provides caching and wildcard support for permission checks.
"""
from typing import Set, Tuple, List
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from apps.core.permission_models_new import Permission, RolePermission, DataScope
from apps.accounts.models import Department

User = get_user_model()

# Cache timeout in seconds (5 minutes)
PERMISSION_CACHE_TIMEOUT = 300

# Scope priority for determining widest scope
SCOPE_PRIORITY = {
    'global': 5,
    'custom': 4,
    'department_and_below': 4,
    'department': 3,
    'self': 2,
}


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
    elif user.role and user.role.is_active and not user.role.is_deleted:
        # Get permissions from user's role
        permissions = set(
            Permission.objects.filter(
                role_permissions__role=user.role,
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


def on_role_permission_change(role):
    """
    Invalidate permission cache when role permissions change.

    Call this function after adding/removing permissions from a role.

    Args:
        role: Role instance whose permissions changed
    """
    # Get all users with this role
    user_ids = role.users.filter(is_deleted=False).values_list('id', flat=True)

    # Clear cache for all affected users
    for user_id in user_ids:
        cache_key = f'user_permissions:{user_id}'
        cache.delete(cache_key)


def on_user_role_change(user):
    """
    Invalidate permission cache when user's role changes.

    Call this function after changing a user's role.

    Args:
        user: User instance whose role changed
    """
    cache_key = f'user_permissions:{user.id}'
    cache.delete(cache_key)


def resolve_data_scope(user, module: str) -> Tuple[str, List[int]]:
    """
    Resolve data scope for a user in a specific module.

    Returns the widest scope type and custom department IDs if applicable.

    Args:
        user: User instance
        module: Module name (e.g., 'projects', 'sales', 'purchase')

    Returns:
        Tuple of (scope_type, custom_dept_ids)
        - scope_type: One of 'global', 'department_and_below', 'department', 'self', 'custom'
        - custom_dept_ids: List of department IDs (only for 'custom' scope)

    Notes:
        - Checks module-specific scope first, then falls back to '__default__' scope
        - If user has multiple roles (future M2M support), takes the widest scope
        - If no scope configured, defaults to 'self'
        - Custom scope collects all department IDs from all roles
    """
    # Handle None/unauthenticated user
    if user is None or not user.is_authenticated:
        return ('self', [])

    # Superuser gets global scope
    if user.is_superuser:
        return ('global', [])

    # Get user's role (currently FK, will be M2M in future)
    if not user.role or not user.role.is_active or user.role.is_deleted:
        return ('self', [])

    # Try to get module-specific scope first
    data_scope = DataScope.objects.filter(
        role=user.role,
        module=module
    ).first()

    # Fall back to default scope if no module-specific scope
    if not data_scope:
        data_scope = DataScope.objects.filter(
            role=user.role,
            module='__default__'
        ).first()

    # If still no scope, default to 'self'
    if not data_scope:
        return ('self', [])

    scope_type = data_scope.scope_type
    custom_dept_ids = []

    # Collect custom department IDs if scope is custom
    if scope_type == 'custom':
        custom_dept_ids = list(
            data_scope.departments.filter(
                is_deleted=False
            ).values_list('id', flat=True)
        )

    return (scope_type, custom_dept_ids)


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
        - For 'global' scope, returns queryset unchanged
        - For 'self' scope, filters by created_by=user
        - For 'department' scope, filters by user's department
        - For 'department_and_below' scope, filters by user's department tree
        - For 'custom' scope, filters by custom department list
    """
    scope_type, custom_dept_ids = scope_result

    # Global scope - no filtering
    if scope_type == 'global':
        return queryset

    # Self scope - only user's own data
    if scope_type == 'self':
        # Try to filter by created_by if field exists
        if hasattr(queryset.model, 'created_by'):
            return queryset.filter(created_by=user)
        return queryset.none()

    # Department scope - user's department only
    if scope_type == 'department':
        if not user.department:
            return queryset.none()
        if hasattr(queryset.model, 'department'):
            return queryset.filter(department=user.department)
        return queryset.none()

    # Department and below scope - user's department tree
    if scope_type == 'department_and_below':
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
        - Checks field-level permissions for the user's role
        - Only returns fields where user does NOT have permission
    """
    # Handle None/unauthenticated user - hide all fields
    if user is None or not user.is_authenticated:
        return []

    # Superuser sees all fields
    if user.is_superuser:
        return []

    # Get user's role
    if not user.role or not user.role.is_active or user.role.is_deleted:
        return []

    # Get all field permissions for this resource
    field_permissions = Permission.objects.filter(
        type='field',
        resource=resource,
        is_active=True,
        is_deleted=False
    )

    # Get user's field permissions
    user_field_permissions = set(
        Permission.objects.filter(
            role_permissions__role=user.role,
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

