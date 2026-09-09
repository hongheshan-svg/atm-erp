from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import (
    OPERATION_ROLES,
    PermissionMixin,
    role,
)

from ..services import tabular, transfers


def key(request):
    return request.headers.get('Idempotency-Key')


class ReadView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    parser_classes = [JSONParser]
    write_roles = OPERATION_ROLES

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        if queryset.count() > tabular.MAX_EXPORT:
            raise ValidationError('导出超过20000条，请缩小筛选范围。')
        serializer = self.get_serializer()
        fields = list(serializer.fields)
        if hasattr(serializer, 'money_roles') and role(request.user) not in serializer.money_roles:
            fields = [field for field in fields if field not in serializer.sensitive_fields]
        return tabular.export_rows(
            self.basename,
            self.get_serializer(queryset, many=True).data,
            request.query_params.get('file_format', 'csv'),
            fields,
        )

    @action(detail=False, methods=['get'], url_path='import-template')
    def import_template(self, request):
        return transfers.template(
            request.user, self.request.path.split('/')[-3], request.query_params.get('file_format', 'csv')
        )

    @action(detail=False, methods=['post'], url_path='import-file', parser_classes=[MultiPartParser])
    def import_file(self, request):
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError('请上传一个表格文件。')
        return Response(transfers.preview(request.user, request.path.split('/')[-3], request.FILES['file']))

    @action(detail=False, methods=['post'], url_path='import-confirm')
    def import_confirm(self, request):
        if set(request.data) != {'token'}:
            raise ValidationError('请提交预览凭据。')
        return Response(transfers.confirm(request.user, request.path.split('/')[-3], request.data['token']))

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {'POST', 'PATCH'} and not isinstance(request.data, dict):
            raise ValidationError('请提交 JSON 对象。')
