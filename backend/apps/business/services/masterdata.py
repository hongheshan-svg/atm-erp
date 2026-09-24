import unicodedata

from django.db.models.functions import Lower, Trim
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.models import CodeRule
from apps.core.permissions import ITEM_WRITERS, PURCHASERS, has_role, require_role

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


IDENTITY_FIELDS = {'unit': '单位', 'specification': '规格', 'drawing_number': '图号', 'drawing_revision': '图档版本'}


def referenced(item):
    """物料是否已被 BOM、采购或库存引用（含已移除的历史行）。"""
    from ..models import BOMLine, PurchaseLine, Stock

    return (
        BOMLine.all_objects.filter(item=item).exists()
        or PurchaseLine.all_objects.filter(item=item).exists()
        or Stock.all_objects.filter(item=item).exists()
    )


def check_referenced_identity(item, data):
    """已被业务引用的物料不能改写单位、规格和图档，否则历史数量和采购内容会被悄悄改义；空值允许补填。"""
    changed = [
        label
        for field, label in IDENTITY_FIELDS.items()
        if isinstance(data.get(field), str)
        and normalized(getattr(item, field))
        and normalized(data[field]).casefold() != normalized(getattr(item, field)).casefold()
    ]
    if changed and referenced(item):
        raise ValidationError(
            f'物料已被 BOM、采购或库存引用，不能改写已有的{"、".join(changed)}；'
            '需要不同单位、规格或图档时请新建物料编码并修订 BOM。'
        )


def masterdata(actor, key, model, data, object_id=None):
    def authorize(user):
        require_role(user, ITEM_WRITERS if model is Item else PURCHASERS | {'sales_manager'})
        if model is Partner and not has_role(user, PURCHASERS):
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
            if object_id:
                check_referenced_identity(obj, data)
            if category and not text(data, 'specification', default=obj.specification, maximum=2000):
                raise ValidationError({'specification': '规范要求所有产品填写型号/规格。'})
            if category.startswith('1') and not text(data, 'drawing_number', default=obj.drawing_number, maximum=100):
                raise ValidationError({'drawing_number': '有图产品必须填写图号。'})
        if (
            model is Partner
            and not has_role(user, PURCHASERS)
            and (data.get('kind', obj.kind) != 'customer' or (object_id and obj.kind != 'customer'))
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
                # 与 lean_item_drawing_key 函数索引同一套表达式；iexact 生成的 UPPER(col::text) 用不上索引。
                and Item.all_objects.annotate(
                    drawing_key=Lower('drawing_number'), revision_key=Lower('drawing_revision')
                )
                .filter(drawing_key=obj.drawing_number.lower(), revision_key=obj.drawing_revision.lower())
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
