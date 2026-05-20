"""
Unified PermissionMixin for DRF ViewSets.

Replaces 4 old mixins:
- DataPermissionMixin
- FinanceDataMixin
- OperationPermissionMixin
- SensitiveFieldMixin

Provides:
- Data scope filtering (get_queryset)
- Operation permission checking (check_permissions)
- Object-level permission with context roles (check_object_permissions)
- Sensitive field filtering (get_serializer)
"""
from rest_framework.exceptions import PermissionDenied

from apps.core.permission_service import apply_scope_filter, get_hidden_fields, has_permission, resolve_data_scope


class PermissionMixin:
    """
    Unified permission mixin for DRF ViewSets.

    Class attributes to configure:
        permission_module: Module name (e.g., 'projects', 'sales')
        permission_resource: Resource identifier (e.g., 'project', 'purchase_order')
        context_role_fields: Dict mapping context roles to model fields
                           e.g., {'owner': 'created_by', 'assignee': 'assignee'}

    Usage:
        class ProjectViewSet(PermissionMixin, viewsets.ModelViewSet):
            permission_module = 'projects'
            permission_resource = 'project'
            context_role_fields = {
                'owner': 'created_by',
                'assignee': 'assignee'
            }
    """

    # Subclasses should override these
    permission_module = None
    permission_resource = None
    context_role_fields = {}  # e.g., {'owner': 'created_by', 'assignee': 'assignee'}

    # Action to permission action mapping
    ACTION_MAP = {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
    }

    def get_queryset(self):
        """
        Apply data scope filtering to queryset.

        Returns:
            Filtered QuerySet based on user's data scope
        """
        queryset = super().get_queryset()

        # Skip filtering for unauthenticated users
        if not self.request.user.is_authenticated:
            return queryset.none()

        # Skip filtering if no module configured
        if not self.permission_module:
            return queryset

        # Resolve data scope for user
        scope_result = resolve_data_scope(self.request.user, self.permission_module)

        # Apply scope filter
        return apply_scope_filter(queryset, self.request.user, scope_result)

    def check_permissions(self, request):
        """
        Check operation-level permissions.

        Raises:
            PermissionDenied: If user doesn't have permission for the action
        """
        # Call parent check_permissions first
        super().check_permissions(request)

        # Skip if no module/resource configured
        if not self.permission_module or not self.permission_resource:
            return

        # Get permission action from DRF action
        action = getattr(self, 'action', None)
        if not action:
            return

        # Map DRF action to permission action
        permission_action = self.ACTION_MAP.get(action, action)

        # Build permission code: module:resource:action
        permission_code = f'{self.permission_module}:{self.permission_resource}:{permission_action}'

        # Check permission
        if not has_permission(request.user, permission_code):
            raise PermissionDenied(
                f'You do not have permission to {permission_action} {self.permission_resource}'
            )

    def check_object_permissions(self, request, obj):
        """
        Check object-level permissions with context role support.

        Supports context roles like @owner and @assignee.

        Args:
            request: DRF request
            obj: Model instance

        Raises:
            PermissionDenied: If user doesn't have permission for the object
        """
        # Call parent check_object_permissions first
        super().check_object_permissions(request, obj)

        # Skip if no module/resource configured
        if not self.permission_module or not self.permission_resource:
            return

        # Get permission action from DRF action
        action = getattr(self, 'action', None)
        if not action:
            return

        # Map DRF action to permission action
        permission_action = self.ACTION_MAP.get(action, action)

        # Build permission code: module:resource:action
        permission_code = f'{self.permission_module}:{self.permission_resource}:{permission_action}'

        # Check if user has general permission (without context role)
        if has_permission(request.user, permission_code):
            return

        # Check context role permissions
        # Try each configured context role
        for context_role, field_name in self.context_role_fields.items():
            # Build context permission code: module:resource:action@context_role
            context_permission_code = f'{permission_code}@{context_role}'

            # Check if user has this context role permission
            if has_permission(request.user, context_permission_code):
                # Check if user matches the context role on this object
                if hasattr(obj, field_name):
                    field_value = getattr(obj, field_name)
                    # Handle both User objects and user IDs
                    if field_value == request.user or (
                        hasattr(field_value, 'id') and field_value.id == request.user.id
                    ):
                        return  # Permission granted via context role

        # No permission found
        raise PermissionDenied(
            f'You do not have permission to {permission_action} this {self.permission_resource}'
        )

    def get_serializer(self, *args, **kwargs):
        """
        Get serializer with sensitive fields filtered.

        Returns:
            Serializer instance with hidden fields removed
        """
        serializer = super().get_serializer(*args, **kwargs)

        # Skip if no module/resource configured
        if not self.permission_module or not self.permission_resource:
            return serializer

        # Get hidden fields for user
        hidden_fields = get_hidden_fields(
            self.request.user,
            self.permission_module,
            self.permission_resource
        )

        # Remove hidden fields from serializer
        # Handle ListSerializer (when many=True)
        from rest_framework.serializers import ListSerializer
        target_serializer = serializer.child if isinstance(serializer, ListSerializer) else serializer

        for field_name in hidden_fields:
            if hasattr(target_serializer, 'fields') and field_name in target_serializer.fields:
                target_serializer.fields.pop(field_name)

        return serializer
