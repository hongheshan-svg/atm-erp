"""IPD 阶段决策评审(Stage Gate / DCP)基础脚手架。

按 IPD(集成产品开发)思想,为项目提供阶段决策评审点(Gate):在关键阶段
(立项/概念/验证/量产等)做 Go / Kill / Redirect 决策。本模块复用 requirement_review
的评审建模与 ViewSet 组合方式(PermissionMixin + SoftDeleteMixin + UserTrackingMixin),
提供模型 + 序列化器 + ViewSet。

**foundation vs 完成边界:**
本次落地“阶段门评审记录 + 决策动作 + 评审人”这一最小可用闭环。与工作流引擎
(WorkflowEnforcementMixin)的审批联动、阶段门通过后自动推进项目/生产阶段、
门禁未过时阻断下游单据、评审检查项打分等,为后续里程碑。
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class StageGate(BaseModel):
    """IPD 阶段决策评审点(Gate / DCP)。"""

    # IPD 常见阶段门:立项、概念/需求、工程验证、设计验证、生产验证、量产、
    # 决策评审点(DCP)、技术评审(TR)。
    STAGE_CHOICES = [
        ('CHARTER', '立项 (Charter)'),
        ('ES', '概念/需求 (ES)'),
        ('EVT', '工程验证 (EVT)'),
        ('DVT', '设计验证 (DVT)'),
        ('PVT', '生产验证 (PVT)'),
        ('MP', '量产 (MP)'),
        ('DCP', '决策评审点 (DCP)'),
        ('TR', '技术评审 (TR)'),
    ]

    DECISION_CHOICES = [
        ('PENDING', '待决策'),
        ('GO', '通过 (Go)'),
        ('KILL', '终止 (Kill)'),
        ('REDIRECT', '调整方向 (Redirect)'),
    ]

    gate_no = models.CharField(max_length=50, unique=True, blank=True, verbose_name='评审编号')
    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='stage_gates', verbose_name='项目'
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, verbose_name='阶段')
    title = models.CharField(max_length=200, blank=True, verbose_name='评审标题')

    decision = models.CharField(
        max_length=20, choices=DECISION_CHOICES, default='PENDING', verbose_name='决策结果'
    )
    decision_date = models.DateField(null=True, blank=True, verbose_name='决策日期')

    scheduled_date = models.DateField(null=True, blank=True, verbose_name='计划评审日期')

    # 评审人集合(基础建模;后续可细化为角色/出席/打分,见 requirement_review)。
    reviewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='stage_gate_reviews', verbose_name='评审人'
    )

    summary = models.TextField(blank=True, verbose_name='评审结论')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'plm_stage_gate'
        verbose_name = 'IPD阶段评审'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'stage']),
            models.Index(fields=['decision']),
        ]

    def __str__(self):
        return f'{self.gate_no} - {self.get_stage_display()}'

    def save(self, *args, **kwargs):
        if not self.gate_no:
            from apps.core.utils import generate_code

            self.gate_no = generate_code('GATE')
        super().save(*args, **kwargs)


# =====================
# Serializer
# =====================


class StageGateSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    decision_display = serializers.CharField(source='get_decision_display', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)

    class Meta:
        model = StageGate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'gate_no']


# =====================
# ViewSet
# =====================


class StageGateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """IPD 阶段决策评审管理。"""

    permission_module = 'projects'
    permission_resource = 'stage_gate'
    queryset = StageGate.objects.filter(is_deleted=False)
    serializer_class = StageGateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'stage', 'decision']
    search_fields = ['gate_no', 'title']
    ordering_fields = ['scheduled_date', 'decision_date', 'created_at']

    @action(detail=True, methods=['post'])
    def decide(self, request, pk=None):
        """记录一次阶段门决策(Go / Kill / Redirect)。"""
        gate = self.get_object()
        decision = request.data.get('decision')
        valid = {c[0] for c in StageGate.DECISION_CHOICES}
        if decision not in valid:
            return Response({'error': f'无效的决策值,应为 {sorted(valid)} 之一'}, status=400)

        gate.decision = decision
        gate.decision_date = request.data.get('decision_date') or timezone.now().date()
        if 'summary' in request.data:
            gate.summary = request.data.get('summary', '')
        gate.updated_by = request.user
        gate.save()
        return Response(self.get_serializer(gate).data)
