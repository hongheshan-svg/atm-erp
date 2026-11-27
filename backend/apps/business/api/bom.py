from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.core.permissions import (
    BOM_WRITERS,
    projects_for,
    require_project,
)

from ..models import (
    BOMLine,
    Project,
)
from ..serializers import (
    BOMSerializer,
)
from ..services import bom, bom_export, corrections, revisions, tabular
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
            tabular.check_export_size(queryset.count())
            lines = queryset
            file_format = request.query_params.get('file_format', 'csv')
        return bom_export.document(lines, file_format, layout)

    @action(detail=True, methods=['post'])
    def remove(self, request, pk=None):
        return Response(corrections.remove_bom(request.user, key(request), pk, request.data))

    @action(detail=True, methods=['post'])
    def replace(self, request, pk=None):
        return Response(corrections.replace_bom(request.user, key(request), pk, request.data))

    @action(detail=True, methods=['post'])
    def upgrade(self, request, pk=None):
        return Response(revisions.upgrade(request.user, key(request), pk, request.data))

    @action(detail=True, methods=['get'], url_path='upgrade-scope')
    def upgrade_scope(self, request, pk=None):
        """升版时可勾选一并换版的其他项目（同一物料仍在其 BOM 中），并标明当前用户能否维护。"""
        line = self.get_object()
        require_project(request.user, line.project, BOM_WRITERS)
        if not line.item.drawing_number:
            raise ValidationError('只有带图号的物料可以升版；换成其他型号请用「替换物料」。')
        return Response(revisions.scope(request.user, line))

    @action(detail=True, methods=['get'], url_path='revision-impact')
    def revision_impact(self, request, pk=None):
        """升版、替换物料前的影响预估：旧版在途怎么转，换版后旧版待处理大约多少。"""
        return Response(revisions.impact(request.user, self.get_object()))

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


class RevisionChangeView(viewsets.ViewSet):
    """换版记录上的旧版处理：报废、留作备件和开返修采购单；角色与项目范围由服务层按项目判断。"""

    parser_classes = [JSONParser]

    @action(detail=True, methods=['post'])
    def dispose(self, request, pk=None):
        return Response(revisions.dispose(request.user, key(request), pk, request.data))

    @action(detail=True, methods=['post'])
    def rework(self, request, pk=None):
        return Response(revisions.rework(request.user, key(request), pk, request.data))
