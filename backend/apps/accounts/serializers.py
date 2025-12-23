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
    
    class Meta:
        model = Role
        fields = [
            'id', 'code', 'name', 'description', 'data_scope', 'permissions',
            'is_active', 'sort_order', 'user_count', 'is_deleted',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_user_count(self, obj):
        return obj.users.filter(is_deleted=False, is_active=True).count()
    
    def create(self, validated_data):
        import uuid
        # 如果没有提供code，自动生成角色编码
        if not validated_data.get('code'):
            validated_data['code'] = f"ROLE{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


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
            'is_superuser', 'last_login', 'date_joined', 'created_at', 'updated_at'
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
    permissions = serializers.SerializerMethodField()
    menu_ids = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'employee_id', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'gender', 'birth_date', 'department', 'department_info',
            'role', 'role_info', 'position', 'hire_date', 'is_active', 'is_staff',
            'is_superuser', 'permissions', 'menu_ids', 'last_login'
        ]
    
    def get_permissions(self, obj):
        if obj.is_superuser:
            return ['*:*:*']  # Superuser has all permissions
        if obj.role and obj.role.is_active:
            return obj.role.permissions.get('permissions', [])
        return []
    
    def get_menu_ids(self, obj):
        if obj.is_superuser:
            return []  # Empty means all menus
        if obj.role and obj.role.is_active:
            return obj.role.permissions.get('menu_ids', [])
        return []

