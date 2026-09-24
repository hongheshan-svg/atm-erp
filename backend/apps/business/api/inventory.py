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
from .common import ImportableMixin, ReadView, key


class StockView(ImportableMixin, ReadView):
    read_roles = PURCHASE_READERS
    queryset = Stock.objects.select_related('item')
    serializer_class = StockSerializer
    # 库位和品牌按关键词匹配；精确匹配要求把完整值输对，实际用起来只会得到空列表。
    filterset_fields = {
        'item': ['exact'],
        'location': ['exact', 'icontains'],
        'item__brand': ['exact', 'icontains'],
        'item__part_type': ['exact'],
    }
    search_fields = ['item__code', 'item__name', 'item__specification', 'item__brand']

    @action(detail=False, methods=['get'])
    def locations(self, request):
        """已使用的库位，供收货和期初选择，避免同一库位手工录成多种写法。"""
        return Response(sorted(set(Stock.objects.values_list('location', flat=True))))

    @action(detail=False, methods=['post'])
    def opening(self, request):
        return Response(inventory.opening(request.user, key(request), request.data))

    @action(detail=False, methods=['post'])
    def issue(self, request):
        return Response(inventory.issue(request.user, key(request), request.data))

    @action(detail=True, methods=['post'])
    def count(self, request, pk=None):
        return Response(inventory.count(request.user, key(request), self.get_object().pk, request.data))


class MoveView(ImportableMixin, ReadView):
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
