from rest_framework.exceptions import ValidationError

from apps.core.actions import perform
from apps.core.models import CodeRule
from apps.core.permissions import PURCHASERS, require_role

from ..models import Item
from .common import (
    audit,
    fields,
    identity,
    save,
    text,
)


def masterdata(actor, key, model, data, object_id=None):
    allowed = {'name', 'is_active'} | (
        {'specification', 'unit'} if model is Item else {'kind', 'contact', 'phone', 'address'}
    )

    def execute(user):
        fields(data, allowed)
        obj = model.objects.select_for_update().get(pk=identity(object_id)) if object_id else model()
        if not object_id:
            obj.code = CodeRule.generate_code('item' if model is Item else 'partner')
        for field in allowed - {'is_active'}:
            if field in data or (not object_id and field in {'name', 'kind'}):
                setattr(
                    obj,
                    field,
                    text(
                        data,
                        field,
                        maximum=obj._meta.get_field(field).max_length,
                        default=None if field in {'name', 'kind', 'unit'} else '',
                    ),
                )
        if 'is_active' in data:
            if not isinstance(data['is_active'], bool):
                raise ValidationError({'is_active': '必须为布尔值。'})
            obj.is_active = data['is_active']
        save(obj, user)
        return audit(user, f'{model._meta.model_name}.save', obj, fields=sorted(data))

    return perform(
        actor=actor,
        key=key,
        operation=f'{model._meta.model_name}.save',
        payload={'id': object_id, 'data': data},
        authorize=lambda user: require_role(user, PURCHASERS),
        execute=execute,
    )
