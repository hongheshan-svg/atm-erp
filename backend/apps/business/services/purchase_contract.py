"""Printable purchase agreement projected from the current order, without a second ledger."""

import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import Company
from apps.core.permissions import MONEY_READERS, PURCHASERS, require_project, require_role

from ..models import Document, PurchaseContractVersion
from .common import ZERO, audit, fields, lookup, rounded, save, state, text
from .contract_clauses import CLAUSES
from .supply import purchase_action, total


def preview(actor, purchase):
    require_role(actor, MONEY_READERS | PURCHASERS)
    require_project(actor, purchase.project)
    company = Company.objects.first()
    supplier = purchase.supplier
    lines = list(purchase.lines.all())
    cancelled = sum((rounded(line.cancelled_quantity * line.unit_price) for line in lines), ZERO)
    return {
        'template_version': 1,
        'clauses': CLAUSES,
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
            raise ValidationError({'confirmed': '请确认上传的签署文件与当前正文及附件一致。'})
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
                reason=text(data, 'reason'),
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
