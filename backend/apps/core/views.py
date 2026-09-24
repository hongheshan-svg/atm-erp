import django_filters
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import AuditLog, CodeRule, Company
from .permissions import ADMIN, PermissionMixin


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    from .version import VERSION

    return Response({'status': 'ok', 'schema': 'lean-erp-v1', 'version': VERSION})


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'address', 'phone', 'locked_through', 'period_revision']
        read_only_fields = ['id', 'locked_through', 'period_revision']


class CompanyView(PermissionMixin, mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Company.objects.filter(pk=1)
    serializer_class = CompanySerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    @action(detail=True, methods=['post'], url_path='period-lock')
    def period_lock(self, request, pk=None):
        from rest_framework.exceptions import ValidationError

        from .periods import configure

        # 公司资料行还没建时，get_object() 只会给一个 404，看不出该去哪里补。
        if not Company.objects.filter(pk=1).exists():
            raise ValidationError('公司资料尚未初始化，请先在设置中完成公司资料后再锁账。')
        self.get_object()
        return Response(configure(request.user, request.headers.get('Idempotency-Key'), request.data))

    def perform_update(self, serializer):
        from django.db import transaction

        with transaction.atomic():
            # A company edit opened before setup/period changes must not restore stale state.
            serializer.instance = Company.objects.select_for_update().get(pk=serializer.instance.pk)
            company = serializer.save()
            AuditLog.objects.create(
                actor=self.request.user,
                operation='company.update',
                resource=f'company:{company.pk}',
                detail={'fields': sorted(serializer.validated_data)},
            )


class CodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodeRule
        fields = ['id', 'key', 'prefix', 'counter', 'date_format', 'padding', 'reset_cycle', 'period', 'revision']


class CodeView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    read_roles = ADMIN
    queryset = CodeRule.objects.order_by('id')
    serializer_class = CodeSerializer

    @action(detail=True, methods=['post'])
    def configure(self, request, pk=None):
        from .codes import configure

        return Response(configure(request.user, request.headers.get('Idempotency-Key'), pk, request.data))


class AuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    def get_actor_name(self, obj):
        return obj.actor.display_name or obj.actor.username

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_name', 'operation', 'resource', 'detail', 'created_at']


class AuditFilter(django_filters.FilterSet):
    # 按本地日期筛选；created_at__date 在 USE_TZ 下按 Asia/Shanghai 取日期。
    date_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = AuditLog
        fields = ['actor', 'operation', 'resource']


class AuditView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    read_roles = ADMIN
    queryset = AuditLog.objects.select_related('actor')
    serializer_class = AuditSerializer
    filterset_class = AuditFilter
    search_fields = ['operation', 'resource', 'actor__username', 'actor__display_name']
