"""
BOM版本对比服务
BOM Version Comparison Service

支持:
- BOM版本对比（新增/删除/修改/数量变化）
- 与CAD导出BOM对比
- 变更报告生成
"""

import logging
from decimal import Decimal
from typing import Dict, List

from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel

logger = logging.getLogger(__name__)


class BOMCompareService:
    """BOM版本对比服务"""

    # 对比结果类型
    CHANGE_TYPES = {
        'ADDED': '新增',
        'REMOVED': '删除',
        'QTY_CHANGED': '数量变化',
        'SPEC_CHANGED': '规格变化',
        'MATERIAL_CHANGED': '材质变化',
        'PRICE_CHANGED': '价格变化',
        'SUPPLIER_CHANGED': '供应商变化',
        'LEVEL_CHANGED': '层级变化',
        'PARENT_CHANGED': '父级变化',
    }

    @classmethod
    def compare_bom_versions(cls, old_bom_items: List, new_bom_items: List, compare_fields: List[str] = None) -> Dict:
        """
        对比两个版本的BOM差异

        Args:
            old_bom_items: 旧版本BOM项列表（QuerySet或dict列表）
            new_bom_items: 新版本BOM项列表
            compare_fields: 要对比的字段列表，默认对比常用字段

        Returns:
            {
                'summary': {'added': 5, 'removed': 2, 'modified': 3, 'unchanged': 10},
                'details': [
                    {'item_sku': 'ABC001', 'change_type': 'ADDED', 'new_qty': 10, ...},
                    {'item_sku': 'ABC002', 'change_type': 'QTY_CHANGED', 'old_qty': 5, 'new_qty': 8, ...},
                ]
            }
        """
        compare_fields = compare_fields or [
            'planned_qty',
            'material_spec',
            'estimated_cost',
            'supplier_id',
            'level',
            'parent_id',
        ]

        # 将BOM项转换为字典格式（以item_id或item.sku为key）
        old_dict = cls._bom_to_dict(old_bom_items)
        new_dict = cls._bom_to_dict(new_bom_items)

        old_keys = set(old_dict.keys())
        new_keys = set(new_dict.keys())

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        common_keys = old_keys & new_keys

        details = []
        modified_count = 0
        unchanged_count = 0

        # 新增项
        for key in added_keys:
            item = new_dict[key]
            details.append(
                {
                    'item_sku': item.get('item_sku', key),
                    'item_name': item.get('item_name', ''),
                    'change_type': 'ADDED',
                    'new_qty': float(item.get('planned_qty', 0)),
                    'old_qty': 0,
                    'new_data': item,
                }
            )

        # 删除项
        for key in removed_keys:
            item = old_dict[key]
            details.append(
                {
                    'item_sku': item.get('item_sku', key),
                    'item_name': item.get('item_name', ''),
                    'change_type': 'REMOVED',
                    'new_qty': 0,
                    'old_qty': float(item.get('planned_qty', 0)),
                    'old_data': item,
                }
            )

        # 对比共同项
        for key in common_keys:
            old_item = old_dict[key]
            new_item = new_dict[key]

            changes = cls._compare_items(old_item, new_item, compare_fields)

            if changes:
                modified_count += 1
                details.append(
                    {
                        'item_sku': new_item.get('item_sku', key),
                        'item_name': new_item.get('item_name', ''),
                        'change_type': changes[0]['type'],  # 主要变更类型
                        'changes': changes,
                        'old_qty': float(old_item.get('planned_qty', 0)),
                        'new_qty': float(new_item.get('planned_qty', 0)),
                        'old_data': old_item,
                        'new_data': new_item,
                    }
                )
            else:
                unchanged_count += 1

        return {
            'summary': {
                'added': len(added_keys),
                'removed': len(removed_keys),
                'modified': modified_count,
                'unchanged': unchanged_count,
                'total_old': len(old_keys),
                'total_new': len(new_keys),
            },
            'details': details,
            'compare_time': timezone.now().isoformat(),
        }

    @classmethod
    def _bom_to_dict(cls, bom_items) -> Dict:
        """将BOM项列表转换为以item_sku为key的字典"""
        result = {}

        for item in bom_items:
            # 处理QuerySet或dict
            if hasattr(item, '__dict__'):
                # Model对象
                key = item.item.sku if hasattr(item, 'item') and item.item else str(item.id)
                data = {
                    'id': item.id,
                    'item_id': item.item_id if hasattr(item, 'item_id') else None,
                    'item_sku': item.item.sku if hasattr(item, 'item') and item.item else '',
                    'item_name': item.item.name if hasattr(item, 'item') and item.item else '',
                    'planned_qty': item.planned_qty,
                    'level': item.level,
                    'parent_id': item.parent_id,
                    'material_spec': getattr(item, 'material_spec', ''),
                    'estimated_cost': getattr(item, 'estimated_cost', 0),
                    'supplier_id': getattr(item, 'supplier_id', None),
                    'has_drawing': getattr(item, 'has_drawing', ''),
                    'drawing_no': getattr(item, 'drawing_no', ''),
                }
            else:
                # 字典对象
                key = item.get('item_sku') or item.get('part_number') or str(item.get('id', ''))
                data = item

            result[key] = data

        return result

    @classmethod
    def _compare_items(cls, old_item: Dict, new_item: Dict, fields: List[str]) -> List[Dict]:
        """对比两个BOM项的差异"""
        changes = []

        field_change_types = {
            'planned_qty': 'QTY_CHANGED',
            'material_spec': 'MATERIAL_CHANGED',
            'estimated_cost': 'PRICE_CHANGED',
            'supplier_id': 'SUPPLIER_CHANGED',
            'level': 'LEVEL_CHANGED',
            'parent_id': 'PARENT_CHANGED',
        }

        for field in fields:
            old_val = old_item.get(field)
            new_val = new_item.get(field)

            # 数值类型特殊处理
            if isinstance(old_val, (int, float, Decimal)) and isinstance(new_val, (int, float, Decimal)):
                if abs(float(old_val) - float(new_val)) > 0.0001:
                    changes.append(
                        {
                            'field': field,
                            'type': field_change_types.get(field, 'SPEC_CHANGED'),
                            'old_value': float(old_val),
                            'new_value': float(new_val),
                        }
                    )
            elif old_val != new_val:
                changes.append(
                    {
                        'field': field,
                        'type': field_change_types.get(field, 'SPEC_CHANGED'),
                        'old_value': old_val,
                        'new_value': new_val,
                    }
                )

        return changes

    @classmethod
    def compare_with_cad_bom(cls, project_id: int, cad_items: List[Dict]) -> Dict:
        """
        对比项目现有BOM与CAD导出BOM的差异

        Args:
            project_id: 项目ID
            cad_items: CAD导出的BOM项列表

        Returns:
            对比结果
        """
        from apps.projects.models import ProjectBOM

        # 获取项目现有BOM
        existing_bom = ProjectBOM.objects.filter(project_id=project_id, is_deleted=False).select_related('item')

        return cls.compare_bom_versions(existing_bom, cad_items)

    @classmethod
    def compare_project_snapshots(cls, project_id: int, snapshot_date1: str, snapshot_date2: str) -> Dict:
        """
        对比项目BOM在两个时间点的差异（需要BOM快照功能支持）
        """
        # TODO: 需要实现BOM快照功能
        return {'error': '快照功能尚未实现'}

    @classmethod
    def generate_change_report(cls, diff_result: Dict, format: str = 'dict') -> any:
        """
        生成变更报告

        Args:
            diff_result: compare_bom_versions的返回结果
            format: 输出格式 'dict'|'excel'|'pdf'

        Returns:
            根据format返回不同格式的报告
        """
        if format == 'dict':
            return cls._generate_dict_report(diff_result)
        elif format == 'excel':
            return cls._generate_excel_report(diff_result)
        else:
            return diff_result

    @classmethod
    def _generate_dict_report(cls, diff_result: Dict) -> Dict:
        """生成字典格式报告"""
        summary = diff_result['summary']
        details = diff_result['details']

        report = {
            'title': 'BOM变更对比报告',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                '新增项目': summary['added'],
                '删除项目': summary['removed'],
                '修改项目': summary['modified'],
                '未变更项目': summary['unchanged'],
            },
            'statistics': {
                '原BOM项数': summary['total_old'],
                '新BOM项数': summary['total_new'],
                '变更率': f"{(summary['added'] + summary['removed'] + summary['modified']) / max(summary['total_old'], 1) * 100:.1f}%",
            },
            'changes': {
                'added': [d for d in details if d['change_type'] == 'ADDED'],
                'removed': [d for d in details if d['change_type'] == 'REMOVED'],
                'modified': [d for d in details if d['change_type'] not in ('ADDED', 'REMOVED')],
            },
        }

        return report

    @classmethod
    def _generate_excel_report(cls, diff_result: Dict):
        """生成Excel格式报告"""
        import io

        import pandas as pd

        details = diff_result['details']

        # 准备数据
        rows = []
        for d in details:
            row = {
                '物料编码': d.get('item_sku', ''),
                '物料名称': d.get('item_name', ''),
                '变更类型': cls.CHANGE_TYPES.get(d['change_type'], d['change_type']),
                '原数量': d.get('old_qty', 0),
                '新数量': d.get('new_qty', 0),
                '数量差异': d.get('new_qty', 0) - d.get('old_qty', 0),
            }

            # 添加具体变更信息
            changes = d.get('changes', [])
            for change in changes:
                field_name = {
                    'material_spec': '材质规格',
                    'estimated_cost': '预估成本',
                    'supplier_id': '供应商',
                    'level': 'BOM层级',
                }.get(change['field'], change['field'])
                row[f'{field_name}(原)'] = change.get('old_value', '')
                row[f'{field_name}(新)'] = change.get('new_value', '')

            rows.append(row)

        # 创建DataFrame
        df = pd.DataFrame(rows)

        # 写入Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 汇总页
            summary_df = pd.DataFrame([diff_result['summary']])
            summary_df.to_excel(writer, sheet_name='汇总', index=False)

            # 明细页
            df.to_excel(writer, sheet_name='变更明细', index=False)

        output.seek(0)
        return output


# BOM快照模型（用于版本对比）
class BOMSnapshot(BaseModel):
    """BOM快照 - 保存某个时间点的BOM状态"""

    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, related_name='bom_snapshots', verbose_name='项目'
    )
    name = models.CharField(max_length=200, verbose_name='快照名称')
    description = models.TextField(blank=True, verbose_name='描述')
    snapshot_data = models.JSONField(default=list, verbose_name='BOM数据')
    item_count = models.IntegerField(default=0, verbose_name='项目数量')
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='总成本')

    class Meta:
        db_table = 'project_bom_snapshot'
        verbose_name = 'BOM快照'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.code} - {self.name}'

    @classmethod
    def create_snapshot(cls, project_id: int, name: str, user, description: str = '') -> 'BOMSnapshot':
        """创建BOM快照"""
        from apps.projects.models import Project, ProjectBOM

        project = Project.objects.get(id=project_id)
        bom_items = ProjectBOM.objects.filter(project=project, is_deleted=False).select_related('item', 'parent')

        # 序列化BOM数据
        snapshot_data = []
        total_cost = Decimal('0')

        for item in bom_items:
            data = {
                'id': item.id,
                'item_id': item.item_id,
                'item_sku': item.item.sku if item.item else '',
                'item_name': item.item.name if item.item else '',
                'item_code': item.item_code,
                'planned_qty': float(item.planned_qty),
                'estimated_cost': float(item.estimated_cost),
                'total_cost': float(item.planned_qty * item.estimated_cost),
                'level': item.level,
                'parent_id': item.parent_id,
                'material_spec': item.material_spec,
                'has_drawing': item.has_drawing,
                'drawing_no': item.drawing_no,
                'supplier_id': item.supplier_id,
                'is_custom_part': getattr(item, 'is_custom_part', False),
                'custom_part_type': getattr(item, 'custom_part_type', ''),
            }
            snapshot_data.append(data)
            total_cost += item.planned_qty * item.estimated_cost

        snapshot = cls.objects.create(
            project=project,
            name=name,
            description=description,
            snapshot_data=snapshot_data,
            item_count=len(snapshot_data),
            total_cost=total_cost,
            created_by=user,
        )

        return snapshot


# Serializers
class BOMCompareRequestSerializer(serializers.Serializer):
    project_id = serializers.IntegerField(required=False)
    snapshot_id_1 = serializers.IntegerField(required=False)
    snapshot_id_2 = serializers.IntegerField(required=False)
    cad_bom_session_id = serializers.IntegerField(required=False)
    output_format = serializers.ChoiceField(choices=['dict', 'excel'], default='dict')


class BOMSnapshotSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_code = serializers.CharField(source='project.code', read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BOMSnapshot
        fields = [
            'id',
            'project',
            'project_name',
            'project_code',
            'name',
            'description',
            'item_count',
            'total_cost',
            'created_at',
            'created_by',
            'created_by_name',
        ]
        read_only_fields = ['item_count', 'total_cost']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''


class BOMSnapshotDetailSerializer(BOMSnapshotSerializer):
    snapshot_data = serializers.JSONField(read_only=True)

    class Meta(BOMSnapshotSerializer.Meta):
        fields = BOMSnapshotSerializer.Meta.fields + ['snapshot_data']


# ViewSet
class BOMCompareViewSet(viewsets.ViewSet):
    """BOM版本对比"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def compare(self, request):
        """对比BOM版本"""
        snapshot_id_1 = request.data.get('snapshot_id_1')
        snapshot_id_2 = request.data.get('snapshot_id_2')
        cad_session_id = request.data.get('cad_bom_session_id')
        project_id = request.data.get('project_id')
        output_format = request.data.get('output_format', 'dict')

        # 对比两个快照
        if snapshot_id_1 and snapshot_id_2:
            try:
                snapshot1 = BOMSnapshot.objects.get(id=snapshot_id_1)
                snapshot2 = BOMSnapshot.objects.get(id=snapshot_id_2)

                result = BOMCompareService.compare_bom_versions(snapshot1.snapshot_data, snapshot2.snapshot_data)
            except BOMSnapshot.DoesNotExist:
                return Response({'error': '快照不存在'}, status=404)

        # 对比项目当前BOM与CAD导入会话
        elif project_id and cad_session_id:
            from .creo_integration import CreoBOMImportSession

            try:
                session = CreoBOMImportSession.objects.get(id=cad_session_id)
                cad_items = list(session.items.values('part_number', 'part_name', 'quantity', 'level', 'material'))
                # 转换字段名
                for item in cad_items:
                    item['item_sku'] = item.pop('part_number', '')
                    item['item_name'] = item.pop('part_name', '')
                    item['planned_qty'] = item.pop('quantity', 1)

                result = BOMCompareService.compare_with_cad_bom(int(project_id), cad_items)
            except CreoBOMImportSession.DoesNotExist:
                return Response({'error': 'CAD导入会话不存在'}, status=404)
        else:
            return Response({'error': '请指定对比参数'}, status=400)

        # 生成报告
        if output_format == 'excel':
            from django.http import HttpResponse

            excel_file = BOMCompareService.generate_change_report(result, 'excel')
            response = HttpResponse(
                excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = (
                f'attachment; filename=bom_compare_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
            return response

        report = BOMCompareService.generate_change_report(result, 'dict')
        return Response(report)


class BOMSnapshotViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """BOM快照管理"""

    queryset = BOMSnapshot.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BOMSnapshotDetailSerializer
        return BOMSnapshotSerializer

    @action(detail=False, methods=['post'])
    def create_snapshot(self, request):
        """创建BOM快照"""
        project_id = request.data.get('project_id')
        name = request.data.get('name', f'快照_{timezone.now().strftime("%Y%m%d_%H%M%S")}')
        description = request.data.get('description', '')

        if not project_id:
            return Response({'error': '请指定项目ID'}, status=400)

        try:
            snapshot = BOMSnapshot.create_snapshot(int(project_id), name, request.user, description)
            return Response(BOMSnapshotSerializer(snapshot).data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def compare_with_current(self, request, pk=None):
        """与当前BOM对比"""
        snapshot = self.get_object()

        from apps.projects.models import ProjectBOM

        current_bom = ProjectBOM.objects.filter(project=snapshot.project, is_deleted=False).select_related('item')

        result = BOMCompareService.compare_bom_versions(snapshot.snapshot_data, current_bom)

        report = BOMCompareService.generate_change_report(result, 'dict')
        return Response(report)
