"""
BOM Multi-level Cost Rollup for Non-standard Automation Industry
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class BOMCostSnapshot(BaseModel):
    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='bom_cost_snapshots', verbose_name='项目'
    )
    version_label = models.CharField(max_length=100, verbose_name='版本标签')
    total_material_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='材料总成本'
    )
    total_labor_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='人工总成本'
    )
    total_overhead_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='制造费用总成本'
    )
    total_outsource_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='委外总成本'
    )
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='总计')
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_cost_calculations',
        verbose_name='计算人',
    )

    class Meta:
        db_table = 'projects_bom_cost_snapshot'
        ordering = ['-created_at']
        verbose_name = 'BOM成本快照'
        verbose_name_plural = 'BOM成本快照'

    def __str__(self):
        return f'{self.project} - {self.version_label}'


class BOMCostDetail(BaseModel):
    snapshot = models.ForeignKey(
        BOMCostSnapshot, on_delete=models.CASCADE, related_name='details', verbose_name='成本快照'
    )
    material_code = models.CharField(max_length=100, verbose_name='物料编码')
    material_name = models.CharField(max_length=200, verbose_name='物料名称')
    bom_level = models.IntegerField(default=0, verbose_name='BOM层级')
    parent_material_code = models.CharField(max_length=100, blank=True, default='', verbose_name='父物料编码')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'), verbose_name='数量')
    unit_material_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='单位材料成本'
    )
    extended_material_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='材料成本小计'
    )
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='人工成本')
    overhead_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='制造费用'
    )
    outsource_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='委外成本'
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='小计')

    class Meta:
        db_table = 'projects_bom_cost_detail'
        ordering = ['bom_level', 'material_code']
        verbose_name = 'BOM成本明细'
        verbose_name_plural = 'BOM成本明细'

    def __str__(self):
        return f'{self.material_code} - {self.material_name}'


class BOMCostRollupService:
    """BOM multi-level cost rollup calculation service."""

    @staticmethod
    def calculate_rollup(project_id, version_label, user):
        from apps.projects.models import BOM

        snapshot = BOMCostSnapshot.objects.create(
            project_id=project_id,
            version_label=version_label,
            calculated_by=user,
            created_by=user,
        )
        total_material = Decimal('0.00')
        total_labor = Decimal('0.00')
        total_overhead = Decimal('0.00')
        total_outsource = Decimal('0.00')

        bom_items = BOM.objects.filter(project_id=project_id, is_deleted=False).select_related('material')

        for item in bom_items:
            qty = getattr(item, 'quantity', Decimal('1'))
            unit_cost = Decimal('0.00')
            if hasattr(item, 'material') and item.material:
                unit_cost = getattr(item.material, 'unit_price', Decimal('0.00')) or Decimal('0.00')
            ext_cost = qty * unit_cost
            labor = Decimal('0.00')
            overhead = ext_cost * Decimal('0.10')
            outsource = Decimal('0.00')
            sub = ext_cost + labor + overhead + outsource

            BOMCostDetail.objects.create(
                snapshot=snapshot,
                material_code=getattr(item, 'material_code', '') or getattr(item.material, 'code', ''),
                material_name=getattr(item, 'material_name', '') or getattr(item.material, 'name', ''),
                bom_level=getattr(item, 'level', 0),
                parent_material_code=getattr(item, 'parent_material_code', ''),
                quantity=qty,
                unit_material_cost=unit_cost,
                extended_material_cost=ext_cost,
                labor_cost=labor,
                overhead_cost=overhead,
                outsource_cost=outsource,
                subtotal=sub,
                created_by=user,
            )
            total_material += ext_cost
            total_labor += labor
            total_overhead += overhead
            total_outsource += outsource

        snapshot.total_material_cost = total_material
        snapshot.total_labor_cost = total_labor
        snapshot.total_overhead_cost = total_overhead
        snapshot.total_outsource_cost = total_outsource
        snapshot.grand_total = total_material + total_labor + total_overhead + total_outsource
        snapshot.save()
        return snapshot


# ─── Serializers ────────────────────────────────────────────────


class BOMCostDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BOMCostDetail
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class BOMCostSnapshotSerializer(serializers.ModelSerializer):
    details = BOMCostDetailSerializer(many=True, read_only=True)

    class Meta:
        model = BOMCostSnapshot
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'calculated_by']


# ─── ViewSets ───────────────────────────────────────────────────


class BOMCostSnapshotViewSet(PermissionMixin, viewsets.ModelViewSet):
    permission_module = 'projects'
    permission_resource = 'bom_cost_snapshot'
    serializer_class = BOMCostSnapshotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BOMCostSnapshot.objects.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        project_id = request.data.get('project_id')
        version_label = request.data.get('version_label', 'v1')
        if not project_id:
            return Response({'error': '项目ID必填'}, status=status.HTTP_400_BAD_REQUEST)
        snapshot = BOMCostRollupService.calculate_rollup(project_id, version_label, request.user)
        return Response(BOMCostSnapshotSerializer(snapshot).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def compare(self, request):
        snapshot_ids = request.data.get('snapshot_ids', [])
        if len(snapshot_ids) < 2:
            return Response({'error': '至少选择两个快照进行对比'}, status=status.HTTP_400_BAD_REQUEST)
        snapshots = BOMCostSnapshot.objects.filter(id__in=snapshot_ids, is_deleted=False)
        return Response(BOMCostSnapshotSerializer(snapshots, many=True).data)


class BOMCostDetailViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    permission_module = 'projects'
    permission_resource = 'bom_cost_detail'
    serializer_class = BOMCostDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = BOMCostDetail.objects.filter(is_deleted=False)
        snapshot_id = self.request.query_params.get('snapshot_id')
        if snapshot_id:
            qs = qs.filter(snapshot_id=snapshot_id)
        return qs
