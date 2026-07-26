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

from apps.core.permission_service import (
    apply_scope_filter,
    get_defined_operations,
    get_hidden_fields,
    get_user_menu_permissions,
    has_exact_permission,
    has_operation_permission,
    has_permission,
    resolve_data_scope,
)

# 后端 permission_module 到前端菜单权限码的映射。
# 当用户持有右侧任一菜单前缀（精确相等或 `prefix:` 开头）时，_has_module_menu_access
# 即认为其有权访问左侧后端模块——这是“菜单级粒度”兜底授权。
#
# 操作级细粒度（审计 C2 整改）：check_permissions 先调用
# permission_service.has_operation_permission。只要某 resource 已定义 CRUD 操作节点，
# 缺少具体授权就拒绝；完全没有定义操作节点的历史资源才回落到菜单授权。自定义 action
# 优先使用独立操作节点，否则按 HTTP 方法映射到 view/edit/delete。字段级脱敏同理由
# get_serializer + get_hidden_fields 在种子化字段权限后生效。
#
# 安全注意（审计 C1）：'accounts' 故意只映射到具体的用户/角色/部门菜单码，而不是宽泛的
# 'system'。否则任何持有 'system:report' 的角色（几乎所有 manager 都有）都会因前缀
# 'system' 命中而获得增删用户/角色/部门的权限。同理，'system' 模块上挂着的敏感 RBAC/
# 配置 ViewSet（Permission/DataScope/CodeRule/Webhook/EmailLog/AuditLog 等）已各自用
# apps.core.permissions.IsSystemAdmin[OrReadOnly] 加了独立硬门槛，使得此处的菜单兜底
# 无法再越权写入它们——'system' 仍保留 'oa' 仅为放行同模块下的 OA 协同类 ViewSet
# （公告/日程/会议/会话），它们对 OA 用户本就应可读写。
MODULE_MENU_MAP = {
    'purchase': ['supply', 'purchase'],
    'inventory': ['supply', 'inventory'],
    'projects': ['projects', 'design', 'plm', 'knowledge'],
    'sales': ['sales'],
    'finance': ['finance'],
    'production': ['manufacturing', 'production', 'mes', 'equipment'],
    'accounts': ['system:user', 'system:role', 'system:department'],
    'system': ['system', 'oa'],
    'masterdata': ['supply', 'sales', 'masterdata'],
    'oa': ['oa'],
    'reports': ['system:report', 'reports', 'analytics'],
    'core': ['system'],
}


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

    # Set to True on reference-data ViewSets (customers, users, suppliers, items, etc.)
    # to allow any authenticated user to list/retrieve without module-level permission.
    allow_authenticated_read = False

    # Set True on ViewSets whose row visibility is governed by their own get_queryset
    # 或 per-action 受众过滤（OA 协同：公告/日程/会议/会话）。通用的按用户数据范围过滤
    # （尤其 'self' = created_by=user）会把公开/共享/被邀请的数据从常见角色视图中错误隐藏，
    # 故在这些 ViewSet 上跳过它，让其自身可见性逻辑权威生效。（审计 H13）
    skip_data_scope = False

    # Model field identifying row ownership for the 'self' data scope (default
    # 'created_by'). Set to 'user' on ViewSets whose rows belong to a user via a
    # 不同字段 —— 如考勤/请假/加班：created_by 是导入它的管理员，而非本人。（审计 H14）
    data_scope_user_field = 'created_by'

    # Sensitive cross-module endpoints can declare the exact menu entries that
    # grant access instead of inheriting every menu in permission_module.
    permission_menu_codes = None

    # Action to permission action mapping
    ACTION_MAP = {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
    }
    CUSTOM_METHOD_ACTION_MAP = {
        'GET': 'view',
        'HEAD': 'view',
        'OPTIONS': 'view',
        'POST': 'edit',
        'PUT': 'edit',
        'PATCH': 'edit',
        'DELETE': 'delete',
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

        # A PermissionMixin without a complete contract is a programming error.
        # Return no rows defensively even if get_queryset is called outside DRF's
        # normal check_permissions -> handler sequence.
        if not self.permission_module or not self.permission_resource:
            return queryset.none()

        # Skip the generic data-scope filter when the ViewSet manages its own row
        # visibility（OA 协同：公告/日程/会议/会话）。否则 'self' 范围的 created_by=user
        # 过滤会把公开/共享/被邀请的数据从常见角色视图中错误隐藏。（审计 H13）
        if self.skip_data_scope:
            return queryset

        # Resolve data scope for user
        scope_result = resolve_data_scope(self.request.user, self.permission_module)

        # Apply scope filter
        return apply_scope_filter(queryset, self.request.user, scope_result, user_field=self.data_scope_user_field)

    def _has_module_menu_access(self, request):
        """
        Check if the user has menu-level access to this ViewSet's module.

        Bridges the gap between the menu permission tree (2-level codes like
        'supply', 'supply:order') and ViewSet permission_codes (3-level like
        'inventory:material_requisition:view'). When a user holds a menu code
        that maps to this module, they are considered authorized for any
        operation on its resources — operation-level granularity is not
        modeled in the permission tree.
        """
        user_perms = get_user_menu_permissions(request.user)
        if self.permission_menu_codes:
            return any(
                granted == required or required.startswith(granted + ':')
                for required in self.permission_menu_codes
                for granted in user_perms
            )

        menu_prefixes = MODULE_MENU_MAP.get(self.permission_module, [])
        if not menu_prefixes:
            return False
        for prefix in menu_prefixes:
            if any(p == prefix or p.startswith(prefix + ':') for p in user_perms):
                return True
        return False

    def _get_context_grants(self, request, permission_code):
        return {
            context_role
            for context_role in self.context_role_fields
            if has_exact_permission(request.user, f'{permission_code}@{context_role}')
        }

    def _is_detail_action(self):
        action = getattr(self, 'action', None)
        return bool(getattr(self, 'detail', False) or action in {'retrieve', 'update', 'partial_update', 'destroy'})

    def _resolve_permission_action(self, request, action):
        if action in self.ACTION_MAP:
            return self.ACTION_MAP[action]

        # A separately defined custom permission (approve/export/etc.) is more
        # specific and takes precedence. Otherwise custom actions inherit a safe
        # CRUD category so POST side effects cannot bypass a configured edit
        # restriction merely by using a different action name.
        if action in get_defined_operations(self.permission_module, self.permission_resource):
            return action
        return self.CUSTOM_METHOD_ACTION_MAP.get(request.method.upper(), action)

    def check_permissions(self, request):
        """
        Check operation-level permissions.

        Raises:
            PermissionDenied: If user doesn't have permission for the action
        """
        # Call parent check_permissions first
        super().check_permissions(request)

        # Fail closed if a ViewSet opted into PermissionMixin but forgot its
        # authorization contract.
        if not self.permission_module or not self.permission_resource:
            raise PermissionDenied('Permission configuration is incomplete')

        # Get permission action from DRF action
        action = getattr(self, 'action', None)
        if not action:
            return

        # Map DRF action to permission action
        permission_action = self._resolve_permission_action(request, action)

        # Allow any authenticated user to read reference data
        # For standard list/retrieve actions, permission_action is 'view'.
        # Custom actions use a dedicated operation when one exists; otherwise
        # _resolve_permission_action maps their HTTP method to a CRUD category.
        if (
            self.allow_authenticated_read
            and request.user
            and request.user.is_authenticated
            and action in {'list', 'retrieve'}
        ):
            return

        permission_code = f'{self.permission_module}:{self.permission_resource}:{permission_action}'
        context_grants = self._get_context_grants(request, permission_code)

        # Operation-level enforcement is opt-in per resource definition.
        #
        # has_operation_permission is tri-state:
        #   False -> operation policy is defined but this concrete grant is absent.
        #   True  -> the action is explicitly granted -> allow.
        #   None  -> no operation policy is defined for this resource/action; use
        #            legacy menu-level authorization.
        op_result = has_operation_permission(
            request.user, self.permission_module, self.permission_resource, permission_action
        )
        if op_result is False:
            if context_grants and self._is_detail_action():
                return
            raise PermissionDenied(f'You do not have permission to {permission_action} {self.permission_resource}')
        if op_result is True:
            return

        # Check permission
        if has_permission(request.user, permission_code):
            return

        # Fallback: menu-level access to this module grants full access to its
        # resources. This is the default grant path for roles without operation-level
        # permissions configured (op_result is None above).
        if self._has_module_menu_access(request):
            return

        if context_grants and self._is_detail_action():
            return

        raise PermissionDenied(f'You do not have permission to {permission_action} {self.permission_resource}')

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
        permission_action = self._resolve_permission_action(request, action)

        if self.allow_authenticated_read and request.user and request.user.is_authenticated and action == 'retrieve':
            return

        # Build permission code: module:resource:action
        permission_code = f'{self.permission_module}:{self.permission_resource}:{permission_action}'

        op_result = has_operation_permission(
            request.user, self.permission_module, self.permission_resource, permission_action
        )

        # A concrete operation grant is object-wide. Parent menu inheritance is
        # considered only when operation policy is not configured.
        if op_result is True or has_exact_permission(request.user, permission_code):
            return

        if op_result is None:
            if has_permission(request.user, permission_code):
                return
            if self._has_module_menu_access(request):
                return

        # Check context role permissions
        # Try each configured context role
        for context_role, field_name in self.context_role_fields.items():
            # Build context permission code: module:resource:action@context_role
            context_permission_code = f'{permission_code}@{context_role}'

            # Check if user has this context role permission
            if has_exact_permission(request.user, context_permission_code):
                # Check if user matches the context role on this object
                if hasattr(obj, field_name):
                    field_value = getattr(obj, field_name)
                    # Handle both User objects and user IDs
                    if field_value == request.user or (
                        hasattr(field_value, 'id') and field_value.id == request.user.id
                    ):
                        return  # Permission granted via context role

        # No permission found
        raise PermissionDenied(f'You do not have permission to {permission_action} this {self.permission_resource}')

    def get_serializer(self, *args, **kwargs):
        """
        Get serializer with sensitive fields filtered.

        Returns:
            Serializer instance with hidden (de-sensitized) fields removed

        字段级脱敏（审计 C2 整改）：
            get_hidden_fields 返回“该用户角色被拒绝可见”的字段名集合（即 module:resource
            已种子化 type='field' 权限、但用户角色未被授予者），本方法据此从序列化器中剔除
            这些字段。向后兼容：若某 resource 未种子化任何字段权限，get_hidden_fields 返回空，
            不剔除任何字段——与历史行为一致。init_permissions 负责种子化敏感字段（成本/价格/
            信用额度等）并授予有权查看的角色；从角色移除某字段权限即对其屏蔽该字段。
        """
        serializer = super().get_serializer(*args, **kwargs)

        # Skip if no module/resource configured
        if not self.permission_module or not self.permission_resource:
            return serializer

        # Get hidden fields for user
        hidden_fields = get_hidden_fields(self.request.user, self.permission_module, self.permission_resource)

        # Remove hidden fields from serializer
        # Handle ListSerializer (when many=True)
        from rest_framework.serializers import ListSerializer

        target_serializer = serializer.child if isinstance(serializer, ListSerializer) else serializer

        for field_name in hidden_fields:
            if hasattr(target_serializer, 'fields') and field_name in target_serializer.fields:
                target_serializer.fields.pop(field_name)

        return serializer
