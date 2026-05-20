"""
非标自动化行业专用报表
Industry-specific Reports for Non-standard Automation

功能：
- 项目毛利分析
- 设备全生命周期分析
- 产能利用率分析
- 客户价值分析
"""
from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# =============================================================================
# 报表API
# =============================================================================

class ProjectProfitabilityReportView(APIView):
    """项目毛利分析报表"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.projects.cost_tracking import ProjectBudget, ProjectCostRecord
        from apps.projects.models import Project

        # 筛选条件
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        customer_id = request.query_params.get('customer_id')
        status_filter = request.query_params.get('status')

        queryset = Project.objects.filter(is_deleted=False)

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        projects_data = []

        for project in queryset.select_related('sales_order', 'customer'):
            # 合同金额：优先使用关联销售订单金额，否则使用项目预算
            if project.sales_order and hasattr(project.sales_order, 'total_with_tax') and project.sales_order.total_with_tax:
                contract_amount = float(project.sales_order.total_with_tax)
            else:
                contract_amount = float(project.budget_total or 0)

            # 实际成本
            costs = ProjectCostRecord.objects.filter(
                project=project, is_deleted=False
            ).aggregate(total=Sum('amount'))
            actual_cost = float(costs['total'] or 0)

            # 预算
            try:
                budget = project.budget
                budget_amount = float(budget.total_budget)
            except ProjectBudget.DoesNotExist:
                budget_amount = 0

            # 毛利
            gross_profit = contract_amount - actual_cost
            gross_margin = (gross_profit / contract_amount * 100) if contract_amount > 0 else 0

            # 预算偏差
            budget_variance = budget_amount - actual_cost
            budget_variance_rate = (budget_variance / budget_amount * 100) if budget_amount > 0 else 0

            projects_data.append({
                'project_id': project.id,
                'project_no': project.code,
                'project_name': project.name,
                'customer_name': project.customer.name if project.customer else '',
                'status': project.status,
                'contract_amount': contract_amount,
                'budget_amount': budget_amount,
                'actual_cost': actual_cost,
                'gross_profit': gross_profit,
                'gross_margin': round(gross_margin, 2),
                'budget_variance': budget_variance,
                'budget_variance_rate': round(budget_variance_rate, 2),
            })

        # 汇总
        total_contract = sum(p['contract_amount'] for p in projects_data)
        total_cost = sum(p['actual_cost'] for p in projects_data)
        total_profit = sum(p['gross_profit'] for p in projects_data)
        avg_margin = (total_profit / total_contract * 100) if total_contract > 0 else 0

        # 按客户汇总
        by_customer = {}
        for p in projects_data:
            customer = p['customer_name']
            if customer not in by_customer:
                by_customer[customer] = {
                    'contract_amount': 0,
                    'actual_cost': 0,
                    'gross_profit': 0,
                    'project_count': 0
                }
            by_customer[customer]['contract_amount'] += p['contract_amount']
            by_customer[customer]['actual_cost'] += p['actual_cost']
            by_customer[customer]['gross_profit'] += p['gross_profit']
            by_customer[customer]['project_count'] += 1

        return Response({
            'projects': projects_data,
            'summary': {
                'total_projects': len(projects_data),
                'total_contract_amount': total_contract,
                'total_actual_cost': total_cost,
                'total_gross_profit': total_profit,
                'average_gross_margin': round(avg_margin, 2),
            },
            'by_customer': [
                {'customer': k, **v} for k, v in sorted(
                    by_customer.items(), key=lambda x: x[1]['gross_profit'], reverse=True
                )
            ]
        })


class EquipmentLifecycleReportView(APIView):
    """设备全生命周期分析"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.inventory.spare_parts import SparePartConsumption
        from apps.projects.field_service import ServiceOrder
        from apps.projects.models import Equipment

        equipment_id = request.query_params.get('equipment_id')

        if not equipment_id:
            # 返回设备概览
            equipments = Equipment.objects.filter(is_deleted=False)

            overview = []
            for eq in equipments[:50]:  # 限制数量
                # 服务次数
                service_count = ServiceOrder.objects.filter(
                    equipment=eq, is_deleted=False
                ).count()

                # 备件消耗
                spare_cost = SparePartConsumption.objects.filter(
                    equipment=eq, is_deleted=False
                ).aggregate(total=Sum('total_cost'))['total'] or 0

                overview.append({
                    'equipment_id': eq.id,
                    'equipment_no': eq.equipment_no,
                    'name': eq.name,
                    'customer_name': eq.customer.name if eq.customer else '',
                    'install_date': eq.install_date,
                    'service_count': service_count,
                    'spare_cost': float(spare_cost),
                })

            return Response({'equipments': overview})

        # 单设备详细分析
        try:
            equipment = Equipment.objects.get(id=equipment_id, is_deleted=False)
        except Equipment.DoesNotExist:
            return Response({'error': '设备不存在'}, status=404)

        # 服务历史
        services = ServiceOrder.objects.filter(
            equipment=equipment, is_deleted=False
        ).values('service_type').annotate(
            count=Count('id'),
            total_cost=Sum('actual_cost')
        )

        # 备件消耗趋势
        spare_trend = SparePartConsumption.objects.filter(
            equipment=equipment, is_deleted=False
        ).annotate(
            month=TruncMonth('consumption_date')
        ).values('month').annotate(
            count=Count('id'),
            cost=Sum('total_cost')
        ).order_by('month')

        # 故障统计
        from apps.projects.remote_monitoring import EquipmentAlarm
        alarms = EquipmentAlarm.objects.filter(
            equipment=equipment, is_deleted=False
        ).values('severity').annotate(count=Count('id'))

        # 计算设备健康分数
        health_score = 100
        critical_alarms = sum(a['count'] for a in alarms if a['severity'] == 'CRITICAL')
        health_score -= critical_alarms * 10
        health_score = max(health_score, 0)

        return Response({
            'equipment': {
                'id': equipment.id,
                'equipment_no': equipment.equipment_no,
                'name': equipment.name,
                'customer_name': equipment.customer.name if equipment.customer else '',
                'install_date': equipment.install_date,
                'warranty_end': equipment.warranty_end_date,
            },
            'service_summary': list(services),
            'spare_trend': list(spare_trend),
            'alarm_summary': list(alarms),
            'health_score': health_score,
        })


class CapacityUtilizationReportView(APIView):
    """产能利用率分析"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.production.aps import ScheduleOrder
        from apps.production.models import WorkCenter
        from apps.production.routing import WorkStation

        start_date = request.query_params.get('start_date', str(date.today() - timedelta(days=30)))
        end_date = request.query_params.get('end_date', str(date.today()))

        # 计算工作天数
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        work_days = (end - start).days + 1
        daily_hours = 8

        # 工作中心利用率
        work_centers = []
        for wc in WorkCenter.objects.filter(is_deleted=False):
            # 计划工时
            planned = ScheduleOrder.objects.filter(
                work_center=wc,
                planned_start__lte=end,
                planned_end__gte=start,
                is_deleted=False
            ).aggregate(total=Sum('planned_hours'))['total'] or 0

            # 可用工时
            available = work_days * daily_hours * float(wc.capacity_per_day or 1)

            utilization = (float(planned) / available * 100) if available > 0 else 0

            work_centers.append({
                'work_center_id': wc.id,
                'work_center_name': wc.name,
                'available_hours': available,
                'planned_hours': float(planned),
                'utilization_rate': round(utilization, 2),
            })

        # 工位利用率
        stations = []
        for ws in WorkStation.objects.filter(is_deleted=False, is_active=True):
            # 简化计算
            available = work_days * daily_hours

            stations.append({
                'station_id': ws.id,
                'station_name': ws.name,
                'station_type': ws.station_type,
                'standard_capacity': float(ws.standard_capacity),
                'uph': float(ws.uph),
            })

        # 整体统计
        total_available = sum(wc['available_hours'] for wc in work_centers)
        total_planned = sum(wc['planned_hours'] for wc in work_centers)
        overall_utilization = (total_planned / total_available * 100) if total_available > 0 else 0

        # 瓶颈分析
        bottlenecks = sorted(work_centers, key=lambda x: x['utilization_rate'], reverse=True)[:5]

        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'work_days': work_days,
            },
            'work_centers': sorted(work_centers, key=lambda x: x['utilization_rate'], reverse=True),
            'stations': stations,
            'summary': {
                'total_available_hours': total_available,
                'total_planned_hours': total_planned,
                'overall_utilization': round(overall_utilization, 2),
            },
            'bottlenecks': bottlenecks,
        })


class CustomerValueReportView(APIView):
    """客户价值分析"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.masterdata.models import Customer
        from apps.projects.field_service import ServiceOrder
        from apps.projects.models import Project
        from apps.sales.models import SalesOrder

        # 筛选条件
        year = int(request.query_params.get('year', date.today().year))

        customers_data = []

        for customer in Customer.objects.filter(is_deleted=False):
            # 项目统计
            projects = Project.objects.filter(
                customer=customer,
                created_at__year=year,
                is_deleted=False
            )
            project_count = projects.count()
            project_amount = projects.aggregate(total=Sum('budget_total'))['total'] or 0

            # 订单统计
            orders = SalesOrder.objects.filter(
                customer=customer,
                order_date__year=year,
                is_deleted=False
            )
            order_count = orders.count()
            order_amount = orders.aggregate(total=Sum('total_amount'))['total'] or 0

            # 服务统计
            services = ServiceOrder.objects.filter(
                customer=customer,
                created_at__year=year,
                is_deleted=False
            )
            service_count = services.count()
            service_cost = services.aggregate(total=Sum('actual_cost'))['total'] or 0

            # 总收入
            total_revenue = float(project_amount) + float(order_amount)

            if total_revenue > 0 or project_count > 0:
                customers_data.append({
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'industry': getattr(customer, 'industry', '') or '',
                    'project_count': project_count,
                    'project_amount': float(project_amount),
                    'order_count': order_count,
                    'order_amount': float(order_amount),
                    'total_revenue': total_revenue,
                    'service_count': service_count,
                    'service_cost': float(service_cost),
                })

        # 排序（按总收入）
        customers_data = sorted(customers_data, key=lambda x: x['total_revenue'], reverse=True)

        # 客户分级（RFM简化版）
        total_revenue_all = sum(c['total_revenue'] for c in customers_data)
        running_total = 0
        for c in customers_data:
            running_total += c['total_revenue']
            percentage = (running_total / total_revenue_all * 100) if total_revenue_all > 0 else 0
            if percentage <= 20:
                c['tier'] = 'A'
            elif percentage <= 50:
                c['tier'] = 'B'
            elif percentage <= 80:
                c['tier'] = 'C'
            else:
                c['tier'] = 'D'

        # 汇总
        tier_summary = {}
        for c in customers_data:
            tier = c['tier']
            if tier not in tier_summary:
                tier_summary[tier] = {'count': 0, 'revenue': 0}
            tier_summary[tier]['count'] += 1
            tier_summary[tier]['revenue'] += c['total_revenue']

        return Response({
            'year': year,
            'customers': customers_data[:50],  # 前50
            'tier_summary': tier_summary,
            'total_customers': len(customers_data),
            'total_revenue': total_revenue_all,
        })


class ProjectDeliveryReportView(APIView):
    """项目交付分析"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.projects.models import Project

        year = int(request.query_params.get('year', date.today().year))

        projects = Project.objects.filter(
            created_at__year=year,
            is_deleted=False
        )

        # 按月统计
        monthly_stats = projects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED')),
        ).order_by('month')

        # 状态分布
        status_dist = projects.values('status').annotate(count=Count('id'))

        # 交期统计
        completed = projects.filter(status='COMPLETED')
        on_time = 0
        delayed = 0
        total_delay_days = 0

        for p in completed:
            if p.actual_end_date and p.planned_end_date:
                if p.actual_end_date <= p.planned_end_date:
                    on_time += 1
                else:
                    delayed += 1
                    total_delay_days += (p.actual_end_date - p.planned_end_date).days

        on_time_rate = (on_time / completed.count() * 100) if completed.count() > 0 else 0
        avg_delay = (total_delay_days / delayed) if delayed > 0 else 0

        # 项目周期分析
        cycle_times = []
        for p in completed:
            if p.actual_end_date and p.start_date:
                cycle = (p.actual_end_date - p.start_date).days
                cycle_times.append(cycle)

        avg_cycle = sum(cycle_times) / len(cycle_times) if cycle_times else 0

        return Response({
            'year': year,
            'monthly_stats': list(monthly_stats),
            'status_distribution': list(status_dist),
            'delivery_performance': {
                'total_completed': completed.count(),
                'on_time': on_time,
                'delayed': delayed,
                'on_time_rate': round(on_time_rate, 2),
                'average_delay_days': round(avg_delay, 1),
            },
            'cycle_analysis': {
                'average_cycle_days': round(avg_cycle, 1),
                'min_cycle_days': min(cycle_times) if cycle_times else 0,
                'max_cycle_days': max(cycle_times) if cycle_times else 0,
            }
        })


class OutsourceAnalysisReportView(APIView):
    """外协分析报表"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.purchase.outsource_tracking import OutsourceCapability, OutsourceInspection, OutsourceOrder

        year = int(request.query_params.get('year', date.today().year))

        orders = OutsourceOrder.objects.filter(
            order_date__year=year,
            is_deleted=False
        )

        # 总体统计
        total_orders = orders.count()
        total_amount = orders.aggregate(total=Sum('total_amount'))['total'] or 0
        completed = orders.filter(status='COMPLETED').count()

        # 按供应商统计
        by_supplier = orders.values(
            'supplier__name'
        ).annotate(
            order_count=Count('id'),
            total_amount=Sum('total_amount'),
            completed=Count('id', filter=Q(status='COMPLETED'))
        ).order_by('-total_amount')[:20]

        # 按工艺类型统计
        by_process = orders.values('process_type').annotate(
            order_count=Count('id'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')

        # 质量统计
        inspections = OutsourceInspection.objects.filter(
            order__order_date__year=year,
            is_deleted=False
        )
        total_inspected = inspections.aggregate(total=Sum('inspected_quantity'))['total'] or 0
        total_qualified = inspections.aggregate(total=Sum('qualified_quantity'))['total'] or 0
        pass_rate = (float(total_qualified) / float(total_inspected) * 100) if total_inspected else 0

        # 供应商能力分布
        capabilities = OutsourceCapability.objects.filter(is_deleted=False)
        capability_dist = capabilities.values('process_type').annotate(
            supplier_count=Count('supplier', distinct=True),
            avg_rating=Avg('overall_rating')
        )

        return Response({
            'year': year,
            'summary': {
                'total_orders': total_orders,
                'total_amount': float(total_amount),
                'completed_orders': completed,
                'completion_rate': round(completed / total_orders * 100, 2) if total_orders else 0,
            },
            'quality': {
                'total_inspected': float(total_inspected),
                'total_qualified': float(total_qualified),
                'pass_rate': round(pass_rate, 2),
            },
            'by_supplier': list(by_supplier),
            'by_process': list(by_process),
            'capability_distribution': list(capability_dist),
        })
