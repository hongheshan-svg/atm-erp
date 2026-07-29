"""
Export views for all modules.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .export_service import EXPORT_COLUMNS, ExcelExportService
from .permission_service import apply_scope_filter, get_hidden_fields, resolve_data_scope
from .permissions import module_menu_permission


def _scoped_queryset(queryset, user, module, user_field='created_by'):
    """按用户在 module 的数据范围过滤 queryset，与对应 ViewSet(PermissionMixin)列表页一致。

    导出接口此前只做菜单授权，任何持菜单权限的用户都能导出全公司数据，
    绕过了其在列表页受限的数据范围（self/dept/dept_tree/custom）。此处复用
    与 PermissionMixin.get_queryset 相同的 resolve_data_scope + apply_scope_filter。
    """
    if user is None or not user.is_authenticated:
        return queryset.none()
    scope_result = resolve_data_scope(user, module)
    return apply_scope_filter(queryset, user, scope_result, user_field=user_field)


def _visible_columns(columns, user, module, resource):
    """剔除该用户角色被拒绝可见的敏感字段列，与 PermissionMixin.get_serializer 字段级脱敏一致。

    仅按列的 field 名精确匹配隐藏字段（模型自身字段，如 budget_total/weighted_avg_cost/
    amount_due 等成本价格类）；关联字段（customer__name 等）不受影响。未种子化字段权限的
    resource 返回空集合，不剔除任何列——与历史行为向后兼容。
    """
    hidden = get_hidden_fields(user, module, resource)
    if not hidden:
        return columns
    return [col for col in columns if col['field'] not in hidden]


@api_view(['GET'])
@permission_classes([module_menu_permission('projects')])
def export_projects(request):
    """Export projects to Excel."""
    from apps.projects.models import Project

    queryset = Project.objects.filter(is_deleted=False).select_related('customer', 'manager')

    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    queryset = _scoped_queryset(queryset, request.user, 'projects')
    columns = _visible_columns(EXPORT_COLUMNS['project'], request.user, 'projects', 'project')
    return ExcelExportService.export_queryset(queryset, columns, 'projects', '项目列表')


@api_view(['GET'])
@permission_classes([module_menu_permission('sales')])
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

    queryset = _scoped_queryset(queryset, request.user, 'sales')
    columns = _visible_columns(EXPORT_COLUMNS['sales_order'], request.user, 'sales', 'order')
    return ExcelExportService.export_queryset(queryset, columns, 'sales_orders', '销售订单')


@api_view(['GET'])
@permission_classes([module_menu_permission('purchase')])
def export_purchase_orders(request):
    """Export purchase orders to Excel."""
    from apps.purchase.models import PurchaseOrder

    queryset = PurchaseOrder.objects.filter(is_deleted=False).select_related('supplier', 'project')

    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    queryset = _scoped_queryset(queryset, request.user, 'purchase')
    columns = _visible_columns(EXPORT_COLUMNS['purchase_order'], request.user, 'purchase', 'purchase_order')
    return ExcelExportService.export_queryset(queryset, columns, 'purchase_orders', '采购订单')


@api_view(['GET'])
@permission_classes([module_menu_permission('inventory')])
def export_stock(request):
    """Export stock to Excel."""
    from apps.inventory.models import Stock

    queryset = Stock.objects.select_related('warehouse', 'item')

    warehouse_id = request.query_params.get('warehouse')
    if warehouse_id:
        queryset = queryset.filter(warehouse_id=warehouse_id)

    queryset = _scoped_queryset(queryset, request.user, 'inventory')
    columns = _visible_columns(EXPORT_COLUMNS['stock'], request.user, 'inventory', 'stock')
    return ExcelExportService.export_queryset(queryset, columns, 'stock', '库存列表')


@api_view(['GET'])
@permission_classes([module_menu_permission('finance')])
def export_expenses(request):
    """Export expenses to Excel."""
    from apps.finance.models import Expense

    queryset = Expense.objects.filter(is_deleted=False).select_related('user', 'project')

    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    queryset = _scoped_queryset(queryset, request.user, 'finance')
    columns = _visible_columns(EXPORT_COLUMNS['expense'], request.user, 'finance', 'expense')
    return ExcelExportService.export_queryset(queryset, columns, 'expenses', '费用报销')


@api_view(['GET'])
@permission_classes([module_menu_permission('finance')])
def export_ar(request):
    """Export accounts receivable to Excel."""
    from apps.finance.models import AccountReceivable

    queryset = AccountReceivable.objects.filter(is_deleted=False).select_related('customer', 'so', 'project')

    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    customer_id = request.query_params.get('customer')
    if customer_id:
        queryset = queryset.filter(customer_id=customer_id)

    queryset = _scoped_queryset(queryset, request.user, 'finance')
    columns = _visible_columns(EXPORT_COLUMNS['ar'], request.user, 'finance', 'receivable')
    return ExcelExportService.export_queryset(queryset, columns, 'accounts_receivable', '应收账款')


@api_view(['GET'])
@permission_classes([module_menu_permission('finance')])
def export_ap(request):
    """Export accounts payable to Excel."""
    from apps.finance.models import AccountPayable

    queryset = AccountPayable.objects.filter(is_deleted=False).select_related('supplier')

    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    queryset = _scoped_queryset(queryset, request.user, 'finance')
    columns = _visible_columns(EXPORT_COLUMNS['ap'], request.user, 'finance', 'payable')
    return ExcelExportService.export_queryset(queryset, columns, 'accounts_payable', '应付账款')


@api_view(['GET'])
@permission_classes([module_menu_permission('finance')])
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

    return ExcelExportService.export_queryset(df.to_dict('records'), columns, 'project_profit_report', '项目利润报表')
