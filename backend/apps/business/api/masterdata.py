from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    ITEM_WRITERS,
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
from .common import ImportableMixin, ReadView, key


class MasterView(ImportableMixin, ReadView):
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
    write_roles = ITEM_WRITERS
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    # 品牌按关键词匹配：精确匹配要求输对完整品牌名，换个写法就只剩空列表。
    filterset_fields = {
        'is_active': ['exact'],
        'brand': ['exact', 'icontains'],
        'part_type': ['exact'],
        'product_category': ['exact'],
    }
    search_fields = ['code', 'name', 'specification', 'brand', 'drawing_number']

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'revision_hints': self.action in {'list', 'retrieve', 'similar'}}

    @action(detail=True, methods=['get'])
    def revisions(self, request, pk=None):
        """同图号的全部版本与可见项目里的换版记录。"""
        from ..services.revision_chain import history

        return Response(history(request.user, self.get_object()))

    @action(detail=False, methods=['get'])
    def similar(self, request):
        items = masterdata.similar({key: request.query_params.get(key, '')[:2000] for key in ('name', 'specification')})
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
