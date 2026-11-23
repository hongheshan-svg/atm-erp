import re
import unicodedata

from django.db.models import Q
from django.db.models.functions import Lower
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import ITEM_WRITERS, PURCHASERS, has_role, require_role

from ..models import Item, Partner, comparison_expression
from .common import (
    audit,
    fields,
    identity,
    save,
    text,
)


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).split())


# 淘宝、京东 App「分享」复制出来的是一段文字（【淘宝】… https://m.tb.cn/h.xxx?tk=… 「商品名」点击链接直接打开），
# 只保留其中第一个 http(s) 链接；链接到空白或中文标点为止。
LINK = re.compile(r'https?://[^\s<>"\'「」『』【】（）《》，。；：！？、]+', re.IGNORECASE)
LINK_MAX = Item._meta.get_field('purchase_url').max_length


def purchase_link(value):
    """物料购买链接：空串表示清除；否则只接受 http(s) 链接，存入前去掉分享文字和结尾标点。"""
    if not isinstance(value, str):
        raise ValidationError({'purchase_url': '购买链接必须是文本。'})
    if not value.strip():
        return ''
    match = LINK.search(value)
    if not match:
        raise ValidationError(
            {
                'purchase_url': '请填写以 http:// 或 https:// 开头的商品链接；可直接粘贴淘宝、京东的分享文字，'
                '系统只保留其中的链接。表格里只显示“链接”等文字的单元格，请复制实际链接地址。'
            }
        )
    link = match.group().rstrip('.,;:!?')
    if len(link) > LINK_MAX:
        raise ValidationError(
            {'purchase_url': f'购买链接最长{LINK_MAX}字符，请改用 App 里“分享 → 复制链接”得到的短链接。'}
        )
    return link


def fill_purchase_link(actor, item, link):
    """BOM 导入给已有或刚建的物料补填购买链接：只改这一项，不重走名称、规格查重。

    链接不参与物料身份；按原因独立建码的相似物料补链接时，不应再被要求填写独立建码原因。
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    item.purchase_url = link
    save(item, actor)
    audit(actor, 'item.save', item, fields=['purchase_url'], source='bom.import')
    return item


def comparison_key(value):
    """用于查找候选，绝不写回供应商型号或名称。"""
    return ''.join(normalized(str(value)).split()).casefold()


def candidates():
    return Item.objects.annotate(
        comparison_name=comparison_expression('name'),
        comparison_specification=comparison_expression('specification'),
    )


def similar(data):
    name, specification = comparison_key(data.get('name', '')), comparison_key(data.get('specification', ''))
    query = Q(comparison_name__contains=name) if name else Q(pk__in=[])
    if specification:
        query |= Q(comparison_specification=specification)
    return candidates().filter(query).order_by('code')[:10]


def duplicates(data, exclude=None):
    name = normalized(str(data.get('name', '')))
    if not name:
        return []
    items = candidates().filter(comparison_name=comparison_key(name)).exclude(pk=exclude)
    keys = (
        'name',
        'specification',
        'brand',
        'unit',
        'part_type',
        'product_category',
        'drawing_number',
        'drawing_revision',
    )
    return [
        item
        for item in items
        if all(
            normalized(getattr(item, key)).casefold()
            == normalized(str(data.get(key, '件' if key == 'unit' else ''))).casefold()
            for key in keys
        )
    ]


def suspected_duplicates(data, exclude=None):
    """相似只阻止未经核对的新建，不用于 BOM 自动复用。"""
    specification = comparison_key(data.get('specification', ''))
    if not specification:
        return duplicates(data, exclude)
    items = candidates().filter(comparison_specification=specification).exclude(pk=exclude)
    result = []
    for item in items:
        if comparison_key(item.unit) != comparison_key(data.get('unit', '件')):
            continue
        brand = comparison_key(data.get('brand', ''))
        if comparison_key(item.brand) != brand:
            continue
        if comparison_key(item.name) != comparison_key(data.get('name', '')) and not brand:
            continue
        # 图号或版本明确不同时，按不同图档处理。
        if any(
            data.get(key) and getattr(item, key) and comparison_key(data[key]) != comparison_key(getattr(item, key))
            for key in ('drawing_number', 'drawing_revision')
        ):
            continue
        result.append(item)
        if len(result) == 10:
            break
    return result


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
        {
            'specification',
            'unit',
            'brand',
            'part_type',
            'product_category',
            'drawing_number',
            'drawing_revision',
            'purchase_url',
        }
        if model is Item
        else {'kind', 'contact', 'phone', 'address', 'payment_term', 'payment_days'}
    )
    if not object_id:
        allowed.add('code')
    if model is Item:
        allowed.add('duplicate_reason')

    def execute(user):
        fields(data, allowed)
        errors = {}
        if (
            model is Item
            and 'part_type' in data
            and (not isinstance(data['part_type'], str) or data['part_type'] not in {'', *Item.PartType.values})
        ):
            # 同一行互相独立的字段问题先收集，稍后一次性报告；校验条件本身不变。
            errors['part_type'] = '请选择标准件或非标件，未分类可留空。'
        if model is Item:
            # 建料、改料与 BOM 物料导入共用一个锁序：先物料编码规则、后物料行（导入经 revise_bom 锁物料）。
            # 先锁物料再锁编码规则会与导入确认形成锁环；物料行在锁后读取，下面的校验都基于最新数据。
            CodeRule.objects.select_for_update().get(key='item')
        obj = model.objects.select_for_update().get(pk=identity(object_id)) if object_id else model()
        if object_id:
            from .deletions import visible_rows

            # 管理员停用归档的资料不在列表里；直接改回启用会得到一条在用却看不到的资料。
            if not visible_rows(model.objects.filter(pk=obj.pk)).exists():
                raise Conflict('该资料已移入“已删除记录”，请先由管理员在已删除记录中恢复，再编辑或启用。')
        category = ''
        if model is Item:
            category = data.get('product_category', obj.product_category)
            if category not in ('', *Item.ProductCategory.values):
                # 规格、图号的要求取决于类别；类别无效时无法判断，只报类别（及已收集的其他问题）。
                errors['product_category'] = '请选择规范中的产品编码类别。'
                raise ValidationError(errors)
            if (
                not errors  # 已有 part_type 问题时它本就优先报告，不让这里的整体拒绝掩盖它
                and object_id
                and obj.product_category
                and any(
                    field in data and data[field] != getattr(obj, field)
                    for field in ('product_category', 'specification', 'drawing_number', 'drawing_revision')
                )
            ):
                raise ValidationError('已编码产品的类别、型号或图档版本不能覆盖；版本升级请新增物料编码并修订 BOM。')
            if object_id and not errors:
                check_referenced_identity(obj, data)
            for field, maximum, required, message in (
                ('specification', 2000, bool(category), '规范要求所有产品填写型号/规格。'),
                ('drawing_number', 100, category.startswith('1'), '有图产品必须填写图号。'),
            ):
                if required:
                    try:
                        if not text(data, field, default=getattr(obj, field), maximum=maximum):
                            errors[field] = message
                    except ValidationError as exc:
                        errors.update(exc.detail)
            if not object_id or 'name' in data:
                try:
                    text(data, 'name', maximum=obj._meta.get_field('name').max_length, default=None)
                except ValidationError as exc:
                    errors.update(exc.detail)
            if errors:
                raise ValidationError(errors)
        if (
            model is Partner
            and not has_role(user, PURCHASERS)
            and (data.get('kind', obj.kind) != 'customer' or (object_id and obj.kind != 'customer'))
        ):
            raise PermissionDenied('销售经理只能维护纯客户资料，不能修改供应商或双用途往来单位。')
        if not object_id:
            obj.code = CodeRule.generate_code(
                'item' if model is Item else 'partner',
                product_category=category,
                custom=text(data, 'code', default='', maximum=30),
            )
        if model is Partner:
            from .payment_terms import terms

            values = terms(data, obj)
            if data.get('kind', obj.kind) == 'customer' and values['payment_term'] != 'manual':
                raise ValidationError({'payment_term': '采购账期仅适用于供应商。'})
            for field, value in values.items():
                setattr(obj, field, value)
        for field in allowed - {
            'is_active',
            'code',
            'payment_term',
            'payment_days',
            'duplicate_reason',
            'purchase_url',
        }:
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
        if 'purchase_url' in data:
            obj.purchase_url = purchase_link(data['purchase_url'])
        if 'is_active' in data:
            if not isinstance(data['is_active'], bool):
                raise ValidationError({'is_active': '必须为布尔值。'})
            obj.is_active = data['is_active']
        duplicate_reason = ''
        if model is Item:
            # 图号判重同样在 CodeRule('item') 锁内，建料和改料不会并发占用同一图号版本。
            # 停用物料仍占用图号；管理员删除的物料只能是未被引用的误建记录，且不可见、不可恢复，
            # 不再占用图号版本（物料编码仍按含软删除的全局唯一，见上方 code 校验与自动取号）。
            owner = (
                # 与 lean_item_drawing_key 函数索引同一套表达式；iexact 生成的 UPPER(col::text) 用不上索引。
                Item.objects.annotate(drawing_key=Lower('drawing_number'), revision_key=Lower('drawing_revision'))
                .filter(drawing_key=obj.drawing_number.lower(), revision_key=obj.drawing_revision.lower())
                .exclude(pk=obj.pk)
                .first()
                if obj.drawing_number
                else None
            )
            if owner is not None:
                # 写出占用者的编码和名称，填表的人不用再去基础资料里查是哪一个。
                stopped = '（已停用）' if not owner.is_active else ''
                raise ValidationError(
                    {
                        'drawing_number': f'此图号及版本已由物料 {owner.code}「{owner.name}」{stopped}使用；'
                        '请复用该物料，图档升级需填写新版本并新建编码。'
                    }
                )
            repeated = suspected_duplicates(
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
                            'duplicate_reason': f'名称、规格、品牌、单位和类别与现有物料 {", ".join(item.code for item in repeated[:10])} 相同或相似（已忽略空格及全角差异）。请核对厂家完整型号后优先复用；确需独立编码请在基础资料中说明差异原因。'
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
