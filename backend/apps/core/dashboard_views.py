"""
仪表盘组件视图
Dashboard Widget Views
"""

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permission_mixin import PermissionMixin

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
    """仪表盘组件管理"""

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

        return Response({'widget': DashboardWidgetSerializer(widget).data, 'data': data})

    @action(detail=False, methods=['get'])
    def available(self, request):
        """获取可用的组件列表"""
        widgets = self.get_queryset().filter(is_active=True)
        return Response(DashboardWidgetSerializer(widgets, many=True).data)


class UserDashboardViewSet(PermissionMixin, viewsets.ModelViewSet):
    """用户仪表盘配置"""

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
        dashboard, created = UserDashboard.objects.get_or_create(user=request.user, defaults={'layout': []})

        return Response(UserDashboardSerializer(dashboard).data)

    @action(detail=False, methods=['post'])
    def save_layout(self, request):
        """保存用户仪表盘布局"""
        dashboard, created = UserDashboard.objects.get_or_create(user=request.user, defaults={'layout': []})

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
