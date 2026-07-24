"""AI 网关 URL 配置。

在 config/urls.py 中挂载:path('api/ai/', include('apps.ai.urls'))
(见 integration_notes——config/urls.py 非本包 own 文件)。
"""

from django.urls import path

from .views import AIChatView

app_name = 'ai'

urlpatterns = [
    path('chat/', AIChatView.as_view(), name='ai-chat'),
]
