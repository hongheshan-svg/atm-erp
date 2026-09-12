from rest_framework.decorators import action
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
from ..services import corrections
from .common import ReadView, key


class BOMView(ReadView):
    queryset = BOMLine.objects.select_related('item', 'project').prefetch_related('project__members')
    serializer_class = BOMSerializer
    filterset_fields = ['project', 'item']

    def get_queryset(self):
        return super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))

    @action(detail=True, methods=['post'])
    def remove(self, request, pk=None):
        return Response(corrections.remove_bom(request.user, key(request), pk, request.data))
