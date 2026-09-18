from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.core.permissions import (
    GLOBAL_PROJECT_ROLES,
    OPERATION_ROLES,
    PermissionMixin,
    has_role,
    projects_for,
)

from ..models import Project
from ..services import tabular, transfers


def key(request):
    return request.headers.get('Idempotency-Key')


class ExportThrottle(UserRateThrottle):
    """导出一次最多序列化两万行，是这里最贵的接口。"""

    scope = 'export'


class ImportThrottle(UserRateThrottle):
    """解析上传表格和落库。放得比导出宽，因为「传错→改文件→重传」是正常节奏。"""

    scope = 'import'


class ReadView(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    parser_classes = [JSONParser]
    write_roles = OPERATION_ROLES

    def get_queryset(self):
        queryset = super().get_queryset()
        # List, detail, export and action lookup share the same project boundary.
        path = {
            'purchaseorder': 'project',
            'entry': 'project',
            'payment': 'entry__project',
            'reconciliation': 'entry__project',
            'stockmove': 'project',
        }.get(queryset.model._meta.model_name)
        if path and not has_role(self.request.user, GLOBAL_PROJECT_ROLES):
            queryset = queryset.filter(**{f'{path}__in': projects_for(self.request.user, Project.objects.all())})
        return queryset

    @action(detail=False, methods=['get'], url_path='export', throttle_classes=[ExportThrottle])
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        if queryset.count() > tabular.MAX_EXPORT:
            raise ValidationError('导出超过20000条，请缩小筛选范围。')
        serializer = self.get_serializer()
        fields = list(serializer.fields)
        if hasattr(serializer, 'money_roles') and not has_role(request.user, serializer.money_roles):
            fields = [field for field in fields if field not in serializer.sensitive_fields]
        return tabular.export_rows(
            self.basename,
            self.get_serializer(queryset, many=True).data,
            request.query_params.get('file_format', 'csv'),
            fields,
        )

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {'POST', 'PATCH'} and not isinstance(request.data, dict):
            raise ValidationError('请提交 JSON 对象。')


class ImportableMixin:
    """表格导入的四个步骤。只混入 transfers 真正登记了字段表的资源。

    以前这些 action 挂在 ReadView 上，附件、银行匹配、对账这些用不上表格导入的资源
    也各自多出四条路由，除了返回 400 没有别的作用。
    """

    @action(detail=False, methods=['get'], url_path='import-template')
    def import_template(self, request):
        return transfers.template(
            request.user, self.request.path.split('/')[-3], request.query_params.get('file_format', 'csv')
        )

    @action(detail=False, methods=['get'], url_path='import-schema')
    def import_schema(self, request):
        return Response(transfers.layout(request.user, request.path.split('/')[-3]))

    @action(
        detail=False,
        methods=['post'],
        url_path='import-file',
        parser_classes=[MultiPartParser],
        throttle_classes=[ImportThrottle],
    )
    def import_file(self, request):
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError('请上传一个表格文件。')
        return Response(transfers.preview(request.user, request.path.split('/')[-3], request.FILES['file']))

    @action(detail=False, methods=['post'], url_path='import-confirm', throttle_classes=[ImportThrottle])
    def import_confirm(self, request):
        if set(request.data) != {'token'}:
            raise ValidationError('请提交预览凭据。')
        return Response(transfers.confirm(request.user, request.path.split('/')[-3], request.data['token']))
