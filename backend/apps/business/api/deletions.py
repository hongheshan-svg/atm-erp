from django.db.models import F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce, NullIf
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditLog
from apps.core.permissions import ADMIN, PermissionMixin

from ..services import deletions
from .common import key


class DeletionSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    restored = serializers.SerializerMethodField()
    restored_at = serializers.DateTimeField(read_only=True)
    restored_by = serializers.CharField(read_only=True)

    def get_actor_name(self, obj):
        return obj.actor.display_name or obj.actor.username

    def get_restored(self, obj):
        return obj.restored_at is not None

    class Meta:
        model = AuditLog
        fields = ['id', 'actor_name', 'created_at', 'detail', 'restored', 'restored_at', 'restored_by']


class DeletionView(PermissionMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    read_roles = write_roles = ADMIN
    queryset = AuditLog.objects.filter(operation=deletions.OPERATION).select_related('actor')
    serializer_class = DeletionSerializer

    def get_queryset(self):
        resource = self.request.query_params.get('resource')
        deletions.resource_definition(resource)
        # The restore answering a deletion is the next restore of the same record (one subquery per column).
        later = AuditLog.objects.filter(
            operation=deletions.RESTORE, resource=OuterRef('resource'), pk__gt=OuterRef('pk')
        ).order_by('pk')
        restorer = Coalesce(NullIf(F('actor__display_name'), Value('')), F('actor__username'))
        queryset = (
            super()
            .get_queryset()
            .filter(detail__resource=resource)
            .annotate(
                restored_at=Subquery(later.values('created_at')[:1]),
                restored_by=Subquery(later.annotate(name=restorer).values('name')[:1]),
            )
        )
        from ..services.common import identity

        for scope in ('project', 'sale', 'purchase'):
            value = self.request.query_params.get(scope)
            if value:
                queryset = queryset.filter(**{f'detail__record__{scope}': identity(value, scope)})
        return queryset

    def create(self, request):
        return Response(deletions.remove(request, key(request), request.data))

    @action(detail=False, methods=['post'])
    def restore(self, request):
        return Response(deletions.restore(request, key(request), request.data))
