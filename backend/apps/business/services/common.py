import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import AuditLog
from apps.core.permissions import require_project, require_role

from ..models import Item, Project, Stock

ZERO = Decimal('0')


def fields(data, allowed):
    if not isinstance(data, dict):
        raise ValidationError('请提交 JSON 对象。')
    unknown = set(data) - set(allowed)
    if unknown:
        raise ValidationError({key: '不支持此字段。' for key in sorted(unknown)})


def text(data, key, *, default=None, maximum=500):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value.strip()) > maximum or (default is None and not value.strip()):
        raise ValidationError({key: f'请填写不超过 {maximum} 字符的文本。'})
    return value.strip()


def identity(value, key='id'):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]{0,18}', str(value)):
        raise ValidationError({key: '必须是有效的正整数标识。'})
    result = int(value)
    if result > 9223372036854775807:
        raise ValidationError({key: '标识超出范围。'})
    return result


def integer(data, key, default, minimum=0, maximum=1000000):
    value = data.get(key, default)
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,10}', str(value)) or not minimum <= int(value) <= maximum:
        raise ValidationError({key: f'必须为 {minimum} 至 {maximum} 的整数。'})
    return int(value)


def number(value, key, places=2, *, positive=False):
    try:
        if isinstance(value, bool) or len(str(value)) > 64:
            raise ValueError
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result >= Decimal(10) ** (18 - places):
            raise ValueError
        rounded = result.quantize(Decimal(10) ** -places)
        if result != rounded or (positive and result == 0):
            raise ValueError
        return rounded
    except (ValueError, InvalidOperation):
        raise ValidationError({key: f'请输入范围内的{"正数" if positive else "非负数"}，最多 {places} 位小数。'})


def rounded(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def day(data, key, *, optional=False):
    value = data.get(key)
    if optional and value in (None, ''):
        return None
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({key: '请填写有效日期 YYYY-MM-DD。'})


def rows(data, key='lines'):
    value = data.get(key)
    if not isinstance(value, list) or not 1 <= len(value) <= 1000 or not all(isinstance(row, dict) for row in value):
        raise ValidationError({key: '请提供 1 至 1000 行有效明细。'})
    return value


def lookup(model, value, key='id', **filters):
    return get_object_or_404(model.objects, pk=identity(value, key), **filters)


def save(obj, actor):
    if obj._state.adding:
        obj.created_by = actor
    obj.updated_by = actor
    obj.full_clean()
    obj.save()
    return obj


def audit(actor, operation, obj, **detail):
    AuditLog.objects.create(
        actor=actor, operation=operation, resource=f'{obj._meta.model_name}:{obj.pk}', detail=detail
    )
    return {'id': obj.pk}


def state(obj, allowed):
    if obj.status not in allowed:
        raise Conflict('当前状态不允许此操作，请刷新后确认。')


def project_action(actor, key, operation, project_id, data, roles, execute):
    context = {}

    def authorize(current_actor):
        require_role(current_actor, roles)
        project = get_object_or_404(Project.objects.select_for_update(), pk=identity(project_id, 'project'))
        current_actor.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        require_role(current_actor, roles)
        require_project(current_actor, project)
        context['project'] = project

    return perform(
        actor=actor,
        key=key,
        operation=operation,
        payload={'project': project_id, 'data': data},
        authorize=authorize,
        execute=lambda user: execute(user, context['project']),
    )


def lock_items(item_ids):
    ids = sorted(set(item_ids))
    items = list(Item.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    if len(items) != len(ids):
        raise ValidationError('物料不存在或已删除。')
    return {item.pk: item for item in items}


def lock_stocks(item_ids, location, actor):
    items = lock_items(item_ids)
    stocks = {}
    for item_id in sorted(items):
        stock, _ = Stock.objects.get_or_create(
            item_id=item_id, location=location, defaults={'created_by': actor, 'updated_by': actor}
        )
        stocks[item_id] = Stock.objects.select_for_update().get(pk=stock.pk)
    return stocks
