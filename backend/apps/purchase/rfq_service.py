"""
RFQ增强服务
RFQ Enhancement Service for Non-standard Automation Industry

支持:
- 供应商能力匹配和推荐
- 从项目BOM批量创建询价单
- 询价模板管理
- 附件管理
- 历史价格参考
"""
import os
import logging
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from django.db import transaction
from django.db.models import Q, Count, Avg, Max
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .rfq_models import (
    RFQ, RFQLine, RFQSupplier, RFQTemplate, RFQTemplateItem,
    RFQAttachment, SupplierCapability, SupplierCapabilityMapping,
    ItemCapabilityRequirement, ItemPriceHistory
)

logger = logging.getLogger(__name__)


class SupplierMatchingService:
    """供应商能力匹配服务"""
    
    @classmethod
    def match_suppliers_for_item(cls, item_id: int, min_level: int = 1) -> List[Dict]:
        """
        根据物料能力需求匹配供应商
        
        Args:
            item_id: 物料ID
            min_level: 最低能力等级要求
            
        Returns:
            匹配的供应商列表，按匹配度排序
        """
        from apps.masterdata.models import Item, Supplier
        
        try:
            item = Item.objects.get(id=item_id)
        except Item.DoesNotExist:
            return []
        
        # 获取物料的能力需求
        requirements = ItemCapabilityRequirement.objects.filter(
            item=item, is_deleted=False
        ).select_related('capability')
        
        if not requirements:
            # 如果没有能力需求，返回所有活跃供应商
            suppliers = Supplier.objects.filter(
                is_deleted=False, status='ACTIVE'
            )[:20]
            return [{'supplier_id': s.id, 'supplier_name': s.name, 'match_score': 50, 'matched_capabilities': []} for s in suppliers]
        
        # 查找匹配的供应商
        required_capabilities = [r.capability_id for r in requirements if r.is_required]
        optional_capabilities = [r.capability_id for r in requirements if not r.is_required]
        min_levels = {r.capability_id: r.min_level for r in requirements}
        
        # 获取具有相关能力的供应商
        supplier_scores = defaultdict(lambda: {'required_match': 0, 'optional_match': 0, 'capabilities': []})
        
        mappings = SupplierCapabilityMapping.objects.filter(
            capability_id__in=required_capabilities + optional_capabilities,
            is_deleted=False
        ).select_related('supplier', 'capability')
        
        for mapping in mappings:
            supplier_id = mapping.supplier_id
            cap_id = mapping.capability_id
            min_level_required = min_levels.get(cap_id, 1)
            
            if mapping.level >= min_level_required:
                if cap_id in required_capabilities:
                    supplier_scores[supplier_id]['required_match'] += 1
                else:
                    supplier_scores[supplier_id]['optional_match'] += 1
                
                supplier_scores[supplier_id]['capabilities'].append({
                    'capability_id': cap_id,
                    'capability_name': mapping.capability.name,
                    'level': mapping.level,
                    'required': cap_id in required_capabilities
                })
        
        # 计算匹配得分
        total_required = len(required_capabilities)
        total_optional = len(optional_capabilities)
        
        results = []
        for supplier_id, scores in supplier_scores.items():
            # 必须满足所有必需能力
            if total_required > 0 and scores['required_match'] < total_required:
                continue
            
            # 计算匹配得分 (必需能力满分60分，可选能力满分40分)
            if total_required > 0:
                required_score = (scores['required_match'] / total_required) * 60
            else:
                required_score = 60
            
            if total_optional > 0:
                optional_score = (scores['optional_match'] / total_optional) * 40
            else:
                optional_score = 40
            
            match_score = required_score + optional_score
            
            supplier = Supplier.objects.get(id=supplier_id)
            results.append({
                'supplier_id': supplier_id,
                'supplier_name': supplier.name,
                'supplier_code': supplier.code,
                'match_score': round(match_score, 1),
                'matched_capabilities': scores['capabilities'],
                'required_matched': scores['required_match'],
                'optional_matched': scores['optional_match']
            })
        
        # 按匹配得分排序
        results.sort(key=lambda x: -x['match_score'])
        
        return results
    
    @classmethod
    def match_suppliers_for_rfq(cls, rfq_id: int) -> Dict:
        """
        为询价单匹配供应商（综合所有明细物料的能力需求）
        
        Returns:
            {
                'recommended_suppliers': [...],  # 推荐供应商
                'item_matches': {...}  # 每个物料的匹配详情
            }
        """
        rfq = RFQ.objects.get(id=rfq_id)
        rfq_lines = rfq.lines.filter(is_deleted=False).select_related('item')
        
        item_matches = {}
        supplier_scores = defaultdict(lambda: {'total_score': 0, 'item_count': 0})
        
        for line in rfq_lines:
            matches = cls.match_suppliers_for_item(line.item_id)
            item_matches[line.item_id] = {
                'item_sku': line.item.sku,
                'item_name': line.item.name,
                'matches': matches
            }
            
            for match in matches:
                supplier_id = match['supplier_id']
                supplier_scores[supplier_id]['total_score'] += match['match_score']
                supplier_scores[supplier_id]['item_count'] += 1
                supplier_scores[supplier_id]['name'] = match['supplier_name']
        
        # 计算综合得分
        recommended = []
        total_items = len(rfq_lines)
        
        for supplier_id, scores in supplier_scores.items():
            # 覆盖率 = 匹配的物料数 / 总物料数
            coverage = scores['item_count'] / total_items if total_items > 0 else 0
            # 平均匹配得分
            avg_score = scores['total_score'] / scores['item_count'] if scores['item_count'] > 0 else 0
            # 综合得分 = 覆盖率 * 40 + 平均匹配得分 * 0.6
            overall_score = coverage * 40 + avg_score * 0.6
            
            recommended.append({
                'supplier_id': supplier_id,
                'supplier_name': scores['name'],
                'overall_score': round(overall_score, 1),
                'coverage': round(coverage * 100, 1),
                'avg_match_score': round(avg_score, 1),
                'matched_items': scores['item_count'],
                'total_items': total_items
            })
        
        recommended.sort(key=lambda x: -x['overall_score'])
        
        return {
            'recommended_suppliers': recommended[:10],  # 最多推荐10个
            'item_matches': item_matches
        }


class BatchRFQService:
    """批量询价服务"""
    
    @classmethod
    def create_rfq_from_bom(cls, project_id: int, bom_item_ids: List[int], user,
                            options: Dict = None) -> RFQ:
        """
        从项目BOM创建询价单
        
        Args:
            project_id: 项目ID
            bom_item_ids: 要询价的BOM项ID列表
            user: 当前用户
            options: 选项 {
                'rfq_type': 询价类型,
                'priority': 优先级,
                'deadline_days': 报价截止天数,
                'template_id': 模板ID,
                'supplier_ids': 供应商ID列表,
                'auto_match_suppliers': 是否自动匹配供应商
            }
        """
        from apps.projects.models import Project, ProjectBOM
        
        options = options or {}
        
        project = Project.objects.get(id=project_id)
        bom_items = ProjectBOM.objects.filter(
            id__in=bom_item_ids,
            project=project,
            is_deleted=False
        ).select_related('item', 'drawing')
        
        if not bom_items:
            raise ValueError("未找到有效的BOM项")
        
        with transaction.atomic():
            # 应用模板（如果有）
            template = None
            if options.get('template_id'):
                template = RFQTemplate.objects.get(id=options['template_id'])
                template.use_count += 1
                template.save()
            
            # 创建询价单
            rfq = RFQ.objects.create(
                project=project,
                rfq_type=options.get('rfq_type', template.default_rfq_type if template else 'NORMAL'),
                priority=options.get('priority', template.default_priority if template else 'NORMAL'),
                response_deadline=date.today() + timedelta(
                    days=options.get('deadline_days', template.default_deadline_days if template else 7)
                ),
                template=template,
                technical_requirements=template.default_technical_requirements if template else '',
                quality_requirements=template.default_quality_requirements if template else '',
                packaging_requirements=template.default_packaging_requirements if template else '',
                delivery_requirements=template.default_delivery_requirements if template else '',
                created_by=user
            )
            
            # 创建询价明细
            for bom in bom_items:
                # 获取历史价格
                last_price_record = ItemPriceHistory.objects.filter(
                    item=bom.item, is_deleted=False
                ).order_by('-price_date').first()
                
                RFQLine.objects.create(
                    rfq=rfq,
                    item=bom.item,
                    qty=bom.planned_qty,
                    required_date=project.target_completion_date or date.today() + timedelta(days=30),
                    specifications=bom.material_spec or '',
                    bom_item=bom,
                    drawing=bom.drawing if hasattr(bom, 'drawing') else None,
                    drawing_no=bom.drawing_no or '',
                    drawing_version=bom.drawing_version or '',
                    technical_specs=cls._extract_technical_specs(bom),
                    is_critical=bom.is_critical if hasattr(bom, 'is_critical') else False,
                    is_long_lead=bom.is_long_lead if hasattr(bom, 'is_long_lead') else False,
                    is_custom=bom.is_custom_part if hasattr(bom, 'is_custom_part') else False,
                    target_price=bom.estimated_cost if hasattr(bom, 'estimated_cost') else None,
                    last_supplier_id=last_price_record.supplier_id if last_price_record else None,
                    last_price=last_price_record.unit_price if last_price_record else None,
                    created_by=user
                )
            
            # 添加供应商
            supplier_ids = options.get('supplier_ids', [])
            
            # 自动匹配供应商
            if options.get('auto_match_suppliers') and not supplier_ids:
                match_result = SupplierMatchingService.match_suppliers_for_rfq(rfq.id)
                supplier_ids = [s['supplier_id'] for s in match_result['recommended_suppliers'][:5]]
            
            # 使用模板默认供应商
            if not supplier_ids and template:
                supplier_ids = list(template.default_suppliers.values_list('id', flat=True))
            
            for supplier_id in supplier_ids:
                RFQSupplier.objects.create(
                    rfq=rfq,
                    supplier_id=supplier_id,
                    created_by=user
                )
            
            logger.info(f"Created RFQ {rfq.rfq_no} from project {project.code} with {len(bom_items)} items")
        
        return rfq
    
    @classmethod
    def _extract_technical_specs(cls, bom) -> Dict:
        """从BOM项提取技术规格"""
        specs = {}
        
        if hasattr(bom, 'material_spec') and bom.material_spec:
            specs['material'] = bom.material_spec
        
        if hasattr(bom, 'item') and bom.item:
            item = bom.item
            if hasattr(item, 'specification') and item.specification:
                specs['specification'] = item.specification
        
        return specs
    
    @classmethod
    def batch_send_rfq(cls, rfq_ids: List[int], user) -> Dict:
        """批量发送询价单"""
        results = {'success': [], 'failed': []}
        
        for rfq_id in rfq_ids:
            try:
                rfq = RFQ.objects.get(id=rfq_id)
                if rfq.status == 'DRAFT':
                    rfq.status = 'SENT'
                    rfq.save()
                    
                    # 更新供应商发送时间
                    rfq.supplier_rfqs.update(sent_date=timezone.now())
                    
                    results['success'].append({
                        'rfq_id': rfq_id,
                        'rfq_no': rfq.rfq_no
                    })
                else:
                    results['failed'].append({
                        'rfq_id': rfq_id,
                        'error': f'询价单状态为{rfq.get_status_display()}，无法发送'
                    })
            except RFQ.DoesNotExist:
                results['failed'].append({'rfq_id': rfq_id, 'error': '询价单不存在'})
            except Exception as e:
                results['failed'].append({'rfq_id': rfq_id, 'error': str(e)})
        
        return results


class RFQAttachmentService:
    """询价单附件服务"""
    
    ALLOWED_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.dwg', '.dxf', '.step', '.stp', '.iges', '.igs',
        '.jpg', '.jpeg', '.png', '.gif',
        '.zip', '.rar', '.7z'
    }
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    @classmethod
    def upload_attachment(cls, file, rfq_id: int = None, rfq_line_id: int = None,
                          category: str = 'OTHER', description: str = '', 
                          version: str = '', user=None) -> RFQAttachment:
        """
        上传询价单附件
        
        Args:
            file: 上传的文件
            rfq_id: 询价单ID（与rfq_line_id二选一）
            rfq_line_id: 询价明细ID
            category: 附件类别
            description: 描述
            version: 版本
            user: 当前用户
        """
        filename = file.name
        ext = os.path.splitext(filename)[1].lower()
        
        # 验证文件类型
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f'不支持的文件类型: {ext}')
        
        # 验证文件大小
        if file.size > cls.MAX_FILE_SIZE:
            raise ValueError(f'文件大小超过限制 ({cls.MAX_FILE_SIZE / 1024 / 1024}MB)')
        
        # 确定保存路径
        if rfq_id:
            rfq = RFQ.objects.get(id=rfq_id)
            save_path = f'rfq_attachments/{rfq.rfq_no}/{filename}'
        elif rfq_line_id:
            rfq_line = RFQLine.objects.get(id=rfq_line_id)
            save_path = f'rfq_attachments/{rfq_line.rfq.rfq_no}/lines/{rfq_line_id}/{filename}'
        else:
            raise ValueError('必须指定rfq_id或rfq_line_id')
        
        # 保存文件
        saved_path = default_storage.save(save_path, ContentFile(file.read()))
        
        # 根据扩展名判断文件类型
        file_type = cls._get_file_type(ext)
        
        # 创建附件记录
        attachment = RFQAttachment.objects.create(
            rfq_id=rfq_id,
            rfq_line_id=rfq_line_id,
            file_name=filename,
            file_path=saved_path,
            file_size=file.size,
            file_type=file_type,
            category=category,
            description=description,
            version=version,
            created_by=user
        )
        
        # 更新附件计数
        if rfq_id:
            RFQ.objects.filter(id=rfq_id).update(
                attachment_count=RFQAttachment.objects.filter(rfq_id=rfq_id, is_deleted=False).count()
            )
        if rfq_line_id:
            RFQLine.objects.filter(id=rfq_line_id).update(
                attachment_count=RFQAttachment.objects.filter(rfq_line_id=rfq_line_id, is_deleted=False).count()
            )
        
        return attachment
    
    @classmethod
    def _get_file_type(cls, ext: str) -> str:
        """根据扩展名获取文件类型"""
        type_mapping = {
            '.pdf': 'PDF',
            '.doc': 'WORD', '.docx': 'WORD',
            '.xls': 'EXCEL', '.xlsx': 'EXCEL',
            '.dwg': 'CAD', '.dxf': 'CAD',
            '.step': '3D', '.stp': '3D', '.iges': '3D', '.igs': '3D',
            '.jpg': 'IMAGE', '.jpeg': 'IMAGE', '.png': 'IMAGE', '.gif': 'IMAGE',
            '.zip': 'ARCHIVE', '.rar': 'ARCHIVE', '.7z': 'ARCHIVE',
        }
        return type_mapping.get(ext, 'OTHER')
    
    @classmethod
    def delete_attachment(cls, attachment_id: int) -> bool:
        """删除附件"""
        try:
            attachment = RFQAttachment.objects.get(id=attachment_id)
            
            # 删除文件
            if attachment.file_path and default_storage.exists(attachment.file_path):
                default_storage.delete(attachment.file_path)
            
            # 软删除记录
            attachment.is_deleted = True
            attachment.save()
            
            # 更新计数
            if attachment.rfq_id:
                RFQ.objects.filter(id=attachment.rfq_id).update(
                    attachment_count=RFQAttachment.objects.filter(
                        rfq_id=attachment.rfq_id, is_deleted=False
                    ).count()
                )
            if attachment.rfq_line_id:
                RFQLine.objects.filter(id=attachment.rfq_line_id).update(
                    attachment_count=RFQAttachment.objects.filter(
                        rfq_line_id=attachment.rfq_line_id, is_deleted=False
                    ).count()
                )
            
            return True
        except RFQAttachment.DoesNotExist:
            return False


class RFQTemplateService:
    """询价模板服务"""
    
    @classmethod
    def create_template_from_rfq(cls, rfq_id: int, name: str, user, description: str = '') -> RFQTemplate:
        """从现有询价单创建模板"""
        rfq = RFQ.objects.get(id=rfq_id)
        
        with transaction.atomic():
            template = RFQTemplate.objects.create(
                name=name,
                description=description,
                default_rfq_type=rfq.rfq_type,
                default_priority=rfq.priority,
                default_deadline_days=7,
                default_technical_requirements=rfq.technical_requirements,
                default_quality_requirements=rfq.quality_requirements,
                default_packaging_requirements=rfq.packaging_requirements,
                default_delivery_requirements=rfq.delivery_requirements,
                created_by=user
            )
            
            # 添加物料
            for line in rfq.lines.filter(is_deleted=False):
                RFQTemplateItem.objects.create(
                    template=template,
                    item=line.item,
                    default_qty=line.qty,
                    specifications=line.specifications or '',
                    technical_specs=line.technical_specs or {},
                    created_by=user
                )
            
            # 添加默认供应商
            supplier_ids = rfq.supplier_rfqs.values_list('supplier_id', flat=True)
            template.default_suppliers.set(supplier_ids)
        
        return template
    
    @classmethod
    def create_rfq_from_template(cls, template_id: int, project_id: int, user,
                                  options: Dict = None) -> RFQ:
        """从模板创建询价单"""
        template = RFQTemplate.objects.get(id=template_id)
        options = options or {}
        
        from apps.projects.models import Project
        project = Project.objects.get(id=project_id) if project_id else None
        
        with transaction.atomic():
            # 更新使用次数
            template.use_count += 1
            template.save()
            
            # 创建询价单
            rfq = RFQ.objects.create(
                project=project,
                rfq_type=options.get('rfq_type', template.default_rfq_type),
                priority=options.get('priority', template.default_priority),
                response_deadline=date.today() + timedelta(
                    days=options.get('deadline_days', template.default_deadline_days)
                ),
                template=template,
                technical_requirements=template.default_technical_requirements,
                quality_requirements=template.default_quality_requirements,
                packaging_requirements=template.default_packaging_requirements,
                delivery_requirements=template.default_delivery_requirements,
                created_by=user
            )
            
            # 创建明细
            target_date = project.target_completion_date if project else date.today() + timedelta(days=30)
            
            for item in template.items.filter(is_deleted=False):
                RFQLine.objects.create(
                    rfq=rfq,
                    item=item.item,
                    qty=item.default_qty,
                    required_date=target_date,
                    specifications=item.specifications,
                    technical_specs=item.technical_specs,
                    created_by=user
                )
            
            # 添加默认供应商
            for supplier in template.default_suppliers.all():
                RFQSupplier.objects.create(
                    rfq=rfq,
                    supplier=supplier,
                    created_by=user
                )
        
        return rfq
