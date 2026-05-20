"""
Views for accounts app.
"""
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.mixins import SoftDeleteMixin

from .models import Department, Role, User
from .serializers import (
    ChangePasswordSerializer,
    DepartmentSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    UserSerializer,
    UserUpdateSerializer,
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
    throttle_scope = 'login'
    throttle_classes = [ScopedRateThrottle] if settings.LOGIN_THROTTLE_ENABLED else []


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


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Role management.
    角色使用物理删除，以便删除后可以创建同名角色。
    """
    queryset = Role.objects.filter(is_deleted=False).prefetch_related(
        'permissions_new',
        'data_scopes__custom_departments',
    )
    serializer_class = RoleSerializer
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['sort_order', 'code', 'created_at']

    def destroy(self, request, *args, **kwargs):
        """物理删除角色"""
        instance = self.get_object()

        # 检查是否有用户关联此角色
        user_count = instance.users.filter(is_deleted=False, is_active=True).count()
        if user_count > 0:
            return Response(
                {'detail': f'无法删除，还有 {user_count} 个用户使用此角色'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 记录审计日志
        from apps.core.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action='DELETE',
            model_name='Role',
            object_id=instance.id,
            details=f'删除角色: {instance.name} ({instance.code})'
        )

        # 物理删除
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        new_password = request.data.get('new_password')

        # 密码安全验证
        if not new_password or len(new_password) < 6:
            return Response(
                {'detail': '新密码至少需要6位字符'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        # 记录敏感操作日志
        from apps.core.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action='RESET_PASSWORD',
            model_name='User',
            object_id=user.id,
            details=f'管理员重置了用户 {user.username} 的密码'
        )

        # 安全返回：不在响应中包含明文密码
        return Response({'message': '密码重置成功，请通知用户使用新密码登录'})

    @action(detail=True, methods=['post'])
    def set_wechat_id(self, request, pk=None):
        """
        Set user's WeChat Work ID for personal notifications.
        Admin only.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': '无权限执行此操作'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = self.get_object()
        wechat_work_id = request.data.get('wechat_work_id', '').strip()

        user.wechat_work_id = wechat_work_id
        user.save(update_fields=['wechat_work_id'])

        return Response({
            'message': '企业微信ID已更新',
            'wechat_work_id': user.wechat_work_id
        })

    @action(detail=False, methods=['get'])
    def wechat_work_users(self, request):
        """
        Get list of users from WeChat Work API.
        Can be used to match with ERP users.
        Admin only.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': '无权限执行此操作'},
                status=status.HTTP_403_FORBIDDEN
            )


        import requests
        from django.conf import settings

        corp_id = getattr(settings, 'WECHAT_WORK_CORP_ID', '')
        corp_secret = getattr(settings, 'WECHAT_WORK_CORP_SECRET', '')

        if not corp_id or not corp_secret:
            return Response(
                {'detail': '企业微信未配置'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get access token
            token_url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={corp_secret}'
            token_resp = requests.get(token_url, timeout=10)
            token_data = token_resp.json()

            if token_data.get('errcode') != 0:
                return Response(
                    {'detail': f"获取token失败: {token_data.get('errmsg')}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            access_token = token_data.get('access_token')

            # Get department list first
            dept_url = f'https://qyapi.weixin.qq.com/cgi-bin/department/list?access_token={access_token}'
            dept_resp = requests.get(dept_url, timeout=10)
            dept_data = dept_resp.json()

            if dept_data.get('errcode') != 0:
                return Response(
                    {'detail': f"获取部门失败: {dept_data.get('errmsg')}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            departments = dept_data.get('department', [])

            # Get users for each department
            all_users = []
            seen_userids = set()

            for dept in departments:
                dept_id = dept['id']
                users_url = f'https://qyapi.weixin.qq.com/cgi-bin/user/list?access_token={access_token}&department_id={dept_id}'
                users_resp = requests.get(users_url, timeout=10)
                users_data = users_resp.json()

                if users_data.get('errcode') == 0:
                    for user in users_data.get('userlist', []):
                        if user['userid'] not in seen_userids:
                            seen_userids.add(user['userid'])
                            all_users.append({
                                'userid': user['userid'],
                                'name': user.get('name', ''),
                                'mobile': user.get('mobile', ''),
                                'email': user.get('email', ''),
                                'department': dept.get('name', '')
                            })

            # Match with ERP users
            erp_users = User.objects.filter(is_deleted=False)
            matched = []
            unmatched_wechat = []
            unmatched_erp = list(erp_users.filter(wechat_work_id='').values('id', 'username', 'employee_id', 'phone'))

            for wu in all_users:
                # Try to match by phone, employee_id, or username
                erp_match = erp_users.filter(
                    models.Q(phone=wu['mobile']) |
                    models.Q(employee_id=wu['userid']) |
                    models.Q(username=wu['userid'])
                ).first()

                if erp_match:
                    matched.append({
                        'erp_user': {
                            'id': erp_match.id,
                            'username': erp_match.username,
                            'name': erp_match.get_full_name()
                        },
                        'wechat_user': wu,
                        'already_linked': erp_match.wechat_work_id == wu['userid']
                    })
                else:
                    unmatched_wechat.append(wu)

            return Response({
                'matched': matched,
                'unmatched_wechat_users': unmatched_wechat,
                'unmatched_erp_users': unmatched_erp,
                'total_wechat_users': len(all_users),
                'total_erp_users': erp_users.count()
            })

        except Exception as e:
            return Response(
                {'detail': f'获取企业微信用户失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def sync_wechat_ids(self, request):
        """
        Bulk sync WeChat Work IDs for matched users.
        Admin only.
        
        Request body:
        {
            "mappings": [
                {"erp_user_id": 1, "wechat_work_id": "zhangsan"},
                ...
            ]
        }
        """
        if not request.user.is_staff:
            return Response(
                {'detail': '无权限执行此操作'},
                status=status.HTTP_403_FORBIDDEN
            )

        mappings = request.data.get('mappings', [])

        if not mappings:
            return Response(
                {'detail': '没有提供映射数据'},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated = 0
        errors = []

        for mapping in mappings:
            erp_user_id = mapping.get('erp_user_id')
            wechat_work_id = mapping.get('wechat_work_id', '').strip()

            if not erp_user_id or not wechat_work_id:
                continue

            try:
                user = User.objects.get(id=erp_user_id, is_deleted=False)
                user.wechat_work_id = wechat_work_id
                user.save(update_fields=['wechat_work_id'])
                updated += 1
            except User.DoesNotExist:
                errors.append(f'用户ID {erp_user_id} 不存在')
            except Exception as e:
                errors.append(f'用户ID {erp_user_id} 更新失败: {str(e)}')

        return Response({
            'updated': updated,
            'errors': errors
        })

    @action(detail=False, methods=['post'])
    def test_personal_notification(self, request):
        """
        Send a test personal notification to the specified user.
        Admin only.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': '无权限执行此操作'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')
        if not user_id:
            # Default to current user
            user = request.user
        else:
            try:
                user = User.objects.get(id=user_id, is_deleted=False)
            except User.DoesNotExist:
                return Response(
                    {'detail': '用户不存在'},
                    status=status.HTTP_404_NOT_FOUND
                )

        if not user.wechat_work_id:
            return Response(
                {'detail': f'用户 {user.username} 未配置企业微信ID'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.core.notification_service import NotificationService

        title = "🔔 ERP系统测试通知"
        content = f"这是一条发送给 {user.get_full_name()} 的测试通知。\n\n如果您收到此消息，说明企业微信个人通知功能配置成功！"

        try:
            NotificationService.send_to_user(user, title, content)
            return Response({
                'message': f'测试通知已发送给 {user.get_full_name()}',
                'wechat_work_id': user.wechat_work_id
            })
        except Exception as e:
            return Response(
                {'detail': f'发送失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

