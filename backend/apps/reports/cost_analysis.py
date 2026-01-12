"""
项目成本分析报表
Project Cost Analysis Report
"""
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.projects.models import Project, TimeLog


class ProjectCostAnalysisView(APIView):
    """项目成本分析"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        project_id = request.query_params.get('project')
        
        if not project_id:
            return Response({'error': '请选择项目'}, status=400)
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=404)
        
        # 1. 采购成本
        from apps.purchase.models import PurchaseOrderLine
        purchase_cost = PurchaseOrderLine.objects.filter(
            po__project_id=project_id,
            po__is_deleted=False
        ).aggregate(
            total=Sum(F('qty') * F('unit_price'))
        )['total'] or Decimal('0')
        
        # 2. 外协成本
        from apps.purchase.outsource_models import OutsourceOrderLine
        outsource_cost = OutsourceOrderLine.objects.filter(
            outsource_order__project_id=project_id,
            outsource_order__is_deleted=False
        ).aggregate(
            total=Sum(F('qty') * F('unit_price'))
        )['total'] or Decimal('0')
        
        # 3. 人工成本（按工时计算，假设标准工时成本100元/小时）
        hourly_rate = Decimal(request.query_params.get('hourly_rate', '100'))
        total_hours = TimeLog.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).aggregate(total=Sum('hours'))['total'] or Decimal('0')
        labor_cost = Decimal(str(total_hours)) * hourly_rate
        
        # 4. 按阶段分析人工
        labor_by_phase = TimeLog.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).values(
            'task__task_type'
        ).annotate(
            hours=Sum('hours'),
            cost=Sum('hours') * hourly_rate
        ).order_by('-hours')
        
        # 5. 物料领用成本
        from apps.inventory.models import StockOut
        material_cost = StockOut.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).aggregate(
            total=Sum(F('quantity') * F('unit_cost'))
        )['total'] or Decimal('0')
        
        # 总成本
        total_cost = purchase_cost + outsource_cost + labor_cost + material_cost
        
        # 项目预算金额（作为合同金额）
        contract_amount = project.budget_total or Decimal('0')
        
        # 毛利分析
        gross_profit = contract_amount - total_cost
        gross_margin = (gross_profit / contract_amount * 100) if contract_amount > 0 else 0
        
        # 成本构成
        cost_breakdown = [
            {'name': '采购成本', 'value': float(purchase_cost), 'percentage': 0},
            {'name': '外协成本', 'value': float(outsource_cost), 'percentage': 0},
            {'name': '人工成本', 'value': float(labor_cost), 'percentage': 0},
            {'name': '物料成本', 'value': float(material_cost), 'percentage': 0},
        ]
        
        if total_cost > 0:
            for item in cost_breakdown:
                item['percentage'] = round(item['value'] / float(total_cost) * 100, 1)
        
        return Response({
            'project': {
                'id': project.id,
                'project_no': project.project_no,
                'name': project.name,
                'status': project.status,
                'contract_amount': float(contract_amount),
            },
            'cost_summary': {
                'purchase_cost': float(purchase_cost),
                'outsource_cost': float(outsource_cost),
                'labor_cost': float(labor_cost),
                'material_cost': float(material_cost),
                'total_cost': float(total_cost),
                'labor_hours': float(total_hours),
                'hourly_rate': float(hourly_rate),
            },
            'profitability': {
                'contract_amount': float(contract_amount),
                'total_cost': float(total_cost),
                'gross_profit': float(gross_profit),
                'gross_margin': round(gross_margin, 2),
            },
            'cost_breakdown': cost_breakdown,
            'labor_by_phase': list(labor_by_phase),
        })


class ProjectCostComparisonView(APIView):
    """多项目成本对比"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        project_ids = request.query_params.getlist('projects')
        
        if not project_ids:
            # 默认取最近10个项目
            projects = Project.objects.filter(
                is_deleted=False
            ).order_by('-created_at')[:10]
            project_ids = [p.id for p in projects]
        
        comparison_data = []
        
        for pid in project_ids:
            try:
                project = Project.objects.get(id=pid)
            except Project.DoesNotExist:
                continue
            
            # 计算成本
            from apps.purchase.models import PurchaseOrderLine
            purchase_cost = PurchaseOrderLine.objects.filter(
                po__project_id=pid,
                po__is_deleted=False
            ).aggregate(total=Sum(F('qty') * F('unit_price')))['total'] or 0
            
            labor_hours = TimeLog.objects.filter(
                project_id=pid,
                is_deleted=False
            ).aggregate(total=Sum('hours'))['total'] or 0
            
            labor_cost = float(labor_hours) * 100  # 默认100元/小时
            
            total_cost = float(purchase_cost) + labor_cost
            budget_total = float(project.budget_total or 0)
            gross_profit = budget_total - total_cost
            
            comparison_data.append({
                'project_id': project.id,
                'project_no': project.project_no,
                'project_name': project.name,
                'status': project.status,
                'contract_amount': budget_total,  # Use budget_total as contract amount
                'total_cost': total_cost,
                'gross_profit': gross_profit,
                'gross_margin': round((gross_profit / budget_total * 100), 1) if budget_total > 0 else 0,
                'labor_hours': float(labor_hours),
            })
        
        # 按毛利率排序
        comparison_data.sort(key=lambda x: x['gross_margin'], reverse=True)
        
        return Response({
            'comparison': comparison_data,
            'summary': {
                'total_projects': len(comparison_data),
                'avg_margin': round(sum(d['gross_margin'] for d in comparison_data) / len(comparison_data), 1) if comparison_data else 0,
                'total_revenue': sum(d['contract_amount'] for d in comparison_data),
                'total_cost': sum(d['total_cost'] for d in comparison_data),
            }
        })


class CostTrendView(APIView):
    """成本趋势分析"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        months = int(request.query_params.get('months', 12))
        
        from django.db.models.functions import TruncMonth
        from apps.purchase.models import PurchaseOrder
        
        today = timezone.now().date()
        start_date = today.replace(day=1)
        for _ in range(months - 1):
            if start_date.month == 1:
                start_date = start_date.replace(year=start_date.year - 1, month=12)
            else:
                start_date = start_date.replace(month=start_date.month - 1)
        
        # 采购成本趋势
        purchase_trend = PurchaseOrder.objects.filter(
            order_date__gte=start_date,
            is_deleted=False
        ).annotate(
            month=TruncMonth('order_date')
        ).values('month').annotate(
            total=Sum('total_amount')
        ).order_by('month')
        
        # 人工成本趋势
        labor_trend = TimeLog.objects.filter(
            log_date__gte=start_date,
            is_deleted=False
        ).annotate(
            month=TruncMonth('log_date')
        ).values('month').annotate(
            hours=Sum('hours'),
            cost=Sum('hours') * 100
        ).order_by('month')
        
        return Response({
            'purchase_trend': list(purchase_trend),
            'labor_trend': list(labor_trend),
            'period': {
                'start': start_date.isoformat(),
                'end': today.isoformat(),
                'months': months
            }
        })
