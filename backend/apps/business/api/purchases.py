from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    PURCHASE_READERS,
)

from ..models import (
    PurchaseOrder,
)
from ..serializers import (
    PurchaseSerializer,
)
from ..services import supply
from .common import ReadView, key


class PurchaseView(ReadView):
    read_roles = PURCHASE_READERS
    write_roles = PURCHASE_READERS
    queryset = PurchaseOrder.objects.select_related('supplier', 'project').prefetch_related('lines__item')
    serializer_class = PurchaseSerializer
    filterset_fields = ['project', 'supplier', 'status']
    search_fields = ['code', 'supplier__name', 'project__name']

    def create(self, request):
        return Response(supply.create_purchase(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return Response(supply.submit(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return Response(supply.approve(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        return Response(supply.receive(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='cancel-remainder')
    def cancel_remainder(self, request, pk=None):
        return Response(supply.cancel_remainder(request.user, key(request), self.get_object().pk, request.data))
