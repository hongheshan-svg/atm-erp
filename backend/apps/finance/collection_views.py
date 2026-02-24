"""
回款计划管理视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.data_permission import DataPermissionMixin

from .collection_models import (
    CollectionPlan, CollectionMilestone, CollectionRecord, CollectionReminder
)
from .collection_serializers import (
    CollectionPlanSerializer, CollectionPlanListSerializer,
    CollectionMilestoneSerializer, CollectionMilestoneListSerializer,
    CollectionRecordSerializer, CollectionReminderSerializer,
    CreateMilestoneSerializer
)


class CollectionPlanViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """回款计划管理"""
    queryset = CollectionPlan.objects.select_related('customer', 'project', 'owner')
    serializer_class = CollectionPlanSerializer
    filterset_fields = ['status', 'customer', 'project', 'owner']
    search_fields = ['plan_no', 'name', 'customer__name', 'project__name']
    ordering_fields = ['created_at', 'total_amount', 'collected_amount']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CollectionPlanListSerializer
        return CollectionPlanSerializer
    
    def perform_create(self, serializer):
        if not serializer.validated_data.get('owner'):
            serializer.save(owner=self.request.user)
        else:
            serializer.save()
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """回款统计"""
        queryset = self.filter_queryset(self.get_queryset())
        today = timezone.now().date()
        
        # 基础统计
        stats = queryset.aggregate(
            total_plans=Count('id'),
            total_amount=Sum('total_amount'),
            collected_amount=Sum('collected_amount')
        )
        
        stats['total_amount'] = float(stats['total_amount'] or 0)
        stats['collected_amount'] = float(stats['collected_amount'] or 0)
        stats['remaining_amount'] = stats['total_amount'] - stats['collected_amount']
        stats['collection_rate'] = round(
            stats['collected_amount'] / stats['total_amount'] * 100, 2
        ) if stats['total_amount'] > 0 else 0
        
        # 逾期统计
        overdue_milestones = CollectionMilestone.objects.filter(
            plan__in=queryset,
            status__in=['PENDING', 'PARTIAL'],
            planned_date__lt=today,
            is_deleted=False
        )
        stats['overdue_count'] = overdue_milestones.count()
        stats['overdue_amount'] = float(
            overdue_milestones.aggregate(
                total=Sum('planned_amount') - Sum('collected_amount')
            )['total'] or 0
        )
        
        # 即将到期（7天内）
        upcoming_milestones = CollectionMilestone.objects.filter(
            plan__in=queryset,
            status__in=['PENDING', 'PARTIAL'],
            planned_date__gte=today,
            planned_date__lte=today + timedelta(days=7),
            is_deleted=False
        )
        stats['upcoming_count'] = upcoming_milestones.count()
        stats['upcoming_amount'] = float(
            upcoming_milestones.aggregate(
                total=Sum('planned_amount') - Sum('collected_amount')
            )['total'] or 0
        )
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """获取逾期回款"""
        today = timezone.now().date()
        
        overdue_milestones = CollectionMilestone.objects.filter(
            status__in=['PENDING', 'PARTIAL'],
            planned_date__lt=today,
            is_deleted=False
        ).select_related('plan', 'plan__customer', 'plan__project').order_by('planned_date')
        
        return Response(CollectionMilestoneListSerializer(overdue_milestones, many=True).data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """获取即将到期回款"""
        today = timezone.now().date()
        days = int(request.query_params.get('days', 30))
        
        upcoming_milestones = CollectionMilestone.objects.filter(
            status__in=['PENDING', 'PARTIAL'],
            planned_date__gte=today,
            planned_date__lte=today + timedelta(days=days),
            is_deleted=False
        ).select_related('plan', 'plan__customer', 'plan__project').order_by('planned_date')
        
        return Response(CollectionMilestoneListSerializer(upcoming_milestones, many=True).data)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认回款计划"""
        plan = self.get_object()
        
        if plan.status != 'DRAFT':
            return Response({'error': '只能确认草稿状态的计划'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not plan.milestones.exists():
            return Response({'error': '请先添加回款节点'}, status=status.HTTP_400_BAD_REQUEST)
        
        plan.status = 'CONFIRMED'
        plan.save()
        
        return Response(CollectionPlanSerializer(plan).data)
    
    @action(detail=True, methods=['post'])
    def add_milestones(self, request, pk=None):
        """批量添加回款节点"""
        plan = self.get_object()
        
        serializer = CreateMilestoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        created = []
        for item in serializer.validated_data['milestones']:
            milestone = CollectionMilestone.objects.create(
                plan=plan,
                milestone_type=item.get('milestone_type', 'OTHER'),
                name=item['name'],
                description=item.get('description', ''),
                percentage=item.get('percentage', 0),
                planned_amount=item['planned_amount'],
                planned_date=item['planned_date'],
                trigger_condition=item.get('trigger_condition', ''),
                created_by=request.user,
                updated_by=request.user
            )
            created.append(milestone)
        
        # 更新计划的计划金额
        plan.planned_amount = plan.milestones.aggregate(Sum('planned_amount'))['planned_amount__sum'] or 0
        plan.save()
        
        return Response(CollectionMilestoneSerializer(created, many=True).data)
    
    @action(detail=True, methods=['post'])
    def create_from_contract(self, request, pk=None):
        """从合同创建标准回款节点"""
        plan = self.get_object()
        
        # 标准节点配置（可配置）
        standard_milestones = [
            {'type': 'ADVANCE', 'name': '预付款', 'percentage': 30},
            {'type': 'DELIVERY', 'name': '发货款', 'percentage': 40},
            {'type': 'ACCEPTANCE', 'name': '验收款', 'percentage': 20},
            {'type': 'WARRANTY', 'name': '质保款', 'percentage': 10},
        ]
        
        # 获取合同/订单日期作为基准
        base_date = request.data.get('base_date') or timezone.now().date()
        if isinstance(base_date, str):
            from datetime import datetime
            base_date = datetime.strptime(base_date, '%Y-%m-%d').date()
        
        # 预估各节点日期间隔（天）
        intervals = {
            'ADVANCE': 0,
            'DELIVERY': 90,
            'ACCEPTANCE': 120,
            'WARRANTY': 480,  # 验收后一年
        }
        
        created = []
        for item in standard_milestones:
            planned_amount = plan.total_amount * item['percentage'] / 100
            planned_date = base_date + timedelta(days=intervals[item['type']])
            
            milestone = CollectionMilestone.objects.create(
                plan=plan,
                milestone_type=item['type'],
                name=item['name'],
                percentage=item['percentage'],
                planned_amount=planned_amount,
                planned_date=planned_date,
                created_by=request.user,
                updated_by=request.user
            )
            created.append(milestone)
        
        plan.planned_amount = plan.total_amount
        plan.save()
        
        return Response(CollectionMilestoneSerializer(created, many=True).data)


class CollectionMilestoneViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """回款节点管理"""
    queryset = CollectionMilestone.objects.select_related('plan', 'plan__customer', 'plan__project')
    serializer_class = CollectionMilestoneSerializer
    filterset_fields = ['plan', 'milestone_type', 'status']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CollectionMilestoneListSerializer
        return CollectionMilestoneSerializer
    
    @action(detail=True, methods=['post'])
    def add_record(self, request, pk=None):
        """添加收款记录"""
        milestone = self.get_object()
        
        record_data = request.data.copy()
        record_data['milestone'] = milestone.id
        
        serializer = CollectionRecordSerializer(data=record_data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        """触发回款条件"""
        milestone = self.get_object()
        
        milestone.is_triggered = True
        milestone.triggered_at = timezone.now()
        milestone.save()
        
        return Response(CollectionMilestoneSerializer(milestone).data)
    
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None):
        """发送回款提醒"""
        milestone = self.get_object()
        
        # 创建提醒记录
        reminder = CollectionReminder.objects.create(
            milestone=milestone,
            reminder_type='DUE' if milestone.is_overdue else 'UPCOMING',
            reminder_date=timezone.now(),
            message=request.data.get('message', f'回款提醒: {milestone.name}'),
            created_by=request.user,
            updated_by=request.user
        )
        
        # 添加接收人
        recipients = request.data.get('recipients', [])
        if not recipients and milestone.plan.owner:
            recipients = [milestone.plan.owner.id]
        reminder.recipients.set(recipients)
        
        # TODO: 实际发送通知（邮件、站内信等）
        reminder.sent = True
        reminder.sent_at = timezone.now()
        reminder.save()
        
        milestone.last_reminder = timezone.now()
        milestone.save()
        
        return Response({'message': '提醒已发送'})


class CollectionRecordViewSet(SoftDeleteMixin, UserTrackingMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """收款记录管理"""
    queryset = CollectionRecord.objects.select_related('milestone', 'milestone__plan')
    serializer_class = CollectionRecordSerializer
    filterset_fields = ['milestone', 'payment_method', 'confirmed']
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认收款"""
        record = self.get_object()
        
        record.confirmed = True
        record.confirmed_by = request.user
        record.confirmed_at = timezone.now()
        record.save()
        
        return Response(CollectionRecordSerializer(record).data)


class CollectionReminderViewSet(SoftDeleteMixin, DataPermissionMixin, viewsets.ModelViewSet):
    """回款提醒管理"""
    queryset = CollectionReminder.objects.select_related('milestone', 'milestone__plan')
    serializer_class = CollectionReminderSerializer
    filterset_fields = ['milestone', 'reminder_type', 'sent']
