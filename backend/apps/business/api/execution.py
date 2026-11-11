from django.db.models import Q, Sum
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
from ..services import corrections, deletions, execution, milestones
from ..services.common import identity
from ..services.task_supervision import supervised_tasks
from ..task_milestones import PHASES, ordered_tasks
from .common import ImportableMixin, ReadView, key


class TaskFilter(filters.FilterSet):
    assignee = filters.NumberFilter(method='filter_assignee')
    supervisor = filters.NumberFilter(method='filter_supervisor')
    # 「进行中」只是未完成任务里已记录实际开始日期的那部分，不新增状态值。
    started = filters.BooleanFilter(method='filter_started')
    # 项目处于执行中、交付中或已验收（与 TaskSerializer.can_confirm 的项目状态口径一致）：
    # 主管代录工时入口按它取任务，不会因草稿、报价项目的任务排在前面而误判没有可确认任务。
    project_open = filters.BooleanFilter(method='filter_project_open')

    def filter_started(self, queryset, name, value):
        return queryset.filter(status='open', started_date__isnull=not value)

    def filter_project_open(self, queryset, name, value):
        scope = Q(project__status__in=execution.OPEN_PROJECT)
        return queryset.filter(scope) if value else queryset.exclude(scope)

    def filter_supervisor(self, queryset, name, value):
        return supervised_tasks(
            identity(value, 'supervisor'), queryset.exclude(project__status__in=['closed', 'cancelled'])
        )

    def filter_assignee(self, queryset, name, value):
        person = identity(value, 'assignee')
        return queryset.filter(Q(assignee_id=person) | Q(co_assignees__pk=person)).distinct()

    class Meta:
        model = Task
        # kind__in：工作台「生产与售后派工」按装配、调试、安装、售后多类任务一起列出，与工作台计数同一口径。
        fields = {
            'project': ['exact'],
            'kind': ['exact', 'in'],
            'milestone': ['exact'],
            'status': ['exact'],
            'assignee': ['exact'],
            'delivery': ['exact'],
        }


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
    def start(self, request, pk=None):
        return Response(execution.start_task(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='start-date')
    def start_date(self, request, pk=None):
        return Response(
            execution.start_task(request.user, key(request), self.get_object().pk, request.data, amend=True)
        )

    @action(detail=True, methods=['post'], url_path='completion-date')
    def completion_date(self, request, pk=None):
        return Response(execution.amend_task_completion(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def time(self, request, pk=None):
        return Response(execution.log_time(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'], url_path='time-records')
    def time_records(self, request, pk=None):
        task = self.get_object()
        # 已移出默认列表的流水仍是原始事实；任务核对需展示它们，才能解释净工时。
        records = (
            TimeEntry.objects.filter(task=task)
            .select_related('user', 'task__project', 'reversal')
            .prefetch_related('task__project__members')
            .annotate(archived=deletions.removed(TimeEntry))
        )
        totals = records.aggregate(total=Sum('hours'), mine=Sum('hours', filter=Q(user=request.user)))
        mine = request.query_params.get('mine', 'false')
        if mine not in {'true', 'false'}:
            raise ValidationError({'mine': '请选择是否只看本人工时。'})
        if mine == 'true':
            records = records.filter(user=request.user)
        page = self.paginate_queryset(records.order_by('-created_at', '-pk'))
        response = self.get_paginated_response(
            TimeSerializer(page, many=True, context=self.get_serializer_context()).data
        )
        response.data['summary'] = {
            'task_title': task.title,
            'logged_hours': str(totals['total'] or execution.ZERO),
            'my_hours': str(totals['mine'] or execution.ZERO),
        }
        return response

    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        return Response(execution.edit_task(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        return Response(execution.reschedule_task(request.user, key(request), self.get_object().pk, request.data))

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
    # 批次状态、安装人和验收负责人取自本批的安装、验收任务，一次预取。
    queryset = Delivery.objects.select_related('project').prefetch_related('tasks__assignee', 'tasks__co_assignees')
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
