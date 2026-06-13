"""
Serializers for accounts app.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.core.permission_models_new import DataScope, Permission
from apps.core.permission_service import normalize_scope_type, on_role_permission_change

from .models import Department, Role, User


class RoleDataScopeConfigSerializer(serializers.Serializer):
    module = serializers.CharField(required=False, allow_blank=True, default='')
    scope_type = serializers.CharField()
    department_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        default=list,
    )


class DepartmentSerializer(serializers.ModelSerializer):
    """Department serializer."""

    parent_name = serializers.CharField(source='parent.name', read_only=True)
    manager_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    total_member_count = serializers.SerializerMethodField()

    def get_manager_name(self, obj):
        if obj.manager:
            # 中文姓名：姓在前，名在后
            if obj.manager.last_name or obj.manager.first_name:
                return f'{obj.manager.last_name}{obj.manager.first_name}'
            return obj.manager.username
        return ''

    def get_member_count(self, obj):
        """直属成员数（不含下级部门）。"""
        return obj.users.filter(is_deleted=False, is_active=True).count()

    def get_total_member_count(self, obj):
        """全部成员数（含所有下级部门），按部门树递归统计。"""
        from apps.accounts.models import User

        dept_ids = [obj.id]
        frontier = [obj.id]
        # 逐层向下收集子部门ID，避免对每个用户做查询
        while frontier:
            children = list(
                Department.objects.filter(parent_id__in=frontier, is_deleted=False).values_list('id', flat=True)
            )
            children = [cid for cid in children if cid not in dept_ids]
            if not children:
                break
            dept_ids.extend(children)
            frontier = children
        return User.objects.filter(department_id__in=dept_ids, is_deleted=False, is_active=True).count()

    class Meta:
        model = Department
        fields = [
            'id',
            'code',
            'name',
            'parent',
            'parent_name',
            'manager',
            'manager_name',
            'member_count',
            'total_member_count',
            'description',
            'sort_order',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['code', 'created_at', 'updated_at']

    def create(self, validated_data):
        import uuid

        # 自动生成部门编码
        validated_data['code'] = f'DEPT{uuid.uuid4().hex[:6].upper()}'
        return super().create(validated_data)


class RoleSerializer(serializers.ModelSerializer):
    """Role serializer."""

    user_count = serializers.SerializerMethodField()
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )
    data_scopes = RoleDataScopeConfigSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Role
        fields = [
            'id',
            'code',
            'name',
            'description',
            'permission_ids',
            'data_scopes',
            'is_active',
            'sort_order',
            'user_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_user_count(self, obj):
        return obj.users.filter(is_deleted=False, is_active=True).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['permission_ids'] = list(instance.permissions_new.values_list('id', flat=True))
        scopes = DataScope.objects.filter(role=instance).prefetch_related('custom_departments')
        data['data_scopes'] = [
            {
                'module': '' if not scope.module else scope.module,
                'scope_type': normalize_scope_type(scope.scope_type),
                'department_ids': list(scope.custom_departments.values_list('id', flat=True)),
            }
            for scope in scopes
        ]
        return data

    def validate_name(self, value):
        """检查角色名称唯一性（排除当前记录）"""
        instance = self.instance
        qs = Role.objects.filter(name=value, is_deleted=False)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('该角色名称已存在')
        return value

    def validate_code(self, value):
        """检查角色编码唯一性（排除当前记录和空值）"""
        if not value:
            return value
        instance = self.instance
        qs = Role.objects.filter(code=value, is_deleted=False)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('该角色编码已存在')
        return value

    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        data_scopes = validated_data.pop('data_scopes', [])
        import uuid

        if not validated_data.get('code'):
            validated_data['code'] = f'ROLE{uuid.uuid4().hex[:6].upper()}'
        role = super().create(validated_data)
        self._save_permissions(role, permission_ids)
        self._save_data_scopes(role, data_scopes)
        return role

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        data_scopes = validated_data.pop('data_scopes', None)
        role = super().update(instance, validated_data)

        if permission_ids is not None:
            self._save_permissions(role, permission_ids)

        if data_scopes is not None:
            self._save_data_scopes(role, data_scopes)

        return role

    def _save_permissions(self, role, permission_ids):
        if permission_ids is None:
            return

        permissions = Permission.active.filter(id__in=permission_ids)
        role.permissions_new.set(permissions)
        on_role_permission_change(role)

    def _save_data_scopes(self, role, data_scopes):
        if data_scopes is None:
            return

        scope_payloads = data_scopes or []

        existing = {scope.module: scope for scope in DataScope.objects.filter(role=role)}
        retained_modules = set()

        for scope_data in scope_payloads:
            module = scope_data.get('module', '') or ''
            scope_type = normalize_scope_type(scope_data.get('scope_type'), target='model')
            department_ids = scope_data.get('department_ids', [])

            scope, _ = DataScope.objects.update_or_create(
                role=role,
                module=module,
                defaults={'scope_type': scope_type},
            )
            retained_modules.add(module)

            departments = Department.objects.filter(id__in=department_ids, is_deleted=False)
            scope.custom_departments.set(departments)

        for module, scope in existing.items():
            if module not in retained_modules:
                scope.delete()


class UserSerializer(serializers.ModelSerializer):
    """User serializer for list and retrieve."""

    department_name = serializers.CharField(source='department.name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        """显示用姓名：中文姓在前名在后，缺省回退 username。"""
        if obj.last_name or obj.first_name:
            return f'{obj.last_name}{obj.first_name}'
        return obj.username

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'employee_id',
            'email',
            'first_name',
            'last_name',
            'display_name',
            'phone',
            'avatar',
            'gender',
            'birth_date',
            'department',
            'department_name',
            'role',
            'role_name',
            'position',
            'hire_date',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'date_joined',
            'created_at',
            'updated_at',
            'wechat_work_id',
            'dingtalk_id',
        ]
        read_only_fields = ['last_login', 'date_joined', 'created_at', 'updated_at']
        extra_kwargs = {'password': {'write_only': True}}


def _guard_privileged_role_assignment(request, role):
    """非系统管理员不得为用户分配「特权角色」(授予 system 模块权限的角色)。

    防止持 accounts:user(system:user)的 HR 通过建/改用户把自己或他人的 role 设为 admin 提权。
    （审计 C1 补强 —— 提交后对抗式复核发现的提权路径）
    """
    if role is None:
        return
    from apps.core.permissions import _is_system_admin

    user = getattr(request, 'user', None) if request is not None else None
    if _is_system_admin(user):
        return

    from django.db.models import Q

    from apps.core.permission_models_new import RolePermission

    is_privileged = RolePermission.objects.filter(
        Q(permission__code='system') | Q(permission__code__startswith='system:'),
        role=role,
        permission__is_active=True,
    ).exists()
    if is_privileged:
        raise serializers.ValidationError({'role': '无权分配该角色:仅系统管理员可分配具有系统管理权限的角色'})


class UserCreateSerializer(serializers.ModelSerializer):
    """User serializer for creation."""

    password = serializers.CharField(write_only=True, required=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username',
            'employee_id',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'phone',
            'gender',
            'birth_date',
            'department',
            'role',
            'position',
            'hire_date',
            'is_active',
            'is_staff',
        ]
        extra_kwargs = {
            'employee_id': {'required': False, 'allow_blank': True},
            'email': {'required': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'phone': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': '两次密码不一致'})
        _guard_privileged_role_assignment(self.context.get('request'), attrs.get('role'))
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        # 如果 employee_id 为空，自动生成一个
        if not validated_data.get('employee_id'):
            import uuid

            validated_data['employee_id'] = f'EMP{uuid.uuid4().hex[:8].upper()}'
        # 移除空字符串字段（但保留 employee_id）
        validated_data = {k: v for k, v in validated_data.items() if v not in [None, ''] or k == 'employee_id'}
        user = User.objects.create_user(**validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """User serializer for update（管理端：HR/管理员经 UserViewSet 改用户）。"""

    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'phone',
            'avatar',
            'gender',
            'birth_date',
            'department',
            'role',
            'position',
            'hire_date',
            'is_active',
            'is_staff',
        ]

    def validate(self, attrs):
        _guard_privileged_role_assignment(self.context.get('request'), attrs.get('role'))
        return attrs


class ProfileSelfUpdateSerializer(serializers.ModelSerializer):
    """用户自助更新个人资料 —— 仅本人可编辑的非权限字段。

    刻意不含 role/is_staff/is_active/department/position/hire_date 等管理字段:
    update_profile 是 SELF_ACTION(仅需登录),若用含 role/is_staff 的 UserUpdateSerializer,
    任意登录用户即可 PUT /users/update_profile/ 自赋 admin 角色或 is_staff 提权。
    （审计 C1 补强 —— 提交后对抗式复核发现的提权路径）
    """

    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'phone',
            'avatar',
            'gender',
            'birth_date',
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({'new_password': '两次密码不一致'})
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """User profile serializer with additional info."""

    department_info = DepartmentSerializer(source='department', read_only=True)
    role_info = RoleSerializer(source='role', read_only=True)
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    menus = serializers.SerializerMethodField()
    data_scopes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'employee_id',
            'email',
            'first_name',
            'last_name',
            'phone',
            'avatar',
            'gender',
            'birth_date',
            'department',
            'department_info',
            'role',
            'role_info',
            'roles',
            'position',
            'hire_date',
            'is_active',
            'is_staff',
            'is_superuser',
            'permissions',
            'menus',
            'data_scopes',
            'last_login',
        ]

    def get_roles(self, obj):
        """返回用户的所有角色代码"""
        return list(obj.roles.filter(is_active=True).values_list('code', flat=True))

    def get_permissions(self, obj):
        """返回用户的所有权限代码"""
        from apps.core.permission_service import get_user_permissions

        if obj.is_superuser:
            return ['*']
        return list(get_user_permissions(obj))

    def get_menus(self, obj):
        """返回用户可访问的菜单树（支持三级分组）"""
        from django.db.models import Q

        from apps.core.permission_models_new import Permission
        from apps.core.permission_service import get_user_permissions

        if obj.is_superuser:
            all_menus = list(Permission.active.filter(type='menu').order_by('sort_order'))
        else:
            user_perms = get_user_permissions(obj)
            user_menus = Permission.active.filter(type='menu', code__in=user_perms)
            # 自动补全祖先节点(分组容器、一级菜单)，保证树结构完整
            parent_ids = set(user_menus.exclude(parent_id=None).values_list('parent_id', flat=True))
            grandparent_ids = set(
                Permission.active.filter(id__in=parent_ids, parent_id__isnull=False).values_list('parent_id', flat=True)
            )
            ancestor_ids = parent_ids | grandparent_ids
            all_menus = list(
                Permission.active.filter(type='menu')
                .filter(Q(code__in=user_perms) | Q(id__in=ancestor_ids))
                .order_by('sort_order')
            )

        # 按 parent_id 分组，内存中构建树（单次查询）
        children_map = {}
        for menu in all_menus:
            children_map.setdefault(menu.parent_id, []).append(menu)

        def build_tree(parent_id=None):
            nodes = []
            for perm in children_map.get(parent_id, []):
                children = build_tree(perm.id)
                # 跳过没有可见子项的空分组容器
                if not perm.route_path and not children:
                    continue
                nodes.append(
                    {
                        'code': perm.code,
                        'name': perm.name,
                        'icon': perm.icon,
                        'route': perm.route_path,
                        'children': children,
                    }
                )
            return nodes

        return build_tree()

    def get_data_scopes(self, obj):
        """返回用户的数据权限范围"""
        from apps.core.permission_service import resolve_data_scope

        if obj.is_superuser:
            return {'': 'all'}

        scopes = {}
        modules = ['', 'finance', 'purchase', 'projects', 'sales']
        for module in modules:
            scope_type, _ = resolve_data_scope(obj, module)
            scopes[module] = scope_type

        return scopes
