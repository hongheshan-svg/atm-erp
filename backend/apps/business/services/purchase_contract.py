"""Printable purchase agreement projected from the current order, without a second ledger."""

import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F, OuterRef, Subquery
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import Company
from apps.core.permissions import MONEY_READERS, PURCHASERS, require_project, require_role

from ..models import Document, PurchaseContractVersion, PurchaseLine
from .common import ZERO, audit, fields, lookup, rounded, save, state, text
from .contract_clauses import TEMPLATE_VERSION, clauses
from .supply import purchase_action, total


def preview(actor, purchase):
    require_role(actor, MONEY_READERS | PURCHASERS)
    require_project(actor, purchase.project, MONEY_READERS | PURCHASERS)
    company = Company.objects.first()
    supplier = purchase.supplier
    lines = list(purchase.lines.all())
    cancelled = sum(
        (
            rounded(line.quantity * line.unit_price)
            - rounded((line.quantity - line.cancelled_quantity) * line.unit_price)
            for line in lines
        ),
        ZERO,
    )
    return {
        'template_version': TEMPLATE_VERSION,
        'clauses': clauses(purchase.warranty_months),
        'warranty_months': purchase.warranty_months,
        'id': purchase.pk,
        'code': purchase.code,
        'status': purchase.status,
        'status_label': purchase.get_status_display(),
        'draft': purchase.status in {'draft', 'submitted'},
        'date': timezone.localdate(purchase.created_at),
        'updated_at': purchase.updated_at,
        'project': purchase.project.name,
        'buyer': {
            'name': company.name if company else '',
            'address': company.address if company else '',
            'phone': company.phone if company else '',
        },
        'supplier': {
            'name': supplier.name,
            'address': supplier.address,
            'contact': supplier.contact,
            'phone': supplier.phone,
        },
        'due_date': purchase.due_date,
        'payment_term': purchase.payment_term,
        'payment_days': purchase.payment_days,
        'payment_due_date': purchase.payment_due_date or purchase.due_date
        if purchase.payment_term == 'manual'
        else None,
        'note': purchase.note,
        'total': str(total(purchase)),
        'cancelled_amount': str(cancelled),
        'lines': [
            {
                'number': index,
                'code': line.item.code,
                'name': line.item.name,
                'specification': line.item.specification,
                'drawing_number': line.item.drawing_number,
                'drawing_revision': line.item.drawing_revision,
                'product_category': line.item.product_category,
                'brand': line.item.brand,
                'unit': line.item.unit,
                'quantity': str(line.quantity),
                'unit_price': str(line.unit_price),
                'amount': str(rounded(line.quantity * line.unit_price)),
                'due_date': line.due_date or purchase.due_date,
                'cancelled_quantity': str(line.cancelled_quantity),
            }
            for index, line in enumerate(lines, 1)
        ],
    }


def amount(value):
    try:
        return Decimal(str(value or '0'))
    except InvalidOperation:
        return Decimal('0')


def plain(value):
    return format(amount(value).normalize(), 'f')


def by_item(snapshot):
    """按物料编码汇总合同明细：同一物料分在多个 BOM 单元时合在一起比较，明细顺序变化不算合同变化。"""
    result = {}
    for line in snapshot.get('lines', []):
        row = result.setdefault(
            line['code'],
            {**line, 'effective': Decimal('0'), 'prices': [], 'due_dates': []},
        )
        row['effective'] += amount(line['quantity']) - amount(line.get('cancelled_quantity'))
        price = format(amount(line['unit_price']).quantize(Decimal('0.01')), 'f')
        for key, value in (('prices', price), ('due_dates', str(line.get('due_date') or '—'))):
            if value not in row[key]:
                row[key].append(value)
    return result


def contract_changes(archived, current):
    """归档版本到当前采购资料的合同实质变化：各物料（含图档版本）的有效数量（扣除取消）、单价、交期，
    以及整单交期与付款条件。收货进度、状态和双方联系方式不算合同变化。返回逐条中文说明，空列表表示一致。
    """
    changes = []
    old, new = by_item(archived), by_item(current)

    def name(line):
        return f'{line["code"]}（{line["drawing_revision"]} 版）' if line.get('drawing_revision') else line['code']

    def count(line, value):
        return f'{plain(value)} {line["unit"]}'.strip()

    for code in [*old, *(code for code in new if code not in old)]:
        before, after = old.get(code), new.get(code)
        if before is None:
            changes.append(
                f'新增 {name(after)} {after["name"]} {count(after, after["effective"])}，单价 {"/".join(after["prices"])}'
            )
            continue
        if after is None:
            changes.append(f'{name(before)} 已不在采购单')
            continue
        if before['effective'] != after['effective']:
            changes.append(f'{name(after)} 数量 {plain(before["effective"])} → {plain(after["effective"])}')
        if before['prices'] != after['prices']:
            changes.append(f'{name(after)} 单价 {"/".join(before["prices"])} → {"/".join(after["prices"])}')
        if before['due_dates'] != after['due_dates']:
            changes.append(f'{name(after)} 交期 {"/".join(before["due_dates"])} → {"/".join(after["due_dates"])}')
    if str(archived.get('due_date') or '') != str(current.get('due_date') or ''):
        changes.append(f'整单交期 {archived.get("due_date") or "—"} → {current.get("due_date") or "—"}')
    terms = ('payment_term', 'payment_days', 'payment_due_date')
    if any(str(archived.get(field) or '') != str(current.get(field) or '') for field in terms):
        changes.append('付款条件已变化')
    return changes


def stale_contracts(actor, queryset):
    """换版改单确认后合同内容已变化、还没归档新版本的采购单 ID（工作台提醒采购重签）。"""
    archived = PurchaseContractVersion.objects.filter(purchase=OuterRef('purchase_id')).order_by('-version')
    candidates = (
        PurchaseLine.objects.filter(
            purchase__in=queryset,
            revision_role='converted',
            revision_pending=False,
            quantity__gt=F('cancelled_quantity'),
        )
        .annotate(archived_at=Subquery(archived.values('created_at')[:1]))
        .filter(archived_at__isnull=False, updated_at__gt=F('archived_at'))
        .values_list('purchase_id', flat=True)
        .distinct()
    )
    result = []
    for purchase in queryset.filter(pk__in=list(candidates)).select_related('project', 'supplier'):
        saved = purchase.contract_versions.order_by('-version').first()
        if saved and contract_changes(saved.snapshot, preview(actor, purchase)):
            result.append(purchase.pk)
    return result


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def archive(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'expected_snapshot', 'document', 'delivery_address', 'reason', 'confirmed'})
        state(purchase, {'approved', 'partial', 'received'})
        current = preview(user, purchase)
        if data.get('expected_snapshot') != fingerprint(current):
            raise Conflict('采购或主体资料已变化，请刷新合同后重新确认签署版本。')
        if data.get('confirmed') is not True:
            raise ValidationError({'confirmed': '请确认上传的签署文件与当前完整合同、明细及条款一致。'})
        for party in ('buyer', 'supplier'):
            if not all(current[party].get(field, '').strip() for field in ('name', 'address', 'phone')):
                raise ValidationError('归档前请补齐双方名称、地址、电话，并重新核对合同。')
        doc = lookup(Document, data.get('document'), 'document', purchase=purchase, category='contract')
        current['delivery_address'] = text(data, 'delivery_address', maximum=250)
        latest = purchase.contract_versions.order_by('-version').first()
        version = save(
            PurchaseContractVersion(
                purchase=purchase,
                version=latest.version + 1 if latest else 1,
                snapshot=json.loads(json.dumps(current, cls=DjangoJSONEncoder)),
                document=doc,
                reason=text(data, 'reason', default='') or '归档采购合同',
            ),
            user,
        )
        return audit(
            user,
            'purchase.contract_archive',
            version,
            purchase=purchase.pk,
            version=version.version,
            document=doc.pk,
            sha256=doc.sha256,
            reason=version.reason,
        )

    return purchase_action(actor, key, 'purchase.contract_archive', purchase_id, data, PURCHASERS, execute)
