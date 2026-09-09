import hashlib
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

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
    projects_for,
    require_project,
    require_role,
    require_sale,
    role,
)

from ..models import Document, Project, PurchaseOrder, SalesOrder
from .common import audit, identity, project_action, save

MAX_BYTES = 20 * 1024 * 1024
MONEY_CATEGORIES = {'contract', 'receipt'}


def visible_documents(user, queryset):
    allowed = Q(pk__in=[])
    if role(user) in OPERATION_ROLES:
        direct = Q(project__in=projects_for(user, Project.objects.all()))
        if role(user) not in MONEY_READERS:
            direct &= ~Q(category__in=MONEY_CATEGORIES)
        allowed |= direct
    if role(user) in SALES_READERS:
        sales = SalesOrder.objects.all()
        if role(user) == 'sales_manager':
            sales = sales.filter(manager=user)
        allowed |= Q(sale__in=sales)
    if role(user) in PURCHASERS | FINANCE:
        allowed |= Q(purchase__in=PurchaseOrder.objects.filter(project__in=Project.objects.all()))
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
                user.refresh_from_db(fields=['role', 'is_active', 'is_superuser'])
                require_role(user, roles)
                if owner == 'sale':
                    require_sale(user, source)
                elif project:
                    require_project(user, project)
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
