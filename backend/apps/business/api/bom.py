from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.permissions import (
    projects_for,
)

from ..models import (
    BOMLine,
    Project,
)
from ..serializers import (
    BOMSerializer,
)
from ..services import bom, bom_export, corrections, tabular
from ..services.common import identity
from .common import ExportThrottle, ReadView, key


class BOMView(ReadView):
    queryset = BOMLine.objects.select_related('item', 'project').prefetch_related('project__members')
    serializer_class = BOMSerializer
    filterset_fields = ['project', 'item']

    def get_queryset(self):
        return super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))

    @action(detail=False, methods=['get', 'post'], throttle_classes=[ExportThrottle])
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        layout = 'standard'
        if request.method == 'POST':
            lines = bom_export.selected_rows(queryset, request.data)
            file_format = request.data.get('file_format', 'xlsx')
            layout = request.data.get('layout', 'standard')
        else:
            if queryset.count() > tabular.MAX_EXPORT:
                raise ValidationError('导出超过20000条，请缩小筛选范围。')
            lines = queryset
            file_format = request.query_params.get('file_format', 'csv')
        return bom_export.document(lines, file_format, layout)

    @action(detail=True, methods=['post'])
    def remove(self, request, pk=None):
        return Response(corrections.remove_bom(request.user, key(request), pk, request.data))

    @action(detail=True, methods=['post'])
    def replace(self, request, pk=None):
        return Response(corrections.replace_bom(request.user, key(request), pk, request.data))

    @action(detail=False, methods=['post'], url_path='remove-batch')
    def remove_batch(self, request):
        return Response(corrections.remove_bom_lines(request.user, key(request), request.data))

    @action(detail=False, methods=['get'])
    def changes(self, request):
        """项目成员可读的 BOM 变更记录：谁在什么时候把哪行从多少改成多少。"""
        project = get_object_or_404(
            projects_for(request.user, Project.objects.all()),
            pk=identity(request.query_params.get('project'), 'project'),
        )
        logs, lines = bom.change_log(project, request.query_params)
        page = self.paginate_queryset(logs)
        return self.get_paginated_response([bom.change_row(log, lines[log.resource]) for log in page])
