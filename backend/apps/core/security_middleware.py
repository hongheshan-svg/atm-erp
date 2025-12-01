"""
Security middleware for request validation and protection.
"""
import re
import logging
import time
from django.conf import settings
from django.http import JsonResponse
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('security')


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware to prevent abuse.
    """
    
    def process_request(self, request):
        # Skip rate limiting for certain paths
        skip_paths = ['/api/docs/', '/static/', '/media/', '/admin/']
        if any(request.path.startswith(p) for p in skip_paths):
            return None
        
        # Get client identifier
        client_ip = self.get_client_ip(request)
        user_id = request.user.id if request.user.is_authenticated else None
        
        # Different rate limits for different endpoints
        if '/api/auth/login/' in request.path:
            limit, window = 5, 60  # 5 requests per minute
            key = f'ratelimit:login:{client_ip}'
        elif '/api/auth/password-reset/' in request.path:
            limit, window = 3, 3600  # 3 requests per hour
            key = f'ratelimit:password_reset:{client_ip}'
        elif user_id:
            limit, window = 1000, 3600  # 1000 requests per hour for authenticated users
            key = f'ratelimit:user:{user_id}'
        else:
            limit, window = 100, 3600  # 100 requests per hour for anonymous
            key = f'ratelimit:anon:{client_ip}'
        
        # Check rate limit
        current = cache.get(key, 0)
        if current >= limit:
            logger.warning(f'Rate limit exceeded: {key}')
            return JsonResponse({
                'error': '请求过于频繁，请稍后再试',
                'retry_after': window
            }, status=429)
        
        # Increment counter
        cache.set(key, current + 1, window)
        return None
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    """
    
    def process_response(self, request, response):
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: https:; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy
        response['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), gyroscope=(), '
            'magnetometer=(), microphone=(), payment=(), usb=()'
        )
        
        return response


class SQLInjectionProtectionMiddleware(MiddlewareMixin):
    """
    Basic SQL injection detection middleware.
    """
    
    SQL_PATTERNS = [
        r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
        r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
        r"\w*((\%27)|(\'))((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
        r"((\%27)|(\'))union",
        r"exec(\s|\+)+(s|x)p\w+",
        r"UNION(\s+)SELECT",
        r"INSERT(\s+)INTO",
        r"DELETE(\s+)FROM",
        r"DROP(\s+)TABLE",
        r"UPDATE(\s+)\w+(\s+)SET",
    ]
    
    def process_request(self, request):
        # Check query parameters
        query_string = request.META.get('QUERY_STRING', '')
        if self.detect_sql_injection(query_string):
            logger.warning(f'SQL injection attempt detected in query: {query_string[:200]}')
            return JsonResponse({'error': '非法请求'}, status=400)
        
        # Check POST data
        if request.method == 'POST' and request.content_type == 'application/x-www-form-urlencoded':
            body = request.body.decode('utf-8', errors='ignore')
            if self.detect_sql_injection(body):
                logger.warning(f'SQL injection attempt detected in body')
                return JsonResponse({'error': '非法请求'}, status=400)
        
        return None
    
    def detect_sql_injection(self, text):
        for pattern in self.SQL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class XSSProtectionMiddleware(MiddlewareMixin):
    """
    Basic XSS detection middleware.
    """
    
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<link[^>]*>',
        r'expression\s*\(',
        r'url\s*\(',
    ]
    
    def process_request(self, request):
        # Skip for file uploads
        if request.content_type and 'multipart/form-data' in request.content_type:
            return None
        
        # Check query parameters
        query_string = request.META.get('QUERY_STRING', '')
        if self.detect_xss(query_string):
            logger.warning(f'XSS attempt detected in query')
            return JsonResponse({'error': '非法请求'}, status=400)
        
        return None
    
    def detect_xss(self, text):
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log all requests for security auditing.
    """
    
    def process_request(self, request):
        request._start_time = time.time()
        return None
    
    def process_response(self, request, response):
        # Calculate request duration
        duration = time.time() - getattr(request, '_start_time', time.time())
        
        # Log slow requests
        if duration > 5:  # More than 5 seconds
            logger.warning(
                f'Slow request: {request.method} {request.path} '
                f'took {duration:.2f}s, status={response.status_code}'
            )
        
        # Log failed authentication attempts
        if response.status_code == 401:
            client_ip = self.get_client_ip(request)
            logger.warning(f'Authentication failed: {request.path} from {client_ip}')
        
        # Log server errors
        if response.status_code >= 500:
            logger.error(
                f'Server error: {request.method} {request.path} '
                f'status={response.status_code}'
            )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
