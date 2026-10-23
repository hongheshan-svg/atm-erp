from apps.accounts.api import DirectoryView, LoginView, MeView, PasswordView, RefreshView, UserView
from apps.core.ota import AgentView, RestartView, UpgradeView
from apps.core.setup import SetupView
from apps.core.views import AuditView, CodeView, CompanyView, health
from django.urls import include, path
from rest_framework.routers import SimpleRouter

accounts = SimpleRouter()
accounts.register('users', UserView)
core = SimpleRouter()
core.register('company', CompanyView)
core.register('codes', CodeView)
core.register('audit', AuditView)

# 未捕获异常返回中文 JSON 与请求编号，而不是 Django 的英文 HTML 错误页。
handler500 = 'apps.core.request_id.server_error'

urlpatterns = [
    path('api/core/setup/', SetupView.as_view()),
    path('api/core/upgrade/', UpgradeView.as_view()),
    path('api/core/upgrade/restart/', RestartView.as_view()),
    path('api/core/upgrade/agent/', AgentView.as_view()),
    path('api/health/', health),
    path('api/auth/login/', LoginView.as_view()),
    path('api/auth/refresh/', RefreshView.as_view()),
    path('api/auth/me/', MeView.as_view()),
    path('api/auth/password/', PasswordView.as_view()),
    path('api/auth/directory/', DirectoryView.as_view()),
    path('api/auth/', include(accounts.urls)),
    path('api/core/', include(core.urls)),
    path('api/business/', include('apps.business.urls')),
]
