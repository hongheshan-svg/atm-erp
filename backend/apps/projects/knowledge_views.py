"""
知识库视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin

from .knowledge_models import (
    KnowledgeCategory, KnowledgeArticle, ProjectArchive,
    TechnicalIssue, StandardComponent
)
from .knowledge_serializers import (
    KnowledgeCategorySerializer, KnowledgeCategoryTreeSerializer,
    KnowledgeArticleSerializer, KnowledgeArticleListSerializer,
    ProjectArchiveSerializer, TechnicalIssueSerializer,
    TechnicalIssueListSerializer, StandardComponentSerializer,
    StandardComponentListSerializer
)


class KnowledgeCategoryViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """知识分类管理"""
    queryset = KnowledgeCategory.objects.all()
    serializer_class = KnowledgeCategorySerializer
    filterset_fields = ['parent']
    search_fields = ['code', 'name']
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取树形结构"""
        root_categories = self.get_queryset().filter(
            parent__isnull=True,
            is_deleted=False
        ).order_by('sort_order', 'code')
        
        return Response(KnowledgeCategoryTreeSerializer(root_categories, many=True).data)


class KnowledgeArticleViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """知识文章管理"""
    queryset = KnowledgeArticle.objects.select_related('category', 'project', 'author')
    serializer_class = KnowledgeArticleSerializer
    filterset_fields = ['category', 'article_type', 'status', 'author', 'project']
    search_fields = ['title', 'summary', 'content', 'tags']
    ordering_fields = ['created_at', 'published_at', 'view_count', 'like_count']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return KnowledgeArticleListSerializer
        return KnowledgeArticleSerializer
    
    def perform_create(self, serializer):
        if not serializer.validated_data.get('author'):
            serializer.save(author=self.request.user)
        else:
            serializer.save()
    
    def retrieve(self, request, *args, **kwargs):
        """获取详情时增加浏览次数"""
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """知识库统计"""
        queryset = self.get_queryset().filter(is_deleted=False)
        
        stats = {
            'total': queryset.count(),
            'published': queryset.filter(status='PUBLISHED').count(),
            'draft': queryset.filter(status='DRAFT').count(),
            'by_type': {},
            'by_category': {},
            'top_viewed': [],
            'recent': []
        }
        
        # 按类型统计
        type_counts = queryset.values('article_type').annotate(count=Count('id'))
        for item in type_counts:
            stats['by_type'][item['article_type']] = item['count']
        
        # 按分类统计
        category_counts = queryset.values('category__name').annotate(count=Count('id'))
        for item in category_counts:
            cat_name = item['category__name'] or '未分类'
            stats['by_category'][cat_name] = item['count']
        
        # 热门文章
        top_articles = queryset.filter(status='PUBLISHED').order_by('-view_count')[:5]
        stats['top_viewed'] = KnowledgeArticleListSerializer(top_articles, many=True).data
        
        # 最新文章
        recent_articles = queryset.filter(status='PUBLISHED').order_by('-published_at')[:5]
        stats['recent'] = KnowledgeArticleListSerializer(recent_articles, many=True).data
        
        return Response(stats)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """发布文章"""
        article = self.get_object()
        article.status = 'PUBLISHED'
        article.published_at = timezone.now()
        article.save()
        
        return Response(KnowledgeArticleSerializer(article).data)
    
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """点赞"""
        article = self.get_object()
        article.like_count += 1
        article.save(update_fields=['like_count'])
        
        return Response({'like_count': article.like_count})
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """全文搜索"""
        keyword = request.query_params.get('q', '')
        if not keyword:
            return Response([])
        
        results = self.get_queryset().filter(
            Q(title__icontains=keyword) |
            Q(summary__icontains=keyword) |
            Q(content__icontains=keyword) |
            Q(tags__contains=[keyword]),
            status='PUBLISHED',
            is_deleted=False
        ).order_by('-view_count')[:20]
        
        return Response(KnowledgeArticleListSerializer(results, many=True).data)


class ProjectArchiveViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """项目归档报告管理"""
    queryset = ProjectArchive.objects.select_related('project', 'reviewer')
    serializer_class = ProjectArchiveSerializer
    filterset_fields = ['status', 'project']
    search_fields = ['project__name', 'project__project_no']
    
    @action(detail=True, methods=['post'])
    def submit_review(self, request, pk=None):
        """提交审核"""
        archive = self.get_object()
        
        if archive.status != 'DRAFT':
            return Response({'error': '只能提交草稿状态的报告'}, status=status.HTTP_400_BAD_REQUEST)
        
        archive.status = 'REVIEW'
        archive.save()
        
        return Response(ProjectArchiveSerializer(archive).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过"""
        archive = self.get_object()
        
        if archive.status != 'REVIEW':
            return Response({'error': '只能审核待审核的报告'}, status=status.HTTP_400_BAD_REQUEST)
        
        archive.status = 'APPROVED'
        archive.reviewer = request.user
        archive.reviewed_at = timezone.now()
        archive.review_comments = request.data.get('comments', '')
        archive.save()
        
        # 更新项目状态为已归档
        project = archive.project
        project.status = 'ARCHIVED'
        project.save()
        
        return Response(ProjectArchiveSerializer(archive).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审核驳回"""
        archive = self.get_object()
        
        if archive.status != 'REVIEW':
            return Response({'error': '只能审核待审核的报告'}, status=status.HTTP_400_BAD_REQUEST)
        
        archive.status = 'REJECTED'
        archive.reviewer = request.user
        archive.reviewed_at = timezone.now()
        archive.review_comments = request.data.get('comments', '')
        archive.save()
        
        return Response(ProjectArchiveSerializer(archive).data)
    
    @action(detail=True, methods=['post'])
    def generate_knowledge(self, request, pk=None):
        """从归档报告生成知识文章"""
        archive = self.get_object()
        
        # 生成技术总结文章
        if archive.technical_challenges and archive.solutions_applied:
            article = KnowledgeArticle.objects.create(
                title=f"{archive.project.name} - 技术总结",
                article_type='SOLUTION',
                summary=f"项目{archive.project.name}的技术难点和解决方案",
                content=f"## 技术难点\n{archive.technical_challenges}\n\n## 解决方案\n{archive.solutions_applied}\n\n## 技术创新\n{archive.innovations}",
                project=archive.project,
                author=request.user,
                status='DRAFT',
                created_by=request.user,
                updated_by=request.user
            )
            
            return Response({
                'message': '知识文章已创建',
                'article_id': article.id
            })
        
        return Response({'error': '归档报告缺少技术总结内容'}, status=status.HTTP_400_BAD_REQUEST)


class TechnicalIssueViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """技术问题记录管理"""
    queryset = TechnicalIssue.objects.select_related('project', 'category', 'reported_by', 'resolved_by')
    serializer_class = TechnicalIssueSerializer
    filterset_fields = ['project', 'category', 'severity', 'status']
    search_fields = ['title', 'description', 'solution', 'tags']
    ordering_fields = ['created_at', 'occurred_at', 'severity']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TechnicalIssueListSerializer
        return TechnicalIssueSerializer
    
    def perform_create(self, serializer):
        if not serializer.validated_data.get('reported_by'):
            serializer.save(reported_by=self.request.user, occurred_at=timezone.now())
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决问题"""
        issue = self.get_object()
        
        issue.status = 'RESOLVED'
        issue.solution = request.data.get('solution', issue.solution)
        issue.prevention = request.data.get('prevention', issue.prevention)
        issue.resolved_by = request.user
        issue.resolved_at = timezone.now()
        
        if issue.occurred_at:
            delta = timezone.now() - issue.occurred_at
            issue.resolution_hours = delta.total_seconds() / 3600
        
        issue.save()
        
        return Response(TechnicalIssueSerializer(issue).data)
    
    @action(detail=True, methods=['post'])
    def convert_to_knowledge(self, request, pk=None):
        """转换为知识文章"""
        issue = self.get_object()
        
        if issue.status != 'RESOLVED':
            return Response({'error': '只能将已解决的问题转为知识文章'}, status=status.HTTP_400_BAD_REQUEST)
        
        article = KnowledgeArticle.objects.create(
            title=issue.title,
            category=issue.category,
            article_type='SOLUTION',
            summary=issue.description[:200] if len(issue.description) > 200 else issue.description,
            content=f"## 问题描述\n{issue.description}\n\n## 问题现象\n{issue.symptoms}\n\n## 根本原因\n{issue.root_cause}\n\n## 解决方案\n{issue.solution}\n\n## 预防措施\n{issue.prevention}",
            project=issue.project,
            author=request.user,
            tags=issue.tags,
            status='DRAFT',
            created_by=request.user,
            updated_by=request.user
        )
        
        issue.knowledge_article = article
        issue.status = 'CLOSED'
        issue.save()
        
        return Response({
            'message': '知识文章已创建',
            'article_id': article.id
        })


class StandardComponentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """标准部件管理"""
    queryset = StandardComponent.objects.select_related('category', 'maintainer')
    serializer_class = StandardComponentSerializer
    filterset_fields = ['category', 'status']
    search_fields = ['code', 'name', 'description', 'tags']
    ordering_fields = ['code', 'usage_count', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return StandardComponentListSerializer
        return StandardComponentSerializer
    
    def perform_create(self, serializer):
        # 自动生成编码
        from apps.core.models import CodeRule
        code = CodeRule.generate_code('COMPONENT')
        serializer.save(code=code, maintainer=self.request.user)
    
    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """使用标准部件"""
        component = self.get_object()
        
        component.usage_count += 1
        component.last_used = timezone.now()
        component.save(update_fields=['usage_count', 'last_used'])
        
        return Response({'usage_count': component.usage_count})
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活部件"""
        component = self.get_object()
        component.status = 'ACTIVE'
        component.save()
        
        return Response(StandardComponentSerializer(component).data)
    
    @action(detail=True, methods=['post'])
    def deprecate(self, request, pk=None):
        """废弃部件"""
        component = self.get_object()
        component.status = 'DEPRECATED'
        component.save()
        
        return Response(StandardComponentSerializer(component).data)
