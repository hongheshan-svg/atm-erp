"""
JWT Authentication Middleware for WebSocket connections
"""
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
import jwt
from django.conf import settings


@database_sync_to_async
def get_user(token):
    """Get user from JWT token"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        # Decode the JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        user_id = payload.get('user_id')
        if user_id:
            return User.objects.get(id=user_id)
    except jwt.ExpiredSignatureError:
        pass
    except jwt.InvalidTokenError:
        pass
    except User.DoesNotExist:
        pass
    
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
