"""Administrator removal: soft-delete unused forms, retain posted facts as history.

AuditLog is the single removal record. Ledger queries never use this list filter:
removing a row from the screen must not change stock, money or project costs.
"""

import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import CharField, Exists, OuterRef, Value
from django.db.models.functions import Cast, Concat
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import AuditLog, Company, LedgerModel
from apps.core.permissions import ADMIN, require_role

from .. import models
from .common import audit, fields, text

OPERATION = 'record.delete'
RESOURCES = {
    'items': (models.Item, '物料'),
    'partners': (models.Partner, '往来单位'),
    'sales': (models.SalesOrder, '销售单'),
    'projects': (models.Project, '项目'),
    'bom': (models.BOMLine, 'BOM明细'),
    'purchases': (models.PurchaseOrder, '采购单'),
    'stocks': (models.Stock, '库存余额'),
    'moves': (models.StockMove, '库存流水'),
    'entries': (models.Entry, '应收应付与费用'),
    'payments': (models.Payment, '收付款流水'),
    'reconciliations': (models.Reconciliation, '对账单'),
    'bank-records': (models.BankRecord, '银行流水'),
    'bank-matches': (models.BankMatch, '银行匹配'),
    'tasks': (models.Task, '项目任务'),
    'deliveries': (models.Delivery, '交付记录'),
    'time': (models.TimeEntry, '工时记录'),
    'documents': (models.Document, '附件'),
    'users': (User, '用户'),
}


def resource_definition(resource):
    if not isinstance(resource, str) or resource not in RESOURCES:
        raise ValidationError({'resource': '请选择支持删除的业务记录；公司资料、编号规则和审计日志不能删除。'})
    return RESOURCES[resource]


def visible_rows(queryset):
    """Only list/export call this; business services keep the original fact queries."""
    if queryset.model not in {definition[0] for definition in RESOURCES.values()}:
        return queryset
    removals = AuditLog.objects.filter(
        operation=OPERATION,
        resource=Concat(Value(f'{queryset.model._meta.model_name}:'), Cast(OuterRef('pk'), CharField())),
    )
    # A zero stock row can be put away, but a later receipt makes it visible again.
    if queryset.model is models.Stock:
        removals = removals.filter(created_at__gte=OuterRef('updated_at'))
    return queryset.alias(_admin_removed=Exists(removals)).filter(_admin_removed=False)


def references(obj, *, ignore=()):
    for relation in obj._meta.related_objects:
        if relation.many_to_many or relation.related_model in ignore:
            continue
        model = relation.related_model
        if model.objects.filter(**{relation.field.name: obj}).exists():
            label = next((title for candidate, title in RESOURCES.values() if candidate is model), '关联记录')
            return label
    return ''


def mode_for(obj, actor):
    if isinstance(obj, models.Stock):
        if obj.quantity or obj.value:
            raise Conflict('库存余额不为零，不能移出库存列表；请先通过收退料或盘点核实库存。')
        return 'archive'
    if isinstance(obj, (LedgerModel, models.Delivery)):
        return 'archive'
    if isinstance(obj, User):
        if obj.pk == actor.pk:
            raise Conflict('不能删除当前登录账号，请保留一位启用的管理员。')
        return 'disable'
    if isinstance(obj, models.Document):
        from .documents import referenced

        return 'archive' if referenced(obj) else 'soft'
    if isinstance(obj, models.BOMLine):
        return 'archive' if obj.project.status in {'closed', 'cancelled'} else 'bom'
    if isinstance(obj, models.Project):
        used = references(obj)
        if used:
            if obj.status not in {'cancelled', 'closed'}:
                raise Conflict(f'项目已有{used}，请先按业务规则取消或结项，再移入已删除记录。')
            return 'archive'
    elif isinstance(obj, models.SalesOrder) and (obj.project_id or obj.status == 'signed'):
        if not obj.project_id or obj.project.status not in {'cancelled', 'closed'}:
            raise Conflict('销售单已关联项目，请先取消或结项项目；删除不会撤销合同或应收款。')
        return 'archive'
    elif isinstance(obj, models.PurchaseOrder):
        if obj.status in {'approved', 'partial'}:
            raise Conflict('采购单仍有收货业务，请先完成收货或取消未收余量，再删除。')
        if obj.status in {'received', 'cancelled'}:
            return 'archive'
        if any(references(line) or line.received_quantity or line.pending_quantity for line in obj.lines.all()):
            raise Conflict('采购明细已有收货或库存关联，请先核实采购状态，不能删除。')
        used = references(obj, ignore=(models.PurchaseLine,))
        if used:
            raise Conflict(f'采购单已有{used}，请先处理关联记录。')
        return 'purchase'
    elif isinstance(obj, models.Task):
        if obj.status == 'done':
            return 'archive'
        if obj.delivery_id or references(obj):
            if obj.status not in {'cancelled', 'done'}:
                raise Conflict('任务已有工时、账款或交付关联，请先完成或取消任务，再移入已删除记录。')
            return 'archive'
    used = references(obj)
    if used:
        raise Conflict(f'此记录已被{used}使用，不能删除；基础资料可先停用，其他单据请先处理关联记录。')
    return 'soft'


def snapshot(obj, request):
    # Use the existing public serializers; never capture password hashes or files.
    from apps.accounts.api import UserSerializer

    from .. import serializers
    from ..api.reconciliation import BankMatchSerializer, BankSerializer, ReconciliationSerializer
    from ..attachments import DocumentSerializer
    from ..sales import SalesSerializer

    mapping = {
        models.Item: serializers.ItemSerializer,
        models.Partner: serializers.PartnerSerializer,
        models.Project: serializers.ProjectSerializer,
        models.SalesOrder: SalesSerializer,
        models.BOMLine: serializers.BOMSerializer,
        models.PurchaseOrder: serializers.PurchaseSerializer,
        models.Stock: serializers.StockSerializer,
        models.StockMove: serializers.MoveSerializer,
        models.Entry: serializers.EntrySerializer,
        models.Payment: serializers.PaymentSerializer,
        models.Task: serializers.TaskSerializer,
        models.Delivery: serializers.DeliverySerializer,
        models.TimeEntry: serializers.TimeSerializer,
        models.Reconciliation: ReconciliationSerializer,
        models.BankRecord: BankSerializer,
        models.BankMatch: BankMatchSerializer,
        models.Document: DocumentSerializer,
        User: UserSerializer,
    }
    data = mapping[type(obj)](obj, context={'request': request}).data
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def remove(request, key, data):
    actor = request.user
    require_role(actor, ADMIN)
    if not isinstance(data, dict):
        raise ValidationError('请提交 JSON 对象。')
    fields(data, {'resource', 'ids', 'reason'})
    resource = data.get('resource')
    model, label = resource_definition(resource)
    ids = data.get('ids')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(type(i) is not int or i < 1 for i in ids):
        raise ValidationError({'ids': '请勾选 1 至 200 条有效记录。'})
    if len(ids) != len(set(ids)):
        raise ValidationError({'ids': '勾选记录不能重复。'})
    reason = text(data, 'reason')

    def authorize(user):
        # User maintenance uses this same lock, preserving admin-role transitions.
        if model is User:
            Company.objects.get_or_create(pk=1)
            Company.objects.select_for_update().get(pk=1)
        user.refresh_from_db()
        require_role(user, ADMIN)

    def execute(user):
        records = list(model.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        if len(records) != len(ids):
            raise Conflict('部分记录不存在或已删除，请刷新列表后重新勾选。')
        if visible_rows(model.objects.filter(pk__in=ids)).count() != len(ids):
            raise Conflict('部分记录已移入已删除记录，请刷新列表后重新勾选。')
        results = []
        for obj in records:
            try:
                mode = mode_for(obj, user)
                record = snapshot(obj, request)
                if mode == 'bom':
                    from .corrections import remove_bom

                    nested_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{user.pk}:{key}:bom:{obj.pk}'))
                    remove_bom(user, nested_key, obj.pk, {'reason': reason})
                elif mode == 'purchase':
                    for line in obj.lines.select_for_update().order_by('pk'):
                        line.soft_delete(user)
                    obj.soft_delete(user)
                elif mode == 'soft':
                    obj.soft_delete(user)
                elif mode == 'disable':
                    obj.is_active = False
                    obj.save(update_fields=['is_active'])
                audit(user, OPERATION, obj, resource=resource, record=record, reason=reason, mode=mode)
                results.append({'id': obj.pk, 'mode': mode})
            except (ValidationError, Conflict) as exc:
                from .bom_import import message

                name = getattr(obj, 'code', None) or getattr(obj, 'title', None) or getattr(obj, 'name', None)
                raise Conflict(f'{label}「{name or obj.pk}」不能删除：{message(exc.detail)}整批未删除。') from exc
        return {'count': len(results), 'records': results}

    return perform(actor=actor, key=key, operation=OPERATION, payload=data, authorize=authorize, execute=execute)
