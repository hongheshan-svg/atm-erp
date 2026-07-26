from django.db.models import Q

from apps.core.permission_service import has_permission


def can_manage_workflows(user):
    return bool(user and user.is_authenticated and (user.is_superuser or has_permission(user, 'workflow:config')))


def visible_workflow_instances(queryset, user):
    if can_manage_workflows(user):
        return queryset
    return queryset.filter(Q(submitter=user) | Q(tasks__assignee=user)).distinct()
