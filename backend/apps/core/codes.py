import re

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from .actions import perform
from .api import Conflict
from .models import AuditLog, CodeRule
from .permissions import ADMIN, require_role


def configure(actor, key, rule_id, data):
    def execute(user):
        allowed = {'prefix', 'date_format', 'padding', 'reset_cycle', 'reason', 'expected_revision'}
        if not isinstance(data, dict) or set(data) != allowed:
            raise ValidationError('请提交完整编号规则、修改原因及版本，不允许修改已用流水。')
        rule = get_object_or_404(CodeRule.objects.select_for_update(), pk=rule_id)
        if type(data['expected_revision']) is not int or data['expected_revision'] != rule.revision:
            raise Conflict('编号规则已更新，请刷新后重试。')
        prefix = data['prefix']
        if not isinstance(prefix, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,10}', prefix):
            raise ValidationError({'prefix': '前缀需为 1 至 10 位字母、数字、下划线或短横线。'})
        date_format, cycle = data['date_format'], data['reset_cycle']
        if date_format not in ('', 'YY', 'YYYY', 'YYYYMM', 'YYYYMMDD') or cycle not in (
            'never',
            'year',
            'month',
            'day',
        ):
            raise ValidationError('无效的日期格式或重置周期。')
        if (4 if date_format == 'YY' else len(date_format)) < {'never': 0, 'year': 4, 'month': 6, 'day': 8}[cycle]:
            raise ValidationError('日期格式必须包含重置周期，例如按月重置至少包含年月。')
        if (
            isinstance(data['padding'], bool)
            or not re.fullmatch(r'[0-9]{1,2}', str(data['padding']))
            or not 1 <= int(data['padding']) <= 10
        ):
            raise ValidationError({'padding': '流水位数必须为 1 至 10。'})
        reason = data['reason']
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValidationError({'reason': '请填写不超过 500 字符的修改原因。'})
        names = ['prefix', 'date_format', 'padding', 'reset_cycle']
        before = {name: getattr(rule, name) for name in names}
        after = dict(prefix=prefix, date_format=date_format, padding=int(data['padding']), reset_cycle=cycle)
        if before == after:
            raise ValidationError('编号规则没有变化。')
        for name, value in after.items():
            setattr(rule, name, value)
        # Configuration changes never rewind the current sequence.
        from django.utils import timezone

        rule.period = timezone.localdate().strftime('%Y%m%d')[: {'never': 0, 'year': 4, 'month': 6, 'day': 8}[cycle]]
        rule.revision += 1
        rule.save()
        AuditLog.objects.create(
            actor=user,
            operation='code.configure',
            resource=f'code:{rule.pk}',
            detail={'before': before, 'after': after, 'reason': reason.strip(), 'revision': rule.revision},
        )
        return {'id': rule.pk, 'revision': rule.revision}

    return perform(
        actor=actor,
        key=key,
        operation='code.configure',
        payload={'id': rule_id, 'data': data},
        authorize=lambda user: require_role(user, ADMIN),
        execute=execute,
    )
