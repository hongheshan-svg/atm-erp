import hashlib
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.permissions import (
    ALL_ROLES,
    FINANCE,
    MANAGERS,
    MONEY_READERS,
    OPERATION_ROLES,
    PURCHASERS,
    SALES,
    SALES_READERS,
    has_role,
    project_allowed,
    projects_for,
    require_project,
    require_role,
    require_sale,
)

from ..models import Document, Project, PurchaseOrder, SalesOrder
from .common import audit, fields, identity, project_action, save, text

MAX_BYTES = 20 * 1024 * 1024
MONEY_CATEGORIES = {'contract', 'receipt'}


def visible_documents(user, queryset):
    allowed = Q(pk__in=[])
    if has_role(user, OPERATION_ROLES):
        direct = Q(project__in=projects_for(user, Project.objects.all())) & ~Q(category__in=MONEY_CATEGORIES)
        if has_role(user, MONEY_READERS):
            direct |= Q(
                project__in=projects_for(user, Project.objects.all(), MONEY_READERS), category__in=MONEY_CATEGORIES
            )
        allowed |= direct
    if has_role(user, SALES_READERS):
        sales = SalesOrder.objects.all()
        # 销售合同附件与合同额同一口径：未签约或本人负责的销售可见，关联项目后按该项目金额读取范围。
        money = Q(sale__project__isnull=True) | Q(sale__manager=user)
        if has_role(user, MONEY_READERS):
            money |= Q(sale__project__in=projects_for(user, Project.objects.all(), MONEY_READERS))
        else:
            sales = sales.filter(manager=user)
        allowed |= Q(sale__in=sales) & (~Q(category__in=MONEY_CATEGORIES) | money)
    if has_role(user, PURCHASERS | FINANCE):
        allowed |= Q(
            purchase__in=PurchaseOrder.objects.filter(
                project__in=projects_for(user, Project.objects.all(), PURCHASERS | FINANCE)
            )
        )
    return queryset.filter(allowed)


def for_project(queryset, project_id):
    return queryset.filter(
        Q(project_id=project_id) | Q(sale__project_id=project_id) | Q(purchase__project_id=project_id)
    )


def upload(actor, key, project_id, category, file, *, sale_id=None, purchase_id=None):
    if sum(value is not None for value in (project_id, sale_id, purchase_id)) != 1:
        raise ValidationError('附件必须且只能关联一个项目、销售单或采购单。')
    if category not in Document.Category.values:
        raise ValidationError({'category': '请选择有效的附件分类。'})
    owner = 'sale' if sale_id is not None else 'purchase' if purchase_id is not None else 'project'
    roles = (
        SALES
        if owner == 'sale'
        else PURCHASERS
        if owner == 'purchase'
        else MANAGERS
        if category == 'contract'
        else FINANCE
        if category == 'receipt'
        else ALL_ROLES
    )
    if owner != 'project' and category not in {'contract', 'other'}:
        raise ValidationError({'category': '单据附件请选择合同或其他（报价及技术资料）。结算凭证请沿用项目凭证。'})
    require_role(actor, roles)
    if file is None or not hasattr(file, 'read'):
        raise ValidationError({'file': '请选择文件。'})
    name = Path(file.name.replace('\\', '/')).name
    if not name or len(name) > 250 or any(ord(char) < 32 for char in name):
        raise ValidationError({'file': '文件名无效或超过 250 字符。'})
    content = file.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise ValidationError({'file': '附件不能为空且不能超过 20 MB。'})
    digest = hashlib.sha256(content).hexdigest()
    written = []

    def execute(user, project, source=None):
        if project and (project.status == 'closed' or (project.status == 'cancelled' and category != 'receipt')):
            raise Conflict('当前项目只能补充取消后的结算凭证，其他附件需重新打开项目。')
        if source and source.status == 'cancelled':
            raise Conflict('已取消的单据不能新增附件。')
        document = Document(
            **{owner: source or project}, category=category, original_name=name, size=len(content), sha256=digest
        )
        document.file.save(uuid.uuid4().hex, ContentFile(content), save=False)
        written.append((document.file.storage, document.file.name))
        save(document, user)
        return audit(user, 'document.upload', document, filename=name, sha256=digest, category=category)

    try:
        if owner != 'project':
            model = SalesOrder if owner == 'sale' else PurchaseOrder
            owner_id = identity(sale_id if owner == 'sale' else purchase_id, owner)
            context = {}

            def authorize(user):
                require_role(user, roles)
                initial = get_object_or_404(model.objects, pk=owner_id)
                project = (
                    get_object_or_404(Project.objects.select_for_update(), pk=initial.project_id)
                    if initial.project_id
                    else None
                )
                source = get_object_or_404(model.objects.select_for_update(), pk=owner_id)
                if source.project_id != initial.project_id:
                    raise Conflict('单据项目关联已变化，请重试。')
                user.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
                require_role(user, roles)
                if owner == 'sale':
                    require_sale(user, source)
                elif project:
                    require_project(user, project, roles)
                context.update(project=project, source=source)

            return perform(
                actor=actor,
                key=key,
                operation='document.upload',
                payload={owner: owner_id, 'category': category, 'name': name, 'size': len(content), 'sha256': digest},
                authorize=authorize,
                execute=lambda user: execute(user, **context),
            )
        return project_action(
            actor,
            key,
            'document.upload',
            identity(project_id, 'project'),
            {'category': category, 'name': name, 'size': len(content), 'sha256': digest},
            roles,
            execute,
        )
    except Exception:
        for storage, path in written:
            storage.delete(path)
        raise


def referenced(document):
    """附件一旦被资金、对账或合同事实引用，就是这些记录的依据，不能再撤走。"""
    from ..models import ContractAmendment, Payment, PaymentEvidence, PurchaseContractVersion, Reconciliation

    for model, label in (
        (Payment, '收付款流水'),
        (PaymentEvidence, '补录的收付凭证'),
        (Reconciliation, '对账单'),
        (ContractAmendment, '补充协议'),
        (PurchaseContractVersion, '归档的采购合同'),
    ):
        if model.objects.filter(document=document).exists():
            return label
    return ''


MAX_REMOVE_BATCH = 50


def _lock_for_removal(user, document_ids):
    """按固定锁序（项目 → 采购/销售单 → 附件，同层按主键升序）锁定附件并逐个授权。

    与上传和 project_action 同一锁序：先无锁读出关联，按序加锁后复核关联未变；
    反序加锁会与同项目的提交、补充协议等操作形成死锁。单个和批量删除共用此函数，
    批量时 ``label`` 让提示写明是哪个文件，授权规则与单个删除完全一致。
    """
    ids = sorted(set(document_ids))
    initial = {doc.pk: doc for doc in Document.objects.filter(pk__in=ids)}
    if len(initial) != len(ids):
        raise Conflict('部分附件不存在或已被删除，请刷新后重试。')
    labelled = len(ids) > 1

    def label(document, message):
        return f'「{document.original_name}」：{message}' if labelled else message

    owner_models = {'purchase': PurchaseOrder, 'sale': SalesOrder}
    owner_keys = {}
    project_of = {}
    for pk, doc in initial.items():
        kind = 'purchase' if doc.purchase_id else 'sale' if doc.sale_id else None
        owner_keys[pk] = (kind, doc.purchase_id or doc.sale_id) if kind else None
        project_of[pk] = (
            get_object_or_404(owner_models[kind].objects, pk=owner_keys[pk][1]).project_id if kind else doc.project_id
        )
    projects = {
        project_id: get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        for project_id in sorted({value for value in project_of.values() if value})
    }
    owners = {
        key: get_object_or_404(owner_models[key[0]].objects.select_for_update(), pk=key[1])
        for key in sorted({value for value in owner_keys.values() if value})
    }
    locked = {doc.pk: doc for doc in Document.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    if len(locked) != len(ids):
        raise Conflict('部分附件不存在或已被删除，请刷新后重试。')
    result = []
    for pk in ids:
        document, before = locked[pk], initial[pk]
        owner = owners.get(owner_keys[pk])
        project = projects.get(project_of[pk])
        if (owner.project_id if owner else document.project_id) != project_of[pk] or any(
            getattr(document, field) != getattr(before, field) for field in ('project_id', 'purchase_id', 'sale_id')
        ):
            raise Conflict(label(document, '附件所属的项目或单据已变化，请刷新后重试。'))
        try:
            if document.sale_id:
                require_sale(user, owner)
            if project is not None and not document.sale_id:
                require_project(user, project, ALL_ROLES)
            if document.created_by_id != user.pk and not (
                project is not None and project_allowed(user, project, MANAGERS)
            ):
                raise PermissionDenied('只能删除本人上传的附件；其他附件请由项目经理或管理员处理。')
        except PermissionDenied as exc:
            raise PermissionDenied(label(document, str(exc.detail))) from exc
        result.append((document, project, label))
    return result


def _remove_locked(user, entries, reason):
    for document, project, label in entries:
        if project is not None and project.status == 'closed':
            raise Conflict(label(document, '项目已结项，请先重新打开后再整理附件。'))
        used = referenced(document)
        if used:
            raise Conflict(label(document, f'此附件已作为{used}的依据，不能删除；请上传新版本并在原单据中说明。'))
    for document, _project, _label in entries:
        document.soft_delete(user)
        audit(user, 'document.remove', document, filename=document.original_name, sha256=document.sha256, reason=reason)


def remove(actor, key, document_id, data):
    """软删除误传的附件。

    以前上传是单向的：传错文件、传错分类、传错项目都只能再传一份，两份并存。
    这里保留记录和文件本体，只把它移出列表，并要求填写原因留审计。
    """
    source = get_object_or_404(Document.objects, pk=identity(document_id, 'document'))
    context = {}

    def authorize(user):
        require_role(user, ALL_ROLES)
        user.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        context['entries'] = _lock_for_removal(user, [source.pk])

    def execute(user):
        fields(data, {'reason'})
        reason = text(data, 'reason')
        _remove_locked(user, context['entries'], reason)
        return {'id': source.pk}

    return perform(
        actor=actor,
        key=key,
        operation='document.remove',
        payload={'document': source.pk, 'data': data},
        authorize=authorize,
        execute=execute,
    )


def remove_many(actor, key, data):
    """一次事务删除多份误传附件：授权、拦截与单个删除相同，任一份被拦截则整批不动。"""
    if not isinstance(data, dict):
        raise ValidationError('请提交 JSON 对象。')
    fields(data, {'documents', 'reason'})
    raw = data.get('documents')
    if not isinstance(raw, list) or not raw:
        raise ValidationError({'documents': '请选择要删除的附件。'})
    if len(raw) > MAX_REMOVE_BATCH:
        raise ValidationError({'documents': f'每次最多删除 {MAX_REMOVE_BATCH} 份附件，请分批处理。'})
    ids = [identity(value, 'documents') for value in raw]
    if len(set(ids)) != len(ids):
        raise ValidationError({'documents': '附件重复，请刷新后重新选择。'})
    reason = text(data, 'reason')
    context = {}

    def authorize(user):
        require_role(user, ALL_ROLES)
        user.refresh_from_db(fields=['role', 'additional_roles', 'is_active', 'is_superuser'])
        # 与单个删除一致：看不到的附件按不存在处理，不泄露其存在。
        visible = set(visible_documents(user, Document.objects.filter(pk__in=ids)).values_list('pk', flat=True))
        if visible != set(ids):
            raise NotFound('部分附件不存在或无权访问，请刷新后重新选择。')
        context['entries'] = _lock_for_removal(user, ids)

    def execute(user):
        _remove_locked(user, context['entries'], reason)
        return {'removed': len(ids), 'documents': sorted(ids)}

    return perform(
        actor=actor,
        key=key,
        operation='document.remove_batch',
        payload={'documents': sorted(ids), 'reason': reason},
        authorize=authorize,
        execute=execute,
    )
