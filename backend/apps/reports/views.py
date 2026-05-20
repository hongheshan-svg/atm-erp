"""
Views for reports app.
"""
import csv
from io import BytesIO

import pandas as pd
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.cost_service import CostCalculationService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_profitability(request):
    """
    Get profitability analysis for a single project or all projects.
    Query params:
        - project_id or project: specific project (optional)
        - status: filter by project status (optional)
        - format: json or excel (default: json)
    """
    project_id = request.query_params.get('project_id') or request.query_params.get('project')
    status = request.query_params.get('status')
    output_format = request.query_params.get('format', 'json')

    if project_id:
        # Single project analysis - 需要补充项目基本信息
        from apps.projects.models import Project
        try:
            project = Project.objects.select_related('manager').get(id=project_id, is_deleted=False)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在'}, status=status.HTTP_404_NOT_FOUND)

        result = CostCalculationService.calculate_project_profit(project_id)
        # 补充项目基本信息
        result.update({
            'code': project.code,
            'name': project.name,
            'status': project.status,
            'manager': project.manager.username if project.manager else ''
        })

        if output_format == 'excel':
            df = pd.DataFrame([result])
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='项目利润')
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename=project_{project_id}_profit.xlsx'
            return response
        else:
            # 返回数组格式以保持前端一致性
            return Response([result] if result else [])

    else:
        # All projects analysis
        df = CostCalculationService.calculate_all_projects_profit(status=status)

        if output_format == 'excel':
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='项目利润汇总')
            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename=all_projects_profit.xlsx'
            return response
        else:
            return Response(df.to_dict('records'))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_cost_detail(request):
    """
    Get detailed cost breakdown for a project.
    Query params:
        - project_id: required
    """
    project_id = request.query_params.get('project_id')

    if not project_id:
        return Response(
            {'error': '请提供project_id参数'},
            status=status.HTTP_400_BAD_REQUEST
        )

    detail = CostCalculationService.get_project_cost_detail_with_pandas(project_id)
    return Response(detail)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_project_cache(request):
    """
    Refresh cached calculations for a project.
    Body params:
        - project_id: required
    """
    project_id = request.data.get('project_id')

    if not project_id:
        return Response(
            {'error': '请提供project_id参数'},
            status=status.HTTP_400_BAD_REQUEST
        )

    CostCalculationService.clear_project_cache(project_id)
    result = CostCalculationService.calculate_project_profit(project_id)

    return Response({
        'message': '缓存已刷新',
        'data': result
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    Get dashboard summary with key metrics.
    """
    from django.db.models import Count, Sum

    from apps.inventory.models import Stock
    from apps.projects.models import Project
    from apps.purchase.models import PurchaseOrder
    from apps.sales.models import SalesOrder

    # Project stats
    project_stats = Project.objects.filter(is_deleted=False).aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status='ACTIVE')),
        completed=Count('id', filter=Q(status='COMPLETED'))
    )

    # Sales stats - 使用含税金额
    sales_stats = SalesOrder.objects.filter(is_deleted=False).aggregate(
        total_orders=Count('id'),
        total_amount=Sum('total_with_tax', filter=Q(status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED']))
    )

    # Purchase stats - 使用含税金额
    purchase_stats = PurchaseOrder.objects.filter(is_deleted=False).aggregate(
        total_orders=Count('id'),
        total_amount=Sum('total_with_tax', filter=Q(status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED']))
    )

    # Inventory stats
    from django.db.models import F as DbF
    low_stock_count = Stock.objects.filter(
        qty_on_hand__lt=DbF('item__min_stock'),
        item__min_stock__gt=0
    ).count()

    total_stock_value = Stock.objects.aggregate(
        total=Sum(DbF('qty_on_hand') * DbF('weighted_avg_cost'))
    )['total'] or 0

    # Get top profitable projects
    df_projects = CostCalculationService.calculate_all_projects_profit()
    if not df_projects.empty:
        top_projects = df_projects.nlargest(5, 'profit')[['code', 'name', 'profit', 'margin_percent']].to_dict('records')
    else:
        top_projects = []

    return Response({
        'projects': project_stats,
        'sales': {
            'total_orders': sales_stats['total_orders'],
            'total_amount': float(sales_stats['total_amount'] or 0)
        },
        'purchase': {
            'total_orders': purchase_stats['total_orders'],
            'total_amount': float(purchase_stats['total_amount'] or 0)
        },
        'inventory': {
            'low_stock_items': low_stock_count,
            'total_value': float(total_stock_value)
        },
        'top_projects': top_projects
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def aging_report(request):
    """
    Get AR/AP aging report.
    Query params:
        - type: 'ar' or 'ap'
        - customer/supplier: filter by customer/supplier
    """
    from datetime import datetime

    from apps.finance.models import AccountPayable, AccountReceivable

    report_type = request.query_params.get('type', 'ar')
    today = datetime.now().date()

    # Define aging buckets
    buckets = [
        ('current', 0, 30),
        ('30_60', 31, 60),
        ('60_90', 61, 90),
        ('over_90', 91, 9999)
    ]

    if report_type == 'ar':
        customer_id = request.query_params.get('customer')
        queryset = AccountReceivable.objects.filter(is_deleted=False, status__in=['PENDING', 'PARTIAL'])
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        results = []
        for ar in queryset.select_related('customer'):
            days_overdue = (today - ar.due_date).days if ar.due_date else 0
            balance = float(ar.amount_due) - float(ar.amount_paid)

            # Determine bucket
            bucket = 'current'
            for name, min_days, max_days in buckets:
                if min_days <= days_overdue <= max_days:
                    bucket = name
                    break

            results.append({
                'id': ar.id,
                'ar_no': ar.ar_no,
                'customer_name': ar.customer.name if ar.customer else '',
                'invoice_no': ar.invoice_no,
                'invoice_date': ar.invoice_date.isoformat() if ar.invoice_date else '',
                'due_date': ar.due_date.isoformat() if ar.due_date else '',
                'amount_due': float(ar.amount_due),
                'amount_paid': float(ar.amount_paid),
                'balance': balance,
                'days_overdue': max(0, days_overdue),
                'bucket': bucket
            })
    else:
        supplier_id = request.query_params.get('supplier')
        queryset = AccountPayable.objects.filter(is_deleted=False, status__in=['PENDING', 'PARTIAL'])
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        results = []
        for ap in queryset.select_related('supplier'):
            days_overdue = (today - ap.due_date).days if ap.due_date else 0
            balance = float(ap.amount_due) - float(ap.amount_paid)

            bucket = 'current'
            for name, min_days, max_days in buckets:
                if min_days <= days_overdue <= max_days:
                    bucket = name
                    break

            results.append({
                'id': ap.id,
                'ap_no': ap.ap_no,
                'supplier_name': ap.supplier.name if ap.supplier else '',
                'invoice_no': ap.invoice_no,
                'invoice_date': ap.invoice_date.isoformat() if ap.invoice_date else '',
                'due_date': ap.due_date.isoformat() if ap.due_date else '',
                'amount_due': float(ap.amount_due),
                'amount_paid': float(ap.amount_paid),
                'balance': balance,
                'days_overdue': max(0, days_overdue),
                'bucket': bucket
            })

    # Calculate summary
    summary = {
        'current': sum(r['balance'] for r in results if r['bucket'] == 'current'),
        '30_60': sum(r['balance'] for r in results if r['bucket'] == '30_60'),
        '60_90': sum(r['balance'] for r in results if r['bucket'] == '60_90'),
        'over_90': sum(r['balance'] for r in results if r['bucket'] == 'over_90'),
        'total': sum(r['balance'] for r in results)
    }

    return Response({
        'results': results,
        'summary': summary,
        'type': report_type
    })



class TimelogReportExportView(APIView):
    """工时报表导出"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.projects.models import WorkLog
        qs = WorkLog.objects.filter(is_deleted=False).select_related('project', 'task', 'user')

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(work_date__gte=start_date)
        if end_date:
            qs = qs.filter(work_date__lte=end_date)

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="timelog_report.csv"'

        writer = csv.writer(response)
        writer.writerow(['日期', '项目', '任务', '人员', '工时(小时)', '描述'])
        for log in qs[:5000]:
            writer.writerow([
                str(log.work_date) if hasattr(log, 'work_date') else '',
                str(log.project) if log.project else '',
                str(log.task) if hasattr(log, 'task') and log.task else '',
                str(log.user) if log.user else '',
                log.hours if hasattr(log, 'hours') else '',
                log.description if hasattr(log, 'description') else '',
            ])
        return response


class ProjectProfitabilityExportView(APIView):
    """项目利润分析导出"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.projects.models import Project
        projects = Project.objects.filter(is_deleted=False)

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="project_profitability.csv"'

        writer = csv.writer(response)
        writer.writerow(['项目编号', '项目名称', '状态', '合同金额', '实际成本', '利润', '利润率'])
        for p in projects[:5000]:
            contract = float(p.contract_amount) if hasattr(p, 'contract_amount') and p.contract_amount else 0
            cost = float(p.actual_cost) if hasattr(p, 'actual_cost') and p.actual_cost else 0
            profit = contract - cost
            rate = f"{profit/contract*100:.1f}%" if contract > 0 else "N/A"
            writer.writerow([
                p.project_no if hasattr(p, 'project_no') else p.id,
                p.name if hasattr(p, 'name') else str(p),
                p.status if hasattr(p, 'status') else '',
                contract,
                cost,
                profit,
                rate,
            ])
        return response
