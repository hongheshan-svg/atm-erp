from rest_framework.views import APIView

from apps.core.api import Pagination
from apps.core.permissions import ADMIN, PermissionMixin

from ..services import data_checks
from .common import ExportThrottle


class DataCheckView(PermissionMixin, APIView):
    """Administrator-only, read-only checklist; corrections stay on the original forms."""

    read_roles = write_roles = ADMIN
    http_method_names = ['get', 'head', 'options']

    def get_throttles(self):
        throttles = super().get_throttles()
        return [*throttles, ExportThrottle()] if self.request.query_params.get('file_format') else throttles

    def get(self, request):
        selected = request.query_params.get('category')
        file_format = request.query_params.get('file_format')
        if file_format:
            return data_checks.export(selected, file_format)
        result = data_checks.report(selected)
        paginator = Pagination()
        page = paginator.paginate_queryset(result.pop('rows'), request, view=self)
        response = paginator.get_paginated_response(page)
        response.data.update(result)
        return response
