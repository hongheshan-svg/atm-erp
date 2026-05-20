"""
Kanban WIP Limits Management
"""

from django.db import models
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class KanbanWIPRule(BaseModel):
    process_name = models.CharField(max_length=200, unique=True, verbose_name='工序名称')
    wip_limit = models.IntegerField(verbose_name='WIP上限')
    warning_threshold = models.IntegerField(default=80, verbose_name='预警阈值(%)')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'production_kanban_wip_rule'
        ordering = ['process_name']
        verbose_name = '看板WIP规则'
        verbose_name_plural = '看板WIP规则'

    def __str__(self):
        return f'{self.process_name} (limit={self.wip_limit})'


class KanbanWIPAlert(BaseModel):
    ALERT_TYPE_CHOICES = [
        ('warning', '预警'),
        ('critical', '严重'),
        ('blocked', '阻塞'),
    ]

    process_name = models.CharField(max_length=200, verbose_name='工序名称')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, verbose_name='告警类型')
    current_wip = models.IntegerField(verbose_name='当前WIP')
    wip_limit = models.IntegerField(verbose_name='WIP上限')
    message = models.TextField(blank=True, default='', verbose_name='告警消息')

    class Meta:
        db_table = 'production_kanban_wip_alert'
        ordering = ['-created_at']
        verbose_name = '看板WIP告警'
        verbose_name_plural = '看板WIP告警'

    def __str__(self):
        return f'{self.process_name} - {self.alert_type}'


class KanbanWIPService:
    """Service for checking WIP status and generating alerts."""

    @staticmethod
    def check_wip_status():
        rules = KanbanWIPRule.objects.filter(is_deleted=False, is_active=True)
        statuses = []
        for rule in rules:
            try:
                from apps.production.models import ProductionOrder

                current_wip = ProductionOrder.objects.filter(
                    process_name=rule.process_name,
                    status='in_progress',
                    is_deleted=False,
                ).count()
            except Exception:
                current_wip = 0

            utilization = (current_wip / rule.wip_limit * 100) if rule.wip_limit > 0 else 0
            if current_wip >= rule.wip_limit:
                level = 'blocked'
            elif utilization >= rule.warning_threshold:
                level = 'warning'
            else:
                level = 'normal'

            statuses.append(
                {
                    'process_name': rule.process_name,
                    'wip_limit': rule.wip_limit,
                    'current_wip': current_wip,
                    'utilization_pct': round(utilization, 1),
                    'level': level,
                    'warning_threshold': rule.warning_threshold,
                }
            )
        return statuses

    @staticmethod
    def generate_alerts():
        statuses = KanbanWIPService.check_wip_status()
        alerts_created = []
        for s in statuses:
            if s['level'] in ('warning', 'blocked'):
                alert_type = 'critical' if s['level'] == 'blocked' else 'warning'
                message = (
                    f"工序 {s['process_name']} 当前WIP={s['current_wip']}, "
                    f"上限={s['wip_limit']}, 利用率={s['utilization_pct']}%"
                )
                alert = KanbanWIPAlert.objects.create(
                    process_name=s['process_name'],
                    alert_type=alert_type,
                    current_wip=s['current_wip'],
                    wip_limit=s['wip_limit'],
                    message=message,
                )
                alerts_created.append(alert)
        return alerts_created


# ─── Serializers ────────────────────────────────────────────────


class KanbanWIPRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = KanbanWIPRule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class KanbanWIPAlertSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)

    class Meta:
        model = KanbanWIPAlert
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# ─── ViewSets ───────────────────────────────────────────────────


class KanbanWIPRuleViewSet(PermissionMixin, viewsets.ModelViewSet):
    serializer_class = KanbanWIPRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return KanbanWIPRule.objects.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class KanbanWIPAlertViewSet(PermissionMixin, viewsets.ModelViewSet):
    serializer_class = KanbanWIPAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = KanbanWIPAlert.objects.filter(is_deleted=False)
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            qs = qs.filter(alert_type=alert_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ─── APIView ────────────────────────────────────────────────────


class KanbanWIPStatusView(APIView):
    """GET: Return current WIP status for all active processes."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        statuses = KanbanWIPService.check_wip_status()
        return Response(
            {
                'total_processes': len(statuses),
                'statuses': statuses,
            }
        )
