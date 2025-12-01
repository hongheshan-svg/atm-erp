"""
Security views for login logs, password policy, and sensitive operations.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import serializers
from django.utils import timezone
from .security import LoginLog, SensitiveOperationLog, PasswordPolicy, SecurityService


class LoginLogSerializer(serializers.ModelSerializer):
    """Serializer for login logs."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = LoginLog
        fields = [
            'id', 'username', 'ip_address', 'user_agent', 'status',
            'status_display', 'failure_reason', 'login_time', 'location',
            'device_type'
        ]


class SensitiveOperationLogSerializer(serializers.ModelSerializer):
    """Serializer for sensitive operation logs."""
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = SensitiveOperationLog
        fields = [
            'id', 'user', 'user_name', 'operation_type', 'operation_type_display',
            'target_model', 'target_id', 'target_desc', 'ip_address',
            'confirmed', 'confirmed_at', 'created_at'
        ]


class LoginLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for login logs."""
    serializer_class = LoginLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = LoginLog.objects.all()
        
        # Non-admin users can only see their own logs
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        # Filter by username
        username = self.request.query_params.get('username')
        if username:
            queryset = queryset.filter(username__icontains=username)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(login_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(login_time__date__lte=end_date)
        
        return queryset.order_by('-login_time')
    
    @action(detail=False, methods=['get'])
    def my_history(self, request):
        """Get current user's login history."""
        logs = SecurityService.get_login_history(request.user, days=30)
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get login statistics."""
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from datetime import timedelta
        
        days = int(request.query_params.get('days', 7))
        cutoff = timezone.now() - timedelta(days=days)
        
        queryset = LoginLog.objects.filter(login_time__gte=cutoff)
        
        stats = {
            'total': queryset.count(),
            'success': queryset.filter(status='SUCCESS').count(),
            'failed': queryset.filter(status='FAILED').count(),
            'locked': queryset.filter(status='LOCKED').count(),
            'by_device': list(queryset.values('device_type').annotate(count=Count('id'))),
            'by_day': list(queryset.annotate(
                day=TruncDate('login_time')
            ).values('day').annotate(count=Count('id')).order_by('day'))
        }
        
        return Response(stats)


class SensitiveOperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for sensitive operation logs."""
    serializer_class = SensitiveOperationLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = SensitiveOperationLog.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by operation type
        op_type = self.request.query_params.get('operation_type')
        if op_type:
            queryset = queryset.filter(operation_type=op_type)
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset


class PasswordPolicyViewSet(viewsets.ViewSet):
    """ViewSet for password policy operations."""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def policy(self, request):
        """Get current password policy."""
        from django.conf import settings
        
        return Response({
            'min_length': getattr(settings, 'PASSWORD_MIN_LENGTH', PasswordPolicy.MIN_LENGTH),
            'require_uppercase': getattr(settings, 'PASSWORD_REQUIRE_UPPERCASE', PasswordPolicy.REQUIRE_UPPERCASE),
            'require_lowercase': getattr(settings, 'PASSWORD_REQUIRE_LOWERCASE', PasswordPolicy.REQUIRE_LOWERCASE),
            'require_digit': getattr(settings, 'PASSWORD_REQUIRE_DIGIT', PasswordPolicy.REQUIRE_DIGIT),
            'require_special': getattr(settings, 'PASSWORD_REQUIRE_SPECIAL', PasswordPolicy.REQUIRE_SPECIAL),
            'expiry_days': getattr(settings, 'PASSWORD_EXPIRY_DAYS', PasswordPolicy.PASSWORD_EXPIRY_DAYS),
            'max_login_attempts': getattr(settings, 'MAX_LOGIN_ATTEMPTS', PasswordPolicy.MAX_LOGIN_ATTEMPTS),
            'lockout_duration_minutes': getattr(settings, 'LOCKOUT_DURATION_MINUTES', PasswordPolicy.LOCKOUT_DURATION_MINUTES),
        })
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate a password against policy."""
        password = request.data.get('password', '')
        is_valid, errors = PasswordPolicy.validate_password(password, request.user)
        
        return Response({
            'is_valid': is_valid,
            'errors': errors
        })
    
    @action(detail=False, methods=['get'])
    def check_expiry(self, request):
        """Check if current user's password is expired."""
        is_expired, days_until = PasswordPolicy.check_password_expiry(request.user)
        
        return Response({
            'is_expired': is_expired,
            'days_until_expiry': days_until,
            'should_warn': days_until is not None and 0 < days_until <= 14
        })
