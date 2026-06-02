"""
项目仪表盘增强模块 - 提供项目全景视图和关键指标
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ProjectDashboardView(APIView):
    """项目仪表盘 - 提供项目概览和关键指标"""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        from apps.finance.models import AccountPayable, AccountReceivable
        from apps.production.models import ProductionPlan
        from apps.purchase.models import PurchaseOrder

        from .models import Project, ProjectBOM, ProjectTask, TimeLog

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=404)

        # 基本信息
        basic_info = {
            'id': project.id,
            'code': project.code,
            'name': project.name,
            'customer_name': project.customer.name if project.customer else '',
            'manager_name': project.manager.get_full_name() if project.manager else '',
            'status': project.status,
            'start_date': project.start_date,
            'end_date': project.end_date,
        }

        # 进度指标
        tasks = ProjectTask.objects.filter(project=project, is_deleted=False)
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='DONE').count()
        in_progress_tasks = tasks.filter(status='IN_PROGRESS').count()

        progress_metrics = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'pending_tasks': total_tasks - completed_tasks - in_progress_tasks,
            'progress_percent': round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
        }

        # 工时统计
        time_logs = TimeLog.objects.filter(project=project, is_deleted=False, status='APPROVED')
        planned_hours = tasks.aggregate(
            total=Coalesce(Sum('planned_hours'), Value(Decimal('0')), output_field=DecimalField())
        )['total'] or Decimal('0')
        actual_hours = time_logs.aggregate(
            total=Coalesce(Sum('hours'), Value(Decimal('0')), output_field=DecimalField())
        )['total'] or Decimal('0')

        time_metrics = {
            'planned_hours': float(planned_hours),
            'actual_hours': float(actual_hours),
            'hours_utilization': round(actual_hours / planned_hours * 100, 1) if planned_hours > 0 else 0,
        }

        # 预算与成本
        budget_metrics = {
            'budget_total': float(project.budget_total),
            'budget_material': float(project.budget_material),
            'budget_labor': float(project.budget_labor),
            'budget_expense': float(project.budget_expense),
            'actual_material_cost': float(project.get_actual_material_cost()),
            'actual_labor_cost': float(project.get_actual_labor_cost()),
            'actual_expense_cost': float(project.get_actual_expense_cost()),
        }
        budget_metrics['actual_total'] = (
            budget_metrics['actual_material_cost']
            + budget_metrics['actual_labor_cost']
            + budget_metrics['actual_expense_cost']
        )
        budget_metrics['budget_variance'] = budget_metrics['budget_total'] - budget_metrics['actual_total']
        budget_metrics['budget_utilization'] = (
            round(budget_metrics['actual_total'] / budget_metrics['budget_total'] * 100, 1)
            if budget_metrics['budget_total'] > 0
            else 0
        )

        # 财务指标
        receivables = AccountReceivable.objects.filter(project=project, is_deleted=False)
        payables = AccountPayable.objects.filter(project=project, is_deleted=False)

        finance_metrics = {
            'total_receivable': float(
                receivables.aggregate(
                    total=Coalesce(Sum('amount_due'), Value(Decimal('0')), output_field=DecimalField())
                )['total']
                or 0
            ),
            'received': float(
                receivables.aggregate(
                    total=Coalesce(Sum('amount_paid'), Value(Decimal('0')), output_field=DecimalField())
                )['total']
                or 0
            ),
            'total_payable': float(
                payables.aggregate(total=Coalesce(Sum('amount_due'), Value(Decimal('0')), output_field=DecimalField()))[
                    'total'
                ]
                or 0
            ),
            'paid': float(
                payables.aggregate(
                    total=Coalesce(Sum('amount_paid'), Value(Decimal('0')), output_field=DecimalField())
                )['total']
                or 0
            ),
        }
        finance_metrics['pending_receivable'] = finance_metrics['total_receivable'] - finance_metrics['received']
        finance_metrics['pending_payable'] = finance_metrics['total_payable'] - finance_metrics['paid']
        finance_metrics['cash_flow'] = finance_metrics['received'] - finance_metrics['paid']

        # BOM成本
        bom_items = ProjectBOM.objects.filter(project=project, is_deleted=False)
        bom_estimated_cost = Decimal('0')
        for bom in bom_items:
            bom_estimated_cost += bom.planned_qty * bom.estimated_cost
        bom_metrics = {
            'total_items': bom_items.count(),
            'estimated_cost': float(bom_estimated_cost),
        }

        # 采购状态
        po_list = PurchaseOrder.objects.filter(project=project, is_deleted=False)
        purchase_metrics = {
            'total_orders': po_list.count(),
            'pending_orders': po_list.filter(status__in=['DRAFT', 'PENDING', 'APPROVED']).count(),
            'in_delivery': po_list.filter(status='SHIPPED').count(),
            'completed_orders': po_list.filter(status__in=['RECEIVED', 'COMPLETED']).count(),
            'total_amount': float(
                po_list.aggregate(
                    total=Coalesce(Sum('total_amount'), Value(Decimal('0')), output_field=DecimalField())
                )['total']
                or 0
            ),
        }

        # 生产状态
        production_plans = ProductionPlan.objects.filter(project=project, is_deleted=False)
        production_metrics = {
            'total_plans': production_plans.count(),
            'in_progress': production_plans.filter(status='IN_PROGRESS').count(),
            'completed': production_plans.filter(status='COMPLETED').count(),
        }

        # 风险提醒
        today = timezone.now().date()
        alerts = []

        # 进度延期风险
        if (
            project.end_date
            and project.end_date < today
            and project.status not in ['COMPLETED', 'CANCELLED', 'ARCHIVED']
        ):
            alerts.append(
                {'type': 'OVERDUE', 'severity': 'HIGH', 'message': f'项目已超期 {(today - project.end_date).days} 天'}
            )
        elif (
            project.end_date
            and (project.end_date - today).days <= 7
            and project.status not in ['COMPLETED', 'CANCELLED', 'ARCHIVED']
        ):
            alerts.append(
                {
                    'type': 'DEADLINE',
                    'severity': 'MEDIUM',
                    'message': f'项目将在 {(project.end_date - today).days} 天后到期',
                }
            )

        # 预算超支风险
        if budget_metrics['budget_utilization'] > 90:
            alerts.append(
                {
                    'type': 'BUDGET',
                    'severity': 'HIGH' if budget_metrics['budget_utilization'] > 100 else 'MEDIUM',
                    'message': f'预算使用率已达 {budget_metrics["budget_utilization"]}%',
                }
            )

        # 回款延迟
        overdue_ar = receivables.filter(due_date__lt=today, status='PENDING').count()
        if overdue_ar > 0:
            alerts.append({'type': 'RECEIVABLE', 'severity': 'MEDIUM', 'message': f'有 {overdue_ar} 笔应收款已逾期'})

        return Response(
            {
                'basic_info': basic_info,
                'progress': progress_metrics,
                'time': time_metrics,
                'budget': budget_metrics,
                'finance': finance_metrics,
                'bom': bom_metrics,
                'purchase': purchase_metrics,
                'production': production_metrics,
                'alerts': alerts,
            }
        )


class ProjectListDashboardView(APIView):
    """项目列表仪表盘 - 提供所有项目概览"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import Project

        # 筛选参数
        status = request.query_params.get('status')
        manager_id = request.query_params.get('manager')
        customer_id = request.query_params.get('customer')

        queryset = Project.objects.filter(is_deleted=False)
        if status:
            queryset = queryset.filter(status=status)
        if manager_id:
            queryset = queryset.filter(manager_id=manager_id)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        today = timezone.now().date()

        # 总体统计
        overall = {
            'total': queryset.count(),
            'active': queryset.filter(status__in=['IN_PROGRESS', 'ACTIVE']).count(),
            'completed': queryset.filter(status='COMPLETED').count(),
            'overdue': queryset.filter(end_date__lt=today, status__in=['IN_PROGRESS', 'ACTIVE', 'PLANNING']).count(),
            'total_budget': float(
                queryset.aggregate(
                    total=Coalesce(Sum('budget_total'), Value(Decimal('0')), output_field=DecimalField())
                )['total']
                or 0
            ),
        }

        # 按状态分组
        by_status = {}
        for status_code, status_name in Project.STATUS_CHOICES:
            count = queryset.filter(status=status_code).count()
            if count > 0:
                by_status[status_code] = {'name': status_name, 'count': count}

        # 按客户分组（Top 10）
        by_customer = list(
            queryset.values('customer__name')
            .annotate(count=Count('id'), total_budget=Sum('budget_total'))
            .order_by('-count')[:10]
        )

        # 近期到期项目（30天内）
        upcoming_deadline = list(
            queryset.filter(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30),
                status__in=['IN_PROGRESS', 'ACTIVE', 'PLANNING'],
            )
            .values('id', 'code', 'name', 'end_date', 'status')
            .order_by('end_date')[:10]
        )

        # 逾期项目
        overdue_projects = list(
            queryset.filter(end_date__lt=today, status__in=['IN_PROGRESS', 'ACTIVE', 'PLANNING'])
            .values('id', 'code', 'name', 'end_date', 'status')
            .order_by('end_date')[:10]
        )

        return Response(
            {
                'overall': overall,
                'by_status': by_status,
                'by_customer': by_customer,
                'upcoming_deadline': upcoming_deadline,
                'overdue_projects': overdue_projects,
            }
        )


class BOMCostRollupView(APIView):
    """BOM成本汇总分析"""

    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        from apps.purchase.models import PurchaseOrderLine

        from .models import Project, ProjectBOM

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=404)

        bom_items = ProjectBOM.objects.filter(project=project, is_deleted=False)

        # BOM成本汇总
        cost_summary = {
            'total_items': bom_items.count(),
            'estimated_cost': 0,
            'actual_cost': 0,
            'variance': 0,
        }

        item_details = []
        for bom in bom_items:
            estimated = float(bom.planned_qty) * float(bom.estimated_cost)

            # 计算实际采购成本
            actual_purchases = PurchaseOrderLine.objects.filter(
                item=bom.item,
                po__project=project,
                po__status__in=['RECEIVED', 'COMPLETED'],
                po__is_deleted=False,
            ).aggregate(
                total_qty=Coalesce(Sum('qty'), Value(Decimal('0')), output_field=DecimalField()),
                total_amount=Coalesce(Sum('line_amount'), Value(Decimal('0')), output_field=DecimalField()),
            )

            actual_cost = float(actual_purchases['total_amount'])

            item_details.append(
                {
                    'id': bom.id,
                    'item_sku': bom.item.sku if bom.item else '',
                    'item_name': bom.item.name if bom.item else '',
                    'status': bom.status,
                    'quantity': float(bom.planned_qty),
                    'unit_price': float(bom.estimated_cost),
                    'estimated_cost': estimated,
                    'actual_purchased_qty': float(actual_purchases['total_qty']),
                    'actual_cost': actual_cost,
                    'variance': estimated - actual_cost,
                }
            )

            cost_summary['estimated_cost'] += estimated
            cost_summary['actual_cost'] += actual_cost

        cost_summary['variance'] = cost_summary['estimated_cost'] - cost_summary['actual_cost']

        # 按BOM状态分组
        by_status = {}
        for item in item_details:
            item_status = item['status']
            if item_status not in by_status:
                by_status[item_status] = {'estimated': 0, 'actual': 0, 'count': 0}
            by_status[item_status]['estimated'] += item['estimated_cost']
            by_status[item_status]['actual'] += item['actual_cost']
            by_status[item_status]['count'] += 1

        return Response(
            {
                'summary': cost_summary,
                'by_status': by_status,
                'items': item_details,
            }
        )


class DeliveryTrackingView(APIView):
    """销售订单交付跟踪"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.sales.models import SalesOrder

        # 筛选参数
        customer_id = request.query_params.get('customer')
        project_id = request.query_params.get('project')
        status = request.query_params.get('status')

        queryset = SalesOrder.objects.filter(is_deleted=False)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if status:
            queryset = queryset.filter(status=status)

        today = timezone.now().date()

        # 交付状态统计
        delivery_stats = {
            'total_orders': queryset.count(),
            'pending_delivery': queryset.filter(status__in=['APPROVED', 'CONFIRMED']).count(),
            'partially_delivered': queryset.filter(status='PARTIAL_DELIVERED').count(),
            'fully_delivered': queryset.filter(status='DELIVERED').count(),
            'overdue': queryset.filter(
                delivery_date__lt=today, status__in=['APPROVED', 'CONFIRMED', 'PARTIAL_DELIVERED']
            ).count(),
        }

        # 待交付订单详情
        pending_orders = list(
            queryset.filter(status__in=['APPROVED', 'CONFIRMED', 'PARTIAL_DELIVERED'])
            .values('id', 'order_no', 'customer__name', 'project__name', 'total_amount', 'delivery_date', 'status')
            .order_by('delivery_date')[:20]
        )

        # 计算逾期天数
        for order in pending_orders:
            if order['delivery_date'] and order['delivery_date'] < today:
                order['overdue_days'] = (today - order['delivery_date']).days
            else:
                order['overdue_days'] = 0

        return Response(
            {
                'stats': delivery_stats,
                'pending_orders': pending_orders,
            }
        )


class ProcurementTrackingView(APIView):
    """采购状态跟踪"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.purchase.models import PurchaseOrder, PurchaseRequest

        # 筛选参数
        supplier_id = request.query_params.get('supplier')
        project_id = request.query_params.get('project')

        po_queryset = PurchaseOrder.objects.filter(is_deleted=False)
        pr_queryset = PurchaseRequest.objects.filter(is_deleted=False)

        if supplier_id:
            po_queryset = po_queryset.filter(supplier_id=supplier_id)
        if project_id:
            po_queryset = po_queryset.filter(project_id=project_id)
            pr_queryset = pr_queryset.filter(project_id=project_id)

        today = timezone.now().date()

        # 采购申请统计
        pr_stats = {
            'total': pr_queryset.count(),
            'pending_approval': pr_queryset.filter(status='PENDING').count(),
            'approved': pr_queryset.filter(status='APPROVED').count(),
            'rejected': pr_queryset.filter(status='REJECTED').count(),
        }

        # 采购订单统计
        po_stats = {
            'total': po_queryset.count(),
            'draft': po_queryset.filter(status='DRAFT').count(),
            'pending_approval': po_queryset.filter(status='PENDING').count(),
            'approved': po_queryset.filter(status='APPROVED').count(),
            'shipped': po_queryset.filter(status='SHIPPED').count(),
            'received': po_queryset.filter(status='RECEIVED').count(),
            'overdue': po_queryset.filter(delivery_date__lt=today, status__in=['APPROVED', 'SHIPPED']).count(),
            'total_amount': float(
                po_queryset.aggregate(
                    total=Coalesce(Sum('total_amount'), Value(Decimal('0')), output_field=DecimalField())
                )['total']
                or 0
            ),
        }

        # 待收货订单
        pending_receipt = list(
            po_queryset.filter(status__in=['APPROVED', 'SHIPPED'])
            .values('id', 'order_no', 'supplier__name', 'project__name', 'total_amount', 'delivery_date', 'status')
            .order_by('delivery_date')[:20]
        )

        for order in pending_receipt:
            order['expected_date'] = order.pop('delivery_date')  # PurchaseOrder 字段为 delivery_date，保留前端键名
            if order['expected_date'] and order['expected_date'] < today:
                order['overdue_days'] = (today - order['expected_date']).days
            else:
                order['overdue_days'] = 0

        return Response(
            {
                'purchase_request': pr_stats,
                'purchase_order': po_stats,
                'pending_receipt': pending_receipt,
            }
        )


class ProductionProgressView(APIView):
    """生产进度跟踪"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.production.models import ProductionPlan

        # 筛选参数
        project_id = request.query_params.get('project')

        plan_queryset = ProductionPlan.objects.filter(is_deleted=False)
        if project_id:
            plan_queryset = plan_queryset.filter(project_id=project_id)

        today = timezone.now().date()

        # 生产计划统计
        plan_stats = {
            'total': plan_queryset.count(),
            'draft': plan_queryset.filter(status='DRAFT').count(),
            'pending': plan_queryset.filter(status='PENDING').count(),
            'in_progress': plan_queryset.filter(status='IN_PROGRESS').count(),
            'completed': plan_queryset.filter(status='COMPLETED').count(),
            'overdue': plan_queryset.filter(planned_end__lt=today, status__in=['PENDING', 'IN_PROGRESS']).count(),
        }

        # 进行中的生产计划
        # ProductionPlan 无 item/数量字段，用真实字段；planned_start/end 在循环里重映射为前端键
        active_plans = list(
            plan_queryset.filter(status='IN_PROGRESS')
            .values('id', 'plan_no', 'title', 'project__name', 'progress_percent', 'planned_start', 'planned_end')
            .order_by('planned_end')[:20]
        )

        for plan in active_plans:
            plan['planned_start_date'] = plan.pop('planned_start')
            plan['planned_end_date'] = plan.pop('planned_end')
            ped = plan['planned_end_date']
            plan['overdue_days'] = (today - ped).days if ped and ped < today else 0

        return Response(
            {
                'stats': plan_stats,
                'active_plans': active_plans,
            }
        )
