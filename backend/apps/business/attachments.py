from django.http import FileResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import ALL_ROLES

from .api.common import ReadView, key
from .models import Document
from .services import documents
from .services.common import identity


class DocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()

    def get_project(self, obj):
        return obj.sale.project_id if obj.sale_id else obj.purchase.project_id if obj.purchase_id else obj.project_id

    def get_source(self, obj):
        return (
            f'销售单 {obj.sale.code}'
            if obj.sale_id
            else f'采购单 {obj.purchase.code}'
            if obj.purchase_id
            else '项目附件'
        )

    def get_download_url(self, obj):
        return f'/api/business/documents/{obj.pk}/download/'

    class Meta:
        model = Document
        fields = [
            'id',
            'project',
            'sale',
            'purchase',
            'source',
            'category',
            'original_name',
            'size',
            'sha256',
            'created_at',
            'created_by',
            'download_url',
        ]


class DocumentView(ReadView):
    read_roles = ALL_ROLES
    write_roles = ALL_ROLES
    queryset = Document.objects.select_related('sale', 'purchase')
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser]
    filterset_fields = ['sale', 'purchase', 'category']
    search_fields = ['original_name']

    def get_queryset(self):
        scoped = documents.visible_documents(self.request.user, super().get_queryset())
        if self.request.query_params.get('project'):
            scoped = documents.for_project(scoped, identity(self.request.query_params['project'], 'project'))
        return scoped

    def create(self, request):
        owners = set(request.data) & {'project', 'sale', 'purchase'}
        if (
            len(owners) != 1
            or set(request.data) != owners | {'category', 'file'}
            or any(len(request.data.getlist(field)) != 1 for field in request.data)
        ):
            raise ValidationError('请提交一个项目、销售单或采购单，附件分类和一个文件。')
        return Response(
            documents.upload(
                request.user,
                key(request),
                request.data.get('project'),
                request.data['category'],
                request.FILES.get('file'),
                sale_id=request.data.get('sale'),
                purchase_id=request.data.get('purchase'),
            ),
            status=201,
        )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        document = self.get_object()
        try:
            stream = document.file.open('rb')
        except (OSError, ValueError) as exc:
            raise NotFound('附件文件暂不可用，请联系管理员检查或恢复备份。') from exc
        response = FileResponse(
            stream, as_attachment=True, filename=document.original_name, content_type='application/octet-stream'
        )
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
