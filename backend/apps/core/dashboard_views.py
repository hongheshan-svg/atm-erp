"""
Dashboard configuration views for customizable widgets.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import serializers
from .dashboard_config import DashboardWidget, UserDashboard, DashboardDataService


class DashboardWidgetSerializer(serializers.ModelSerializer):
    """Serializer for dashboard widgets."""
    widget_type_display = serializers.CharField(source='get_widget_type_display', read_only=True)
    data_source_display = serializers.CharField(source='get_data_source_display', read_only=True)
    
    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'name', 'code', 'widget_type', 'widget_type_display',
            'data_source', 'data_source_display', 'config', 'custom_query',
            'default_width', 'default_height', 'refresh_interval',
            'is_active', 'is_system', 'created_at', 'updated_at'
        ]
        read_only_fields = ['is_system']


class UserDashboardSerializer(serializers.ModelSerializer):
    """Serializer for user dashboard configuration."""
    
    class Meta:
        model = UserDashboard
        fields = ['id', 'layout', 'theme', 'created_at', 'updated_at']


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """ViewSet for dashboard widgets."""
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]
    queryset = DashboardWidget.objects.filter(is_active=True)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by widget type
        widget_type = self.request.query_params.get('widget_type')
        if widget_type:
            queryset = queryset.filter(widget_type=widget_type)
        
        # Filter by data source
        data_source = self.request.query_params.get('data_source')
        if data_source:
            queryset = queryset.filter(data_source=data_source)
        
        return queryset.order_by('name')
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get data for a specific widget."""
        widget = self.get_object()
        params = dict(request.query_params)
        
        # Remove pagination params
        params.pop('page', None)
        params.pop('page_size', None)
        
        data = DashboardDataService.get_widget_data(widget, params)
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def widget_types(self, request):
        """Get available widget types."""
        return Response([
            {'value': code, 'label': label}
            for code, label in DashboardWidget.WIDGET_TYPES
        ])
    
    @action(detail=False, methods=['get'])
    def data_sources(self, request):
        """Get available data sources."""
        return Response([
            {'value': code, 'label': label}
            for code, label in DashboardWidget.DATA_SOURCES
        ])


class UserDashboardViewSet(viewsets.ViewSet):
    """ViewSet for user dashboard configuration."""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get current user's dashboard configuration."""
        dashboard, created = UserDashboard.objects.get_or_create(
            user=request.user,
            defaults={'layout': self._get_default_layout()}
        )
        serializer = UserDashboardSerializer(dashboard)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_layout(self, request):
        """Update user's dashboard layout."""
        dashboard, created = UserDashboard.objects.get_or_create(
            user=request.user,
            defaults={'layout': []}
        )
        
        layout = request.data.get('layout')
        if layout is not None:
            dashboard.layout = layout
        
        theme = request.data.get('theme')
        if theme:
            dashboard.theme = theme
        
        dashboard.save()
        
        serializer = UserDashboardSerializer(dashboard)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def reset(self, request):
        """Reset user's dashboard to default."""
        dashboard, created = UserDashboard.objects.get_or_create(
            user=request.user,
            defaults={'layout': []}
        )
        
        dashboard.layout = self._get_default_layout()
        dashboard.theme = 'light'
        dashboard.save()
        
        serializer = UserDashboardSerializer(dashboard)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def all_data(self, request):
        """Get data for all widgets in user's dashboard."""
        dashboard, created = UserDashboard.objects.get_or_create(
            user=request.user,
            defaults={'layout': self._get_default_layout()}
        )
        
        widget_codes = [item.get('widget') for item in dashboard.layout if item.get('widget')]
        widgets = DashboardWidget.objects.filter(code__in=widget_codes, is_active=True)
        
        params = dict(request.query_params)
        
        result = {}
        for widget in widgets:
            result[widget.code] = DashboardDataService.get_widget_data(widget, params)
        
        return Response(result)
    
    def _get_default_layout(self):
        """Get default dashboard layout."""
        return [
            {'widget': 'project_stats', 'x': 0, 'y': 0, 'w': 3, 'h': 1},
            {'widget': 'sales_stats', 'x': 3, 'y': 0, 'w': 3, 'h': 1},
            {'widget': 'inventory_stats', 'x': 6, 'y': 0, 'w': 3, 'h': 1},
            {'widget': 'finance_stats', 'x': 9, 'y': 0, 'w': 3, 'h': 1},
            {'widget': 'sales_chart', 'x': 0, 'y': 1, 'w': 6, 'h': 2},
            {'widget': 'ar_aging', 'x': 6, 'y': 1, 'w': 6, 'h': 2},
        ]
