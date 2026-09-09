import hashlib
import json

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from .api import Conflict
from .models import ActionReceipt


def perform(*, actor, key, operation, payload, authorize, execute):
    """Authorize each attempt; receipt creation and business writes commit together."""
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        raise ValidationError({'Idempotency-Key': '必须提供不超过 128 字符的操作标识。'})
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError('操作数据必须为有效 JSON。') from exc
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    with transaction.atomic():
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
