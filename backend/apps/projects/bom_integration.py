"""
BOM集成服务模块
BOM Integration Services for Non-Standard Automation Industry

提供BOM与采购、生产模块的集成功能:
1. 从BOM生成采购申请/订单
2. 从BOM生成生产计划
3. BOM状态同步
"""
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from django.db import transaction
from django.db.models import Sum, Q, F
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.utils import generate_code


class BOMPurchaseService:
    """
    BOM采购集成服务
    处理从BOM生成采购申请和采购订单的逻辑
    """
    
    @staticmethod
    def get_purchasable_bom_items(project_id: int, include_ordered: bool = False) -> list:
        """
        获取可采购的BOM项
        
        Args:
            project_id: 项目ID
            include_ordered: 是否包含已下单的
            
        Returns:
            可采购的BOM项列表
        """
        from apps.projects.models import ProjectBOM
        
        filters = {
            'project_id': project_id,
            'is_deleted': False,
        }
        
        # 只获取外购件、标准件、外协件
        purchasable_properties = ['PURCHASED', 'STANDARD', 'OUTSOURCED', '']
        
        qs = ProjectBOM.objects.filter(**filters).select_related('item', 'supplier')
        
        # 过滤物料属性
        qs = qs.filter(
            Q(item_property__in=purchasable_properties) |
            Q(item_property='', item__item_property__in=['PURCHASED', 'STANDARD', 'OUTSOURCED'])
        )
        
        if not include_ordered:
            # 排除已完全下单的
            qs = qs.exclude(order_status='ORDERED')
        
        return list(qs.order_by('-is_critical', '-is_long_lead', 'required_date'))
    
    @staticmethod
    def calculate_shortage(bom_item) -> Decimal:
        """
        计算BOM项的缺料数量
        
        Args:
            bom_item: ProjectBOM实例
            
        Returns:
            缺料数量
        """
        # 考虑损耗率
        scrap_rate = bom_item.scrap_rate or Decimal('0')
        required_qty = bom_item.planned_qty * (1 + scrap_rate / 100)
        
        # 已有数量 = 已收货 + 预留
        available_qty = (bom_item.received_qty or 0) + (bom_item.reserved_qty or 0)
        
        # 缺料数量
        shortage = required_qty - available_qty - (bom_item.ordered_qty or 0)
        
        return max(Decimal('0'), shortage)
    
    @classmethod
    def create_purchase_request_from_bom(
        cls,
        project_id: int,
        bom_item_ids: List[int],
        user,
        title: str = None,
        notes: str = ''
    ) -> Tuple[object, List[Dict]]:
        """
        从BOM项生成采购申请
        
        Args:
            project_id: 项目ID
            bom_item_ids: BOM项ID列表
            user: 当前用户
            title: 申请标题
            notes: 备注
            
        Returns:
            (采购申请, 创建的明细列表)
        """
        from apps.projects.models import ProjectBOM, Project
        from apps.purchase.models import PurchaseRequest, PurchaseRequestLine
        
        project = Project.objects.get(id=project_id)
        bom_items = ProjectBOM.objects.filter(
            id__in=bom_item_ids,
            project_id=project_id,
            is_deleted=False
        ).select_related('item', 'item__default_supplier')
        
        if not bom_items.exists():
            raise ValueError("未找到有效的BOM项")
        
        with transaction.atomic():
            # 创建采购申请
            pr = PurchaseRequest.objects.create(
                request_no=generate_code('PR', rule_type='PURCHASE_REQUEST'),
                project=project,
                title=title or f"{project.code} BOM物料采购申请",
                status='DRAFT',
                notes=notes,
                created_by=user
            )
            
            created_lines = []
            total_amount = Decimal('0')
            
            for bom in bom_items:
                # 计算采购数量
                shortage = cls.calculate_shortage(bom)
                if shortage <= 0:
                    continue
                
                # 获取预估单价
                estimated_price = (
                    bom.estimated_cost or 
                    bom.item.purchase_price or 
                    bom.item.standard_cost or 
                    Decimal('0')
                )
                
                # 创建采购申请行
                line = PurchaseRequestLine.objects.create(
                    pr=pr,
                    item=bom.item,
                    qty=shortage,
                    estimated_price=estimated_price,
                    required_date=bom.required_date,
                    project=project,
                    bom_item=bom,
                    is_critical=bom.is_critical,
                    is_long_lead=bom.is_long_lead,
                    function_module=bom.function_module or '',
                    notes=f"图纸号:{bom.drawing_no}" if bom.drawing_no else '',
                    created_by=user
                )
                
                total_amount += line.line_amount
                
                created_lines.append({
                    'id': line.id,
                    'item_sku': bom.item.sku,
                    'item_name': bom.item.name,
                    'qty': float(shortage),
                    'estimated_price': float(estimated_price),
                    'line_amount': float(line.line_amount),
                    'is_critical': bom.is_critical,
                    'is_long_lead': bom.is_long_lead,
                })
            
            # 更新总金额
            pr.total_amount = total_amount
            pr.save()
            
            return pr, created_lines
    
    @classmethod
    def sync_bom_from_po(cls, po) -> List[int]:
        """
        采购订单确认后同步更新BOM状态
        
        Args:
            po: PurchaseOrder实例
            
        Returns:
            更新的BOM项ID列表
        """
        from apps.projects.models import ProjectBOM
        
        updated_bom_ids = []
        
        with transaction.atomic():
            for line in po.lines.filter(bom_item__isnull=False):
                bom = line.bom_item
                
                # 更新BOM的采购状态
                bom.ordered_qty = (bom.ordered_qty or 0) + line.qty
                bom.purchase_order = po
                bom.supplier = po.supplier
                bom.delivery_date = po.delivery_date
                
                # 更新下单状态
                if bom.ordered_qty >= bom.planned_qty:
                    bom.order_status = 'ORDERED'
                else:
                    bom.order_status = 'PARTIAL'
                
                bom.save()
                updated_bom_ids.append(bom.id)
        
        return updated_bom_ids
    
    @classmethod
    def sync_bom_from_receipt(cls, receipt) -> List[int]:
        """
        收货后同步更新BOM状态
        
        Args:
            receipt: GoodsReceipt实例
            
        Returns:
            更新的BOM项ID列表
        """
        from apps.projects.models import ProjectBOM
        
        updated_bom_ids = []
        
        with transaction.atomic():
            for line in receipt.lines.all():
                # 查找关联的BOM项
                po_line = line.po_line
                if po_line and po_line.bom_item:
                    bom = po_line.bom_item
                    
                    # 更新已收货数量
                    bom.received_qty = (bom.received_qty or 0) + line.received_qty
                    
                    # 更新实际到货日期
                    bom.actual_delivery_date = receipt.receipt_date
                    
                    # 更新下单状态
                    if bom.received_qty >= bom.planned_qty:
                        bom.order_status = 'RECEIVED'
                    elif bom.received_qty > 0:
                        bom.order_status = 'IN_TRANSIT'
                    
                    bom.save()
                    updated_bom_ids.append(bom.id)
        
        return updated_bom_ids


class BOMProductionService:
    """
    BOM生产集成服务
    处理从BOM生成生产计划的逻辑
    """
    
    @staticmethod
    def get_producible_bom_items(project_id: int) -> list:
        """
        获取可生产的BOM项(自制件和组件)
        
        Args:
            project_id: 项目ID
            
        Returns:
            可生产的BOM项列表
        """
        from apps.projects.models import ProjectBOM
        
        # 自制件和组件需要生产
        producible_properties = ['SELF_MADE', 'ASSEMBLY']
        
        qs = ProjectBOM.objects.filter(
            project_id=project_id,
            is_deleted=False,
        ).select_related('item', 'work_center', 'process')
        
        # 过滤物料属性
        qs = qs.filter(
            Q(item_property__in=producible_properties) |
            Q(item_property='', item__item_property__in=producible_properties)
        )
        
        return list(qs.order_by('-is_critical', 'assembly_sequence', 'required_date'))
    
    @classmethod
    def create_production_plan_from_bom(
        cls,
        project_id: int,
        bom_item_ids: List[int],
        user,
        planned_start: date = None,
        planned_end: date = None,
        title: str = None
    ) -> Tuple[object, List[Dict]]:
        """
        从BOM项生成生产计划
        
        Args:
            project_id: 项目ID
            bom_item_ids: BOM项ID列表
            user: 当前用户
            planned_start: 计划开始日期
            planned_end: 计划完成日期
            title: 计划标题
            
        Returns:
            (生产计划, 创建的工序列表)
        """
        from apps.projects.models import ProjectBOM, Project
        from apps.production.models import ProductionPlan, ProductionProcess, ProductionPlanProcess
        
        project = Project.objects.get(id=project_id)
        bom_items = ProjectBOM.objects.filter(
            id__in=bom_item_ids,
            project_id=project_id,
            is_deleted=False
        ).select_related('item', 'work_center', 'process').order_by('assembly_sequence')
        
        if not bom_items.exists():
            raise ValueError("未找到有效的BOM项")
        
        # 默认日期
        if not planned_start:
            planned_start = date.today()
        if not planned_end:
            planned_end = planned_start + timedelta(days=30)
        
        with transaction.atomic():
            # 创建生产计划
            plan = ProductionPlan.objects.create(
                project=project,
                title=title or f"{project.code} BOM物料生产计划",
                planned_start=planned_start,
                planned_end=planned_end,
                status='DRAFT',
                planner=user,
                created_by=user
            )
            
            created_processes = []
            sequence = 1
            
            # 按工位分组BOM项
            work_center_boms = {}
            for bom in bom_items:
                wc_id = bom.work_center_id or 0
                if wc_id not in work_center_boms:
                    work_center_boms[wc_id] = []
                work_center_boms[wc_id].append(bom)
            
            # 为每个工位创建生产工序
            for wc_id, boms in work_center_boms.items():
                # 创建工序
                process = ProductionProcess.objects.create(
                    project=project,
                    process_no=f"PROC-{plan.plan_no}-{sequence:03d}",
                    name=f"工位{wc_id}物料生产" if wc_id else "通用物料生产",
                    process_type='ASSEMBLY',
                    sequence=sequence,
                    work_center=boms[0].work_center.name if boms[0].work_center else '',
                    description='\n'.join([
                        f"- {b.item.sku}: {b.item.name} x {b.planned_qty}"
                        for b in boms
                    ]),
                    created_by=user
                )
                
                # 关联BOM项
                process.bom_items.set(boms)
                
                # 创建计划工序
                plan_process = ProductionPlanProcess.objects.create(
                    plan=plan,
                    process=process,
                    planned_start=planned_start,
                    planned_end=planned_end,
                    status='PENDING',
                    created_by=user
                )
                
                created_processes.append({
                    'id': process.id,
                    'process_no': process.process_no,
                    'name': process.name,
                    'work_center': process.work_center,
                    'bom_count': len(boms),
                    'is_critical': any(b.is_critical for b in boms),
                })
                
                sequence += 1
            
            return plan, created_processes
    
    @classmethod
    def get_bom_material_requirements(cls, project_id: int) -> Dict:
        """
        获取项目BOM的物料需求汇总
        
        Args:
            project_id: 项目ID
            
        Returns:
            物料需求汇总字典
        """
        from apps.projects.models import ProjectBOM
        
        bom_items = ProjectBOM.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).select_related('item')
        
        summary = {
            'total_items': 0,
            'total_cost': Decimal('0'),
            'by_property': {},
            'critical_items': [],
            'long_lead_items': [],
            'shortage_items': [],
        }
        
        for bom in bom_items:
            summary['total_items'] += 1
            summary['total_cost'] += (bom.estimated_cost or 0) * bom.planned_qty
            
            # 按物料属性分组
            prop = bom.item_property or bom.item.item_property
            if prop not in summary['by_property']:
                summary['by_property'][prop] = {'count': 0, 'cost': Decimal('0')}
            summary['by_property'][prop]['count'] += 1
            summary['by_property'][prop]['cost'] += (bom.estimated_cost or 0) * bom.planned_qty
            
            # 关键件
            if bom.is_critical:
                summary['critical_items'].append({
                    'id': bom.id,
                    'item_sku': bom.item.sku,
                    'item_name': bom.item.name,
                    'qty': float(bom.planned_qty),
                    'required_date': str(bom.required_date) if bom.required_date else None,
                })
            
            # 长周期件
            if bom.is_long_lead:
                summary['long_lead_items'].append({
                    'id': bom.id,
                    'item_sku': bom.item.sku,
                    'item_name': bom.item.name,
                    'lead_time': bom.item.lead_time,
                    'required_date': str(bom.required_date) if bom.required_date else None,
                })
            
            # 缺料项
            shortage = BOMPurchaseService.calculate_shortage(bom)
            if shortage > 0:
                summary['shortage_items'].append({
                    'id': bom.id,
                    'item_sku': bom.item.sku,
                    'item_name': bom.item.name,
                    'shortage_qty': float(shortage),
                    'order_status': bom.order_status,
                })
        
        # 转换Decimal为float
        summary['total_cost'] = float(summary['total_cost'])
        for prop in summary['by_property']:
            summary['by_property'][prop]['cost'] = float(summary['by_property'][prop]['cost'])
        
        return summary


# ==================== Serializers ====================

class BOMPurchaseRequestSerializer(serializers.Serializer):
    """从BOM生成采购申请的请求序列化器"""
    project_id = serializers.IntegerField(required=True)
    bom_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1
    )
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True)


class BOMProductionPlanSerializer(serializers.Serializer):
    """从BOM生成生产计划的请求序列化器"""
    project_id = serializers.IntegerField(required=True)
    bom_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1
    )
    planned_start = serializers.DateField(required=False)
    planned_end = serializers.DateField(required=False)
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)


class PurchasableBOMItemSerializer(serializers.Serializer):
    """可采购BOM项序列化器"""
    id = serializers.IntegerField()
    item_sku = serializers.CharField(source='item.sku')
    item_name = serializers.CharField(source='item.name')
    item_property = serializers.SerializerMethodField()
    planned_qty = serializers.DecimalField(max_digits=15, decimal_places=2)
    ordered_qty = serializers.DecimalField(max_digits=15, decimal_places=2)
    received_qty = serializers.DecimalField(max_digits=15, decimal_places=2)
    shortage_qty = serializers.SerializerMethodField()
    estimated_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    required_date = serializers.DateField()
    is_critical = serializers.BooleanField()
    is_long_lead = serializers.BooleanField()
    function_module = serializers.CharField()
    order_status = serializers.CharField()
    supplier_name = serializers.CharField(source='supplier.name', allow_null=True)
    
    def get_item_property(self, obj):
        return obj.item_property or obj.item.item_property
    
    def get_shortage_qty(self, obj):
        return float(BOMPurchaseService.calculate_shortage(obj))


# ==================== ViewSets ====================

class BOMIntegrationViewSet(viewsets.ViewSet):
    """
    BOM集成API端点
    提供BOM与采购、生产的集成功能
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'], url_path='purchasable/(?P<project_id>[^/.]+)')
    def get_purchasable_items(self, request, project_id=None):
        """
        获取项目可采购的BOM项列表
        GET /api/projects/bom-integration/purchasable/{project_id}/
        """
        include_ordered = request.query_params.get('include_ordered', 'false').lower() == 'true'
        
        items = BOMPurchaseService.get_purchasable_bom_items(
            int(project_id),
            include_ordered=include_ordered
        )
        
        serializer = PurchasableBOMItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='create-pr')
    def create_purchase_request(self, request):
        """
        从BOM生成采购申请
        POST /api/projects/bom-integration/create-pr/
        
        Body:
        {
            "project_id": 1,
            "bom_item_ids": [1, 2, 3],
            "title": "可选标题",
            "notes": "可选备注"
        }
        """
        serializer = BOMPurchaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            pr, lines = BOMPurchaseService.create_purchase_request_from_bom(
                project_id=serializer.validated_data['project_id'],
                bom_item_ids=serializer.validated_data['bom_item_ids'],
                user=request.user,
                title=serializer.validated_data.get('title'),
                notes=serializer.validated_data.get('notes', '')
            )
            
            return Response({
                'message': '采购申请创建成功',
                'pr_id': pr.id,
                'pr_no': pr.request_no,
                'total_amount': float(pr.total_amount),
                'lines_count': len(lines),
                'lines': lines
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='producible/(?P<project_id>[^/.]+)')
    def get_producible_items(self, request, project_id=None):
        """
        获取项目可生产的BOM项列表(自制件和组件)
        GET /api/projects/bom-integration/producible/{project_id}/
        """
        items = BOMProductionService.get_producible_bom_items(int(project_id))
        serializer = PurchasableBOMItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='create-production-plan')
    def create_production_plan(self, request):
        """
        从BOM生成生产计划
        POST /api/projects/bom-integration/create-production-plan/
        
        Body:
        {
            "project_id": 1,
            "bom_item_ids": [1, 2, 3],
            "planned_start": "2026-01-15",
            "planned_end": "2026-02-15",
            "title": "可选标题"
        }
        """
        serializer = BOMProductionPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            plan, processes = BOMProductionService.create_production_plan_from_bom(
                project_id=serializer.validated_data['project_id'],
                bom_item_ids=serializer.validated_data['bom_item_ids'],
                user=request.user,
                planned_start=serializer.validated_data.get('planned_start'),
                planned_end=serializer.validated_data.get('planned_end'),
                title=serializer.validated_data.get('title')
            )
            
            return Response({
                'message': '生产计划创建成功',
                'plan_id': plan.id,
                'plan_no': plan.plan_no,
                'processes_count': len(processes),
                'processes': processes
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='requirements/(?P<project_id>[^/.]+)')
    def get_material_requirements(self, request, project_id=None):
        """
        获取项目物料需求汇总
        GET /api/projects/bom-integration/requirements/{project_id}/
        """
        summary = BOMProductionService.get_bom_material_requirements(int(project_id))
        return Response(summary)
