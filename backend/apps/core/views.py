from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import AuditLog, CodeRule, Company
from .permissions import ADMIN, PermissionMixin


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok', 'schema': 'lean-erp-v1'})


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'address', 'phone']
        read_only_fields = ['id']


class CompanyView(PermissionMixin, mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Company.objects.filter(pk=1)
    serializer_class = CompanySerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        from django.db import transaction

        with transaction.atomic():
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
    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'operation', 'resource', 'detail', 'created_at']


class AuditView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    read_roles = ADMIN
    queryset = AuditLog.objects.all()
    serializer_class = AuditSerializer
