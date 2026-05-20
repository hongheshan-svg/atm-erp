"""
Bug跟踪系统视图
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin

from .bug_models import Bug, BugAttachment, BugComment, BugHistory
from .bug_serializers import (
    BugAttachmentSerializer,
    BugCommentSerializer,
    BugCreateUpdateSerializer,
    BugDetailSerializer,
    BugHistorySerializer,
    BugListSerializer,
)


class BugViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """
    Bug管理视图集
    """

    queryset = Bug.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project', 'task', 'status', 'severity', 'priority', 'bug_type', 'assignee', 'reporter']
    search_fields = ['bug_number', 'title', 'description', 'module']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'severity', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return BugListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return BugCreateUpdateSerializer
        return BugDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # 支持多状态筛选
        statuses = self.request.query_params.get('statuses')
        if statuses:
            status_list = statuses.split(',')
            queryset = queryset.filter(status__in=status_list)

        # 支持"我的Bug"筛选
        my_bugs = self.request.query_params.get('my_bugs')
        if my_bugs == 'assigned':
            queryset = queryset.filter(assignee=self.request.user)
        elif my_bugs == 'reported':
            queryset = queryset.filter(reporter=self.request.user)
        elif my_bugs == 'all':
            queryset = queryset.filter(Q(assignee=self.request.user) | Q(reporter=self.request.user))

        return queryset

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取Bug统计信息"""
        project_id = request.query_params.get('project')
        queryset = self.get_queryset()

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        today = timezone.now().date()

        # 按状态统计
        by_status = dict(queryset.values('status').annotate(count=Count('id')).values_list('status', 'count'))

        # 按严重程度统计
        by_severity = dict(queryset.values('severity').annotate(count=Count('id')).values_list('severity', 'count'))

        # 按优先级统计
        by_priority = dict(queryset.values('priority').annotate(count=Count('id')).values_list('priority', 'count'))

        # 开放和关闭数量
        open_statuses = ['NEW', 'CONFIRMED', 'IN_PROGRESS', 'REOPENED']
        closed_statuses = ['CLOSED', 'RESOLVED', 'CANNOT_REPRODUCE', 'BY_DESIGN', 'DUPLICATE']

        stats = {
            'total': queryset.count(),
            'by_status': by_status,
            'by_severity': by_severity,
            'by_priority': by_priority,
            'open_count': queryset.filter(status__in=open_statuses).count(),
            'closed_count': queryset.filter(status__in=closed_statuses).count(),
            'resolved_today': queryset.filter(resolved_at__date=today).count(),
            'created_today': queryset.filter(created_at__date=today).count(),
        }

        return Response(stats)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """获取Bug趋势数据（最近30天）"""
        project_id = request.query_params.get('project')
        days = int(request.query_params.get('days', 30))

        queryset = self.get_queryset()
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        today = timezone.now().date()
        start_date = today - timedelta(days=days)

        # 按日期统计新建和解决的Bug
        trend_data = []
        for i in range(days + 1):
            date = start_date + timedelta(days=i)
            created = queryset.filter(created_at__date=date).count()
            resolved = queryset.filter(resolved_at__date=date).count()
            trend_data.append({'date': date.isoformat(), 'created': created, 'resolved': resolved})

        return Response(trend_data)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """分配Bug给处理人"""
        bug = self.get_object()
        assignee_id = request.data.get('assignee')

        if not assignee_id:
            return Response({'error': '请指定处理人'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.models import User

        try:
            assignee = User.objects.get(id=assignee_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=status.HTTP_400_BAD_REQUEST)

        old_assignee = bug.assignee
        bug.assignee = assignee

        # 如果是新建状态，改为已确认
        if bug.status == 'NEW':
            bug.status = 'CONFIRMED'

        bug.save()

        # 记录变更
        BugHistory.objects.create(
            bug=bug,
            user=request.user,
            field_name='assignee',
            field_label='处理人',
            old_value=f'{old_assignee.last_name}{old_assignee.first_name}' if old_assignee else '未分配',
            new_value=f'{assignee.last_name}{assignee.first_name}',
        )

        return Response(BugDetailSerializer(bug).data)

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """变更Bug状态"""
        bug = self.get_object()
        new_status = request.data.get('status')
        resolution = request.data.get('resolution', '')
        solution = request.data.get('solution', '')

        if not new_status:
            return Response({'error': '请指定状态'}, status=status.HTTP_400_BAD_REQUEST)

        valid_statuses = [s[0] for s in Bug.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response({'error': '无效的状态'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = bug.status
        bug.status = new_status

        # 解决时需要填写解决方式
        if new_status == 'RESOLVED':
            if not resolution:
                return Response({'error': '请填写解决方式'}, status=status.HTTP_400_BAD_REQUEST)
            bug.resolution = resolution
            bug.solution = solution
            bug.resolved_at = timezone.now()

        # 关闭时间
        if new_status == 'CLOSED':
            bug.closed_at = timezone.now()

        bug.save()

        # 记录变更
        old_display = dict(Bug.STATUS_CHOICES).get(old_status, old_status)
        new_display = dict(Bug.STATUS_CHOICES).get(new_status, new_status)

        BugHistory.objects.create(
            bug=bug,
            user=request.user,
            field_name='status',
            field_label='状态',
            old_value=old_display,
            new_value=new_display,
        )

        return Response(BugDetailSerializer(bug).data)

    @action(detail=True, methods=['get', 'post'])
    def comments(self, request, pk=None):
        """获取或添加评论"""
        bug = self.get_object()

        if request.method == 'GET':
            comments = bug.comments.all()
            serializer = BugCommentSerializer(comments, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = BugCommentSerializer(
                data={'bug': bug.id, 'content': request.data.get('content', '')}, context={'request': request}
            )

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'], parser_classes=[MultiPartParser, FormParser])
    def attachments(self, request, pk=None):
        """获取或上传附件"""
        bug = self.get_object()

        if request.method == 'GET':
            attachments = bug.attachments.all()
            serializer = BugAttachmentSerializer(attachments, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            file = request.FILES.get('file')
            if not file:
                return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

            attachment = BugAttachment.objects.create(
                bug=bug, file=file, filename=file.name, file_size=file.size, uploaded_by=request.user
            )

            serializer = BugAttachmentSerializer(attachment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def histories(self, request, pk=None):
        """获取变更历史"""
        bug = self.get_object()
        histories = bug.histories.all()
        serializer = BugHistorySerializer(histories, many=True)
        return Response(serializer.data)


class BugCommentViewSet(viewsets.ModelViewSet):
    """
    Bug评论视图集
    """

    queryset = BugComment.objects.all()
    serializer_class = BugCommentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['bug']
    ordering = ['created_at']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """只能删除自己的评论"""
        comment = self.get_object()
        if comment.user != request.user and not request.user.is_staff:
            return Response({'error': '只能删除自己的评论'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class BugAttachmentViewSet(viewsets.ModelViewSet):
    """
    Bug附件视图集
    """

    queryset = BugAttachment.objects.all()
    serializer_class = BugAttachmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['bug']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        file = self.request.FILES.get('file')
        if file:
            serializer.save(uploaded_by=self.request.user, file_size=file.size, filename=file.name)
        else:
            serializer.save(uploaded_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """只能删除自己上传的附件"""
        attachment = self.get_object()
        if attachment.uploaded_by != request.user and not request.user.is_staff:
            return Response({'error': '只能删除自己上传的附件'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)
