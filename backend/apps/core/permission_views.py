"""
权限系统视图
"""

from copy import deepcopy

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from apps.core.permission_models_new import DataScope, Permission
from apps.core.permission_serializers import DataScopeSerializer, PermissionSerializer


class PermissionViewSet(viewsets.ModelViewSet):
    """权限节点管理（仅超级管理员）"""

    queryset = Permission.active.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['type', 'parent', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order']

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取权限树"""
        permissions = list(Permission.active.all().order_by('sort_order', 'id'))
        nodes_by_code = {
            perm.code: {
                'id': perm.id,
                'code': perm.code,
                'name': perm.name,
                'type': self._normalize_permission_type(perm.type),
                'icon': perm.icon,
                'sort_order': perm.sort_order,
                'is_active': perm.is_active,
                'children': [],
            }
            for perm in permissions
        }

        attached_codes = set()
        for perm in permissions:
            parent_code = self._resolve_parent_code(perm, nodes_by_code)
            if not parent_code:
                continue
            nodes_by_code[parent_code]['children'].append(nodes_by_code[perm.code])
            attached_codes.add(perm.code)

        roots = [deepcopy(nodes_by_code[perm.code]) for perm in permissions if perm.code not in attached_codes]

        self._sort_tree(roots)
        return Response(roots)

    @staticmethod
    def _normalize_permission_type(permission_type):
        if permission_type == 'action':
            return 'operation'
        return permission_type

    @staticmethod
    def _resolve_parent_code(permission, nodes_by_code):
        if permission.parent and permission.parent.code in nodes_by_code:
            return permission.parent.code

        parts = permission.code.split(':')
        for index in range(len(parts) - 1, 0, -1):
            candidate = ':'.join(parts[:index])
            if candidate in nodes_by_code:
                return candidate
        return None

    def _sort_tree(self, nodes):
        nodes.sort(key=self._node_sort_key)
        for node in nodes:
            self._sort_tree(node['children'])

    @staticmethod
    def _node_sort_key(node):
        type_weight = {'menu': 0, 'operation': 1, 'field': 2}
        return (node['sort_order'], type_weight.get(node['type'], 9), node['name'], node['id'])


class DataScopeViewSet(viewsets.ModelViewSet):
    """数据权限管理"""

    queryset = DataScope.objects.all()
    serializer_class = DataScopeSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['role', 'module', 'scope_type']
