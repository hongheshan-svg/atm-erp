from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import (
    MANAGERS,
    MONEY_READERS,
    projects_for,
    require_role,
)

from ..models import (
    Project,
)
from ..serializers import (
    ProjectSerializer,
)
from ..services import bom, bom_import, budgets, corrections, execution, finance, projects
from .common import ReadView, key


class ProjectView(ReadView):
    queryset = Project.objects.select_related('customer', 'manager', 'sale').prefetch_related('members')
    serializer_class = ProjectSerializer
    write_roles = MANAGERS
    search_fields = ['code', 'name']
    filterset_fields = ['status', 'customer', 'manager']

    def get_queryset(self):
        return projects_for(self.request.user, super().get_queryset())

    def create(self, request):
        return Response(projects.create_project(request.user, key(request), request.data), status=201)

    @action(detail=True, methods=['get'])
    def demand(self, request, pk=None):
        project = self.get_object()
        return Response({'revision': bom.revision(project), 'lines': bom.demand(project)})

    @action(detail=True, methods=['get'], url_path='bom-impact')
    def bom_impact(self, request, pk=None):
        require_role(request.user, MANAGERS)
        return Response(bom.impact(self.get_object()))

    @action(detail=True, methods=['post'], url_path='bom-change-preview')
    def bom_change_preview(self, request, pk=None):
        require_role(request.user, MANAGERS)
        return Response(bom.preview_revision(request.user, self.get_object(), request.data))

    @action(detail=True, methods=['post'], url_path='revise-bom')
    def revise_bom(self, request, pk=None):
        return Response(bom.revise_bom(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['get'])
    def cost(self, request, pk=None):
        require_role(request.user, MONEY_READERS)
        return Response(finance.cost(self.get_object()))

    @action(detail=True, methods=['get'], url_path='cost-sources')
    def cost_sources(self, request, pk=None):
        require_role(request.user, MONEY_READERS)
        from django.db.models import DecimalField, ExpressionWrapper, F

        from ..models import Entry, StockMove, TimeEntry

        project = self.get_object()
        category = request.query_params.get('category', 'materials')
        if category == 'materials':
            records = (
                StockMove.objects.filter(project=project, kind__in=['issue', 'return'])
                .select_related('stock__item')
                .annotate(contribution=-F('value'))
            )

            def describe(row):
                return f'{row.stock.item.name} · {row.reason}'
        elif category == 'purchase_return_variance':
            records = (
                StockMove.objects.filter(project=project, kind='purchase_return')
                .select_related('stock__item')
                .annotate(
                    contribution=ExpressionWrapper(-F('value') - F('supplier_credit'), output_field=DecimalField())
                )
            )

            def describe(row):
                return f'{row.stock.item.name} · {row.reason}'
        elif category == 'labor':
            records = (
                TimeEntry.objects.filter(task__project=project)
                .select_related('task', 'user')
                .annotate(contribution=F('cost'))
            )

            def describe(row):
                return f'{row.task.title} · {row.user.display_name} · {row.hours}小时'
        elif category == 'expenses':
            records = Entry.objects.filter(project=project, kind='expense', cancelled=False).annotate(
                contribution=F('amount')
            )

            def describe(row):
                return row.title
        else:
            raise ValidationError('请选择材料、人工、费用或退货价差。')
        page = self.paginate_queryset(records.order_by('-contribution', '-pk'))
        return self.get_paginated_response(
            [
                {'id': row.pk, 'description': describe(row), 'amount': str(row.contribution), 'date': row.created_at}
                for row in page
            ]
        )

    @action(detail=True, methods=['get'], url_path='cost-analysis')
    def cost_analysis(self, request, pk=None):
        require_role(request.user, MONEY_READERS)
        project = self.get_object()
        report = budgets.analysis(project)
        if project.forecast_at and not report['forecast_stale']:
            from ..models import Entry, StockMove, TimeEntry

            report['forecast_stale'] = (
                project.purchases.filter(updated_at__gt=project.forecast_at).exists()
                or StockMove.objects.filter(project=project, created_at__gt=project.forecast_at).exists()
                or TimeEntry.objects.filter(task__project=project, created_at__gt=project.forecast_at).exists()
                or Entry.objects.filter(project=project, kind='expense', updated_at__gt=project.forecast_at).exists()
                or project.bom_lines.filter(updated_at__gt=project.forecast_at).exists()
            )
        return Response(report)

    @action(detail=True, methods=['post'], url_path='budget')
    def budget(self, request, pk=None):
        return Response(budgets.revise(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def forecast(self, request, pk=None):
        return Response(budgets.forecast(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'], url_path='import-preview', parser_classes=[MultiPartParser])
    def import_preview(self, request, pk=None):
        if set(request.data) != {'file'} or len(request.FILES.getlist('file')) != 1:
            raise ValidationError({'file': '请提交一个表格文件。'})
        return Response(bom_import.preview(self.get_object(), request.FILES['file']))

    @action(detail=False, methods=['get'], url_path='bom-template')
    def bom_template(self, request):
        require_role(request.user, MANAGERS)
        from ..services.tabular import document

        return document('bom-template', bom_import.HEADERS, [], request.query_params.get('file_format', 'csv'))

    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        return Response(corrections.edit_project(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        return Response(corrections.cancel_project(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        return Response(corrections.reopen_project(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        return Response(execution.close(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        return Response(execution.ship(request.user, key(request), self.get_object().pk, request.data))

    @action(detail=True, methods=['post'])
    def service(self, request, pk=None):
        return Response(execution.service(request.user, key(request), self.get_object().pk, request.data))
