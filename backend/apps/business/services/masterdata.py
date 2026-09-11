import unicodedata

from django.db.models.functions import Lower, Trim
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.models import CodeRule
from apps.core.permissions import PURCHASERS, has_role, require_role

from ..models import Item, Partner
from .common import (
    audit,
    fields,
    identity,
    save,
    text,
)


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).split())


def duplicates(data, exclude=None):
    name = normalized(str(data.get('name', '')))
    if not name:
        return []
    candidates = (
        Item.objects.annotate(clean_name=Lower(Trim('name'))).filter(clean_name=name.lower()).exclude(pk=exclude)
    )
    keys = ('specification', 'brand', 'unit', 'part_type', 'product_category', 'drawing_number', 'drawing_revision')
    return [
        item
        for item in candidates
        if all(
            normalized(getattr(item, key)).casefold()
            == normalized(str(data.get(key, '件' if key == 'unit' else ''))).casefold()
            for key in keys
        )
    ]


def masterdata(actor, key, model, data, object_id=None):
    def authorize(user):
        require_role(user, PURCHASERS | ({'sales_manager'} if model is Partner else set()))
        if not has_role(user, PURCHASERS):
            current = model.objects.select_for_update().get(pk=identity(object_id)) if object_id else None
            if data.get('kind', current.kind if current else None) != 'customer' or (
                current and current.kind != 'customer'
            ):
                raise PermissionDenied('销售经理只能维护纯客户资料。')

    allowed = {'name', 'is_active'} | (
        {'specification', 'unit', 'brand', 'part_type', 'product_category', 'drawing_number', 'drawing_revision'}
        if model is Item
        else {'kind', 'contact', 'phone', 'address', 'payment_term', 'payment_days'}
    )
    if model is Item and not object_id:
        allowed.add('code')
    if model is Item:
        allowed.add('duplicate_reason')

    def execute(user):
        fields(data, allowed)
        if (
            model is Item
            and 'part_type' in data
            and (not isinstance(data['part_type'], str) or data['part_type'] not in {'', *Item.PartType.values})
        ):
            raise ValidationError({'part_type': '请选择标准件或非标件，未分类可留空。'})
        obj = model.objects.select_for_update().get(pk=identity(object_id)) if object_id else model()
        category = ''
        if model is Item:
            category = data.get('product_category', obj.product_category)
            if category not in ('', *Item.ProductCategory.values):
                raise ValidationError({'product_category': '请选择规范中的产品编码类别。'})
            if (
                object_id
                and obj.product_category
                and any(
                    field in data and data[field] != getattr(obj, field)
                    for field in ('product_category', 'specification', 'drawing_number', 'drawing_revision')
                )
            ):
                raise ValidationError('已编码产品的类别、型号或图档版本不能覆盖；版本升级请新增物料编码并修订 BOM。')
            if category and not text(data, 'specification', default=obj.specification, maximum=2000):
                raise ValidationError({'specification': '规范要求所有产品填写型号/规格。'})
            if category.startswith('1') and not text(data, 'drawing_number', default=obj.drawing_number, maximum=100):
                raise ValidationError({'drawing_number': '有图产品必须填写图号。'})
        if not has_role(user, PURCHASERS) and (
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
            obj.code = custom or CodeRule.generate_code(
                'item' if model is Item else 'partner', product_category=category
            )
        if model is Partner:
            from .payment_terms import terms

            values = terms(data, obj)
            if data.get('kind', obj.kind) == 'customer' and values['payment_term'] != 'manual':
                raise ValidationError({'payment_term': '采购账期仅适用于供应商。'})
            for field, value in values.items():
                setattr(obj, field, value)
        for field in allowed - {'is_active', 'code', 'payment_term', 'payment_days', 'duplicate_reason'}:
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
        duplicate_reason = ''
        if model is Item:
            # Same lock as custom code creation, including edits that could collide.
            CodeRule.objects.select_for_update().get(key='item')
            if (
                obj.drawing_number
                and Item.all_objects.filter(
                    drawing_number__iexact=obj.drawing_number, drawing_revision__iexact=obj.drawing_revision
                )
                .exclude(pk=obj.pk)
                .exists()
            ):
                raise ValidationError(
                    {
                        'drawing_number': '此图号及版本已由其他物料使用，包括历史停用记录；请复用该物料，图档升级需填写新版本并新建编码。'
                    }
                )
            for field in ('name', 'specification', 'brand', 'unit'):
                setattr(obj, field, normalized(getattr(obj, field)))
            repeated = duplicates(
                {
                    field: getattr(obj, field)
                    for field in (
                        'name',
                        'specification',
                        'brand',
                        'unit',
                        'part_type',
                        'product_category',
                        'drawing_number',
                        'drawing_revision',
                    )
                },
                obj.pk,
            )
            if repeated:
                duplicate_reason = text(data, 'duplicate_reason', default='')
                if not duplicate_reason:
                    raise ValidationError(
                        {
                            'duplicate_reason': f'名称、规格、品牌、单位和类别与现有物料 {", ".join(item.code for item in repeated[:10])} 相同。请优先复用；确需独立编码请说明差异原因。'
                        }
                    )
        save(obj, user)
        return audit(
            user, f'{model._meta.model_name}.save', obj, fields=sorted(data), duplicate_reason=duplicate_reason
        )

    return perform(
        actor=actor,
        key=key,
        operation=f'{model._meta.model_name}.save',
        payload={'id': object_id, 'data': data},
        authorize=authorize,
        execute=execute,
    )
