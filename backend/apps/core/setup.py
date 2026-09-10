"""First-install configuration; updates the original company, users and code rules atomically."""

import json

from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api import UserSerializer
from apps.accounts.models import User

from .actions import perform
from .api import Conflict
from .codes import configure
from .models import AuditLog, CodeRule, Company
from .permissions import ADMIN, require_role, roles
from .views import CodeSerializer


class CompanyInput(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    address = serializers.CharField(max_length=250)
    phone = serializers.CharField(max_length=50)


class SetupInput(serializers.Serializer):
    display_name = serializers.CharField(max_length=80)
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)
    company = CompanyInput()
    team = serializers.ListField(child=serializers.DictField(), max_length=50)
    codes = serializers.ListField(child=serializers.DictField(), max_length=7)
    confirmed = serializers.BooleanField()


class SetupView(APIView):
    def get(self, request):
        require_role(request.user, ADMIN)
        company = Company.objects.get(pk=1)
        return Response(
            {
                'required': company.setup_required,
                'completed_at': company.setup_completed_at,
                'company': {'name': company.name, 'address': company.address, 'phone': company.phone},
                'codes': CodeSerializer(CodeRule.objects.order_by('id'), many=True).data,
            }
        )

    def post(self, request):
        require_role(request.user, ADMIN)
        serializer = SetupInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not data['confirmed']:
            raise ValidationError('请确认初始化资料。')

        def execute(actor):
            company = Company.objects.select_for_update().get(pk=1)
            actor = User.objects.select_for_update().get(pk=actor.pk)
            require_role(actor, ADMIN)
            if not actor.is_active:
                raise ValidationError('账号已停用。')
            if not company.setup_required:
                raise Conflict('首次配置已经完成，请在设置中维护资料。')
            if not actor.check_password(data['old_password']):
                raise ValidationError({'old_password': '初始密码不正确。'})
            if actor.check_password(data['new_password']):
                raise ValidationError({'new_password': '请设置与初始密码不同的新密码。'})
            validate_password(data['new_password'], actor)
            if data['company']['name'] == '我的公司':
                raise ValidationError({'company': '请填写实际公司名称。'})
            allowed_user_fields = {'username', 'display_name', 'password', 'roles', 'hourly_cost', 'management_reports'}
            created = []
            for index, row in enumerate(data['team']):
                if set(row) - allowed_user_fields:
                    raise ValidationError({'team': f'第 {index + 1} 位人员包含不支持的字段。'})
                member = UserSerializer(data=row)
                if not member.is_valid():
                    raise ValidationError({'team': {str(index + 1): member.errors}})
                target = member.save()
                created.append(target.pk)
                AuditLog.objects.create(
                    actor=actor,
                    operation='user.create',
                    resource=f'user:{target.pk}',
                    detail={'roles': sorted(roles(target)), 'management_reports': target.management_reports},
                )
            seen = set()
            for row in data['codes']:
                rule_id = row.get('id')
                if type(rule_id) is not int or rule_id in seen:
                    raise ValidationError({'codes': '编号规则标识无效或重复。'})
                seen.add(rule_id)
                configure(
                    actor,
                    salted_hmac('setup-code', f'{request.headers.get("Idempotency-Key")}:{rule_id}').hexdigest(),
                    rule_id,
                    {key: value for key, value in row.items() if key != 'id'},
                )
            for name, value in data['company'].items():
                setattr(company, name, value)
            company.setup_required = False
            company.setup_completed_at = timezone.now()
            company.save()
            actor.display_name = data['display_name']
            actor.set_password(data['new_password'])
            actor.save(update_fields=['display_name', 'password'])
            AuditLog.objects.create(
                actor=actor,
                operation='system.setup',
                resource='company:1',
                detail={'users': created, 'codes': sorted(seen), 'company_fields': sorted(data['company'])},
            )
            return {'completed': True, 'detail': '首次配置完成，请使用新密码登录。'}

        # Receipts never contain passwords, or an unsalted digest of password-bearing input.
        payload = salted_hmac('first-install', json.dumps(request.data, sort_keys=True, ensure_ascii=False)).hexdigest()
        return Response(
            perform(
                actor=request.user,
                key=request.headers.get('Idempotency-Key'),
                operation='system.setup',
                payload={'submission': payload},
                authorize=lambda actor: require_role(actor, ADMIN),
                execute=execute,
            )
        )
