"""
CRM - 商机/线索管理视图
"""
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin

from .crm_models import Lead, LeadSource, Opportunity, OpportunityActivity, SalesForecast
from .crm_serializers import (
    LeadConvertSerializer,
    LeadListSerializer,
    LeadSerializer,
    LeadSourceSerializer,
    OpportunityActivitySerializer,
    OpportunityListSerializer,
    OpportunitySerializer,
    OpportunityStageChangeSerializer,
    SalesForecastSerializer,
)


class LeadSourceViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """线索来源管理"""
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceSerializer
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']


class LeadViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """销售线索管理"""
    queryset = Lead.objects.select_related('source', 'owner', 'converted_customer')
    serializer_class = LeadSerializer
    filterset_fields = ['status', 'source', 'owner']
    search_fields = ['lead_no', 'company_name', 'contact_name', 'contact_phone']
    ordering_fields = ['created_at', 'score', 'company_name']

    def get_serializer_class(self):
        if self.action == 'list':
            return LeadListSerializer
        return LeadSerializer

    def perform_create(self, serializer):
        # 如果没有指定负责人，默认为当前用户
        if not serializer.validated_data.get('owner'):
            serializer.save(owner=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """线索统计"""
        queryset = self.filter_queryset(self.get_queryset())

        stats = {
            'total': queryset.count(),
            'by_status': {},
            'by_source': {},
            'conversion_rate': 0
        }

        # 按状态统计
        status_counts = queryset.values('status').annotate(count=Count('id'))
        for item in status_counts:
            stats['by_status'][item['status']] = item['count']

        # 按来源统计
        source_counts = queryset.values('source__name').annotate(count=Count('id'))
        for item in source_counts:
            source_name = item['source__name'] or '未知'
            stats['by_source'][source_name] = item['count']

        # 转化率
        total = stats['total']
        converted = stats['by_status'].get('CONVERTED', 0)
        stats['conversion_rate'] = round(converted / total * 100, 2) if total > 0 else 0

        return Response(stats)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """转化线索为客户和商机"""
        lead = self.get_object()

        if lead.status == 'CONVERTED':
            return Response({'error': '线索已转化'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = LeadConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        customer = None
        opportunity = None

        # 创建或使用已有客户
        if data.get('create_customer', True):
            from apps.masterdata.models import Customer
            customer = Customer.objects.create(
                name=lead.company_name,
                contact_person=lead.contact_name,
                phone=lead.contact_phone,
                email=lead.contact_email,
                address=lead.address,
                website=lead.website,
                industry=lead.industry,
                created_by=request.user,
                updated_by=request.user
            )
        elif data.get('customer_id'):
            from apps.masterdata.models import Customer
            customer = Customer.objects.get(id=data['customer_id'])

        # 创建商机
        if data.get('create_opportunity', True) and customer:
            opportunity = Opportunity.objects.create(
                name=data.get('opportunity_name', f"{lead.company_name}商机"),
                customer=customer,
                contact_name=lead.contact_name,
                contact_phone=lead.contact_phone,
                requirement=lead.requirement,
                estimated_amount=data.get('estimated_amount', 0),
                owner=lead.owner or request.user,
                created_by=request.user,
                updated_by=request.user
            )

        # 更新线索状态
        lead.status = 'CONVERTED'
        lead.converted_customer = customer
        lead.converted_opportunity = opportunity
        lead.converted_at = timezone.now()
        lead.save()

        return Response({
            'message': '线索转化成功',
            'customer_id': customer.id if customer else None,
            'opportunity_id': opportunity.id if opportunity else None
        })

    @action(detail=True, methods=['post'])
    def disqualify(self, request, pk=None):
        """作废线索"""
        lead = self.get_object()
        lead.status = 'DISQUALIFIED'
        lead.notes = request.data.get('reason', '') + '\n' + lead.notes
        lead.save()

        return Response(LeadSerializer(lead).data)


class OpportunityViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """销售商机管理"""
    queryset = Opportunity.objects.select_related('customer', 'owner')
    serializer_class = OpportunitySerializer
    filterset_fields = ['stage', 'priority', 'customer', 'owner']
    search_fields = ['opportunity_no', 'name', 'customer__name']
    ordering_fields = ['created_at', 'estimated_amount', 'expected_close_date']

    def get_serializer_class(self):
        if self.action == 'list':
            return OpportunityListSerializer
        return OpportunitySerializer

    def perform_create(self, serializer):
        if not serializer.validated_data.get('owner'):
            serializer.save(owner=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """商机统计"""
        queryset = self.filter_queryset(self.get_queryset())

        stats = {
            'total': queryset.count(),
            'total_amount': float(queryset.aggregate(Sum('estimated_amount'))['estimated_amount__sum'] or 0),
            'weighted_amount': float(queryset.aggregate(Sum('weighted_amount'))['weighted_amount__sum'] or 0),
            'by_stage': {},
            'win_rate': 0
        }

        # 按阶段统计
        stage_data = queryset.values('stage').annotate(
            count=Count('id'),
            amount=Sum('estimated_amount'),
            weighted=Sum('weighted_amount')
        )
        for item in stage_data:
            stats['by_stage'][item['stage']] = {
                'count': item['count'],
                'amount': float(item['amount'] or 0),
                'weighted': float(item['weighted'] or 0)
            }

        # 赢单率
        closed = queryset.filter(stage__in=['CLOSED_WON', 'CLOSED_LOST']).count()
        won = queryset.filter(stage='CLOSED_WON').count()
        stats['win_rate'] = round(won / closed * 100, 2) if closed > 0 else 0

        return Response(stats)

    @action(detail=False, methods=['get'])
    def pipeline(self, request):
        """销售漏斗"""
        queryset = self.filter_queryset(self.get_queryset())

        # 排除已关闭的商机
        active_queryset = queryset.exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST'])

        pipeline = []
        stage_order = ['QUALIFICATION', 'NEEDS_ANALYSIS', 'PROPOSAL', 'NEGOTIATION']
        stage_display = {
            'QUALIFICATION': '需求确认',
            'NEEDS_ANALYSIS': '需求分析',
            'PROPOSAL': '方案报价',
            'NEGOTIATION': '商务谈判'
        }

        for stage in stage_order:
            stage_data = active_queryset.filter(stage=stage).aggregate(
                count=Count('id'),
                total_amount=Sum('estimated_amount'),
                weighted_amount=Sum('weighted_amount')
            )
            pipeline.append({
                'stage': stage,
                'stage_display': stage_display[stage],
                'count': stage_data['count'] or 0,
                'total_amount': float(stage_data['total_amount'] or 0),
                'weighted_amount': float(stage_data['weighted_amount'] or 0)
            })

        return Response(pipeline)

    @action(detail=True, methods=['post'])
    def change_stage(self, request, pk=None):
        """变更商机阶段"""
        opportunity = self.get_object()

        serializer = OpportunityStageChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        old_stage = opportunity.stage
        new_stage = data['new_stage']

        opportunity.stage = new_stage

        # 更新概率
        if 'probability' in data:
            opportunity.probability = data['probability']
        else:
            # 默认概率
            default_probability = {
                'QUALIFICATION': 20,
                'NEEDS_ANALYSIS': 40,
                'PROPOSAL': 60,
                'NEGOTIATION': 80,
                'CLOSED_WON': 100,
                'CLOSED_LOST': 0
            }
            opportunity.probability = default_probability.get(new_stage, 50)

        # 处理成单/丢单
        if new_stage == 'CLOSED_WON':
            opportunity.actual_close_date = timezone.now().date()
        elif new_stage == 'CLOSED_LOST':
            opportunity.actual_close_date = timezone.now().date()
            opportunity.lost_reason = data.get('lost_reason', '')

        opportunity.save()

        # 记录活动
        OpportunityActivity.objects.create(
            opportunity=opportunity,
            activity_type='OTHER',
            subject=f'阶段变更: {old_stage} → {new_stage}',
            content=data.get('notes', ''),
            activity_date=timezone.now(),
            recorded_by=request.user,
            created_by=request.user,
            updated_by=request.user
        )

        return Response(OpportunitySerializer(opportunity).data)

    @action(detail=True, methods=['post'])
    def add_activity(self, request, pk=None):
        """添加跟进活动"""
        opportunity = self.get_object()

        activity_data = request.data.copy()
        activity_data['opportunity'] = opportunity.id
        activity_data['recorded_by'] = request.user.id

        serializer = OpportunityActivitySerializer(data=activity_data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def create_quotation(self, request, pk=None):
        """从商机创建报价"""
        opportunity = self.get_object()

        from .models import SalesQuotation

        quotation = SalesQuotation.objects.create(
            customer=opportunity.customer,
            project_name=opportunity.name,
            contact_person=opportunity.contact_name,
            contact_phone=opportunity.contact_phone,
            notes=f'来源商机: {opportunity.opportunity_no}\n{opportunity.requirement}',
            created_by=request.user,
            updated_by=request.user
        )

        return Response({
            'message': '报价单创建成功',
            'quotation_id': quotation.id,
            'quotation_no': quotation.quotation_no
        })


class OpportunityActivityViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """商机活动管理"""
    queryset = OpportunityActivity.objects.select_related('opportunity', 'recorded_by')
    serializer_class = OpportunityActivitySerializer
    filterset_fields = ['opportunity', 'activity_type', 'recorded_by']


class SalesForecastViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """销售预测管理"""
    queryset = SalesForecast.objects.select_related('owner')
    serializer_class = SalesForecastSerializer
    filterset_fields = ['year', 'month', 'owner']

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """预测汇总"""
        year = request.query_params.get('year', timezone.now().year)

        queryset = self.get_queryset().filter(year=year)

        summary = queryset.aggregate(
            total_forecast=Sum('forecast_amount'),
            total_weighted=Sum('weighted_amount'),
            total_actual=Sum('actual_amount'),
            total_opportunities=Sum('opportunity_count'),
            total_won=Sum('won_count'),
            total_lost=Sum('lost_count')
        )

        # 计算达成率
        forecast = summary['total_forecast'] or 0
        actual = summary['total_actual'] or 0
        summary['achievement_rate'] = round(actual / forecast * 100, 2) if forecast > 0 else 0

        # 按月明细
        monthly = list(queryset.values('month').annotate(
            forecast=Sum('forecast_amount'),
            actual=Sum('actual_amount'),
            opportunities=Sum('opportunity_count')
        ).order_by('month'))

        return Response({
            'year': year,
            'summary': summary,
            'monthly': monthly
        })

    @action(detail=False, methods=['post'])
    def recalculate(self, request):
        """重新计算预测"""
        year = request.data.get('year', timezone.now().year)
        month = request.data.get('month', timezone.now().month)

        # 获取该月的所有商机

        opportunities = Opportunity.objects.filter(
            expected_close_date__year=year,
            expected_close_date__month=month,
            is_deleted=False
        ).exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST'])

        # 按销售人员汇总
        from collections import defaultdict
        owner_data = defaultdict(lambda: {'forecast': 0, 'weighted': 0, 'count': 0})

        for opp in opportunities:
            if opp.owner_id:
                owner_data[opp.owner_id]['forecast'] += float(opp.estimated_amount)
                owner_data[opp.owner_id]['weighted'] += float(opp.weighted_amount)
                owner_data[opp.owner_id]['count'] += 1

        # 更新或创建预测记录
        for owner_id, data in owner_data.items():
            SalesForecast.objects.update_or_create(
                year=year,
                month=month,
                owner_id=owner_id,
                defaults={
                    'forecast_amount': data['forecast'],
                    'weighted_amount': data['weighted'],
                    'opportunity_count': data['count'],
                    'updated_by': request.user
                }
            )

        return Response({'message': f'{year}年{month}月预测已更新'})


class CRMDashboardView(viewsets.ViewSet):
    """CRM仪表盘数据"""

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取CRM统计数据"""
        from dateutil.relativedelta import relativedelta

        from apps.masterdata.models import Customer

        today = timezone.now().date()
        month_start = today.replace(day=1)
        last_month_start = month_start - relativedelta(months=1)
        last_month_end = month_start - timezone.timedelta(days=1)

        # 线索统计
        leads_count = Lead.objects.filter(
            is_deleted=False
        ).exclude(status__in=['CONVERTED', 'DISQUALIFIED']).count()

        leads_this_month = Lead.objects.filter(
            is_deleted=False,
            created_at__gte=month_start
        ).count()

        leads_last_month = Lead.objects.filter(
            is_deleted=False,
            created_at__gte=last_month_start,
            created_at__lt=month_start
        ).count()

        leads_trend = 0
        if leads_last_month > 0:
            leads_trend = round((leads_this_month - leads_last_month) / leads_last_month * 100, 1)

        # 商机统计
        active_opportunities = Opportunity.objects.filter(
            is_deleted=False
        ).exclude(stage__in=['CLOSED_WON', 'CLOSED_LOST'])

        opportunities_count = active_opportunities.count()
        opportunities_amount = active_opportunities.aggregate(
            total=Sum('estimated_amount')
        )['total'] or 0

        # 客户统计
        customers_count = Customer.objects.filter(
            is_deleted=False,
            status='ACTIVE'
        ).count()

        new_customers = Customer.objects.filter(
            is_deleted=False,
            created_at__gte=month_start
        ).count()

        # 本月成交
        won_this_month = Opportunity.objects.filter(
            is_deleted=False,
            stage='CLOSED_WON',
            actual_close_date__gte=month_start
        ).aggregate(
            count=Count('id'),
            amount=Sum('estimated_amount')
        )

        return Response({
            'leads_count': leads_count,
            'leads_trend': leads_trend,
            'opportunities_count': opportunities_count,
            'opportunities_amount': float(opportunities_amount),
            'customers_count': customers_count,
            'new_customers': new_customers,
            'won_count': won_this_month['count'] or 0,
            'won_amount': float(won_this_month['amount'] or 0)
        })
