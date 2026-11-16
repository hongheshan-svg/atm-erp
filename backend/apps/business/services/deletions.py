"""Administrator removal: soft-delete unused forms, retain posted facts as history.

AuditLog is the single removal record. Ledger queries never use this list filter:
removing a row from the screen must not change stock, money or project costs.
Records still being worked (open balances, draft or unused reconciliations, unmatched
bank money, deliveries awaiting acceptance or in warranty) stay on the list until ended.

A removal never asks the administrator to clear what the record owns first: a mistaken form
takes its unused attachments with it, an ended project takes the forms listed across projects,
and master data that only history still points at is retired (deactivated and off the list)
with its code and drawing number kept. A batch reports every blocked record at once.
"""

import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import CharField, DecimalField, Exists, F, OuterRef, Q, QuerySet, Sum, Value
from django.db.models.functions import Cast, Coalesce, Concat
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts.models import User
from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import AuditLog, Company, LedgerModel
from apps.core.permissions import ADMIN, require_role

from .. import models
from . import banking, finance, reconciliation
from .common import audit, fields, identity, text

OPERATION = 'record.delete'
RESTORE = 'record.restore'
ENDED_PROJECT = {'closed', 'cancelled'}
ENDED_PURCHASE = {'received', 'cancelled'}
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
# Manual restoration covers what a removal only deactivated: accounts and retired master data.
# Business actions restore reopened financial work on their own.
RESTORABLE = {'users', 'items', 'partners'}
# Related models that are not deletable resources still need a readable name in a rejection.
RELATED_LABELS = {
    models.PurchaseLine: '采购明细',
    models.PurchaseContractVersion: '归档的采购合同',
    models.ContractAmendment: '补充协议',
    models.IssueSlip: '领料单',
    models.PurchaseWarranty: '采购质保',
    models.PaymentEvidence: '补录的收付凭证',
    models.BankOffset: '银行退回登记',
}
NAME_FIELDS = ('code', 'title', 'reference', 'original_name', 'name')
OWNER_FIELDS = {models.Project: 'project', models.SalesOrder: 'sale', models.PurchaseOrder: 'purchase'}
KEPT_LIMIT = 100


def resource_definition(resource):
    if not isinstance(resource, str) or resource not in RESOURCES:
        raise ValidationError({'resource': '请选择支持删除的业务记录；公司资料、编号规则和审计日志不能删除。'})
    return RESOURCES[resource]


def unrestored(removals):
    """Deletion logs not followed by a restore of the same record (audit ids only grow)."""
    later = AuditLog.objects.filter(operation=RESTORE, resource=OuterRef('resource'), pk__gt=OuterRef('pk'))
    return removals.alias(_restored=Exists(later)).filter(_restored=False)


def restore_entry_activity(user, entry):
    """A legitimate financial action reopened this entry; preserve deletion and append restoration audits."""
    # Look deletions up by exact resource so lean_audit_resource serves both the entry and its payments.
    # Payments are immutable and never change entry, so their ids are exactly the payment removals whose
    # snapshot names this entry (the former detail->record->entry JSON filter forced a scan of the audit log).
    payments = models.Payment.all_objects.filter(entry_id=entry.pk).values_list('pk', flat=True)
    resources = [f'entry:{entry.pk}', *(f'payment:{pk}' for pk in payments)]
    removals = AuditLog.objects.filter(operation=OPERATION, resource__in=resources)
    # entry_action re-checks after its own execute; one pass per entry and request is enough.
    entry._activity_restored = True
    for deletion in unrestored(removals).order_by('pk'):
        AuditLog.objects.create(
            actor=user,
            operation=RESTORE,
            resource=deletion.resource,
            detail={
                'resource': deletion.detail['resource'],
                'deletion': deletion.pk,
                'automatic': True,
                'reason': '业务更正后重新出现待结算或待退款，恢复款项及相关收付流水显示。',
            },
        )


def removed(model):
    """Whether a row is currently removed: a record.delete exists with no later record.restore."""
    removals = AuditLog.objects.filter(
        operation=OPERATION,
        resource=Concat(Value(f'{model._meta.model_name}:'), Cast(OuterRef('pk'), CharField())),
    )
    # A zero stock row can be put away, but a later receipt makes it visible again.
    if model is models.Stock:
        removals = removals.filter(created_at__gte=OuterRef('updated_at'))
    return Exists(unrestored(removals))


def visible_rows(queryset):
    """Only list/export call this; business services keep the original fact queries."""
    if queryset.model not in {definition[0] for definition in RESOURCES.values()}:
        return queryset
    return queryset.alias(_admin_removed=removed(queryset.model)).filter(_admin_removed=False)


def listing(names, limit=3):
    """'甲、乙、丙 等'：读到比展示多一个就知道要不要加“等”，不为提示语再数一遍总数。"""
    if isinstance(names, QuerySet):
        names = names[: limit + 1]
    names = [str(name) for name in names if name][: limit + 1]
    return '、'.join(names[:limit]) + (' 等' if len(names) > limit else '')


def related_label(model):
    return next((title for candidate, title in RESOURCES.values() if candidate is model), None) or RELATED_LABELS.get(
        model, '关联记录'
    )


def references(obj, *, ignore=()):
    """First live relation still pointing at this record, named so it can be found; '' when unused.

    只看现行引用：已移除的附件、已删的草稿本身不能再处理，计入只会让记录永远删不掉。
    """
    for relation in obj._meta.related_objects:
        model = relation.related_model
        if relation.many_to_many or model in (*ignore, models.TaskNotice):
            continue
        related = model.objects.filter(**{relation.field.name: obj})
        if not related.exists():
            continue
        names = {field.name for field in model._meta.fields}
        field = 'item__code' if model is models.BOMLine else next((n for n in NAME_FIELDS if n in names), None)
        named = listing(related.order_by('pk').values_list(field, flat=True)) if field else ''
        return f'{related_label(model)}（{named}）' if named else related_label(model)
    return ''


def item_in_use(item):
    """Why live business still needs this material; lines in ended projects and finished purchases are history."""
    projects = (
        models.BOMLine.objects.filter(item=item)
        .exclude(project__status__in=ENDED_PROJECT)
        .order_by('project__code')
        .values_list('project__code', flat=True)
        .distinct()
    )
    used = listing(projects)
    if used:
        return (
            f'物料仍在未结束项目的 BOM 中（项目 {used}），请先在 BOM 中替换或移除该物料，或等项目结项、取消后再删除。'
        )
    purchases = (
        models.PurchaseLine.objects.filter(item=item)
        .exclude(purchase__status__in=ENDED_PURCHASE)
        .order_by('purchase__code')
        .values_list('purchase__code', flat=True)
        .distinct()
    )
    used = listing(purchases)
    if used:
        return f'物料仍在未完成的采购单中（{used}），请先完成收货、取消未收余量或删除草稿采购单后再删除。'
    stocks = models.Stock.objects.filter(item=item).exclude(quantity=0).order_by('location', 'pk')[:4]
    used = listing([f'{stock.location} {stock.quantity.normalize():f} {item.unit}' for stock in stocks])
    if used:
        return f'物料还有库存（{used}），请先领用、退货或盘点核实，库存为零后再删除。'
    return ''


def partner_in_use(partner):
    """Why live business still needs this customer or supplier; ended and settled history does not count."""
    projects = models.Project.objects.filter(customer=partner).exclude(status__in=ENDED_PROJECT)
    used = listing(projects.order_by('code').values_list('code', flat=True))
    if used:
        return f'往来单位仍是未结束项目的客户（项目 {used}），请先结项或取消项目后再删除。'
    sales = (
        models.SalesOrder.objects.filter(customer=partner)
        .exclude(status='cancelled')
        .exclude(project__status__in=ENDED_PROJECT)
    )
    used = listing(sales.order_by('code').values_list('code', flat=True))
    if used:
        return f'往来单位仍有未结束的销售单（{used}），请先取消销售单或删除草稿后再删除。'
    purchases = models.PurchaseOrder.objects.filter(supplier=partner).exclude(status__in=ENDED_PURCHASE)
    used = listing(purchases.order_by('code').values_list('code', flat=True))
    if used:
        return f'往来单位仍有未完成的采购单（{used}），请先完成收货、取消未收余量或删除草稿采购单后再删除。'
    money = DecimalField(max_digits=18, decimal_places=2)
    unsettled = (
        models.Entry.objects.filter(Q(purchase__supplier=partner) | Q(project__customer=partner, kind='receivable'))
        .annotate(_paid=Coalesce(Sum('payments__amount'), Value(0), output_field=money))
        .exclude(amount=F('credit_amount') + F('_paid'))
    )
    used = listing(unsettled.order_by('pk').values_list('title', flat=True))
    if used:
        return f'往来单位还有未结清或待退款的款项（{used}），请先结清、退款或按规则取消后再删除。'
    return ''


def masterdata_mode(obj):
    """Unused master data is soft-deleted; used master data is retired once nothing live needs it.

    物料与 masterdata.referenced 同一口径，已移除的 BOM 行、已删草稿的采购明细等历史引用也算被使用：
    软删除会释放图号版本，历史记录就失去唯一对应。因此只停用并移出列表，编码和图号继续占用，原单照常引用。
    往来单位只看现行单据：指向它的草稿都已删除时没有历史需要保留。
    """
    if isinstance(obj, models.Item):
        from .masterdata import referenced

        if not referenced(obj):
            return 'soft'
        pending = item_in_use(obj)
    else:
        if not references(obj):
            return 'soft'
        pending = partner_in_use(obj)
    if pending:
        raise Conflict(pending)
    return 'disable'


def owned_documents(obj):
    return models.Document.objects.filter(**{OWNER_FIELDS[type(obj)]: obj})


def check_owned_documents(obj, label):
    """A mistaken form takes its unused attachments with it; an attachment backing a posted fact keeps the form."""
    from .documents import referenced

    for document in owned_documents(obj).order_by('pk'):
        used = referenced(document)
        if used:
            raise Conflict(
                f'附件「{document.original_name}」已作为{used}的依据，{label}不能直接删除；请先处理该{used}。'
            )


def bank_pending(bank):
    """Why a bank record still needs finance work; voided records are ended."""
    if bank.void_reason:
        return ''
    if bank.needs_review:
        return '待核实对方户名，请先复核户名并记录依据'
    left = banking.remaining(bank)
    if left:
        return f'还有 {left:.2f} 元未认领或未匹配，请先认领、匹配、退回或作废'
    return ''


def check_open(obj):
    """Hiding an in-progress fact would drop it from lists while totals still count it."""
    if isinstance(obj, models.Entry):
        left = finance.balance(obj)
        if left > 0:
            raise Conflict(f'账款余额 {left:.2f} 元尚未结清，请先收付款结清或按规则取消后再删除。')
        if left < 0:
            raise Conflict(f'账款还有待退款 {-left:.2f} 元，请先完成退款对账和退款后再删除。')
        if obj.reconciliations.filter(status='draft').exists():
            raise Conflict('账款还有待确认的对账单，请先确认或作废对账单后再删除。')
    elif isinstance(obj, models.Payment):
        left = finance.balance(obj.entry)
        if left:
            raise Conflict(
                f'所属账款「{obj.entry.title}」余额 {left:.2f} 元尚未结清，流水移出列表后无法冲销或匹配；'
                '请先结清账款后再删除。'
            )
    elif isinstance(obj, models.Reconciliation):
        if obj.status == 'draft':
            raise Conflict('对账单待确认，请先确认或作废后再删除。')
        left = obj.approved_amount - reconciliation.used(obj) if obj.status == 'confirmed' else 0
        if left > 0:
            raise Conflict(
                f'对账单还有 {left:.2f} 元核准额度未使用，请先作废剩余额度（已发生的收付款不受影响）后再删除。'
            )
    elif isinstance(obj, models.BankRecord):
        pending = bank_pending(obj)
        if pending:
            raise Conflict(f'银行流水{pending}后再删除。')
    elif isinstance(obj, models.BankMatch):
        pending = bank_pending(obj.bank)
        if pending:
            raise Conflict(f'所属银行流水「{obj.bank.reference}」{pending}后再删除匹配。')
    elif isinstance(obj, models.Delivery) and obj.project.status not in ENDED_PROJECT:
        if not obj.accepted_date:
            raise Conflict('交付批次尚未验收，请先完成验收（含安装任务）后再删除；项目结项或取消后也可整理。')
        if obj.warranty_until and obj.warranty_until >= timezone.localdate():
            raise Conflict(
                f'交付批次在质保期内（至 {obj.warranty_until}），售后登记需要选择该批次；质保期满或项目结项后再删除。'
            )


def mode_for(obj, actor):
    if isinstance(obj, models.Stock):
        if obj.quantity or obj.value:
            raise Conflict('库存余额不为零，不能移出库存列表；请先通过收退料或盘点核实库存。')
        return 'archive'
    if isinstance(obj, (LedgerModel, models.Delivery)):
        check_open(obj)
        return 'archive'
    if isinstance(obj, User):
        if obj.pk == actor.pk:
            raise Conflict('不能删除当前登录账号，请保留一位启用的管理员。')
        return 'disable'
    if isinstance(obj, models.Document):
        from .documents import referenced

        return 'archive' if referenced(obj) else 'soft'
    if isinstance(obj, models.BOMLine):
        if obj.project.status in ENDED_PROJECT:
            return 'archive'
        if obj.project.status == 'warranty':
            raise Conflict('项目已验收，BOM 已锁定，不能删除；如需调整请联系项目经理按变更流程处理。')
        return 'bom'
    if isinstance(obj, (models.Item, models.Partner)):
        return masterdata_mode(obj)
    # references() runs one EXISTS per relation; compute it at most once per record.
    used = None
    if isinstance(obj, models.Project):
        used = references(obj, ignore=(models.Document,))
        if used:
            if obj.status not in ENDED_PROJECT:
                raise Conflict(
                    f'项目已有{used}，请先在项目页取消项目或完成结项，再删除；'
                    '届时项目下的销售单、采购单、任务、工时和款项会随项目一并移出列表。'
                )
            return 'archive'
        check_owned_documents(obj, '项目')
    elif isinstance(obj, models.SalesOrder):
        if obj.project_id or obj.status == 'signed':
            if not obj.project_id or obj.project.status not in ENDED_PROJECT:
                raise Conflict('销售单已关联项目，请先取消或结项项目；删除不会撤销合同或应收款。')
            return 'archive'
        used = references(obj, ignore=(models.Document,))
        if not used:
            check_owned_documents(obj, '销售单')
    elif isinstance(obj, models.PurchaseOrder):
        if obj.status == 'submitted':
            raise Conflict('待审批采购不能直接删除，请先申请修改，经审批退回草稿后再处理。')
        if obj.status in {'approved', 'partial'}:
            raise Conflict('采购单仍有收货业务，请先完成收货或取消未收余量，再删除。')
        if obj.status in ENDED_PURCHASE:
            return 'archive'
        if any(references(line) or line.received_quantity or line.pending_quantity for line in obj.lines.all()):
            raise Conflict('采购明细已有收货或库存关联，请先核实采购状态，不能删除。')
        used = references(obj, ignore=(models.PurchaseLine, models.Document))
        if used:
            raise Conflict(f'采购单已有{used}，请先处理关联记录。')
        check_owned_documents(obj, '采购单')
        return 'purchase'
    elif isinstance(obj, models.Task):
        if obj.status == 'done':
            return 'archive'
        if obj.started_date or obj.delivery_id or (used := references(obj)):
            if obj.status not in {'cancelled', 'done'}:
                raise Conflict('任务已开始或已有工时、账款或交付关联，请先完成或取消任务，再移入已删除记录。')
            return 'archive'
    if used is None:
        used = references(obj)
    if used:
        raise Conflict(f'此记录已有{used}，请先处理这些关联记录后再删除。')
    return 'soft'


def snapshot(obj, request, *, many=False):
    """What the record looked like when removed; ``many`` snapshots a list of one model in a single pass."""
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
    if many:
        # 整批一起序列化：人员重名统计等按一次序列化缓存的查询只做一遍，不随子单据条数增长。
        data = mapping[type(obj[0])](obj, many=True, context={'request': request}).data if obj else []
    else:
        data = mapping[type(obj)](obj, context={'request': request}).data
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def record_label(obj):
    if isinstance(obj, models.BOMLine):
        return f'{obj.item.code} · {obj.item.name} · 单元：{obj.assembly_unit or "未分单元"} · 项目：{obj.project.code}'
    parts = [
        getattr(obj, 'code', None) or getattr(obj, 'reference', None) or getattr(obj, 'username', None),
        getattr(obj, 'title', None)
        or getattr(obj, 'name', None)
        or getattr(obj, 'original_name', None)
        or getattr(obj, 'display_name', None),
    ]
    return ' · '.join(str(part) for part in parts if part) or f'记录编号：{obj.pk}'


def remove_owned_documents(user, request, resource, obj, reason):
    """Soft-delete the unused attachments of a form being soft-deleted, each with its own removal record."""
    via = {'resource': resource, 'id': obj.pk, 'label': record_label(obj)}
    count = 0
    for document in owned_documents(obj).select_for_update().order_by('pk'):
        record = snapshot(document, request)
        document.soft_delete(user)
        audit(user, OPERATION, document, resource='documents', record=record, reason=reason, mode='soft', via=via)
        count += 1
    return count


def project_children(project):
    """项目归档时随项目一并移出列表的子单据：只列跨项目列表里看得到的。

    BOM、交付和附件只在项目页内出现，项目移出后不再出现在任何列表，从“已删除记录”打开原项目仍能完整查看，
    不逐条另记删除。库存流水和银行流水是仓库与银行的总账，不随项目隐藏。
    查询沿用各列表视图的 queryset：快照用的就是列表序列化器，带上它的关联预取，子单据再多也不逐条补查。
    """
    from ..api.execution import TaskView, TimeView
    from ..api.finance import EntryView, PaymentView
    from ..api.purchases import PurchaseView
    from ..api.reconciliation import ReconciliationView
    from ..sales import SalesView

    return (
        ('sales', SalesView.queryset.filter(project=project)),
        ('purchases', PurchaseView.queryset.filter(project=project)),
        ('tasks', TaskView.queryset.filter(project=project)),
        ('time', TimeView.queryset.filter(task__project=project)),
        ('entries', EntryView.queryset.filter(project=project)),
        ('payments', PaymentView.queryset.filter(entry__project=project)),
        ('reconciliations', ReconciliationView.queryset.filter(entry__project=project)),
    )


def remove_children(user, request, key, project, reason):
    """Move an ended project's cross-project forms off their lists under each form's own rule.

    仍在办的子单据（如取消后待退款的款项）不随项目隐藏，留在原列表并在结果中列出，办结后可单独整理。
    """
    from .bom_import import message

    via = {'resource': 'projects', 'id': project.pk, 'label': record_label(project)}
    cascaded, kept = {}, []
    # record.delete 独占全局写入锁（core.actions.perform），子单据不会被并发业务改写，无需再逐行加锁。
    for resource, children in project_children(project):
        label = RESOURCES[resource][1]
        rows = list(visible_rows(children).order_by('pk'))
        for child, record in zip(rows, snapshot(rows, request, many=True), strict=True):
            try:
                with transaction.atomic():
                    remove_one(user, request, key, resource, child, reason, via=via, record=record)
                cascaded[resource] = cascaded.get(resource, 0) + 1
            except (ValidationError, Conflict) as exc:
                kept.append(
                    {'resource': resource, 'label': f'{label}「{record_label(child)}」', 'reason': message(exc.detail)}
                )
    return cascaded, kept


def remove_one(user, request, key, resource, obj, reason, *, via=None, record=None):
    """Remove one record under its own rule; a project's children go through here exactly like their own lists."""
    mode = mode_for(obj, user)
    if record is None:
        record = snapshot(obj, request)
    result = {'id': obj.pk, 'mode': mode}
    documents = 0
    if mode == 'bom':
        from .corrections import remove_bom

        nested_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{user.pk}:{key}:bom:{obj.pk}'))
        remove_bom(user, nested_key, obj.pk, {'reason': reason})
    elif mode == 'purchase':
        for line in obj.lines.select_for_update().order_by('pk'):
            line.soft_delete(user)
        documents = remove_owned_documents(user, request, resource, obj, reason)
        obj.soft_delete(user)
    elif mode == 'soft':
        if type(obj) in OWNER_FIELDS:
            documents = remove_owned_documents(user, request, resource, obj, reason)
        obj.soft_delete(user)
    elif mode == 'disable':
        obj.is_active = False
        if isinstance(obj, User):
            obj.save(update_fields=['is_active'])
        else:
            obj.updated_by = user
            obj.save(update_fields=['is_active', 'updated_by', 'updated_at'])
    elif mode == 'archive' and isinstance(obj, models.Project):
        cascaded, kept = remove_children(user, request, key, obj, reason)
        if cascaded:
            result['cascaded'] = cascaded
        if kept:
            result['kept'] = kept[:KEPT_LIMIT]
            result['kept_count'] = len(kept)
    if documents:
        result['documents'] = documents
    audit(
        user,
        OPERATION,
        obj,
        resource=resource,
        record=record,
        reason=reason,
        mode=mode,
        **({'via': via} if via else {}),
        **({'documents': documents} if documents else {}),
        **({'cascaded': result['cascaded']} if result.get('cascaded') else {}),
    )
    return result


def remove(request, key, data):
    actor = request.user
    require_role(actor, ADMIN)
    if not isinstance(data, dict):
        raise ValidationError('请提交 JSON 对象。')
    fields(data, {'resource', 'ids', 'reason'})
    resource = data.get('resource')
    model, label = resource_definition(resource)
    ids = data.get('ids')
    maximum = 1000
    if not isinstance(ids, list) or not 1 <= len(ids) <= maximum or any(type(i) is not int or i < 1 for i in ids):
        raise ValidationError({'ids': f'请勾选 1 至 {maximum} 条有效记录。'})
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
        from .bom_import import message

        records = list(model.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        if len(records) != len(ids):
            raise Conflict('部分记录不存在或已删除，请刷新列表后重新勾选。')
        if visible_rows(model.objects.filter(pk__in=ids)).count() != len(ids):
            raise Conflict('部分记录已移入已删除记录，请刷新列表后重新勾选。')
        # 每条记录在自己的保存点里处理：被拦的只回滚它自己，继续检查其余记录，
        # 最后一次报出全部被拦记录和原因；只要有一条被拦，下面的 Conflict 就让整批回滚。
        results, blocked = [], []
        for obj in records:
            try:
                with transaction.atomic():
                    results.append(remove_one(user, request, key, resource, obj, reason))
            except (ValidationError, Conflict) as exc:
                blocked.append({'id': str(obj.pk), 'label': record_label(obj), 'reason': message(exc.detail)})
        if blocked:
            first = blocked[0]
            others = f'另有 {len(blocked) - 1} 条也不能删除，' if len(blocked) > 1 else ''
            raise Conflict(
                {
                    'detail': f'{label}「{first["label"]}」不能删除：{first["reason"]}{others}整批未删除。',
                    'blocked_id': first['id'],
                    'blocked': blocked,
                }
            )
        return {'count': len(results), 'records': results}

    return perform(actor=actor, key=key, operation=OPERATION, payload=data, authorize=authorize, execute=execute)


def restore(request, key, data):
    """Bring a deactivated record back to its list, still disabled until someone reviews and enables it.

    Accounts and retired master data only: the row was never deleted, so restoring is a separate audit entry
    pointing at the deletion log, which stays as history. Roles (accounts) or use (master data) are reviewed
    in the normal edit before enabling.
    """
    actor = request.user
    require_role(actor, ADMIN)
    fields(data, {'resource', 'id', 'reason'})
    resource = data.get('resource')
    if resource not in RESTORABLE:
        raise ValidationError(
            {
                'resource': '仅支持恢复用户账号，以及已停用归档的物料和往来单位；'
                '其他已删除记录仅保留历史，业务错误请按冲销、退料或更正处理。'
            }
        )
    model, label = RESOURCES[resource]
    account = model is User
    pk = identity(data.get('id'))
    reason = text(data, 'reason')

    def authorize(user):
        # Same order as account deletion and user maintenance: company lock, then the account row.
        Company.objects.get_or_create(pk=1)
        Company.objects.select_for_update().get(pk=1)
        user.refresh_from_db()
        require_role(user, ADMIN)

    def execute(user):
        target = model.objects.select_for_update().filter(pk=pk).first()
        if target is None:
            raise NotFound(
                '账号不存在，请刷新已删除记录后重试。'
                if account
                else f'{label}不存在，或删除时未被任何业务使用、已彻底移除，不支持恢复；需要时请重新新建。'
            )
        removals = AuditLog.objects.filter(operation=OPERATION, resource=f'{model._meta.model_name}:{target.pk}')
        deletion = unrestored(removals).order_by('-pk').first()
        if deletion is None:
            raise Conflict(
                '该账号未处于已删除状态，无需恢复；请刷新已删除记录，启用或停用请在用户管理中编辑。'
                if account
                else f'该{label}未处于已删除状态，无需恢复；请刷新已删除记录，启用或停用请在基础资料中编辑。'
            )
        if target.is_active:
            target.is_active = False
            target.save(update_fields=['is_active'])
        record = snapshot(target, request)
        audit(user, RESTORE, target, resource=resource, record=record, reason=reason, deletion=deletion.pk)
        return {'id': target.pk, 'deletion': deletion.pk, 'is_active': target.is_active}

    return perform(actor=actor, key=key, operation=RESTORE, payload=data, authorize=authorize, execute=execute)
