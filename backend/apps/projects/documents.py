"""
Elasticsearch document definitions for projects
"""
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from .models import Project, ProjectTask


@registry.register_document
class ProjectDocument(Document):
    """Elasticsearch document for Project model"""

    customer = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
        'code': fields.TextField(),
    })

    manager = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'username': fields.TextField(),
        'first_name': fields.TextField(),
        'last_name': fields.TextField(),
    })

    class Index:
        name = 'projects'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

    class Django:
        model = Project
        fields = [
            'code',
            'name',
            'start_date',
            'end_date',
            'status',
            'budget_total',
            'budget_material',
            'budget_labor',
            'budget_expense',
        ]
        related_models = ['customer', 'manager']

    def get_queryset(self):
        return super().get_queryset().select_related('customer', 'manager')


@registry.register_document
class ProjectTaskDocument(Document):
    """Elasticsearch document for ProjectTask model"""

    project = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
        'code': fields.TextField(),
    })

    assignee = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'username': fields.TextField(),
        'first_name': fields.TextField(),
        'last_name': fields.TextField(),
    })

    class Index:
        name = 'project_tasks'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

    class Django:
        model = ProjectTask
        fields = [
            'name',
            'description',
            'planned_hours',
            'actual_hours',
            'progress_percent',
            'status',
            'start_date',
            'end_date',
        ]
        related_models = ['project', 'assignee']

    def get_queryset(self):
        return super().get_queryset().select_related('project', 'assignee')

