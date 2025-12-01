"""
Export views for all modules.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .export_service import ExcelExportService, PDFExportService, EXPORT_COLUMNS


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_projects(request):
    """Export projects to Excel."""
    from apps.projects.models import Project
    
    queryset = Project.objects.filter(is_deleted=False).select_related('customer', 'manager')
    
    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['project'],
        'projects',
        '项目列表'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_sales_orders(request):
    """Export sales orders to Excel."""
    from apps.sales.models import SalesOrder
    
    queryset = SalesOrder.objects.filter(is_deleted=False).select_related('customer', 'project')
    
    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    project_id = request.query_params.get('project')
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['sales_order'],
        'sales_orders',
        '销售订单'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_purchase_orders(request):
    """Export purchase orders to Excel."""
    from apps.purchase.models import PurchaseOrder
    
    queryset = PurchaseOrder.objects.filter(is_deleted=False).select_related('supplier', 'project')
    
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['purchase_order'],
        'purchase_orders',
        '采购订单'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_stock(request):
    """Export stock to Excel."""
    from apps.inventory.models import Stock
    
    queryset = Stock.objects.select_related('warehouse', 'item')
    
    warehouse_id = request.query_params.get('warehouse')
    if warehouse_id:
        queryset = queryset.filter(warehouse_id=warehouse_id)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['stock'],
        'stock',
        '库存列表'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_expenses(request):
    """Export expenses to Excel."""
    from apps.finance.models import Expense
    
    queryset = Expense.objects.filter(is_deleted=False).select_related('user', 'project')
    
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['expense'],
        'expenses',
        '费用报销'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_ar(request):
    """Export accounts receivable to Excel."""
    from apps.finance.models import AccountReceivable
    
    queryset = AccountReceivable.objects.filter(is_deleted=False).select_related('customer')
    
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['ar'],
        'accounts_receivable',
        '应收账款'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_ap(request):
    """Export accounts payable to Excel."""
    from apps.finance.models import AccountPayable
    
    queryset = AccountPayable.objects.filter(is_deleted=False).select_related('supplier')
    
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    return ExcelExportService.export_queryset(
        queryset,
        EXPORT_COLUMNS['ap'],
        'accounts_payable',
        '应付账款'
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_project_profit_report(request):
    """Export project profitability report."""
    from apps.reports.services.cost_service import CostCalculationService
    
    status_filter = request.query_params.get('status')
    df = CostCalculationService.calculate_all_projects_profit(status=status_filter)
    
    if df.empty:
        return Response({'error': '没有数据'}, status=status.HTTP_404_NOT_FOUND)
    
    columns = [
        {'field': 'code', 'header': '项目编号', 'width': 15},
        {'field': 'name', 'header': '项目名称', 'width': 25},
        {'field': 'manager', 'header': '项目经理', 'width': 12},
        {'field': 'status', 'header': '状态', 'width': 10},
        {'field': 'revenue', 'header': '收入', 'width': 15},
        {'field': 'material_cost', 'header': '材料成本', 'width': 15},
        {'field': 'labor_cost', 'header': '人工成本', 'width': 15},
        {'field': 'expense_cost', 'header': '费用', 'width': 15},
        {'field': 'total_cost', 'header': '总成本', 'width': 15},
        {'field': 'profit', 'header': '利润', 'width': 15},
        {'field': 'margin_percent', 'header': '利润率(%)', 'width': 12},
    ]
    
    return ExcelExportService.export_queryset(
        df.to_dict('records'),
        columns,
        'project_profit_report',
        '项目利润报表'
    )
