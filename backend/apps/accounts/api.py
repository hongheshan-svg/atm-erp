from ipaddress import ip_address

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
from apps.core.permissions import ADMIN, PermissionMixin, has_role, require_role, role, roles

from .models import User


class LoginThrottle(SimpleRateThrottle):
    scope = 'login'

    def allow_request(self, request, view):
        if settings.APP_ENVIRONMENT == 'development':
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}

    def get_ident(self, request):
        peer = request.META.get('REMOTE_ADDR', '')
        # Both supported Daphne launchers bind loopback. Their Nginx ingress
        # overwrites XFF with its socket peer; never trust a direct remote caller.
        if peer in {'127.0.0.1', '::1'}:
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '').strip()
            try:
                return str(ip_address(forwarded))
            except ValueError:
                pass
        return peer


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
        'roles': sorted(roles(user)),
        'management_reports': user.management_reports,
        'setup_required': has_role(user, ADMIN) and Company.objects.filter(pk=1, setup_required=True).exists(),
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
                {'id': u.pk, 'display_name': u.display_name or u.username, 'role': role(u), 'roles': sorted(roles(u))}
                for u in User.objects.filter(is_active=True)
            ]
        )


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=User.Role.choices),
        required=False,
        allow_empty=False,
        max_length=7,
        write_only=True,
    )

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['roles'] = sorted(roles(instance))
        return result

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'display_name',
            'role',
            'roles',
            'hourly_cost',
            'is_active',
            'password',
            'management_reports',
        ]
        read_only_fields = ['id']
        extra_kwargs = {'hourly_cost': {'min_value': 0}}

    def validate(self, attrs):
        selected = attrs.pop('roles', None)
        if selected is not None:
            if len(selected) != len(set(selected)):
                raise ValidationError({'roles': '角色不能重复。'})
            if 'role' in attrs and attrs['role'] not in selected:
                raise ValidationError({'roles': '角色字段与角色列表不一致。'})
            attrs['role'] = selected[0]
            attrs['additional_roles'] = selected[1:]
        elif 'role' in attrs:
            attrs['additional_roles'] = []
        report_access = attrs.get('management_reports', self.instance.management_reports if self.instance else False)
        target_roles = {
            attrs.get('role', self.instance.role if self.instance else 'member'),
            *attrs.get('additional_roles', self.instance.additional_roles if self.instance else []),
        }
        if report_access and 'manager' not in target_roles:
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
            instance.is_staff = has_role(instance, ADMIN)
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
    search_fields = ['username', 'display_name']
    filterset_fields = ['is_active']

    def get_queryset(self):
        queryset = super().get_queryset()
        selected_role = self.request.query_params.get('role')
        if selected_role:
            if selected_role not in User.Role.values:
                raise ValidationError({'role': '请选择有效岗位。'})
            predicate = Q(role=selected_role) | Q(additional_roles__contains=[selected_role])
            if selected_role == User.Role.ADMIN:
                predicate |= Q(is_superuser=True)
            queryset = queryset.filter(predicate)
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            self._lock_admin()
            user = serializer.save()
            AuditLog.objects.create(
                actor=self.request.user,
                operation='user.create',
                resource=f'user:{user.pk}',
                detail={'management_reports': user.management_reports, 'roles': sorted(roles(user))},
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
            target_roles = {data.get('role', role(user)), *data.get('additional_roles', user.additional_roles)}
            removing_admin = (not data.get('is_active', user.is_active)) or 'admin' not in target_roles
            if user.is_active and has_role(user, ADMIN) and removing_admin:
                other_admin = (
                    User.objects.filter(is_active=True)
                    .filter(Q(role='admin') | Q(additional_roles__contains=['admin']) | Q(is_superuser=True))
                    .exclude(pk=user.pk)
                    .exists()
                )
                if not other_admin:
                    raise ValidationError('至少保留一位启用的管理员。')
            previous_reports = user.management_reports
            previous_roles = sorted(roles(user))
            serializer.save()
            AuditLog.objects.create(
                actor=request.user,
                operation='user.update',
                resource=f'user:{user.pk}',
                detail={
                    'fields': sorted(k for k in data if k != 'password'),
                    'management_reports': {'before': previous_reports, 'after': user.management_reports},
                    'roles': {'before': previous_roles, 'after': sorted(roles(user))},
                },
            )
            return Response(serializer.data)
