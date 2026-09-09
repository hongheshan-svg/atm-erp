from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.models import AuditLog, Company
from apps.core.permissions import ADMIN, PermissionMixin, require_role, role

from .models import User


class LoginThrottle(SimpleRateThrottle):
    scope = 'login'

    def allow_request(self, request, view):
        if settings.APP_ENVIRONMENT == 'development':
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LoginView(TokenObtainPairView):
    throttle_classes = [LoginThrottle]


class RefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs['refresh'])
        JWTAuthentication().get_user(token)
        return super().validate(attrs)


class RefreshView(TokenRefreshView):
    throttle_classes = [LoginThrottle]
    serializer_class = RefreshSerializer


def profile(user):
    return {
        'id': user.pk,
        'username': user.username,
        'display_name': user.display_name,
        'role': role(user),
        'management_reports': user.management_reports,
    }


class MeView(APIView):
    def get(self, request):
        return Response(profile(request.user))


class PasswordView(APIView):
    def post(self, request):
        if not isinstance(request.data, dict):
            raise ValidationError('请提交 JSON 对象。')
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(str(request.data.get('old_password', ''))):
                raise ValidationError({'old_password': '原密码不正确。'})
            password = request.data.get('new_password')
            if not isinstance(password, str):
                raise ValidationError({'new_password': '请填写新密码。'})
            validate_password(password, user)
            user.set_password(password)
            user.save(update_fields=['password'])
            AuditLog.objects.create(actor=user, operation='user.password', resource=f'user:{user.pk}')
        return Response({'detail': '密码已修改，请重新登录。'})


class DirectoryView(APIView):
    def get(self, request):
        return Response(
            [
                {'id': u.pk, 'display_name': u.display_name or u.username, 'role': role(u)}
                for u in User.objects.filter(is_active=True)
            ]
        )


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'display_name',
            'role',
            'hourly_cost',
            'is_active',
            'password',
            'management_reports',
        ]
        read_only_fields = ['id']
        extra_kwargs = {'hourly_cost': {'min_value': 0}}

    def validate(self, attrs):
        report_access = attrs.get('management_reports', self.instance.management_reports if self.instance else False)
        target_role = attrs.get('role', self.instance.role if self.instance else 'member')
        if report_access and target_role != 'manager':
            raise ValidationError({'management_reports': '总经理报表授权仅用于经理角色账号；管理员默认可查看。'})
        if not self.instance and 'password' not in attrs:
            raise ValidationError({'password': '新增用户必须设置密码。'})
        if 'password' in attrs:
            candidate = self.instance or User(
                username=attrs.get('username', ''), display_name=attrs.get('display_name', '')
            )
            validate_password(attrs['password'], candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if 'role' in validated_data:
            instance.is_superuser = False
            instance.is_staff = instance.role == 'admin'
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance


class UserView(
    PermissionMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    read_roles = ADMIN
    queryset = User.objects.all()
    serializer_class = UserSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def perform_create(self, serializer):
        with transaction.atomic():
            self._lock_admin()
            user = serializer.save()
            AuditLog.objects.create(
                actor=self.request.user,
                operation='user.create',
                resource=f'user:{user.pk}',
                detail={'management_reports': user.management_reports},
            )

    def _lock_admin(self):
        Company.objects.select_for_update().get(pk=1)
        actor = User.objects.get(pk=self.request.user.pk)
        require_role(actor, ADMIN)

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            self._lock_admin()
            user = User.objects.select_for_update().get(pk=self.get_object().pk)
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            removing_admin = (not data.get('is_active', user.is_active)) or data.get('role', role(user)) != 'admin'
            if user.is_active and role(user) == 'admin' and removing_admin:
                other_admin = (
                    User.objects.filter(is_active=True)
                    .filter(Q(role='admin') | Q(is_superuser=True))
                    .exclude(pk=user.pk)
                    .exists()
                )
                if not other_admin:
                    raise ValidationError('至少保留一位启用的管理员。')
            previous_reports = user.management_reports
            serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                operation='user.update',
                resource=f'user:{user.pk}',
                detail={
                    'fields': sorted(k for k in data if k != 'password'),
                    'management_reports': {'before': previous_reports, 'after': user.management_reports},
                },
            )
            return Response(serializer.data)
