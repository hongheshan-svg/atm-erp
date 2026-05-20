"""
项目缺料计算
Project Material Shortage Calculation

核心功能：基于项目BOM计算物料缺口，生成采购建议

非标自动化行业使用说明：
- 选择一个或多个项目，展开BOM计算总需求
- 对比现有库存，生成缺料清单
- 可直接生成采购申请

简化说明：
- 安全库存系数(safety_stock_factor)：建议设为0或1，非标不需要额外安全库存
- 提前期系数(lead_time_factor)：建议设为1，按实际采购周期
- 此功能聚焦于"项目需要什么 vs 仓库有什么"的简单对比

典型使用流程：
1. 选择即将开工的项目
2. 运行MRP计算
3. 查看缺料清单
4. 一键生成采购申请
"""

from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class MRPPlan(BaseModel):
    """
    MRP计划
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CALCULATING', '计算中'),
        ('COMPLETED', '已完成'),
        ('APPROVED', '已批准'),
        ('EXECUTING', '执行中'),
        ('CLOSED', '已关闭'),
    ]

    plan_no = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    name = models.CharField(max_length=200, verbose_name='计划名称')

    # 计划范围
    start_date = models.DateField(verbose_name='计划开始日期')
    end_date = models.DateField(verbose_name='计划结束日期')

    # 来源项目
    projects = models.JSONField(default=list, blank=True, verbose_name='来源项目')

    # 计算参数
    safety_stock_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, verbose_name='安全库存系数')
    lead_time_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, verbose_name='提前期系数')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 计算结果统计
    total_items = models.IntegerField(default=0, verbose_name='物料数量')
    shortage_items = models.IntegerField(default=0, verbose_name='缺料物料数')
    total_shortage_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='缺料总金额')

    calculated_at = models.DateTimeField(null=True, blank=True, verbose_name='计算时间')
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_mrp_plans',
        verbose_name='批准人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='批准时间')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'inventory_mrp_plan'
        verbose_name = 'MRP计划'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.plan_no} - {self.name}'

    def save(self, *args, **kwargs):
        if not self.plan_no:
            from apps.core.utils import generate_code

            self.plan_no = generate_code('MRP')
        super().save(*args, **kwargs)


class MRPLine(BaseModel):
    """
    MRP计划明细
    """

    ACTION_TYPES = [
        ('NONE', '无需操作'),
        ('PURCHASE', '需采购'),
        ('PRODUCE', '需生产'),
        ('TRANSFER', '需调拨'),
    ]

    plan = models.ForeignKey(MRPPlan, on_delete=models.CASCADE, related_name='lines', verbose_name='MRP计划')
    item = models.ForeignKey('masterdata.Item', on_delete=models.CASCADE, related_name='mrp_lines', verbose_name='物料')

    # 需求来源
    source_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mrp_lines',
        verbose_name='来源项目',
    )
    source_bom = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mrp_lines',
        verbose_name='来源BOM',
    )

    # 需求
    required_date = models.DateField(verbose_name='需求日期')
    gross_requirement = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='毛需求量')

    # 库存
    on_hand_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='在库数量')
    allocated_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='已分配数量')
    on_order_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='在途数量')
    safety_stock = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='安全库存')

    # 净需求
    net_requirement = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='净需求量')

    # 建议
    suggested_action = models.CharField(max_length=20, choices=ACTION_TYPES, default='NONE', verbose_name='建议操作')
    suggested_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='建议数量')
    suggested_date = models.DateField(null=True, blank=True, verbose_name='建议日期')

    # 金额
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='单价')
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='总金额')

    # 执行
    is_confirmed = models.BooleanField(default=False, verbose_name='已确认')
    purchase_request = models.ForeignKey(
        'purchase.PurchaseRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mrp_lines',
        verbose_name='采购申请',
    )

    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'inventory_mrp_line'
        verbose_name = 'MRP明细'
        verbose_name_plural = verbose_name
        ordering = ['required_date']

    def __str__(self):
        return f'{self.item.code} - {self.net_requirement}'


class MRPService:
    """MRP计算服务"""

    @staticmethod
    def calculate_plan(plan: MRPPlan):
        """计算MRP计划"""
        from apps.inventory.models import Stock
        from apps.projects.models import Project, ProjectBOM
        from apps.purchase.models import PurchaseOrderLine

        # 清除旧的计算结果
        plan.lines.all().delete()

        # 获取项目BOM需求
        project_ids = plan.projects if plan.projects else []
        if not project_ids:
            # 如果没有指定项目，获取计划期间内的所有进行中项目
            projects = Project.objects.filter(
                status__in=['IN_PROGRESS', 'PLANNING'],
                end_date__gte=plan.start_date,
                start_date__lte=plan.end_date,
                is_deleted=False,
            )
            project_ids = list(projects.values_list('id', flat=True))

        # 汇总BOM需求
        requirements = {}

        bom_items = ProjectBOM.objects.filter(project_id__in=project_ids, is_deleted=False).select_related(
            'item', 'project'
        )

        for bom in bom_items:
            if not bom.item:
                continue

            item_id = bom.item_id
            if item_id not in requirements:
                requirements[item_id] = {
                    'item': bom.item,
                    'gross_qty': Decimal('0'),
                    'required_date': plan.end_date,
                    'sources': [],
                }

            requirements[item_id]['gross_qty'] += bom.quantity or Decimal('0')
            requirements[item_id]['sources'].append(
                {
                    'project_id': bom.project_id,
                    'project_name': bom.project.name if bom.project else '',
                    'bom_id': bom.id,
                    'qty': bom.quantity,
                }
            )

            # 使用最早的需求日期
            if bom.required_date and bom.required_date < requirements[item_id]['required_date']:
                requirements[item_id]['required_date'] = bom.required_date

        # 获取库存和在途信息
        lines_to_create = []
        total_shortage = Decimal('0')
        shortage_count = 0

        for item_id, req in requirements.items():
            item = req['item']

            # 获取在库数量
            on_hand = Stock.objects.filter(item_id=item_id, is_deleted=False).aggregate(total=Sum('quantity'))[
                'total'
            ] or Decimal('0')

            # 获取已分配数量（已确认的领料申请）
            from apps.inventory.models import MaterialRequisitionLine

            allocated = MaterialRequisitionLine.objects.filter(
                item_id=item_id, requisition__status__in=['APPROVED', 'PARTIAL'], is_deleted=False
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')

            # 获取在途数量
            on_order = PurchaseOrderLine.objects.filter(
                item_id=item_id, order__status__in=['APPROVED', 'PARTIAL'], is_deleted=False
            ).aggregate(total=Sum(F('quantity') - F('received_qty')))['total'] or Decimal('0')

            # 安全库存
            safety_stock = (item.safety_stock or Decimal('0')) * plan.safety_stock_factor

            # 计算净需求
            available = on_hand - allocated + on_order
            net_requirement = req['gross_qty'] + safety_stock - available
            net_requirement = max(net_requirement, Decimal('0'))

            # 建议操作
            if net_requirement > 0:
                suggested_action = 'PURCHASE'
                shortage_count += 1
            else:
                suggested_action = 'NONE'

            # 建议日期（考虑提前期）
            lead_time = item.lead_time or 7
            suggested_date = req['required_date'] - timedelta(days=int(lead_time * float(plan.lead_time_factor)))

            # 单价和金额
            unit_price = item.purchase_price or Decimal('0')
            total_amount = net_requirement * unit_price
            total_shortage += total_amount if net_requirement > 0 else Decimal('0')

            # 创建明细
            line = MRPLine(
                plan=plan,
                item=item,
                source_project_id=req['sources'][0]['project_id'] if req['sources'] else None,
                required_date=req['required_date'],
                gross_requirement=req['gross_qty'],
                on_hand_qty=on_hand,
                allocated_qty=allocated,
                on_order_qty=on_order,
                safety_stock=safety_stock,
                net_requirement=net_requirement,
                suggested_action=suggested_action,
                suggested_qty=net_requirement,
                suggested_date=suggested_date,
                unit_price=unit_price,
                total_amount=total_amount,
            )
            lines_to_create.append(line)

        # 批量创建
        MRPLine.objects.bulk_create(lines_to_create)

        # 更新计划统计
        plan.total_items = len(lines_to_create)
        plan.shortage_items = shortage_count
        plan.total_shortage_amount = total_shortage
        plan.calculated_at = timezone.now()
        plan.status = 'COMPLETED'
        plan.save()

        return plan

    @staticmethod
    def generate_purchase_requests(plan: MRPPlan, line_ids=None):
        """生成采购申请"""
        from apps.purchase.models import PurchaseRequest, PurchaseRequestLine

        lines = plan.lines.filter(suggested_action='PURCHASE', is_confirmed=False, net_requirement__gt=0)

        if line_ids:
            lines = lines.filter(id__in=line_ids)

        if not lines.exists():
            return None

        # 创建采购申请
        pr = PurchaseRequest.objects.create(
            title=f'MRP自动生成-{plan.plan_no}',
            source_type='MRP',
            source_no=plan.plan_no,
            status='DRAFT',
            created_by=plan.created_by,
        )

        for line in lines:
            PurchaseRequestLine.objects.create(
                request=pr,
                item=line.item,
                quantity=line.suggested_qty,
                required_date=line.suggested_date,
                remarks=f'来自MRP计划: {plan.plan_no}',
            )

            # 标记已确认
            line.is_confirmed = True
            line.purchase_request = pr
            line.save()

        return pr


# =====================
# Serializers
# =====================


class MRPLineSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    project_name = serializers.CharField(source='source_project.name', read_only=True)
    action_display = serializers.CharField(source='get_suggested_action_display', read_only=True)

    class Meta:
        model = MRPLine
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class MRPPlanSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    lines = MRPLineSerializer(many=True, read_only=True)

    class Meta:
        model = MRPPlan
        fields = '__all__'
        read_only_fields = [
            'created_by',
            'updated_by',
            'plan_no',
            'calculated_at',
            'approved_by',
            'approved_at',
            'total_items',
            'shortage_items',
            'total_shortage_amount',
        ]


class MRPPlanListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = MRPPlan
        fields = [
            'id',
            'plan_no',
            'name',
            'start_date',
            'end_date',
            'status',
            'status_display',
            'total_items',
            'shortage_items',
            'total_shortage_amount',
            'calculated_at',
            'created_by_name',
            'created_at',
        ]


# =====================
# ViewSets
# =====================


class MRPPlanViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """MRP计划管理"""

    queryset = MRPPlan.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status']
    search_fields = ['plan_no', 'name']
    ordering_fields = ['created_at', 'start_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return MRPPlanListSerializer
        return MRPPlanSerializer

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """执行MRP计算"""
        plan = self.get_object()

        if plan.status not in ['DRAFT', 'COMPLETED']:
            return Response({'error': '只有草稿或已完成状态可以重新计算'}, status=400)

        plan.status = 'CALCULATING'
        plan.save()

        try:
            MRPService.calculate_plan(plan)
            return Response(self.get_serializer(plan).data)
        except Exception as e:
            plan.status = 'DRAFT'
            plan.save()
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准计划"""
        plan = self.get_object()

        if plan.status != 'COMPLETED':
            return Response({'error': '只有已完成的计划可以批准'}, status=400)

        plan.status = 'APPROVED'
        plan.approved_by = request.user
        plan.approved_at = timezone.now()
        plan.save()

        return Response(self.get_serializer(plan).data)

    @action(detail=True, methods=['post'])
    def generate_pr(self, request, pk=None):
        """生成采购申请"""
        plan = self.get_object()
        line_ids = request.data.get('line_ids')

        if plan.status != 'APPROVED':
            return Response({'error': '只有已批准的计划可以生成采购申请'}, status=400)

        pr = MRPService.generate_purchase_requests(plan, line_ids)

        if not pr:
            return Response({'error': '没有需要采购的物料'}, status=400)

        plan.status = 'EXECUTING'
        plan.save()

        return Response(
            {
                'success': True,
                'purchase_request_id': pr.id,
                'purchase_request_no': pr.request_no if hasattr(pr, 'request_no') else str(pr.id),
            }
        )

    @action(detail=False, methods=['get'])
    def shortage_summary(self, request):
        """缺料汇总"""
        # 获取最新的已批准计划
        plan = self.get_queryset().filter(status='APPROVED').order_by('-created_at').first()

        if not plan:
            return Response({'error': '没有已批准的MRP计划'}, status=404)

        shortage_lines = (
            plan.lines.filter(suggested_action='PURCHASE', net_requirement__gt=0)
            .select_related('item')
            .order_by('-total_amount')
        )

        return Response(
            {
                'plan_no': plan.plan_no,
                'plan_name': plan.name,
                'total_items': shortage_lines.count(),
                'total_amount': sum(line.total_amount for line in shortage_lines),
                'items': MRPLineSerializer(shortage_lines[:50], many=True).data,
            }
        )


class MRPLineViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """MRP明细"""

    queryset = MRPLine.objects.filter(is_deleted=False)
    serializer_class = MRPLineSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['plan', 'suggested_action', 'is_confirmed']
    search_fields = ['item__code', 'item__name']
    ordering_fields = ['required_date', 'net_requirement', 'total_amount']

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认明细"""
        line = self.get_object()
        line.is_confirmed = True
        line.save()
        return Response(self.get_serializer(line).data)
