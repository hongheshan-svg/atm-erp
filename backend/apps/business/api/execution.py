from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import (
    projects_for,
)

from ..models import (
    Delivery,
    Project,
    Task,
    TimeEntry,
)
from ..serializers import (
    DeliverySerializer,
    TaskSerializer,
    TimeSerializer,
)
from ..services import corrections, execution
from .common import ReadView, key


class TaskView(ReadView):
    queryset = Task.objects.select_related('assignee', 'project')
    serializer_class = TaskSerializer
    filterset_fields = ['project', 'kind', 'status', 'assignee', 'delivery']

    def get_queryset(self):
        return super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))

    def create(self, request):
        return Response(execution.create_task(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        return Response(execution.complete_task(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def time(self, request, pk=None):
        return Response(execution.log_time(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        return Response(
            corrections.change_task(request.user, key(request), self.get_object().pk, request.data, 'assign')
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return Response(
            corrections.change_task(request.user, key(request), self.get_object().pk, request.data, 'cancel')
        )

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        return Response(
            corrections.change_task(request.user, key(request), self.get_object().pk, request.data, 'reopen')
        )


class DeliveryView(ReadView):
    queryset = Delivery.objects.select_related('project')
    serializer_class = DeliverySerializer
    filterset_fields = ['project']

    def get_queryset(self):
        return super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        return Response(execution.accept(request.user, key(request), self.get_object().pk, request.data))


class TimeView(ReadView):
    queryset = TimeEntry.objects.select_related('user', 'task', 'reversal')
    serializer_class = TimeSerializer
    filterset_fields = ['task', 'task__project', 'user', 'date']

    def get_queryset(self):
        return super().get_queryset().filter(task__project__in=projects_for(self.request.user, Project.objects.all()))

    @action(detail=True, methods=['post'])
    def amend(self, request, pk=None):
        return Response(execution.amend_time(request.user, key(request), self.get_object().pk, request.data))
