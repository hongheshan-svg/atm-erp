from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.models import CodeRule
from apps.core.permissions import PURCHASERS, require_role, role

from ..models import Item, Partner
from .common import (
    audit,
    fields,
    identity,
    save,
    text,
)


def masterdata(actor, key, model, data, object_id=None):
    def authorize(user):
        require_role(user, PURCHASERS | ({'sales_manager'} if model is Partner else set()))
        if role(user) == 'sales_manager':
            current = model.objects.select_for_update().get(pk=identity(object_id)) if object_id else None
            if data.get('kind', current.kind if current else None) != 'customer' or (
                current and current.kind != 'customer'
            ):
                raise PermissionDenied('销售经理只能维护纯客户资料。')

    allowed = {'name', 'is_active'} | (
        {'specification', 'unit', 'brand', 'part_type'}
        if model is Item
        else {'kind', 'contact', 'phone', 'address', 'payment_term', 'payment_days'}
    )
    if model is Item and not object_id:
        allowed.add('code')

    def execute(user):
        fields(data, allowed)
        if (
            model is Item
            and 'part_type' in data
            and (not isinstance(data['part_type'], str) or data['part_type'] not in {'', *Item.PartType.values})
        ):
            raise ValidationError({'part_type': '请选择标准件或非标件，未分类可留空。'})
        obj = model.objects.select_for_update().get(pk=identity(object_id)) if object_id else model()
        if role(user) == 'sales_manager' and (
            model is not Partner or data.get('kind', obj.kind) != 'customer' or (object_id and obj.kind != 'customer')
        ):
            raise PermissionDenied('销售经理只能维护纯客户资料，不能修改供应商或双用途往来单位。')
        if not object_id:
            # Manual and automatic item codes share the same lock and uniqueness domain.
            if model is Item:
                CodeRule.objects.select_for_update().get(key='item')
            custom = text(data, 'code', default='', maximum=30) if model is Item else ''
            if custom and Item.all_objects.filter(code=custom).exists():
                raise ValidationError({'code': '物料编码已使用，包括停用或已删除记录。'})
            obj.code = custom or CodeRule.generate_code('item' if model is Item else 'partner')
        if model is Partner:
            from .payment_terms import terms

            values = terms(data, obj)
            if data.get('kind', obj.kind) == 'customer' and values['payment_term'] != 'manual':
                raise ValidationError({'payment_term': '采购账期仅适用于供应商。'})
            for field, value in values.items():
                setattr(obj, field, value)
        for field in allowed - {'is_active', 'code', 'payment_term', 'payment_days'}:
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
        authorize=authorize,
        execute=execute,
    )
