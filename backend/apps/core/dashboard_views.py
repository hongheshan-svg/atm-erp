"""
仪表盘组件视图
Dashboard Widget Views
"""
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permission_mixin import PermissionMixin
from apps.core.permissions import IsSystemAdminOrReadOnly

from .dashboard_config import DashboardDataService, DashboardWidget, UserDashboard


class DashboardWidgetSerializer(serializers.ModelSerializer):
    """仪表盘组件序列化器"""
    widget_type_display = serializers.CharField(source='get_widget_type_display', read_only=True)
    data_source_display = serializers.CharField(source='get_data_source_display', read_only=True)
    
    class Meta:
        model = DashboardWidget
        fields = '__all__'


class UserDashboardSerializer(serializers.ModelSerializer):
    """用户仪表盘序列化器"""
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserDashboard
        fields = '__all__'


class DashboardWidgetViewSet(PermissionMixin, viewsets.ModelViewSet):
    """仪表盘组件管理

    组件可携带 data_source='custom_sql' 的自定义查询（custom_query），
    执行时能 SELECT 任意表（含用户密码哈希）。因此**编辑（增删改）**必须
    收紧到系统管理员；普通用户仅可读取/取用已有组件（IsSystemAdminOrReadOnly，
    读走 SAFE_METHODS + PermissionMixin 菜单兜底，与 DictType 等只写门槛一致）。
    """
    permission_module = 'system'
    permission_resource = 'dashboard_widget'
    permission_classes = [IsAuthenticated, IsSystemAdminOrReadOnly]
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    filterset_fields = ['widget_type', 'data_source', 'is_active']
    search_fields = ['name', 'code']
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """获取组件数据"""
        widget = self.get_object()
        
        # 使用DashboardDataService获取数据
        service = DashboardDataService(request.user)
        data = service.get_widget_data(widget)
        
        return Response({
            'widget': DashboardWidgetSerializer(widget).data,
            'data': data
        })
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """获取可用的组件列表"""
        widgets = self.get_queryset().filter(is_active=True)
        return Response(DashboardWidgetSerializer(widgets, many=True).data)

    @action(detail=False, methods=['get'])
    def widget_types(self, request):
        """获取组件类型选项"""
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in DashboardWidget.WIDGET_TYPES
        ])

    @action(detail=False, methods=['get'])
    def data_sources(self, request):
        """获取数据源选项"""
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in DashboardWidget.DATA_SOURCES
        ])


class UserDashboardViewSet(PermissionMixin, viewsets.ModelViewSet):
    """用户仪表盘配置"""
    permission_module = 'system'
    permission_resource = 'user_dashboard'
    queryset = UserDashboard.objects.all()
    serializer_class = UserDashboardSerializer
    
    def get_queryset(self):
        """只能查看自己的仪表盘配置"""
        if self.request.user.is_superuser:
            return UserDashboard.objects.all()
        return UserDashboard.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_dashboard(self, request):
        """获取当前用户的仪表盘配置"""
        dashboard, created = UserDashboard.objects.get_or_create(
            user=request.user,
            defaults={'layout': []}
        )
        
        return Response(UserDashboardSerializer(dashboard).data)
    
    @action(detail=False, methods=['post'])
    def save_layout(self, request):
        """保存用户仪表盘布局"""
        dashboard, created = UserDashboard.objects.get_or_create(
            user=request.user,
            defaults={'layout': []}
        )
        
        dashboard.layout = request.data.get('layout', [])
        dashboard.save()
        
        return Response(UserDashboardSerializer(dashboard).data)
    
    @action(detail=False, methods=['post'])
    def reset(self, request):
        """重置为默认布局"""
        try:
            dashboard = UserDashboard.objects.get(user=request.user)
            dashboard.reset_to_default()
            return Response(UserDashboardSerializer(dashboard).data)
        except UserDashboard.DoesNotExist:
            return Response({'error': '仪表盘配置不存在'}, status=status.HTTP_404_NOT_FOUND)
