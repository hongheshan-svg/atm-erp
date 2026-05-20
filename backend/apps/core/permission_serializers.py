"""
权限系统序列化器
"""
from rest_framework import serializers

from apps.accounts.models import Department
from apps.core.permission_models_new import DataScope, Permission


class PermissionSerializer(serializers.ModelSerializer):
    """权限节点序列化器（支持树形结构）"""
    children = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = [
            'id', 'parent', 'code', 'name', 'type', 'resource',
            'field_name', 'route_path', 'icon', 'sort_order',
            'is_active', 'children', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_children(self, obj):
        """递归获取子节点"""
        if hasattr(obj, '_children'):
            return PermissionSerializer(obj._children, many=True).data
        return []


class PermissionTreeSerializer(serializers.ModelSerializer):
    """权限树序列化器（仅用于树形展示）"""
    children = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ['id', 'code', 'name', 'type', 'icon', 'sort_order', 'is_active', 'children']

    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False).order_by('sort_order')
        return PermissionTreeSerializer(children, many=True).data


class DataScopeSerializer(serializers.ModelSerializer):
    """数据权限序列化器"""
    custom_department_ids = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_deleted=False),
        many=True,
        source='custom_departments',
        required=False
    )

    class Meta:
        model = DataScope
        fields = ['id', 'role', 'module', 'scope_type', 'custom_department_ids', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
