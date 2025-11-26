"""
Middleware for audit logging
"""
from django.utils.deprecation import MiddlewareMixin
from .models import AuditLog
import json


class AuditLogMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log API changes
    """
    
    def process_response(self, request, response):
        # Only log authenticated requests
        if not request.user.is_authenticated:
            return response
        
        # Only log specific methods
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return response
        
        # Don't log authentication endpoints
        if '/api/auth/login' in request.path or '/api/auth/refresh' in request.path:
            return response
        
        # Only log successful requests
        if response.status_code >= 400:
            return response
        
        try:
            # Extract model name from URL
            model_name = self._extract_model_name(request.path)
            action = self._map_method_to_action(request.method)
            
            # Get IP address
            ip_address = self._get_client_ip(request)
            
            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Try to extract changes
            changes = None
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    if hasattr(request, 'body'):
                        changes = json.loads(request.body.decode('utf-8'))
                except:
                    pass
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action=action,
                model_name=model_name,
                object_repr=model_name,
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent[:200] if user_agent else None
            )
        except Exception as e:
            # Don't break the request if audit logging fails
            print(f"Audit logging error: {e}")
        
        return response
    
    def _extract_model_name(self, path):
        """Extract model name from API path"""
        parts = path.split('/')
        if len(parts) >= 3 and parts[1] == 'api':
            return parts[2]
        return 'unknown'
    
    def _map_method_to_action(self, method):
        """Map HTTP method to action"""
        mapping = {
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'UPDATE',
            'DELETE': 'DELETE'
        }
        return mapping.get(method, 'UPDATE')
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

