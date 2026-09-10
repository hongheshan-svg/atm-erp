from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.models import CodeRule
from apps.core.permissions import MANAGERS, has_role, require_role

from ..models import Partner, Project
from .common import (
    audit,
    day,
    fields,
    identity,
    integer,
    lookup,
    save,
    text,
)


def create_record(user, data):
    fields(
        data,
        {
            'name',
            'customer',
            'manager',
            'members',
            'requirements',
            'due_date',
            'equipment_quantity',
            'warranty_months',
        },
    )
    customer = lookup(Partner, data.get('customer'), 'customer', is_active=True, kind__in=['customer', 'both'])
    manager = lookup(User, data.get('manager'), 'manager', is_active=True)
    if not has_role(manager, MANAGERS):
        raise ValidationError({'manager': '项目负责人必须是启用的管理员或项目经理。'})
    member_ids = data.get('members', [])
    if not isinstance(member_ids, list) or len(member_ids) > 500:
        raise ValidationError({'members': '项目成员必须为用户标识数组。'})
    member_ids = {identity(value, 'members') for value in member_ids}
    members = list(User.objects.filter(pk__in=member_ids, is_active=True))
    if len(members) != len(member_ids):
        raise ValidationError({'members': '包含不存在或已停用的成员。'})
    project = save(
        Project(
            code=CodeRule.generate_code('project'),
            status='active',
            name=text(data, 'name', maximum=150),
            customer=customer,
            manager=manager,
            requirements=text(data, 'requirements', default='', maximum=20000),
            due_date=day(data, 'due_date', optional=True),
            equipment_quantity=integer(data, 'equipment_quantity', 1, minimum=1),
            warranty_months=integer(data, 'warranty_months', 12, maximum=120),
        ),
        user,
    )
    project.members.set(members)
    audit(user, 'project.create', project)
    return project


def create_project(actor, key, data):
    return perform(
        actor=actor,
        key=key,
        operation='project.create',
        payload=data,
        authorize=lambda user: require_role(user, MANAGERS),
        execute=lambda user: {'id': create_record(user, data).pk},
    )
