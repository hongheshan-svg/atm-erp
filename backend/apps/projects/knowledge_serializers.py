"""
知识库序列化器
"""
from rest_framework import serializers
from .knowledge_models import (
    KnowledgeCategory, KnowledgeArticle, ProjectArchive,
    TechnicalIssue, StandardComponent
)


class KnowledgeCategorySerializer(serializers.ModelSerializer):
    """知识分类序列化器"""
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    article_count = serializers.SerializerMethodField()
    
    class Meta:
        model = KnowledgeCategory
        fields = '__all__'
    
    def get_article_count(self, obj):
        return obj.articles.filter(is_deleted=False, status='PUBLISHED').count()


class KnowledgeCategoryTreeSerializer(serializers.ModelSerializer):
    """知识分类树形序列化器"""
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = KnowledgeCategory
        fields = ['id', 'code', 'name', 'description', 'icon', 'sort_order', 'children']
    
    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False).order_by('sort_order', 'code')
        return KnowledgeCategoryTreeSerializer(children, many=True).data


class KnowledgeArticleSerializer(serializers.ModelSerializer):
    """知识文章序列化器"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    author_name = serializers.CharField(source='author.name', read_only=True)
    article_type_display = serializers.CharField(source='get_article_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = KnowledgeArticle
        fields = '__all__'


class KnowledgeArticleListSerializer(serializers.ModelSerializer):
    """知识文章列表序列化器（简化）"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    author_name = serializers.CharField(source='author.name', read_only=True)
    article_type_display = serializers.CharField(source='get_article_type_display', read_only=True)
    
    class Meta:
        model = KnowledgeArticle
        fields = [
            'id', 'title', 'category', 'category_name', 'article_type',
            'article_type_display', 'summary', 'tags', 'author', 'author_name',
            'view_count', 'like_count', 'published_at', 'created_at'
        ]


class ProjectArchiveSerializer(serializers.ModelSerializer):
    """项目归档报告序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.name', read_only=True)
    cost_variance_amount = serializers.SerializerMethodField()
    schedule_variance_days = serializers.SerializerMethodField()
    
    class Meta:
        model = ProjectArchive
        fields = '__all__'
    
    def get_cost_variance_amount(self, obj):
        return float(obj.actual_cost - obj.budget_amount)
    
    def get_schedule_variance_days(self, obj):
        if obj.original_end and obj.actual_end:
            return (obj.actual_end - obj.original_end).days
        return 0


class TechnicalIssueSerializer(serializers.ModelSerializer):
    """技术问题记录序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    reported_by_name = serializers.CharField(source='reported_by.name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TechnicalIssue
        fields = '__all__'


class TechnicalIssueListSerializer(serializers.ModelSerializer):
    """技术问题列表序列化器（简化）"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = TechnicalIssue
        fields = [
            'id', 'title', 'project', 'project_name', 'category', 'category_name',
            'severity', 'severity_display', 'status', 'status_display',
            'tags', 'occurred_at', 'resolved_at', 'created_at'
        ]


class StandardComponentSerializer(serializers.ModelSerializer):
    """标准部件序列化器"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    maintainer_name = serializers.CharField(source='maintainer.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = StandardComponent
        fields = '__all__'
        read_only_fields = ['code', 'usage_count', 'last_used']


class StandardComponentListSerializer(serializers.ModelSerializer):
    """标准部件列表序列化器（简化）"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = StandardComponent
        fields = [
            'id', 'code', 'name', 'category', 'category_name', 'version',
            'status', 'status_display', 'estimated_cost', 'usage_count',
            'tags', 'created_at'
        ]
