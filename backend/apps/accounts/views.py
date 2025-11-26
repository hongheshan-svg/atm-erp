"""
Views for accounts app.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import update_session_auth_hash
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from .models import User, Role, Department
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    RoleSerializer, DepartmentSerializer, ChangePasswordSerializer,
    UserProfileSerializer
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with user info."""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add user info to token response
        serializer = UserProfileSerializer(self.user)
        data['user'] = serializer.data
        
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT login view."""
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = []  # 登录接口不需要认证


class DepartmentViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    ViewSet for Department management.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filterset_fields = ['parent', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['sort_order', 'code', 'created_at']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get department tree structure."""
        departments = self.get_queryset().filter(is_deleted=False)
        
        def build_tree(parent_id=None):
            result = []
            items = departments.filter(parent_id=parent_id)
            for item in items:
                node = DepartmentSerializer(item).data
                node['children'] = build_tree(item.id)
                result.append(node)
            return result
        
        tree_data = build_tree()
        return Response(tree_data)


class RoleViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    ViewSet for Role management.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_fields = ['data_scope', 'is_active', 'is_deleted']
    search_fields = ['code', 'name']
    ordering_fields = ['sort_order', 'code', 'created_at']


class UserViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    ViewSet for User management.
    """
    queryset = User.objects.all()
    filterset_fields = ['department', 'role', 'is_active', 'is_staff', 'is_deleted']
    search_fields = ['username', 'employee_id', 'email', 'first_name', 'last_name']
    ordering_fields = ['employee_id', 'created_at', 'last_login']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'profile':
            return UserProfileSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'])
    def update_profile(self, request):
        """Update current user profile."""
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(request.user).data)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change password for current user."""
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            # 返回详细错误信息
            errors = serializer.errors
            error_msg = []
            for field, msgs in errors.items():
                for msg in msgs:
                    error_msg.append(str(msg))
            return Response(
                {'detail': '; '.join(error_msg) if error_msg else '验证失败'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'detail': '当前密码错误'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        update_session_auth_hash(request, user)
        
        return Response({'message': '密码修改成功'})
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """Reset user password (admin only)."""
        if not request.user.is_staff:
            return Response(
                {'detail': '无权限执行此操作'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user = self.get_object()
        new_password = request.data.get('new_password', '123456')
        user.set_password(new_password)
        user.save()
        
        return Response({'message': f'密码已重置为: {new_password}'})

