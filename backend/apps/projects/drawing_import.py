"""
图纸导入与BOM关联服务
Drawing Import and BOM Linking Service

支持:
- 图纸与BOM自动关联（基于图号匹配）
- 批量图纸文件导入
- 图纸层级结构管理
"""
import logging
import os
import re
import zipfile
from difflib import SequenceMatcher
from typing import Dict, List

from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# 图号解析规则
DRAWING_NO_PATTERNS = [
    # 项目编号-零件号-版本 (如: P2024001-001-A0)
    r'^(?P<project>[A-Z0-9]+)-(?P<part>\d+)-(?P<version>[A-Z]\d+)$',
    # 零件号_版本 (如: ABC001_A1)
    r'^(?P<part>[A-Za-z0-9-]+)_(?P<version>[A-Z]\d+)$',
    # 零件号-版本 (如: ABC-001-A)
    r'^(?P<part>[A-Za-z0-9-]+)-(?P<version>[A-Z])$',
    # 纯零件号 (如: ABC001)
    r'^(?P<part>[A-Za-z0-9-]+)$',
]


class DrawingBOMLinkService:
    """图纸与BOM自动关联服务"""

    @classmethod
    def match_drawing_to_bom(cls, drawing_no: str, project_id: int) -> Dict:
        """
        根据图号匹配BOM项
        匹配规则:
        1. 精确匹配: drawing_no == item.sku 或 bom.item_code 或 bom.drawing_no
        2. 前缀匹配: drawing_no 去除版本后缀匹配
        3. 模糊匹配: 相似度 >= 0.8
        
        返回: {'matched': bool, 'bom_item': ProjectBOM or None, 'match_type': str, 'score': float, 'candidates': list}
        """
        from apps.projects.models import ProjectBOM

        if not drawing_no or not project_id:
            return {'matched': False, 'bom_item': None, 'match_type': '', 'score': 0, 'candidates': []}

        drawing_no_clean = drawing_no.strip().upper()

        # 解析图号提取零件号
        part_no = cls._extract_part_number(drawing_no_clean)

        # 1. 精确匹配 - drawing_no字段
        exact_match = ProjectBOM.objects.filter(
            project_id=project_id,
            drawing_no__iexact=drawing_no_clean,
            is_deleted=False
        ).select_related('item').first()

        if exact_match:
            return {
                'matched': True,
                'bom_item': exact_match,
                'match_type': 'EXACT_DRAWING_NO',
                'score': 1.0,
                'candidates': []
            }

        # 2. 精确匹配 - item.sku
        sku_match = ProjectBOM.objects.filter(
            project_id=project_id,
            item__sku__iexact=drawing_no_clean,
            is_deleted=False
        ).select_related('item').first()

        if sku_match:
            return {
                'matched': True,
                'bom_item': sku_match,
                'match_type': 'EXACT_SKU',
                'score': 1.0,
                'candidates': []
            }

        # 3. 精确匹配 - item_code
        code_match = ProjectBOM.objects.filter(
            project_id=project_id,
            item_code__iexact=drawing_no_clean,
            is_deleted=False
        ).select_related('item').first()

        if code_match:
            return {
                'matched': True,
                'bom_item': code_match,
                'match_type': 'EXACT_ITEM_CODE',
                'score': 1.0,
                'candidates': []
            }

        # 4. 部分匹配 - 使用提取的零件号
        if part_no and part_no != drawing_no_clean:
            part_match = ProjectBOM.objects.filter(
                Q(item__sku__icontains=part_no) |
                Q(item_code__icontains=part_no) |
                Q(drawing_no__icontains=part_no),
                project_id=project_id,
                is_deleted=False
            ).select_related('item').first()

            if part_match:
                return {
                    'matched': True,
                    'bom_item': part_match,
                    'match_type': 'PARTIAL',
                    'score': 0.9,
                    'candidates': []
                }

        # 5. 模糊匹配
        all_bom_items = ProjectBOM.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).select_related('item')

        candidates = []
        best_match = None
        best_score = 0.0

        for bom in all_bom_items:
            # 比较各种标识符
            compare_values = [
                bom.item.sku if bom.item else '',
                bom.item_code,
                bom.drawing_no,
                bom.item.name if bom.item else ''
            ]

            max_score = 0
            for val in compare_values:
                if val:
                    score = SequenceMatcher(None, drawing_no_clean, val.upper()).ratio()
                    if score > max_score:
                        max_score = score

            if max_score >= 0.7:
                candidates.append({
                    'bom_id': bom.id,
                    'item_sku': bom.item.sku if bom.item else '',
                    'item_name': bom.item.name if bom.item else '',
                    'score': max_score
                })

                if max_score > best_score:
                    best_score = max_score
                    best_match = bom

        # 排序候选项
        candidates = sorted(candidates, key=lambda x: -x['score'])[:5]

        if best_match and best_score >= 0.8:
            return {
                'matched': True,
                'bom_item': best_match,
                'match_type': 'FUZZY',
                'score': best_score,
                'candidates': candidates
            }

        return {
            'matched': False,
            'bom_item': None,
            'match_type': '',
            'score': 0,
            'candidates': candidates
        }

    @classmethod
    def _extract_part_number(cls, drawing_no: str) -> str:
        """从图号中提取零件号（去除版本后缀）"""
        for pattern in DRAWING_NO_PATTERNS:
            match = re.match(pattern, drawing_no, re.IGNORECASE)
            if match:
                groups = match.groupdict()
                return groups.get('part', drawing_no).upper()

        # 默认去除常见版本后缀
        no_version = re.sub(r'[-_][A-Z]\d*$', '', drawing_no, flags=re.IGNORECASE)
        return no_version.upper()

    @classmethod
    def batch_link_drawings(cls, project_id: int, auto_create_missing: bool = False) -> Dict:
        """
        批量关联项目下所有图纸与BOM
        
        Args:
            project_id: 项目ID
            auto_create_missing: 是否为未匹配的BOM项自动创建图纸记录
            
        Returns:
            {'linked': int, 'not_found': int, 'already_linked': int, 'details': list}
        """
        from apps.projects.models import Drawing, Project

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return {'error': '项目不存在'}

        # 获取项目下所有图纸
        drawings = Drawing.objects.filter(project=project, is_deleted=False)

        linked = 0
        not_found = 0
        already_linked = 0
        details = []

        for drawing in drawings:
            # 检查是否已关联
            if drawing.bom_item_id:
                already_linked += 1
                continue

            # 尝试匹配
            result = cls.match_drawing_to_bom(drawing.drawing_no, project_id)

            if result['matched'] and result['bom_item']:
                bom = result['bom_item']

                # 建立关联
                drawing.bom_item = bom
                drawing.item = bom.item
                drawing.save()

                # 更新BOM项的图纸信息
                bom.drawing = drawing
                bom.drawing_no = drawing.drawing_no
                bom.drawing_version = f"{drawing.version}.{drawing.revision}"
                bom.has_drawing = 'YES'
                bom.save()

                linked += 1
                details.append({
                    'drawing_id': drawing.id,
                    'drawing_no': drawing.drawing_no,
                    'bom_id': bom.id,
                    'item_sku': bom.item.sku if bom.item else '',
                    'match_type': result['match_type'],
                    'score': result['score']
                })
            else:
                not_found += 1
                details.append({
                    'drawing_id': drawing.id,
                    'drawing_no': drawing.drawing_no,
                    'bom_id': None,
                    'match_type': 'NOT_FOUND',
                    'candidates': result['candidates']
                })

        return {
            'linked': linked,
            'not_found': not_found,
            'already_linked': already_linked,
            'details': details
        }

    @classmethod
    def link_single_drawing(cls, drawing_id: int, bom_id: int) -> Dict:
        """手动关联单个图纸与BOM项"""
        from apps.projects.models import Drawing, ProjectBOM

        try:
            drawing = Drawing.objects.get(id=drawing_id, is_deleted=False)
            bom = ProjectBOM.objects.get(id=bom_id, is_deleted=False)
        except (Drawing.DoesNotExist, ProjectBOM.DoesNotExist) as e:
            return {'success': False, 'error': str(e)}

        # 检查是否同一项目
        if drawing.project_id != bom.project_id:
            return {'success': False, 'error': '图纸和BOM不属于同一项目'}

        # 建立关联
        drawing.bom_item = bom
        drawing.item = bom.item
        drawing.save()

        bom.drawing = drawing
        bom.drawing_no = drawing.drawing_no
        bom.drawing_version = f"{drawing.version}.{drawing.revision}"
        bom.has_drawing = 'YES'
        bom.save()

        return {'success': True, 'drawing_id': drawing.id, 'bom_id': bom.id}


class BatchDrawingImportService:
    """批量图纸文件导入服务"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {
        '.pdf': 'PDF',
        '.dwg': 'DWG',
        '.dxf': 'DXF',
        '.step': 'STEP',
        '.stp': 'STP',
        '.iges': 'IGES',
        '.igs': 'IGES',
        '.stl': 'STL',
        '.sldprt': 'SOLIDWORKS',
        '.sldasm': 'SOLIDWORKS',
        '.slddrw': 'SOLIDWORKS',
        '.prt': 'CREO',
        '.asm': 'CREO',
        '.drw': 'CREO',
        '.ipt': 'INVENTOR',
        '.iam': 'INVENTOR',
        '.idw': 'INVENTOR',
    }

    @classmethod
    def parse_filename(cls, filename: str) -> Dict:
        """
        解析文件名提取图纸信息
        
        示例:
        - ABC-001-A1.dwg -> 图号:ABC-001, 版本:A1
        - P2024001_002_B0.pdf -> 图号:P2024001_002, 版本:B0
        - PART001.step -> 图号:PART001, 版本:A0
        
        Returns:
            {'drawing_no': str, 'version': str, 'name': str, 'file_type': str}
        """
        # 获取文件名和扩展名
        name_without_ext, ext = os.path.splitext(filename)
        ext_lower = ext.lower()

        file_type = cls.SUPPORTED_EXTENSIONS.get(ext_lower, 'OTHER')

        # 尝试解析版本号
        version = 'A0'
        drawing_no = name_without_ext

        # 常见版本格式: -A0, _A1, -Rev01, _V2
        version_patterns = [
            (r'^(.+)[-_]([A-Z]\d+)$', 2),  # ABC-001-A1
            (r'^(.+)[-_]Rev(\d+)$', 2),     # ABC-001-Rev01
            (r'^(.+)[-_]V(\d+)$', 2),       # ABC-001-V2
            (r'^(.+)[-_]([A-Z])$', 2),      # ABC-001-A
        ]

        for pattern, ver_group in version_patterns:
            match = re.match(pattern, name_without_ext, re.IGNORECASE)
            if match:
                drawing_no = match.group(1)
                ver_str = match.group(ver_group)
                # 标准化版本格式
                if re.match(r'^[A-Z]$', ver_str, re.IGNORECASE):
                    version = f"{ver_str.upper()}0"
                elif re.match(r'^[A-Z]\d+$', ver_str, re.IGNORECASE):
                    version = ver_str.upper()
                elif re.match(r'^\d+$', ver_str):
                    version = f"A{ver_str}"
                break

        return {
            'drawing_no': drawing_no.upper(),
            'version': version,
            'name': name_without_ext,
            'file_type': file_type,
            'original_filename': filename
        }

    @classmethod
    def import_files(cls, files: List, project_id: int, user, options: Dict = None) -> Dict:
        """
        批量导入图纸文件
        
        Args:
            files: 上传的文件列表
            project_id: 项目ID
            user: 当前用户
            options: 选项 {auto_link: bool, overwrite: bool}
            
        Returns:
            {'imported': int, 'skipped': int, 'errors': list, 'details': list}
        """
        from apps.projects.models import Drawing, Project

        options = options or {}
        auto_link = options.get('auto_link', True)
        overwrite = options.get('overwrite', False)

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return {'error': '项目不存在'}

        imported = 0
        skipped = 0
        errors = []
        details = []

        for f in files:
            try:
                filename = f.name
                parsed = cls.parse_filename(filename)

                # 检查文件类型
                if parsed['file_type'] == 'OTHER':
                    ext = os.path.splitext(filename)[1]
                    if ext.lower() not in cls.SUPPORTED_EXTENSIONS:
                        skipped += 1
                        details.append({
                            'filename': filename,
                            'status': 'SKIPPED',
                            'reason': f'不支持的文件类型: {ext}'
                        })
                        continue

                # 检查是否已存在
                existing = Drawing.objects.filter(
                    project=project,
                    drawing_no=parsed['drawing_no'],
                    version=parsed['version'],
                    is_deleted=False
                ).first()

                if existing and not overwrite:
                    skipped += 1
                    details.append({
                        'filename': filename,
                        'status': 'SKIPPED',
                        'reason': '图纸已存在',
                        'existing_id': existing.id
                    })
                    continue

                # 保存文件
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage

                file_path = f'drawings/{project.code}/{filename}'
                saved_path = default_storage.save(file_path, ContentFile(f.read()))
                file_size = default_storage.size(saved_path)

                if existing and overwrite:
                    # 更新现有记录
                    existing.file_path = saved_path
                    existing.file_size = file_size
                    existing.revision += 1
                    existing.updated_by = user
                    existing.save()
                    drawing = existing
                else:
                    # 创建新记录
                    drawing = Drawing.objects.create(
                        project=project,
                        drawing_no=parsed['drawing_no'],
                        name=parsed['name'],
                        version=parsed['version'],
                        revision=1,
                        file_type=parsed['file_type'],
                        file_path=saved_path,
                        file_size=file_size,
                        status='DRAFT',
                        designer=user,
                        created_by=user
                    )

                imported += 1
                detail = {
                    'filename': filename,
                    'status': 'IMPORTED',
                    'drawing_id': drawing.id,
                    'drawing_no': drawing.drawing_no,
                    'version': drawing.version
                }

                # 自动关联BOM
                if auto_link:
                    link_result = DrawingBOMLinkService.match_drawing_to_bom(
                        drawing.drawing_no, project_id
                    )
                    if link_result['matched'] and link_result['bom_item']:
                        bom = link_result['bom_item']
                        drawing.bom_item = bom
                        drawing.item = bom.item
                        drawing.save()

                        bom.drawing = drawing
                        bom.drawing_no = drawing.drawing_no
                        bom.has_drawing = 'YES'
                        bom.save()

                        detail['linked_bom_id'] = bom.id
                        detail['linked_item_sku'] = bom.item.sku if bom.item else ''

                details.append(detail)

            except Exception as e:
                errors.append({'filename': f.name if hasattr(f, 'name') else str(f), 'error': str(e)})
                logger.exception(f"导入图纸失败: {f.name if hasattr(f, 'name') else f}")

        return {
            'imported': imported,
            'skipped': skipped,
            'errors': errors,
            'details': details
        }

    @classmethod
    def import_from_zip(cls, zip_file, project_id: int, user, options: Dict = None) -> Dict:
        """从ZIP压缩包导入图纸"""
        import tempfile

        options = options or {}

        try:
            # 解压到临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(zip_file, 'r') as zf:
                    zf.extractall(temp_dir)

                # 收集所有文件
                files_to_import = []
                for root, dirs, files in os.walk(temp_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in cls.SUPPORTED_EXTENSIONS:
                            # 创建类文件对象
                            with open(file_path, 'rb') as f:
                                class FileWrapper:
                                    def __init__(self, fp, name):
                                        self._fp = fp
                                        self.name = name
                                        self._content = fp.read()

                                    def read(self):
                                        return self._content

                                files_to_import.append(FileWrapper(f, filename))

                return cls.import_files(files_to_import, project_id, user, options)

        except zipfile.BadZipFile:
            return {'error': '无效的ZIP文件'}
        except Exception as e:
            return {'error': str(e)}


# Serializers
class DrawingLinkSerializer(serializers.Serializer):
    drawing_id = serializers.IntegerField()
    bom_id = serializers.IntegerField()


class BatchDrawingImportSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), required=False)
    zip_file = serializers.FileField(required=False)
    project_id = serializers.IntegerField()
    auto_link = serializers.BooleanField(default=True)
    overwrite = serializers.BooleanField(default=False)

    def validate(self, data):
        if not data.get('files') and not data.get('zip_file'):
            raise serializers.ValidationError('请上传文件或ZIP压缩包')
        return data


# ViewSet
class DrawingImportViewSet(viewsets.ViewSet):
    """图纸导入与关联管理"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @action(detail=False, methods=['post'])
    def batch_import(self, request):
        """批量导入图纸文件"""
        files = request.FILES.getlist('files')
        zip_file = request.FILES.get('zip_file')
        project_id = request.data.get('project_id')

        if not project_id:
            return Response({'error': '请指定项目ID'}, status=400)

        options = {
            'auto_link': request.data.get('auto_link', 'true').lower() == 'true',
            'overwrite': request.data.get('overwrite', 'false').lower() == 'true'
        }

        if zip_file:
            result = BatchDrawingImportService.import_from_zip(
                zip_file, int(project_id), request.user, options
            )
        elif files:
            result = BatchDrawingImportService.import_files(
                files, int(project_id), request.user, options
            )
        else:
            return Response({'error': '请上传文件'}, status=400)

        return Response(result)

    @action(detail=False, methods=['post'])
    def auto_link(self, request):
        """自动关联项目图纸与BOM"""
        project_id = request.data.get('project_id')
        if not project_id:
            return Response({'error': '请指定项目ID'}, status=400)

        result = DrawingBOMLinkService.batch_link_drawings(int(project_id))
        return Response(result)

    @action(detail=False, methods=['post'])
    def manual_link(self, request):
        """手动关联图纸与BOM"""
        drawing_id = request.data.get('drawing_id')
        bom_id = request.data.get('bom_id')

        if not drawing_id or not bom_id:
            return Response({'error': '请指定图纸ID和BOM项ID'}, status=400)

        result = DrawingBOMLinkService.link_single_drawing(int(drawing_id), int(bom_id))
        return Response(result)

    @action(detail=False, methods=['post'])
    def match_drawing(self, request):
        """匹配图号查找BOM项"""
        drawing_no = request.data.get('drawing_no')
        project_id = request.data.get('project_id')

        if not drawing_no or not project_id:
            return Response({'error': '请指定图号和项目ID'}, status=400)

        result = DrawingBOMLinkService.match_drawing_to_bom(drawing_no, int(project_id))

        # 转换BOM对象为可序列化格式
        if result['bom_item']:
            bom = result['bom_item']
            result['bom_item'] = {
                'id': bom.id,
                'item_sku': bom.item.sku if bom.item else '',
                'item_name': bom.item.name if bom.item else '',
                'planned_qty': float(bom.planned_qty),
                'has_drawing': bom.has_drawing
            }

        return Response(result)

    @action(detail=False, methods=['get'])
    def supported_formats(self, request):
        """获取支持的文件格式"""
        formats = []
        for ext, file_type in BatchDrawingImportService.SUPPORTED_EXTENSIONS.items():
            formats.append({'extension': ext, 'type': file_type})

        return Response({
            'formats': formats,
            'max_file_size': '100MB',
            'max_files': 100
        })
