"""
Permission service functions for checking user permissions.

Provides caching and wildcard support for permission checks.
"""
from typing import Set
from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.core.permission_models_new import Permission, RolePermission

User = get_user_model()

# Cache timeout in seconds (5 minutes)
PERMISSION_CACHE_TIMEOUT = 300


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
