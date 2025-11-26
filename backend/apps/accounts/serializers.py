"""
Serializers for accounts app.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Role, Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Department serializer."""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    
    class Meta:
        model = Department
        fields = [
            'id', 'code', 'name', 'parent', 'parent_name', 'manager', 'manager_name',
            'description', 'sort_order', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


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
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'employee_id', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone', 'gender', 'birth_date',
            'department', 'role', 'position', 'hire_date', 'is_active', 'is_staff'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "两次密码不一致"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
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

