"""
生产管理模块视图
"""
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin

from .models import (
    DebugCheckItem,
    DebugRecord,
    InspectionItem,
    ProductionLog,
    ProductionPlan,
    ProductionPlanProcess,
    ProductionProcess,
    QualityInspection,
)
from .serializers import (
    DebugCheckItemSerializer,
    DebugRecordSerializer,
    InspectionItemSerializer,
    ProductionLogSerializer,
    ProductionPlanProcessSerializer,
    ProductionPlanSerializer,
    ProductionProcessSerializer,
    QualityInspectionSerializer,
)


class ProductionProcessViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    生产工序管理 ViewSet
    """
    queryset = ProductionProcess.objects.all()
    serializer_class = ProductionProcessSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'process_type', 'assignee', 'is_deleted']
    search_fields = ['process_no', 'name', 'description']
    ordering_fields = ['sequence', 'created_at']
    ordering = ['project', 'sequence']

    def get_queryset(self):
        queryset = super().get_queryset()
        # 默认只返回未删除的
        if not self.request.query_params.get('include_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset

    @action(detail=False, methods=['get'])
    def by_project(self, request):
        """按项目获取工序列表"""
        project_id = request.query_params.get('project_id')
        if not project_id:
            return Response({'error': '请提供项目ID'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(project_id=project_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新工序进度"""
        process = self.get_object()
        actual_hours = request.data.get('actual_hours')

        if actual_hours is not None:
            process.actual_hours = actual_hours
            process.save()

        serializer = self.get_serializer(process)
        return Response(serializer.data)


class ProductionPlanViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    生产计划管理 ViewSet
    """
    queryset = ProductionPlan.objects.all()
    serializer_class = ProductionPlanSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'status', 'planner', 'production_manager', 'is_deleted']
    search_fields = ['plan_no', 'title', 'description']
    ordering_fields = ['planned_start', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.query_params.get('include_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认生产计划"""
        plan = self.get_object()
        if plan.status != 'DRAFT':
            return Response({'error': '只有草稿状态的计划可以确认'}, status=status.HTTP_400_BAD_REQUEST)

        plan.status = 'CONFIRMED'
        plan.save()
        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始生产"""
        plan = self.get_object()
        if plan.status not in ['CONFIRMED', 'DRAFT']:
            return Response({'error': '计划状态不允许开始'}, status=status.HTTP_400_BAD_REQUEST)

        plan.status = 'IN_PROGRESS'
        plan.actual_start = timezone.now().date()
        plan.save()
        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成生产"""
        plan = self.get_object()
        if plan.status != 'IN_PROGRESS':
            return Response({'error': '只有生产中的计划可以完成'}, status=status.HTTP_400_BAD_REQUEST)

        plan.status = 'COMPLETED'
        plan.actual_end = timezone.now().date()
        plan.progress_percent = 100
        plan.save()
        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新生产进度"""
        plan = self.get_object()
        progress_percent = request.data.get('progress_percent')

        if progress_percent is not None:
            plan.progress_percent = min(max(int(progress_percent), 0), 100)
            plan.save()

        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_processes(self, request, pk=None):
        """批量添加计划工序"""
        plan = self.get_object()
        process_ids = request.data.get('process_ids', [])

        if not process_ids:
            return Response({'error': '请提供工序ID列表'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for process_id in process_ids:
            try:
                process = ProductionProcess.objects.get(id=process_id, project=plan.project)
                plan_process, is_new = ProductionPlanProcess.objects.get_or_create(
                    plan=plan,
                    process=process,
                    defaults={
                        'planned_start': plan.planned_start,
                        'planned_end': plan.planned_end,
                        'planned_hours': process.planned_hours,
                    }
                )
                if is_new:
                    created.append(plan_process.id)
            except ProductionProcess.DoesNotExist:
                pass

        serializer = self.get_serializer(plan)
        return Response({
            'plan': serializer.data,
            'created_count': len(created)
        })


class ProductionPlanProcessViewSet(UserTrackingMixin, viewsets.ModelViewSet):
    """
    生产计划工序管理 ViewSet
    """
    queryset = ProductionPlanProcess.objects.all()
    serializer_class = ProductionPlanProcessSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['plan', 'process', 'status', 'operator']
    search_fields = ['process__name']
    ordering_fields = ['planned_start', 'process__sequence']
    ordering = ['plan', 'process__sequence']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始工序"""
        plan_process = self.get_object()
        if plan_process.status not in ['PENDING']:
            return Response({'error': '工序已开始或已完成'}, status=status.HTTP_400_BAD_REQUEST)

        plan_process.status = 'IN_PROGRESS'
        plan_process.actual_start = timezone.now()
        plan_process.save()
        serializer = self.get_serializer(plan_process)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成工序"""
        plan_process = self.get_object()
        if plan_process.status != 'IN_PROGRESS':
            return Response({'error': '工序未开始或已完成'}, status=status.HTTP_400_BAD_REQUEST)

        plan_process.status = 'COMPLETED'
        plan_process.actual_end = timezone.now()
        plan_process.progress_percent = 100
        plan_process.save()

        # 更新计划总进度
        self._update_plan_progress(plan_process.plan)

        serializer = self.get_serializer(plan_process)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新工序进度"""
        plan_process = self.get_object()
        progress_percent = request.data.get('progress_percent')
        actual_hours = request.data.get('actual_hours')

        if progress_percent is not None:
            plan_process.progress_percent = min(max(int(progress_percent), 0), 100)
        if actual_hours is not None:
            plan_process.actual_hours = actual_hours

        plan_process.save()

        # 更新计划总进度
        self._update_plan_progress(plan_process.plan)

        serializer = self.get_serializer(plan_process)
        return Response(serializer.data)

    def _update_plan_progress(self, plan):
        """更新计划总进度"""
        processes = plan.plan_processes.all()
        if processes.exists():
            avg_progress = sum(p.progress_percent for p in processes) / processes.count()
            plan.progress_percent = int(avg_progress)
            plan.save()


class ProductionLogViewSet(UserTrackingMixin, viewsets.ModelViewSet):
    """
    生产日志管理 ViewSet
    """
    queryset = ProductionLog.objects.all()
    serializer_class = ProductionLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['plan_process', 'operator', 'log_date']
    search_fields = ['work_content', 'issues']
    ordering_fields = ['log_date', 'created_at']
    ordering = ['-log_date', '-created_at']

    def perform_create(self, serializer):
        log = serializer.save(operator=self.request.user)

        # 更新工序实际工时和进度
        plan_process = log.plan_process
        total_hours = sum(l.work_hours for l in plan_process.logs.all())
        plan_process.actual_hours = total_hours

        # 更新进度为最新日志的进度
        plan_process.progress_percent = log.progress_percent
        plan_process.save()


class DebugRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    调试记录管理 ViewSet
    """
    queryset = DebugRecord.objects.all()
    serializer_class = DebugRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'debug_type', 'status', 'result', 'debugger', 'is_deleted']
    search_fields = ['record_no', 'title', 'debug_content']
    ordering_fields = ['debug_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.query_params.get('include_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset

    @action(detail=True, methods=['post'])
    def start_debug(self, request, pk=None):
        """开始调试"""
        record = self.get_object()
        if record.status not in ['PENDING']:
            return Response({'error': '调试已开始'}, status=status.HTTP_400_BAD_REQUEST)

        record.status = 'IN_PROGRESS'
        record.debug_date = timezone.now().date()
        record.debugger = request.user
        record.save()
        serializer = self.get_serializer(record)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete_debug(self, request, pk=None):
        """完成调试"""
        record = self.get_object()
        result = request.data.get('result')
        actual_result = request.data.get('actual_result', '')

        if not result:
            return Response({'error': '请提供调试结果'}, status=status.HTTP_400_BAD_REQUEST)

        record.status = 'COMPLETED'
        record.result = result
        record.actual_result = actual_result
        record.completed_at = timezone.now()
        record.save()
        serializer = self.get_serializer(record)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_check_items(self, request, pk=None):
        """批量添加检查项"""
        record = self.get_object()
        items = request.data.get('items', [])

        if not items:
            return Response({'error': '请提供检查项列表'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for idx, item in enumerate(items, 1):
            check_item = DebugCheckItem.objects.create(
                debug_record=record,
                sequence=item.get('sequence', idx),
                item_name=item.get('item_name', ''),
                standard=item.get('standard', ''),
                method=item.get('method', ''),
                result=item.get('result', 'PENDING'),
                actual_value=item.get('actual_value', ''),
                notes=item.get('notes', '')
            )
            created.append(check_item.id)

        serializer = self.get_serializer(record)
        return Response({
            'record': serializer.data,
            'created_count': len(created)
        })

    @action(detail=True, methods=['post'])
    def update_check_items(self, request, pk=None):
        """更新检查项结果"""
        record = self.get_object()
        items = request.data.get('items', [])

        for item_data in items:
            item_id = item_data.get('id')
            if item_id:
                try:
                    item = DebugCheckItem.objects.get(id=item_id, debug_record=record)
                    item.result = item_data.get('result', item.result)
                    item.actual_value = item_data.get('actual_value', item.actual_value)
                    item.notes = item_data.get('notes', item.notes)
                    item.save()
                except DebugCheckItem.DoesNotExist:
                    pass

        serializer = self.get_serializer(record)
        return Response(serializer.data)


class DebugCheckItemViewSet(UserTrackingMixin, viewsets.ModelViewSet):
    """
    调试检查项管理 ViewSet
    """
    queryset = DebugCheckItem.objects.all()
    serializer_class = DebugCheckItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['debug_record', 'result']
    search_fields = ['item_name']
    ordering_fields = ['sequence']
    ordering = ['debug_record', 'sequence']


class QualityInspectionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    质量检验管理 ViewSet
    """
    queryset = QualityInspection.objects.all()
    serializer_class = QualityInspectionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'inspection_type', 'status', 'result', 'inspector', 'is_deleted']
    search_fields = ['inspection_no', 'title', 'conclusion']
    ordering_fields = ['inspection_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.query_params.get('include_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset

    @action(detail=True, methods=['post'])
    def start_inspection(self, request, pk=None):
        """开始检验"""
        inspection = self.get_object()
        if inspection.status != 'PENDING':
            return Response({'error': '检验已开始'}, status=status.HTTP_400_BAD_REQUEST)

        inspection.status = 'IN_PROGRESS'
        inspection.inspection_date = timezone.now().date()
        inspection.inspector = request.user
        inspection.save()
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete_inspection(self, request, pk=None):
        """完成检验"""
        inspection = self.get_object()
        result = request.data.get('result')
        conclusion = request.data.get('conclusion', '')
        treatment = request.data.get('treatment', '')

        if not result:
            return Response({'error': '请提供检验结果'}, status=status.HTTP_400_BAD_REQUEST)

        inspection.status = 'COMPLETED'
        inspection.result = result
        inspection.conclusion = conclusion
        inspection.treatment = treatment

        # 计算合格/不合格数量
        pass_count = inspection.items.filter(result='PASS').count()
        fail_count = inspection.items.filter(result='FAIL').count()
        inspection.pass_qty = pass_count
        inspection.fail_qty = fail_count

        inspection.save()
        serializer = self.get_serializer(inspection)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_items(self, request, pk=None):
        """批量添加检验项"""
        inspection = self.get_object()
        items = request.data.get('items', [])

        if not items:
            return Response({'error': '请提供检验项列表'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for idx, item in enumerate(items, 1):
            insp_item = InspectionItem.objects.create(
                inspection=inspection,
                sequence=item.get('sequence', idx),
                item_name=item.get('item_name', ''),
                standard=item.get('standard', ''),
                method=item.get('method', ''),
                nominal_value=item.get('nominal_value', ''),
                tolerance_upper=item.get('tolerance_upper', ''),
                tolerance_lower=item.get('tolerance_lower', ''),
                actual_value=item.get('actual_value', ''),
                result=item.get('result', 'PENDING'),
                notes=item.get('notes', '')
            )
            created.append(insp_item.id)

        serializer = self.get_serializer(inspection)
        return Response({
            'inspection': serializer.data,
            'created_count': len(created)
        })

    @action(detail=True, methods=['post'])
    def update_items(self, request, pk=None):
        """更新检验项结果"""
        inspection = self.get_object()
        items = request.data.get('items', [])

        for item_data in items:
            item_id = item_data.get('id')
            if item_id:
                try:
                    item = InspectionItem.objects.get(id=item_id, inspection=inspection)
                    item.actual_value = item_data.get('actual_value', item.actual_value)
                    item.result = item_data.get('result', item.result)
                    item.notes = item_data.get('notes', item.notes)
                    item.save()
                except InspectionItem.DoesNotExist:
                    pass

        serializer = self.get_serializer(inspection)
        return Response(serializer.data)


class InspectionItemViewSet(UserTrackingMixin, viewsets.ModelViewSet):
    """
    检验项目管理 ViewSet
    """
    queryset = InspectionItem.objects.all()
    serializer_class = InspectionItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['inspection', 'result']
    search_fields = ['item_name']
    ordering_fields = ['sequence']
    ordering = ['inspection', 'sequence']

