from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser

from apps.core.permissions import (
    ALL_ROLES,
    PermissionMixin,
)


def key(request):
    return request.headers.get('Idempotency-Key')


class ReadView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    parser_classes = [JSONParser]
    write_roles = ALL_ROLES

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {'POST', 'PATCH'} and not isinstance(request.data, dict):
            raise ValidationError('请提交 JSON 对象。')
