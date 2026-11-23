from rest_framework.views import APIView

from apps.core.api import Pagination

from ..services import material_tracking
from .common import ExportThrottle


class MaterialTrackingView(APIView):
    """物料跟踪总表：跨项目「项目×物料」一行，分页列出；能看 BOM 的人都能看，项目范围与 BOM 相同。"""

    def get(self, request):
        rows = material_tracking.tracked(request.user, request.query_params)
        paginator = Pagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(material_tracking.visible(request.user, page))


class MaterialTrackingExportView(APIView):
    """按当前筛选导出全部跟踪行（Excel 或 CSV），列按岗位与列表相同的规则取舍。"""

    throttle_classes = [ExportThrottle]

    def get(self, request):
        return material_tracking.export(
            request.user, request.query_params, request.query_params.get('file_format', 'csv')
        )
