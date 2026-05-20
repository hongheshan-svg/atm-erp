"""
销售漏斗分析
Sales Funnel Analysis
商机转化分析、阶段转化率等
"""

from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class SalesFunnelView(APIView):
    """销售漏斗分析API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取销售漏斗数据"""
        from apps.sales.crm_models import Lead, Opportunity
        from apps.sales.models import SalesOrder, SalesQuotation

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        salesperson_id = request.query_params.get('salesperson_id')

        # 默认近30天
        if not end_date:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end_date)

        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = date.fromisoformat(start_date)

        # 构建过滤条件
        base_filter = Q(created_at__date__gte=start_date, created_at__date__lte=end_date)

        if salesperson_id:
            base_filter &= Q(salesperson_id=salesperson_id)

        # 统计各阶段数量和金额
        funnel_data = []

        # 1. 线索阶段
        leads = Lead.objects.filter(base_filter, is_deleted=False)
        lead_count = leads.count()
        # Lead模型没有金额字段，使用0
        lead_amount = 0
        funnel_data.append(
            {
                'stage': 'LEAD',
                'stage_name': '线索',
                'count': lead_count,
                'amount': float(lead_amount),
                'conversion_rate': 100,
            }
        )

        # 2. 商机阶段
        opportunities = Opportunity.objects.filter(base_filter, is_deleted=False)
        opp_count = opportunities.count()
        opp_amount = opportunities.aggregate(total=Sum('estimated_amount'))['total'] or 0
        opp_conversion = round(opp_count / lead_count * 100, 1) if lead_count > 0 else 0
        funnel_data.append(
            {
                'stage': 'OPPORTUNITY',
                'stage_name': '商机',
                'count': opp_count,
                'amount': float(opp_amount),
                'conversion_rate': opp_conversion,
            }
        )

        # 3. 报价阶段
        quotations = SalesQuotation.objects.filter(
            created_at__date__gte=start_date, created_at__date__lte=end_date, is_deleted=False
        )
        if salesperson_id:
            quotations = quotations.filter(created_by_id=salesperson_id)

        quote_count = quotations.count()
        quote_amount = quotations.aggregate(total=Sum('total_amount'))['total'] or 0
        quote_conversion = round(quote_count / opp_count * 100, 1) if opp_count > 0 else 0
        funnel_data.append(
            {
                'stage': 'QUOTATION',
                'stage_name': '报价',
                'count': quote_count,
                'amount': float(quote_amount),
                'conversion_rate': quote_conversion,
            }
        )

        # 4. 订单阶段
        orders = SalesOrder.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status__in=['CONFIRMED', 'DELIVERED', 'COMPLETED'],
            is_deleted=False,
        )
        if salesperson_id:
            orders = orders.filter(created_by_id=salesperson_id)

        order_count = orders.count()
        order_amount = orders.aggregate(total=Sum('total_amount'))['total'] or 0
        order_conversion = round(order_count / quote_count * 100, 1) if quote_count > 0 else 0
        funnel_data.append(
            {
                'stage': 'ORDER',
                'stage_name': '成交',
                'count': order_count,
                'amount': float(order_amount),
                'conversion_rate': order_conversion,
            }
        )

        # 计算整体转化率
        overall_conversion = round(order_count / lead_count * 100, 2) if lead_count > 0 else 0

        return Response(
            {
                'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'funnel': funnel_data,
                'overall_conversion': overall_conversion,
                'total_leads': lead_count,
                'total_orders': order_count,
                'total_order_amount': float(order_amount),
            }
        )


class OpportunityStageAnalysisView(APIView):
    """商机阶段分析API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """按阶段分析商机"""
        from apps.sales.crm_models import Opportunity

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not end_date:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end_date)

        if not start_date:
            start_date = end_date - timedelta(days=90)
        else:
            start_date = date.fromisoformat(start_date)

        # 商机阶段定义
        stages = [
            ('QUALIFICATION', '初步接洽'),
            ('NEEDS_ANALYSIS', '需求分析'),
            ('PROPOSAL', '方案报价'),
            ('NEGOTIATION', '商务谈判'),
            ('CLOSED_WON', '成交'),
            ('CLOSED_LOST', '失败'),
        ]

        stage_data = []
        total_count = 0
        total_amount = 0

        for stage_code, stage_name in stages:
            opps = Opportunity.objects.filter(
                stage=stage_code, created_at__date__gte=start_date, created_at__date__lte=end_date, is_deleted=False
            )

            count = opps.count()
            amount = opps.aggregate(total=Sum('estimated_amount'))['total'] or 0
            # days_in_stage 字段可能不存在，使用默认值
            avg_days = 0

            stage_data.append(
                {
                    'stage': stage_code,
                    'stage_name': stage_name,
                    'count': count,
                    'amount': float(amount),
                    'avg_days': round(float(avg_days), 1),
                }
            )

            if stage_code not in ['CLOSED_WON', 'CLOSED_LOST']:
                total_count += count
                total_amount += float(amount)

        # 计算赢单率
        won_count = next((s['count'] for s in stage_data if s['stage'] == 'CLOSED_WON'), 0)
        lost_count = next((s['count'] for s in stage_data if s['stage'] == 'CLOSED_LOST'), 0)
        closed_count = won_count + lost_count
        win_rate = round(won_count / closed_count * 100, 1) if closed_count > 0 else 0

        return Response(
            {
                'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'stages': stage_data,
                'pipeline': {'count': total_count, 'amount': total_amount},
                'win_rate': win_rate,
            }
        )


class SalesTrendView(APIView):
    """销售趋势分析API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取销售趋势"""
        from apps.sales.models import SalesOrder

        period = request.query_params.get('period', 'month')  # day, week, month
        months = int(request.query_params.get('months', 12))

        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)

        orders = SalesOrder.objects.filter(
            order_date__gte=start_date,
            order_date__lte=end_date,
            status__in=['CONFIRMED', 'DELIVERED', 'COMPLETED'],
            is_deleted=False,
        )

        if period == 'day':
            trunc_func = TruncDate('order_date')
        elif period == 'week':
            trunc_func = TruncWeek('order_date')
        else:
            trunc_func = TruncMonth('order_date')

        trend = (
            orders.annotate(period=trunc_func)
            .values('period')
            .annotate(count=Count('id'), amount=Sum('total_amount'))
            .order_by('period')
        )

        return Response(
            {
                'period_type': period,
                'trend': [
                    {
                        'date': item['period'].isoformat() if item['period'] else None,
                        'count': item['count'],
                        'amount': float(item['amount']) if item['amount'] else 0,
                    }
                    for item in trend
                ],
            }
        )


class SalespersonRankingView(APIView):
    """销售人员排名API"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取销售人员排名"""
        from apps.sales.models import SalesOrder

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not end_date:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end_date)

        if not start_date:
            start_date = date(end_date.year, end_date.month, 1)  # 本月开始
        else:
            start_date = date.fromisoformat(start_date)

        # 按销售人员统计
        ranking = (
            SalesOrder.objects.filter(
                order_date__gte=start_date,
                order_date__lte=end_date,
                status__in=['CONFIRMED', 'DELIVERED', 'COMPLETED'],
                is_deleted=False,
            )
            .values('created_by__id', 'created_by__first_name', 'created_by__last_name', 'created_by__username')
            .annotate(order_count=Count('id'), total_amount=Sum('total_amount'))
            .order_by('-total_amount')
        )

        return Response(
            {
                'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'ranking': [
                    {
                        'rank': idx + 1,
                        'user_id': item['created_by__id'],
                        'name': f"{item['created_by__last_name'] or ''}{item['created_by__first_name'] or ''}"
                        or item['created_by__username'],
                        'order_count': item['order_count'],
                        'total_amount': float(item['total_amount']) if item['total_amount'] else 0,
                    }
                    for idx, item in enumerate(ranking)
                ],
            }
        )
