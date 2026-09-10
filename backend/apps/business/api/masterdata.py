from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    OPERATION_ROLES,
    PURCHASERS,
    has_role,
)

from ..models import (
    Item,
    Partner,
)
from ..serializers import (
    ItemSerializer,
    PartnerSerializer,
)
from ..services import masterdata
from .common import ReadView, key


class MasterView(ReadView):
    write_roles = PURCHASERS
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']

    def create(self, request):
        return Response(
            masterdata.masterdata(request.user, key(request), self.queryset.model, request.data), status=201
        )

    def partial_update(self, request, pk=None):
        obj = self.get_object()
        return Response(masterdata.masterdata(request.user, key(request), self.queryset.model, request.data, obj.pk))


class ItemView(MasterView):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    filterset_fields = ['is_active', 'brand', 'part_type']
    search_fields = ['code', 'name', 'specification', 'brand']

    @action(detail=False, methods=['get'])
    def similar(self, request):
        name = masterdata.normalized(request.query_params.get('name', ''))[:150]
        items = Item.objects.filter(name__icontains=name).order_by('code')[:10] if name else []
        return Response(self.get_serializer(items, many=True).data)


class PartnerView(MasterView):
    read_roles = OPERATION_ROLES | {'sales_manager'}
    write_roles = PURCHASERS | {'sales_manager'}
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer
    filterset_fields = ['is_active', 'kind']

    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset.filter(kind__in=['customer', 'both'])
            if not has_role(self.request.user, OPERATION_ROLES)
            else queryset
        )
