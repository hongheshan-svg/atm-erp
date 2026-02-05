"""
Views for reports app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Q
from io import BytesIO
import pandas as pd
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
    from apps.projects.models import Project
    from apps.sales.models import SalesOrder
    from apps.purchase.models import PurchaseOrder
    from apps.inventory.models import Stock
    from django.db.models import Count, Sum, Q
    
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
def inventory_turnover_report(request):
    """
    Get inventory turnover analysis.
    Query params:
        - warehouse: filter by warehouse
        - category: filter by item category
        - start_date: start date for analysis
        - end_date: end date for analysis
    """
    from apps.inventory.models import Stock, StockMove
    from apps.masterdata.models import Warehouse, ItemCategory
    from django.db.models import Sum, F, Q
    from datetime import datetime, timedelta
    
    warehouse_id = request.query_params.get('warehouse')
    category_id = request.query_params.get('category')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Default to last 30 days
    if not end_date:
        end_date = datetime.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    # Build filters
    stock_filters = Q(is_deleted=False) if hasattr(Stock, 'is_deleted') else Q()
    move_filters = Q(move_date__gte=start_date, move_date__lte=end_date)
    
    if warehouse_id:
        stock_filters &= Q(warehouse_id=warehouse_id)
        move_filters &= Q(warehouse_to_id=warehouse_id) | Q(warehouse_from_id=warehouse_id)
    
    if category_id:
        stock_filters &= Q(item__category_id=category_id)
        move_filters &= Q(item__category_id=category_id)
    
    # Calculate inventory turnover
    stocks = Stock.objects.filter(stock_filters).select_related('item', 'warehouse')
    
    results = []
    for stock in stocks[:100]:  # Limit to 100 items
        # Get outbound moves for this item
        outbound = StockMove.objects.filter(
            move_filters,
            item=stock.item,
            move_type__in=['OUT_SALES', 'OUT_PROJECT']
        ).aggregate(
            total_qty=Sum('qty'),
            total_cost=Sum(F('qty') * F('unit_cost'))
        )
        
        avg_inventory = float(stock.qty_on_hand) * float(stock.weighted_avg_cost)
        outbound_cost = float(outbound['total_cost'] or 0)
        
        turnover_rate = outbound_cost / avg_inventory if avg_inventory > 0 else 0
        days_inventory = 30 / turnover_rate if turnover_rate > 0 else 999
        
        results.append({
            'item_id': stock.item.id,
            'item_sku': stock.item.sku,
            'item_name': stock.item.name,
            'warehouse_name': stock.warehouse.name,
            'qty_on_hand': float(stock.qty_on_hand),
            'inventory_value': avg_inventory,
            'outbound_qty': float(outbound['total_qty'] or 0),
            'outbound_value': outbound_cost,
            'turnover_rate': round(turnover_rate, 2),
            'days_inventory': round(days_inventory, 1)
        })
    
    # Sort by turnover rate
    results.sort(key=lambda x: x['turnover_rate'], reverse=True)
    
    return Response({
        'results': results,
        'summary': {
            'total_items': len(results),
            'avg_turnover_rate': round(sum(r['turnover_rate'] for r in results) / len(results), 2) if results else 0,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def purchase_price_trend_report(request):
    """
    Get purchase price trend analysis.
    Query params:
        - item: filter by item
        - supplier: filter by supplier
        - start_date: start date for analysis
        - end_date: end date for analysis
    """
    from apps.purchase.models import PurchaseOrder, PurchaseOrderLine
    from django.db.models import Avg, Min, Max, F
    from datetime import datetime, timedelta
    
    item_id = request.query_params.get('item')
    supplier_id = request.query_params.get('supplier')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # Default to last 180 days
    if not end_date:
        end_date = datetime.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        start_date = end_date - timedelta(days=180)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    # Build filters - Note: PurchaseOrderLine uses 'po' instead of 'purchase_order'
    filters = Q(po__order_date__gte=start_date, po__order_date__lte=end_date)
    filters &= Q(po__is_deleted=False)
    
    if item_id:
        filters &= Q(item_id=item_id)
    
    if supplier_id:
        filters &= Q(po__supplier_id=supplier_id)
    
    # Get price data
    lines = PurchaseOrderLine.objects.filter(filters).select_related(
        'item', 'po', 'po__supplier'
    ).order_by('po__order_date')
    
    # Group by item
    item_data = {}
    for line in lines:
        item_key = line.item.id
        if item_key not in item_data:
            item_data[item_key] = {
                'item_id': item_key,
                'item_sku': line.item.sku,
                'item_name': line.item.name,
                'prices': [],
                'suppliers': set()
            }
        
        item_data[item_key]['prices'].append({
            'date': line.po.order_date.isoformat(),
            'price': float(line.unit_price),
            'qty': float(line.qty),
            'supplier': line.po.supplier.name if line.po.supplier else '',
            'order_no': line.po.order_no  # 添加采购订单号
        })
        if line.po.supplier:
            item_data[item_key]['suppliers'].add(line.po.supplier.name)
    
    # Calculate statistics
    results = []
    for item_id, data in item_data.items():
        prices = [p['price'] for p in data['prices']]
        if prices:
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            price_change = prices[-1] - prices[0] if len(prices) > 1 else 0
            price_change_pct = (price_change / prices[0] * 100) if prices[0] > 0 else 0
            
            results.append({
                'item_id': data['item_id'],
                'item_sku': data['item_sku'],
                'item_name': data['item_name'],
                'avg_price': round(avg_price, 2),
                'min_price': round(min_price, 2),
                'max_price': round(max_price, 2),
                'price_change': round(price_change, 2),
                'price_change_pct': round(price_change_pct, 2),
                'order_count': len(data['prices']),
                'supplier_count': len(data['suppliers']),
                'trend_data': data['prices']
            })
    
    return Response({
        'results': results,
        'period_start': start_date.isoformat(),
        'period_end': end_date.isoformat()
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
    from apps.finance.models import AccountReceivable, AccountPayable
    from datetime import datetime, timedelta
    
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

