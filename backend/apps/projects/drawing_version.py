"""
Drawing Version Management with Approval Workflow
"""
from django.conf import settings
from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel


class DrawingVersion(BaseModel):
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('reviewing', '审核中'),
        ('approved', '已批准'),
        ('released', '已发布'),
        ('obsolete', '已废弃'),
    ]

    drawing_number = models.CharField(max_length=100, verbose_name='图纸编号')
    drawing_name = models.CharField(max_length=200, verbose_name='图纸名称')
    version = models.IntegerField(default=1, verbose_name='版本号')
    revision = models.IntegerField(default=0, verbose_name='修订号')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态'
    )
    file = models.FileField(
        upload_to='drawings/%Y/%m/', null=True, blank=True, verbose_name='图纸文件'
    )
    change_description = models.TextField(blank=True, default='', verbose_name='变更描述')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='drawing_versions_created', verbose_name='创建人'
    )

    class Meta:
        db_table = 'projects_drawing_version'
        ordering = ['drawing_number', '-version', '-revision']
        verbose_name = '图纸版本'
        verbose_name_plural = '图纸版本'
        unique_together = [('drawing_number', 'version', 'revision')]

    def __str__(self):
        return f"{self.drawing_number} v{self.version}.{self.revision}"


class DrawingAffectedPart(BaseModel):
    drawing_version = models.ForeignKey(
        DrawingVersion, on_delete=models.CASCADE,
        related_name='affected_parts', verbose_name='图纸版本'
    )
    part_number = models.CharField(max_length=100, verbose_name='零件编号')
    part_name = models.CharField(max_length=200, verbose_name='零件名称')
    impact_description = models.TextField(blank=True, default='', verbose_name='影响描述')

    class Meta:
        db_table = 'projects_drawing_affected_part'
        ordering = ['part_number']
        verbose_name = '图纸影响零件'
        verbose_name_plural = '图纸影响零件'

    def __str__(self):
        return f"{self.part_number} - {self.part_name}"


# ─── Serializers ────────────────────────────────────────────────

class DrawingAffectedPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrawingAffectedPart
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class DrawingVersionSerializer(serializers.ModelSerializer):
    affected_parts = DrawingAffectedPartSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DrawingVersion
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# ─── ViewSets ───────────────────────────────────────────────────

class DrawingVersionViewSet(viewsets.ModelViewSet):
    serializer_class = DrawingVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = DrawingVersion.objects.filter(is_deleted=False)
        drawing_number = self.request.query_params.get('drawing_number')
        if drawing_number:
            qs = qs.filter(drawing_number=drawing_number)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def timeline(self, request):
        drawing_number = request.query_params.get('drawing_number')
        if not drawing_number:
            return Response({'error': '请指定图纸编号'}, status=status.HTTP_400_BAD_REQUEST)
        versions = self.get_queryset().filter(drawing_number=drawing_number)
        return Response(DrawingVersionSerializer(versions, many=True).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        drawing = self.get_object()
        if drawing.status != 'reviewing':
            return Response({'error': '只有审核中的图纸才能批准'}, status=status.HTTP_400_BAD_REQUEST)
        drawing.status = 'approved'
        drawing.save(update_fields=['status', 'updated_at'])
        return Response(DrawingVersionSerializer(drawing).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        drawing = self.get_object()
        if drawing.status != 'reviewing':
            return Response({'error': '只有审核中的图纸才能驳回'}, status=status.HTTP_400_BAD_REQUEST)
        drawing.status = 'draft'
        drawing.save(update_fields=['status', 'updated_at'])
        return Response(DrawingVersionSerializer(drawing).data)

    @action(detail=False, methods=['post'])
    def batch_upgrade(self, request):
        drawing_number = request.data.get('drawing_number')
        if not drawing_number:
            return Response({'error': '请指定图纸编号'}, status=status.HTTP_400_BAD_REQUEST)
        latest = DrawingVersion.objects.filter(
            drawing_number=drawing_number, is_deleted=False
        ).order_by('-version', '-revision').first()
        if not latest:
            return Response({'error': '未找到该图纸'}, status=status.HTTP_404_NOT_FOUND)
        new_version = DrawingVersion.objects.create(
            drawing_number=drawing_number,
            drawing_name=latest.drawing_name,
            version=latest.version + 1,
            revision=0,
            status='draft',
            change_description=request.data.get('change_description', ''),
            created_by=request.user,
        )
        return Response(DrawingVersionSerializer(new_version).data, status=status.HTTP_201_CREATED)


class DrawingAffectedPartViewSet(viewsets.ModelViewSet):
    serializer_class = DrawingAffectedPartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = DrawingAffectedPart.objects.filter(is_deleted=False)
        drawing_version_id = self.request.query_params.get('drawing_version_id')
        if drawing_version_id:
            qs = qs.filter(drawing_version_id=drawing_version_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
