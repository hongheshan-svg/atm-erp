"""
URL configuration for ERP project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([])
def api_health_check(request):
    """Simple health check for Docker/Kubernetes."""
    return Response({'status': 'healthy', 'version': '1.0.0'})


urlpatterns = [
    path('admin/', admin.site.urls),

    # Health check (for Docker/K8s)
    path('api/v1/health/', api_health_check, name='api-health'),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # API endpoints
    path('api/auth/', include('apps.accounts.urls')),
    path('api/accounts/', include('apps.accounts.urls')),  # 别名
    path('api/masterdata/', include('apps.masterdata.urls')),
    path('api/projects/', include('apps.projects.urls')),
    path('api/purchase/', include('apps.purchase.urls')),
    path('api/sales/', include('apps.sales.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/finance/', include('apps.finance.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/core/', include('apps.core.urls')),
    path('api/production/', include('apps.production.urls')),
    path('api/oa/', include('apps.oa.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

