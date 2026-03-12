"""
权限系统视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from apps.core.permission_models_new import Permission, DataScope
from apps.core.permission_serializers import (
    PermissionSerializer,
    PermissionTreeSerializer,
    DataScopeSerializer
)


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
        roots = Permission.active.filter(parent__isnull=True).order_by('sort_order')
        serializer = PermissionTreeSerializer(roots, many=True)
        return Response(serializer.data)


class DataScopeViewSet(viewsets.ModelViewSet):
    """数据权限管理"""
    queryset = DataScope.objects.all()
    serializer_class = DataScopeSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['role', 'module', 'scope_type']
