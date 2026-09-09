from rest_framework.response import Response

from apps.core.permissions import (
    PURCHASERS,
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


class PartnerView(MasterView):
    queryset = Partner.objects.all()
    serializer_class = PartnerSerializer
    filterset_fields = ['is_active', 'kind']
