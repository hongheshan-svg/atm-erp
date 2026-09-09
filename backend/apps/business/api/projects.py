from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import (
    MANAGERS,
    MONEY_READERS,
    projects_for,
    require_role,
)

from ..models import (
    Project,
)
from ..serializers import (
    ProjectSerializer,
)
from ..services import bom, bom_import, corrections, execution, finance, projects
from .common import ReadView, key


class ProjectView(ReadView):
    queryset = Project.objects.select_related('customer', 'manager', 'sale').prefetch_related('members')
    serializer_class = ProjectSerializer
    write_roles = MANAGERS
    search_fields = ['code', 'name']
    filterset_fields = ['status', 'customer', 'manager']

    def get_queryset(self):
        return projects_for(self.request.user, super().get_queryset())

    def create(self, request):
        return Response(projects.create_project(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['get'])
    def demand(self, request, pk=None):
        project = self.get_object()
        return Response({'revision': bom.revision(project), 'lines': bom.demand(project)})

    @action(detail=True, methods=['post'], url_path='revise-bom')
    def revise_bom(self, request, pk=None):
        return Response(bom.revise_bom(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'])
    def cost(self, request, pk=None):
        require_role(request.user, MONEY_READERS)
        return Response(finance.cost(self.get_object()))

    @action(detail=True, methods=['post'], url_path='import-preview', parser_classes=[MultiPartParser])
    def import_preview(self, request, pk=None):
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError({'file': '请提交一个表格文件。'})
        return Response(bom_import.preview(self.get_object(), request.FILES['file']))

    @action(detail=False, methods=['get'], url_path='bom-template')
    def bom_template(self, request):
        require_role(request.user, MANAGERS)
        response = HttpResponse(
            ('\ufeff' + ','.join(bom_import.HEADERS) + '\r\n').encode('utf-8'), content_type='text/csv; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename="bom-template.csv"'
        return response

    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        return Response(corrections.edit_project(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return Response(corrections.cancel_project(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        return Response(corrections.reopen_project(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        return Response(execution.close(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        return Response(execution.ship(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def service(self, request, pk=None):
        return Response(execution.service(request.user, key(request), self.get_object().pk, request.data))
