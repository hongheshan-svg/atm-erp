from django.db.models import Q
from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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
from ..services import corrections, execution, milestones
from ..services.common import identity
from ..task_milestones import PHASES, ordered_tasks
from .common import ImportableMixin, ReadView, key


class TaskFilter(filters.FilterSet):
    assignee = filters.NumberFilter(method='filter_assignee')

    def filter_assignee(self, queryset, name, value):
        person = identity(value, 'assignee')
        return queryset.filter(Q(assignee_id=person) | Q(co_assignees__pk=person)).distinct()

    class Meta:
        model = Task
        fields = ['project', 'kind', 'milestone', 'status', 'assignee', 'delivery']


class TaskView(ImportableMixin, ReadView):
    queryset = execution.with_task_flags(
        Task.objects.select_related('assignee', 'project', 'delivery', 'entry').prefetch_related(
            'project__members', 'co_assignees'
        )
    )
    serializer_class = TaskSerializer
    filterset_class = TaskFilter
    search_fields = [
        'title',
        'project__code',
        'project__name',
        'assignee__display_name',
        'assignee__username',
        'co_assignees__display_name',
        'co_assignees__username',
    ]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))
        phase = self.request.query_params.get('phase')
        if phase:
            if phase not in dict(PHASES):
                raise ValidationError({'phase': '请选择有效的项目阶段。'})
            kinds = [phase, 'install', 'acceptance'] if phase == 'site' else [phase]
            queryset = queryset.filter(kind__in=kinds)
        return ordered_tasks(queryset)

    def create(self, request):
        return Response(execution.create_task(request.user, key(request), request.data), status=201)

    @action(detail=False, methods=['get'], url_path='milestone-template')
    def milestone_template(self, request):
        return Response(milestones.template(request.user, request.query_params.get('project')))

    @action(detail=False, methods=['get'], url_path='milestone-summary')
    def milestone_summary(self, request):
        return Response(milestones.summary(request.user, request.query_params.get('project')))

    @action(detail=False, methods=['post'], url_path='apply-milestones')
    def apply_milestones(self, request):
        return Response(milestones.apply_template(request.user, key(request), request.data), status=201)

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


class DeliveryView(ImportableMixin, ReadView):
    queryset = Delivery.objects.select_related('project')
    serializer_class = DeliverySerializer
    filterset_fields = ['project']

    def get_queryset(self):
        return super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        return Response(execution.accept(request.user, key(request), self.get_object().pk, request.data))


class TimeView(ImportableMixin, ReadView):
    queryset = TimeEntry.objects.select_related('user', 'task__project', 'reversal').prefetch_related(
        'task__project__members'
    )
    serializer_class = TimeSerializer
    filterset_fields = ['task', 'task__project', 'user', 'date']

    def get_queryset(self):
        return super().get_queryset().filter(task__project__in=projects_for(self.request.user, Project.objects.all()))

    @action(detail=True, methods=['post'])
    def amend(self, request, pk=None):
        return Response(execution.amend_time(request.user, key(request), self.get_object().pk, request.data))
