"""
BOM高级功能模块
Advanced BOM Features
替代料管理、BOM对比等
"""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class BOMSubstitute(BaseModel):
    """BOM替代料"""

    SUBSTITUTE_TYPE_CHOICES = [
        ('EQUIVALENT', '等效替代'),
        ('SIMILAR', '相似替代'),
        ('TEMPORARY', '临时替代'),
        ('UPGRADE', '升级替代'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待审批'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('EXPIRED', '已过期'),
    ]

    bom_item = models.ForeignKey(
        'projects.ProjectBOM', on_delete=models.CASCADE, related_name='substitutes', verbose_name='BOM项'
    )
    original_item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='substitute_originals', verbose_name='原物料'
    )
    substitute_item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='substitute_items', verbose_name='替代物料'
    )

    substitute_type = models.CharField(
        max_length=20, choices=SUBSTITUTE_TYPE_CHOICES, default='EQUIVALENT', verbose_name='替代类型'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # 替代比例
    conversion_ratio = models.DecimalField(
        max_digits=10, decimal_places=4, default=1.0, verbose_name='换算比例', help_text='1个原物料 = N个替代物料'
    )

    # 有效期
    valid_from = models.DateField(null=True, blank=True, verbose_name='生效日期')
    valid_to = models.DateField(null=True, blank=True, verbose_name='失效日期')

    # 优先级 (数值越小优先级越高)
    priority = models.IntegerField(default=1, verbose_name='优先级')

    # 价格差异
    price_difference = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name='价格差异'
    )

    # 审批信息
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_substitutes',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    reason = models.TextField(blank=True, verbose_name='替代原因')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'plm_bom_substitute'
        verbose_name = 'BOM替代料'
        verbose_name_plural = verbose_name
        ordering = ['bom_item', 'priority']
        unique_together = ('bom_item', 'substitute_item')

    def __str__(self):
        return f'{self.original_item.sku} -> {self.substitute_item.sku}'

    @property
    def is_valid(self):
        """检查替代料是否在有效期内"""
        today = date.today()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_to and today > self.valid_to:
            return False
        return self.status == 'APPROVED'


class BOMVersion(BaseModel):
    """BOM版本记录"""

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='bom_versions', verbose_name='项目'
    )
    version = models.CharField(max_length=50, verbose_name='版本号')
    description = models.TextField(blank=True, verbose_name='版本说明')

    # 版本快照
    snapshot_data = models.JSONField(default=list, verbose_name='BOM快照')

    # 统计信息
    item_count = models.IntegerField(default=0, verbose_name='物料数量')
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, verbose_name='总成本')

    is_current = models.BooleanField(default=False, verbose_name='是否当前版本')
    released_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='released_bom_versions',
        verbose_name='发布人',
    )

    class Meta:
        db_table = 'plm_bom_version'
        verbose_name = 'BOM版本'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        unique_together = ('project', 'version')

    def __str__(self):
        return f'{self.project.code} - v{self.version}'

    def create_snapshot(self):
        """创建BOM快照"""
        from apps.projects.models import ProjectBOM

        bom_items = ProjectBOM.objects.filter(project=self.project, is_deleted=False).select_related('item')

        snapshot = []
        for item in bom_items:
            snapshot.append(
                {
                    'id': item.id,
                    'item_id': item.item_id,
                    'item_sku': item.item.sku if item.item else '',
                    'item_name': item.item.name if item.item else '',
                    'planned_qty': float(item.planned_qty),
                    'unit_cost': float(item.unit_cost or 0),
                    'total_cost': float(item.planned_qty * (item.unit_cost or 0)),
                    'parent_id': item.parent_id,
                    'level': item.level,
                    'notes': item.notes or '',
                }
            )

        self.snapshot_data = snapshot
        self.item_count = len(snapshot)
        self.total_cost = sum(i['total_cost'] for i in snapshot)
        self.save()

        return snapshot


class BOMComparison(BaseModel):
    """BOM对比记录"""

    name = models.CharField(max_length=200, verbose_name='对比名称')

    # 对比的两个版本
    version_a = models.ForeignKey(
        BOMVersion, on_delete=models.CASCADE, related_name='comparisons_as_a', verbose_name='版本A'
    )
    version_b = models.ForeignKey(
        BOMVersion, on_delete=models.CASCADE, related_name='comparisons_as_b', verbose_name='版本B'
    )

    # 对比结果
    comparison_result = models.JSONField(default=dict, verbose_name='对比结果')

    # 统计
    added_count = models.IntegerField(default=0, verbose_name='新增数量')
    removed_count = models.IntegerField(default=0, verbose_name='删除数量')
    changed_count = models.IntegerField(default=0, verbose_name='变更数量')
    unchanged_count = models.IntegerField(default=0, verbose_name='未变数量')

    cost_difference = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name='成本差异'
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'plm_bom_comparison'
        verbose_name = 'BOM对比'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def perform_comparison(self):
        """执行BOM对比"""
        snapshot_a = {item['item_id']: item for item in self.version_a.snapshot_data}
        snapshot_b = {item['item_id']: item for item in self.version_b.snapshot_data}

        all_items = set(snapshot_a.keys()) | set(snapshot_b.keys())

        added = []
        removed = []
        changed = []
        unchanged = []

        for item_id in all_items:
            in_a = item_id in snapshot_a
            in_b = item_id in snapshot_b

            if in_a and in_b:
                a = snapshot_a[item_id]
                b = snapshot_b[item_id]

                # 检查是否有变化
                changes = {}
                if a['planned_qty'] != b['planned_qty']:
                    changes['qty'] = {'from': a['planned_qty'], 'to': b['planned_qty']}
                if a['unit_cost'] != b['unit_cost']:
                    changes['unit_cost'] = {'from': a['unit_cost'], 'to': b['unit_cost']}

                if changes:
                    changed.append(
                        {
                            'item_id': item_id,
                            'item_sku': a['item_sku'],
                            'item_name': a['item_name'],
                            'changes': changes,
                            'cost_diff': b['total_cost'] - a['total_cost'],
                        }
                    )
                else:
                    unchanged.append({'item_id': item_id, 'item_sku': a['item_sku'], 'item_name': a['item_name']})
            elif in_a and not in_b:
                a = snapshot_a[item_id]
                removed.append(
                    {
                        'item_id': item_id,
                        'item_sku': a['item_sku'],
                        'item_name': a['item_name'],
                        'qty': a['planned_qty'],
                        'cost': a['total_cost'],
                    }
                )
            else:
                b = snapshot_b[item_id]
                added.append(
                    {
                        'item_id': item_id,
                        'item_sku': b['item_sku'],
                        'item_name': b['item_name'],
                        'qty': b['planned_qty'],
                        'cost': b['total_cost'],
                    }
                )

        self.comparison_result = {'added': added, 'removed': removed, 'changed': changed, 'unchanged': unchanged}

        self.added_count = len(added)
        self.removed_count = len(removed)
        self.changed_count = len(changed)
        self.unchanged_count = len(unchanged)

        cost_a = self.version_a.total_cost or 0
        cost_b = self.version_b.total_cost or 0
        self.cost_difference = Decimal(str(cost_b)) - Decimal(str(cost_a))

        self.save()

        return self.comparison_result


# =====================
# Serializers
# =====================


class BOMSubstituteSerializer(serializers.ModelSerializer):
    original_sku = serializers.CharField(source='original_item.sku', read_only=True)
    original_name = serializers.CharField(source='original_item.name', read_only=True)
    substitute_sku = serializers.CharField(source='substitute_item.sku', read_only=True)
    substitute_name = serializers.CharField(source='substitute_item.name', read_only=True)
    type_display = serializers.CharField(source='get_substitute_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)

    class Meta:
        model = BOMSubstitute
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approved_by', 'approved_at']


class BOMVersionSerializer(serializers.ModelSerializer):
    project_code = serializers.CharField(source='project.code', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    released_by_name = serializers.CharField(source='released_by.get_full_name', read_only=True)

    class Meta:
        model = BOMVersion
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'snapshot_data', 'item_count', 'total_cost']


class BOMComparisonSerializer(serializers.ModelSerializer):
    version_a_name = serializers.CharField(source='version_a.version', read_only=True)
    version_b_name = serializers.CharField(source='version_b.version', read_only=True)

    class Meta:
        model = BOMComparison
        fields = '__all__'
        read_only_fields = [
            'created_by',
            'updated_by',
            'comparison_result',
            'added_count',
            'removed_count',
            'changed_count',
            'unchanged_count',
            'cost_difference',
        ]


# =====================
# ViewSets
# =====================


class BOMSubstituteViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """BOM替代料管理"""

    queryset = BOMSubstitute.objects.filter(is_deleted=False)
    serializer_class = BOMSubstituteSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['bom_item', 'original_item', 'substitute_type', 'status']
    search_fields = ['original_item__sku', 'substitute_item__sku']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批替代料"""
        substitute = self.get_object()

        from django.utils import timezone

        substitute.status = 'APPROVED'
        substitute.approved_by = request.user
        substitute.approved_at = timezone.now()
        substitute.save()

        return Response(self.get_serializer(substitute).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝替代料"""
        substitute = self.get_object()
        substitute.status = 'REJECTED'
        substitute.notes = request.data.get('reason', '')
        substitute.save()

        return Response(self.get_serializer(substitute).data)

    @action(detail=False, methods=['get'])
    def valid_substitutes(self, request):
        """获取有效的替代料"""
        bom_item_id = request.query_params.get('bom_item_id')

        qs = self.get_queryset().filter(status='APPROVED')

        if bom_item_id:
            qs = qs.filter(bom_item_id=bom_item_id)

        # 过滤有效期
        today = date.today()
        qs = qs.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today), Q(valid_to__isnull=True) | Q(valid_to__gte=today)
        ).order_by('priority')

        return Response(self.get_serializer(qs, many=True).data)


class BOMVersionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """BOM版本管理"""

    queryset = BOMVersion.objects.filter(is_deleted=False)
    serializer_class = BOMVersionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'is_current']
    search_fields = ['version', 'description']

    @action(detail=True, methods=['post'])
    def create_snapshot(self, request, pk=None):
        """创建BOM快照"""
        version = self.get_object()
        snapshot = version.create_snapshot()

        return Response({'version': self.get_serializer(version).data, 'snapshot_count': len(snapshot)})

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """发布版本"""
        version = self.get_object()

        from django.utils import timezone

        # 取消之前的当前版本
        BOMVersion.objects.filter(project=version.project, is_current=True).update(is_current=False)

        version.is_current = True
        version.released_at = timezone.now()
        version.released_by = request.user
        version.save()

        return Response(self.get_serializer(version).data)

    @action(detail=False, methods=['post'])
    def create_new_version(self, request):
        """从当前BOM创建新版本"""
        project_id = request.data.get('project_id')
        version_name = request.data.get('version')
        description = request.data.get('description', '')

        from apps.projects.models import Project

        project = Project.objects.get(id=project_id)

        # 创建新版本
        version = BOMVersion.objects.create(
            project=project, version=version_name, description=description, created_by=request.user
        )

        # 创建快照
        version.create_snapshot()

        return Response(self.get_serializer(version).data, status=status.HTTP_201_CREATED)


class BOMComparisonViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """BOM对比管理"""

    queryset = BOMComparison.objects.filter(is_deleted=False)
    serializer_class = BOMComparisonSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['version_a__project']
    search_fields = ['name']

    def perform_create(self, serializer):
        comparison = serializer.save(created_by=self.request.user)
        comparison.perform_comparison()

    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """获取对比详情"""
        comparison = self.get_object()

        return Response(
            {
                'comparison': self.get_serializer(comparison).data,
                'result': comparison.comparison_result,
                'summary': {
                    'added': comparison.added_count,
                    'removed': comparison.removed_count,
                    'changed': comparison.changed_count,
                    'unchanged': comparison.unchanged_count,
                    'cost_difference': float(comparison.cost_difference or 0),
                },
            }
        )


class BOMCompareView(APIView):
    """BOM即时对比API"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """对比两个项目的BOM"""
        from apps.projects.models import ProjectBOM

        project_a_id = request.data.get('project_a_id')
        project_b_id = request.data.get('project_b_id')

        if not project_a_id or not project_b_id:
            return Response({'error': '请提供两个项目ID'}, status=status.HTTP_400_BAD_REQUEST)

        # 获取两个项目的BOM
        bom_a = ProjectBOM.objects.filter(project_id=project_a_id, is_deleted=False).select_related('item')

        bom_b = ProjectBOM.objects.filter(project_id=project_b_id, is_deleted=False).select_related('item')

        # 转换为字典
        dict_a = {
            item.item_id: {
                'sku': item.item.sku if item.item else '',
                'name': item.item.name if item.item else '',
                'qty': float(item.planned_qty),
                'cost': float(item.unit_cost or 0),
            }
            for item in bom_a
        }

        dict_b = {
            item.item_id: {
                'sku': item.item.sku if item.item else '',
                'name': item.item.name if item.item else '',
                'qty': float(item.planned_qty),
                'cost': float(item.unit_cost or 0),
            }
            for item in bom_b
        }

        all_items = set(dict_a.keys()) | set(dict_b.keys())

        result = {'only_in_a': [], 'only_in_b': [], 'different': [], 'same': []}

        for item_id in all_items:
            in_a = item_id in dict_a
            in_b = item_id in dict_b

            if in_a and not in_b:
                result['only_in_a'].append(dict_a[item_id])
            elif in_b and not in_a:
                result['only_in_b'].append(dict_b[item_id])
            else:
                a = dict_a[item_id]
                b = dict_b[item_id]

                if a['qty'] != b['qty'] or a['cost'] != b['cost']:
                    result['different'].append(
                        {
                            'sku': a['sku'],
                            'name': a['name'],
                            'qty_a': a['qty'],
                            'qty_b': b['qty'],
                            'cost_a': a['cost'],
                            'cost_b': b['cost'],
                        }
                    )
                else:
                    result['same'].append(a)

        return Response(
            {
                'project_a': project_a_id,
                'project_b': project_b_id,
                'result': result,
                'summary': {
                    'only_in_a': len(result['only_in_a']),
                    'only_in_b': len(result['only_in_b']),
                    'different': len(result['different']),
                    'same': len(result['same']),
                },
            }
        )
