"""
Serializers for accounts app.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Role, Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Department serializer."""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    manager_name = serializers.SerializerMethodField()
    
    def get_manager_name(self, obj):
        if obj.manager:
            # 中文姓名：姓在前，名在后
            if obj.manager.last_name or obj.manager.first_name:
                return f"{obj.manager.last_name}{obj.manager.first_name}"
            return obj.manager.username
        return ''
    
    class Meta:
        model = Department
        fields = [
            'id', 'code', 'name', 'parent', 'parent_name', 'manager', 'manager_name',
            'description', 'sort_order', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['code', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        import uuid
        # 自动生成部门编码
        validated_data['code'] = f"DEPT{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class RoleSerializer(serializers.ModelSerializer):
    """Role serializer."""
    user_count = serializers.SerializerMethodField()
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=None,
        source='permissions_new',
        required=False,
        allow_null=True
    )
    data_scopes = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.permission_models_new import Permission
        self.fields['permission_ids'].child_relation.queryset = Permission.active.all()

    class Meta:
        model = Role
        fields = [
            'id', 'code', 'name', 'description', 'data_scope', 'permissions',
            'permission_ids', 'data_scopes', 'is_active', 'sort_order', 'user_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_user_count(self, obj):
        return obj.users.filter(is_deleted=False, is_active=True).count()

    def get_data_scopes(self, obj):
        """返回角色的数据权限配置"""
        from apps.core.permission_models_new import DataScope
        scopes = DataScope.objects.filter(role=obj)
        return [{'module': s.module, 'scope_type': s.scope_type} for s in scopes]

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
        import uuid
        if not validated_data.get('code'):
            validated_data['code'] = f"ROLE{uuid.uuid4().hex[:6].upper()}"
        permissions_new = validated_data.pop('permissions_new', [])
        role = super().create(validated_data)
        if permissions_new:
            role.permissions_new.set(permissions_new)
        return role

    def update(self, instance, validated_data):
        permissions_new = validated_data.pop('permissions_new', None)
        role = super().update(instance, validated_data)
        if permissions_new is not None:
            role.permissions_new.set(permissions_new)
        return role



class UserSerializer(serializers.ModelSerializer):
    """User serializer for list and retrieve."""
    department_name = serializers.CharField(source='department.name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'employee_id', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'gender', 'birth_date', 'department', 'department_name',
            'role', 'role_name', 'position', 'hire_date', 'is_active', 'is_staff',
            'is_superuser', 'last_login', 'date_joined', 'created_at', 'updated_at',
            'wechat_work_id', 'dingtalk_id'
        ]
        read_only_fields = ['last_login', 'date_joined', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class UserCreateSerializer(serializers.ModelSerializer):
    """User serializer for creation."""
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'employee_id', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'gender', 'birth_date',
            'department', 'role', 'position', 'hire_date', 'is_active', 'is_staff'
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
            raise serializers.ValidationError({"password_confirm": "两次密码不一致"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        # 如果 employee_id 为空，自动生成一个
        if not validated_data.get('employee_id'):
            import uuid
            validated_data['employee_id'] = f"EMP{uuid.uuid4().hex[:8].upper()}"
        # 移除空字符串字段（但保留 employee_id）
        validated_data = {k: v for k, v in validated_data.items() if v not in [None, ''] or k == 'employee_id'}
        user = User.objects.create_user(**validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """User serializer for update."""
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'phone', 'avatar', 'gender',
            'birth_date', 'department', 'role', 'position', 'hire_date',
            'is_active', 'is_staff'
        ]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "两次密码不一致"})
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
            'id', 'username', 'employee_id', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'gender', 'birth_date', 'department', 'department_info',
            'role', 'role_info', 'roles', 'position', 'hire_date', 'is_active', 'is_staff',
            'is_superuser', 'permissions', 'menus', 'data_scopes', 'last_login'
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
        """返回用户可访问的菜单树"""
        from apps.core.permission_models_new import Permission
        from apps.core.permission_service import get_user_permissions

        if obj.is_superuser:
            menu_perms = Permission.active.filter(type='menu').order_by('sort_order')
        else:
            user_perms = get_user_permissions(obj)
            menu_perms = Permission.active.filter(type='menu', code__in=user_perms).order_by('sort_order')

        def build_tree(parent_id=None):
            nodes = []
            for perm in menu_perms.filter(parent_id=parent_id):
                node = {
                    'code': perm.code,
                    'name': perm.name,
                    'icon': perm.icon,
                    'route': perm.route_path,
                    'children': build_tree(perm.id)
                }
                nodes.append(node)
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

