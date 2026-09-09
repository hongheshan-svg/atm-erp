from django.http import FileResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import projects_for

from .api.common import ReadView, key
from .models import Document, Project
from .services import documents


class DocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, obj):
        return f'/api/business/documents/{obj.pk}/download/'

    class Meta:
        model = Document
        fields = [
            'id',
            'project',
            'category',
            'original_name',
            'size',
            'sha256',
            'created_at',
            'created_by',
            'download_url',
        ]


class DocumentView(ReadView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser]
    filterset_fields = ['project', 'category']

    def get_queryset(self):
        scoped = super().get_queryset().filter(project__in=projects_for(self.request.user, Project.objects.all()))
        return documents.visible_documents(self.request.user, scoped)

    def create(self, request):
        if set(request.data) != {'project', 'category', 'file'} or any(
            len(request.data.getlist(field)) != 1 for field in ('project', 'category', 'file')
        ):
            raise ValidationError('请提交项目、附件分类和一个文件。')
        return Response(
            documents.upload(
                request.user, key(request), request.data['project'], request.data['category'], request.FILES.get('file')
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
