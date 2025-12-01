"""
Health check and system status endpoints.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import time


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Basic health check endpoint.
    Returns 200 if the service is running.
    """
    return Response({'status': 'healthy'})


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check - verifies all dependencies are available.
    """
    checks = {
        'database': False,
        'cache': False,
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = True
    except Exception as e:
        checks['database_error'] = str(e)
    
    # Check cache
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            checks['cache'] = True
        cache.delete('health_check')
    except Exception as e:
        checks['cache_error'] = str(e)
    
    # Overall status
    all_healthy = all(v for k, v in checks.items() if not k.endswith('_error'))
    
    return Response({
        'status': 'ready' if all_healthy else 'not_ready',
        'checks': checks
    }, status=200 if all_healthy else 503)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_status(request):
    """
    Detailed system status for administrators.
    """
    from .performance import PerformanceMonitor
    
    status = {
        'version': '1.0.0',
        'debug': settings.DEBUG,
        'database': {},
        'cache': {},
        'celery': {},
    }
    
    # Database status
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status['database'] = {
            'status': 'connected',
            'latency_ms': round((time.time() - start) * 1000, 2),
            'vendor': connection.vendor,
        }
    except Exception as e:
        status['database'] = {'status': 'error', 'error': str(e)}
    
    # Cache status
    status['cache'] = PerformanceMonitor.get_cache_stats()
    
    # Celery status
    status['celery'] = PerformanceMonitor.get_celery_stats()
    
    # System resources
    try:
        status['system'] = PerformanceMonitor.get_system_health()
    except Exception as e:
        status['system'] = {'error': str(e)}
    
    return Response(status)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def security_status(request):
    """
    Security configuration status for administrators.
    """
    security_config = {
        'debug_mode': settings.DEBUG,
        'https': {
            'ssl_redirect': getattr(settings, 'SECURE_SSL_REDIRECT', False),
            'hsts_enabled': getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0,
            'hsts_seconds': getattr(settings, 'SECURE_HSTS_SECONDS', 0),
        },
        'cookies': {
            'session_secure': getattr(settings, 'SESSION_COOKIE_SECURE', False),
            'csrf_secure': getattr(settings, 'CSRF_COOKIE_SECURE', False),
            'session_httponly': getattr(settings, 'SESSION_COOKIE_HTTPONLY', True),
        },
        'headers': {
            'x_frame_options': getattr(settings, 'X_FRAME_OPTIONS', 'DENY'),
            'content_type_nosniff': getattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF', True),
        },
        'password_policy': {
            'min_length': getattr(settings, 'PASSWORD_MIN_LENGTH', 8),
            'require_uppercase': getattr(settings, 'PASSWORD_REQUIRE_UPPERCASE', True),
            'require_digit': getattr(settings, 'PASSWORD_REQUIRE_DIGIT', True),
            'require_special': getattr(settings, 'PASSWORD_REQUIRE_SPECIAL', True),
            'expiry_days': getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90),
        },
        'login_security': {
            'max_attempts': getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
            'lockout_minutes': getattr(settings, 'LOCKOUT_DURATION_MINUTES', 30),
        },
    }
    
    # Calculate security score
    score = 0
    max_score = 0
    
    # Debug mode (critical)
    max_score += 20
    if not settings.DEBUG:
        score += 20
    
    # HTTPS settings
    max_score += 30
    if security_config['https']['ssl_redirect']:
        score += 10
    if security_config['https']['hsts_enabled']:
        score += 10
    if security_config['https']['hsts_seconds'] >= 31536000:
        score += 10
    
    # Cookie security
    max_score += 20
    if security_config['cookies']['session_secure']:
        score += 10
    if security_config['cookies']['csrf_secure']:
        score += 10
    
    # Password policy
    max_score += 20
    if security_config['password_policy']['min_length'] >= 8:
        score += 5
    if security_config['password_policy']['require_uppercase']:
        score += 5
    if security_config['password_policy']['require_digit']:
        score += 5
    if security_config['password_policy']['require_special']:
        score += 5
    
    # Login security
    max_score += 10
    if security_config['login_security']['max_attempts'] <= 5:
        score += 5
    if security_config['login_security']['lockout_minutes'] >= 15:
        score += 5
    
    security_config['security_score'] = {
        'score': score,
        'max_score': max_score,
        'percentage': round(score / max_score * 100, 1),
        'grade': 'A' if score >= 90 else 'B' if score >= 70 else 'C' if score >= 50 else 'D'
    }
    
    return Response(security_config)
