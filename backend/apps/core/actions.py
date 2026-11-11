import hashlib
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import PermissionDenied, ValidationError

from .api import Conflict
from .models import ActionReceipt


def receipt_data(data):
    """把请求数据整理成回执指纹用的普通对象（表单多值字段保留全部值）。

    回执不存密码，也不存含密码的无盐摘要（与首次配置一致）：密码只以加盐 HMAC 参与比对。
    """
    if hasattr(data, 'lists'):
        data = dict(data.lists())
    elif isinstance(data, dict):
        data = dict(data)
    if isinstance(data, dict) and 'password' in data:
        secret = json.dumps(data['password'], ensure_ascii=False, default=str)
        data['password'] = salted_hmac('action-receipt-password', secret).hexdigest()
    return data


def require_key(key):
    """Reject a missing or oversized Idempotency-Key; callers may check it before any slow or outbound work."""
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        raise ValidationError({'Idempotency-Key': '必须提供不超过 128 字符的操作标识。'})
    return key


def perform(*, actor, key, operation, payload, authorize, execute):
    """Authorize each attempt; receipt creation and business writes commit together."""
    require_key(key)
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError('操作数据必须为有效 JSON。') from exc
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    with transaction.atomic():
        from .periods import mutation_lock

        mutation_lock(exclusive=operation in {'period.lock', 'record.delete'})
        current_actor = get_user_model().objects.get(pk=actor.pk)
        if not current_actor.is_active:
            raise PermissionDenied('用户已停用。')
        authorize(current_actor)
        receipt, created = ActionReceipt.objects.get_or_create(
            actor=current_actor,
            key=key,
            defaults={'operation': operation, 'fingerprint': fingerprint},
        )
        if not created:
            if receipt.operation != operation or receipt.fingerprint != fingerprint:
                raise Conflict('此操作标识已用于不同数据，请刷新后重试。')
            return receipt.result
        result = execute(current_actor)
        receipt.result = result
        receipt.save(update_fields=['result'])
        return result
