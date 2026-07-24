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

# The CRUD actions that operation-level enforcement understands. Only these are
# ever restricted by has_operation_permission; any other (custom @action) verb is
# left to the existing menu-level fallback so bespoke endpoints never regress.
STANDARD_OPERATION_ACTIONS = ('view', 'create', 'edit', 'delete')


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


def get_configured_operations(user, module: str, resource: str) -> Set[str]:
    """
    Return the subset of STANDARD_OPERATION_ACTIONS that the user's roles explicitly
    hold as operation-level permissions for ``{module}:{resource}``.

    Reads only from the cached permission-code set (get_user_permissions), so it adds
    no database queries beyond the already-cached lookup.

    A non-empty result means operation-level control is *configured* for this
    (user, resource): the caller should enforce it. An empty result means no
    operation permissions are seeded/assigned for this resource, which is the
    historical default and signals "fall back to menu-level access".
    """
    if user is None or not user.is_authenticated:
        return set()
    perms = get_user_permissions(user)
    prefix = f'{module}:{resource}:'
    return {action for action in STANDARD_OPERATION_ACTIONS if prefix + action in perms}


def has_operation_permission(user, module: str, resource: str, action: str):
    """
    Opt-in, additive operation-level permission check.

    This is a tri-state helper that layers a *restriction* on top of the existing
    menu-level authorization WITHOUT ever granting access the menu check wouldn't:

    Returns:
        True  -> the user's roles explicitly hold ``{module}:{resource}:{action}``
                 (operation is allowed).
        False -> operation-level control IS configured for this resource (the roles
                 hold at least one CRUD operation permission for it) but NOT this
                 specific action -> an explicit restriction is in force; the caller
                 MUST deny even if menu-level access would otherwise allow.
        None  -> no operation-level control is configured for this (user, resource),
                 OR the action is not a standard CRUD verb, OR the user is anonymous.
                 The caller falls back to the existing menu-level checks. This is the
                 backward-compatible default: menu-only roles keep full CRUD.

    Superusers always return True.

    Enforcement is opt-in *per resource*: it only bites once a role has been given
    operation permissions for that exact resource and then had a specific action
    removed. init_permissions seeds these permissions and grants the full CRUD set
    to every role that already has menu access, so out-of-the-box behavior is
    unchanged; removing one action from a role is what activates a restriction.
    """
    if user is None or not user.is_authenticated:
        return None
    if user.is_superuser:
        return True
    if action not in STANDARD_OPERATION_ACTIONS:
        return None

    configured = get_configured_operations(user, module, resource)
    if not configured:
        return None
    return action in configured


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
    无角色 / 无 DataScope 配置时默认返回 'self'（fail-closed：最小可见，避免未配置数据范围
    导致越权过度暴露；超管恒为 'all'）。标准角色经 init_roles 均有显式 DataScope，不受影响。（审计 H13 相关）

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
        result = ('self', [])
        cache.set(cache_key, result, PERMISSION_CACHE_TIMEOUT)
        return result

    scopes = DataScope.objects.filter(
        role__in=user_roles,
        module__in=[module, '']
    )

    if not scopes.exists():
        result = ('self', [])
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


def apply_scope_filter(
    queryset: QuerySet, user, scope_result: Tuple[str, List[int]], user_field: str = 'created_by'
) -> QuerySet:
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

    # Self scope - only user's own data. 归属字段可配置（默认 'created_by'）：
    # 考勤/请假/加班等模型的归属是 `user`，而 created_by 是导入它的管理员而非本人。（审计 H14）
    if scope_type == 'self':
        if hasattr(queryset.model, user_field):
            return queryset.filter(**{user_field: user})
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
    Collect permission IDs for a list of codes, including all descendants.

    For each selected code, collects:
    - The node itself
    - All descendant nodes (so granting 'sales' also grants 'sales:order' etc.)

    Ancestors are intentionally NOT collected. The frontend permission check
    (usePermissionStore.hasPermission) matches hierarchically — having an ancestor
    code grants every route beneath it — so injecting ancestors here would let a
    role granted a single leaf (e.g. 'sales:lead') reach all sibling routes
    ('sales:order', 'sales:contract', ...). Parent menu containers needed only for
    sidebar rendering are completed separately by UserSerializer.get_menus.

    Special case: ['*'] returns all active permission IDs.

    Args:
        selected_codes: List of permission codes (e.g., ['supply:order', 'finance'])

    Returns:
        List of permission IDs (deduplicated)
    """
    if not selected_codes:
        return []

    if selected_codes == ['*']:
        return list(Permission.objects.filter(is_active=True, is_deleted=False).values_list('id', flat=True))

    permissions = list(Permission.objects.filter(is_active=True, is_deleted=False))
    permissions_by_code = {p.code: p for p in permissions}
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
        stack.extend(children_by_parent.get(perm.id, []))

    return list(collected_ids)


def get_hidden_fields(user, module: str, resource: str) -> List[str]:
    """
    Return the field names that must be masked from this user for ``module:resource``.

    A field is hidden when a field-level Permission (``type='field'``) is seeded for
    this ``module:resource`` but NONE of the user's active roles hold it. This is the
    field-level de-sensitization enforcement point consumed by
    ``PermissionMixin.get_serializer`` (which drops the field from the serializer).

    Args:
        user: User instance
        module: Module name (e.g., 'masterdata', 'inventory')
        resource: Resource identifier (e.g., 'item', 'stock_move')

    Returns:
        List of field names to hide (empty means "show everything").

    Backward compatibility:
        - Superusers and anonymous users -> [] (superuser sees all; anonymous is
          denied earlier by the auth layer).
        - If NO field permissions are seeded for this ``module:resource``, returns []
          (no masking) — identical to the historical behavior. Field-level masking is
          therefore inert until init_permissions seeds field permissions and grants
          them to the roles allowed to see the field; removing a field permission from
          a role is what masks that field for the role's users.

    Field permissions are matched by code prefix ``{module}:{resource}:`` so that
    identically named resources in different modules do not cross-contaminate.
    """
    # Handle None/unauthenticated user
    if user is None or not user.is_authenticated:
        return []

    # Superuser sees all fields
    if user.is_superuser:
        return []

    prefix = f'{module}:{resource}:'

    # All field-level permissions seeded for this module:resource
    defined_field_names = {
        f
        for f in Permission.objects.filter(
            type='field', is_active=True, is_deleted=False, code__startswith=prefix
        ).values_list('field_name', flat=True)
        if f
    }

    # Backward compat: nothing configured -> no masking (current behavior)
    if not defined_field_names:
        return []

    # Field permissions actually granted to the user's roles
    user_roles = get_active_user_roles(user)
    granted_field_names = set()
    if user_roles.exists():
        granted_field_names = set(
            Permission.objects.filter(
                role_permissions__role__in=user_roles,
                type='field',
                is_active=True,
                is_deleted=False,
                code__startswith=prefix,
            ).values_list('field_name', flat=True)
        )

    # Hide every configured field the user's roles were NOT granted
    return [f for f in defined_field_names if f not in granted_field_names]

