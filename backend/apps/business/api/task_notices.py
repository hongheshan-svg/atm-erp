from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.permissions import OPERATION_ROLES, PermissionMixin, projects_for

from ..models import Project, TaskNotice
from ..services.common import audit, fields, project_action, save
from .common import key


class TaskNoticeSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField(source='task.project_id', read_only=True)
    project_name = serializers.CharField(source='task.project.name', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = TaskNotice
        fields = ['id', 'task', 'project', 'project_name', 'task_title', 'message', 'created_at', 'read_at']


class TaskNoticeView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TaskNotice.objects.select_related('task__project')
    serializer_class = TaskNoticeSerializer
    write_roles = OPERATION_ROLES

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                recipient=self.request.user,
                task__is_deleted=False,
                task__project__in=projects_for(self.request.user, Project.objects.all()),
            )
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        unread = request.query_params.get('unread', 'true')
        if unread not in {'true', 'false'}:
            raise ValidationError({'unread': '请选择是否只看未读提醒。'})
        unread_count = queryset.filter(read_at__isnull=True).count()
        if unread == 'true':
            queryset = queryset.filter(read_at__isnull=True)
        page = self.paginate_queryset(queryset.order_by('-pk'))
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data['unread_count'] = unread_count
        return response

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        source = self.get_object()

        def execute(user, project):
            fields(request.data, set())
            notice = self.get_queryset().select_for_update(of=('self',)).get(pk=source.pk)
            if notice.read_at is None:
                notice.read_at = timezone.now()
                save(notice, user)
                return audit(user, 'task.notice-read', notice)
            return {'id': notice.pk}

        return Response(
            project_action(
                request.user,
                key(request),
                'task.notice-read',
                source.task.project_id,
                {'notice': source.pk},
                OPERATION_ROLES,
                execute,
            )
        )
