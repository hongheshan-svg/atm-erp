"""
ASGI config for ERP project with WebSocket support.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import websocket routing after Django initialization
from apps.core.routing import websocket_urlpatterns
from apps.core.websocket_auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        'websocket': JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
