"""
JWT Authentication Middleware for WebSocket connections
"""
import logging
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
from django.conf import settings

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user(token):
    """Get user from JWT token"""
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import TokenError
    
    User = get_user_model()
    
    try:
        # Use simplejwt to validate the token
        access_token = AccessToken(token)
        user_id = access_token.get('user_id')
        if user_id:
            user = User.objects.get(id=user_id)
            logger.info(f"WebSocket auth successful for user {user_id}")
            return user
    except TokenError as e:
        logger.warning(f"WebSocket token error: {e}")
    except User.DoesNotExist:
        logger.warning(f"WebSocket user not found: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
    
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that authenticates WebSocket connections using JWT tokens
    passed as query parameters.
    """
    
    async def __call__(self, scope, receive, send):
        # Parse query string to get token
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            scope['user'] = await get_user(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """Wrapper for applying JWT auth middleware"""
    return JWTAuthMiddleware(inner)
