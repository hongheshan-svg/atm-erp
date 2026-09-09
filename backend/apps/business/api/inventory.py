from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    PURCHASE_READERS,
)

from ..models import (
    Stock,
    StockMove,
)
from ..serializers import (
    MoveSerializer,
    StockSerializer,
)
from ..services import inventory
from .common import ReadView, key


class StockView(ReadView):
    read_roles = PURCHASE_READERS
    queryset = Stock.objects.select_related('item')
    serializer_class = StockSerializer
    filterset_fields = ['item', 'location']

    @action(detail=False, methods=['post'])
    def opening(self, request):
        return Response(inventory.opening(request.user, key(request), request.data))

    @action(detail=False, methods=['post'])
    def issue(self, request):
        return Response(inventory.issue(request.user, key(request), request.data))

    @action(detail=True, methods=['post'])
    def count(self, request, pk=None):
        return Response(inventory.count(request.user, key(request), self.get_object().pk, request.data))


class MoveView(ReadView):
    read_roles = PURCHASE_READERS
    queryset = StockMove.objects.select_related('stock__item')
    serializer_class = MoveSerializer
    filterset_fields = ['project', 'stock', 'kind']

    @action(detail=True, methods=['post'], url_path='return-material')
    def return_material(self, request, pk=None):
        return Response(inventory.return_material(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='return-purchase')
    def return_purchase(self, request, pk=None):
        return Response(inventory.return_purchase(request.user, key(request), self.get_object().pk, request.data))
