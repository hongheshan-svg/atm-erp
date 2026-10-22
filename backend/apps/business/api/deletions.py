from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import ADMIN, PermissionMixin

from ..services import deletions
from .common import key


class DeletionSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    def get_actor_name(self, obj):
        return obj.actor.display_name or obj.actor.username

    class Meta:
        model = AuditLog
        fields = ['id', 'actor_name', 'created_at', 'detail']


class DeletionView(PermissionMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    read_roles = write_roles = ADMIN
    queryset = AuditLog.objects.filter(operation=deletions.OPERATION).select_related('actor')
    serializer_class = DeletionSerializer

    def get_queryset(self):
        resource = self.request.query_params.get('resource')
        deletions.resource_definition(resource)
        queryset = super().get_queryset().filter(detail__resource=resource)
        from ..services.common import identity

        for scope in ('project', 'sale', 'purchase'):
            value = self.request.query_params.get(scope)
            if value:
                queryset = queryset.filter(**{f'detail__record__{scope}': identity(value, scope)})
        return queryset

    def create(self, request):
        return Response(deletions.remove(request, key(request), request.data))
