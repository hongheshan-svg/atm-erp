from django.db.models import OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce, TruncDate
from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import Company
from apps.core.permissions import (
    PURCHASE_READERS,
    WAREHOUSE,
    require_project,
    require_role,
)

from ..models import (
    IssueSlip,
    Stock,
    StockMove,
)
from ..serializers import (
    IssueSlipDetailSerializer,
    IssueSlipSerializer,
    MoveSerializer,
    StockSerializer,
)
from ..services import inventory
from .common import ImportableMixin, ReadView, key

# 每个库位行最近一次采购合格入库的日期（历史流水无实际收货日时按登记当天），列表一条子查询带出。
LAST_RECEIPT = (
    StockMove.objects.filter(stock=OuterRef('pk'), kind='receipt')
    .annotate(day=Coalesce('received_date', TruncDate('created_at')))
    .order_by('-day', '-id')
    .values('day')[:1]
)


class StockView(ImportableMixin, ReadView):
    read_roles = PURCHASE_READERS
    queryset = Stock.objects.select_related('item').annotate(last_received_date=Subquery(LAST_RECEIPT))
    serializer_class = StockSerializer
    # 库位和品牌按关键词匹配；精确匹配要求把完整值输对，实际用起来只会得到空列表。
    # id__in：库存页勾选批量领料时一次重读所选库存行的当前数量。
    filterset_fields = {
        'id': ['in'],
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

    @action(detail=False, methods=['get', 'post'], url_path='bom-issue')
    def bom_issue(self, request):
        """按项目 BOM 批量领料：GET 列出本项目未领完且有库存的物料与预填数量，POST 一次出库多行。"""
        if request.method == 'POST':
            return Response(inventory.issue_batch(request.user, key(request), request.data))
        from django.shortcuts import get_object_or_404

        from ..models import Project
        from ..services.common import identity

        require_role(request.user, WAREHOUSE)
        project = get_object_or_404(Project.objects, pk=identity(request.query_params.get('project'), 'project'))
        require_project(request.user, project, WAREHOUSE)
        return Response(inventory.bom_issue_lines(project))

    @action(detail=True, methods=['post'])
    def count(self, request, pk=None):
        return Response(inventory.count(request.user, key(request), self.get_object().pk, request.data))


class MoveView(ImportableMixin, ReadView):
    read_roles = PURCHASE_READERS
    queryset = StockMove.objects.select_related(
        'stock__item', 'project', 'purchase_line__purchase', 'slip', 'created_by'
    )
    serializer_class = MoveSerializer
    filterset_fields = ['project', 'stock', 'kind', 'slip']

    @action(detail=True, methods=['post'], url_path='return-material')
    def return_material(self, request, pk=None):
        return Response(inventory.return_material(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='return-purchase')
    def return_purchase(self, request, pk=None):
        return Response(inventory.return_purchase(request.user, key(request), self.get_object().pk, request.data))


class IssueSlipFilter(filters.FilterSet):
    # 按领料日期（本地日期）筛选。
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = IssueSlip
        fields = ['project', 'task']


class IssueSlipView(ReadView):
    """领料单只读：读取范围与库存流水相同（采购、仓库、财务等岗位；按项目范围过滤）。"""

    read_roles = PURCHASE_READERS
    queryset = IssueSlip.objects.select_related('project', 'task', 'created_by').prefetch_related(
        Prefetch('moves', queryset=StockMove.objects.select_related('stock__item').order_by('pk'))
    )
    serializer_class = IssueSlipSerializer
    filterset_class = IssueSlipFilter
    search_fields = ['code', 'project__code', 'project__name', 'moves__stock__item__code', 'moves__stock__item__name']

    def get_serializer_class(self):
        return IssueSlipDetailSerializer if self.action == 'retrieve' else IssueSlipSerializer

    def retrieve(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_object()).data
        # 打印抬头用公司名称；未完成公司资料时留空。
        data['company_name'] = Company.objects.filter(pk=1).values_list('name', flat=True).first() or ''
        return Response(data)
