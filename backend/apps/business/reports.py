from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import projects_for, require_reports

from .services.reports import summary
from .services.tabular import export_rows


class ReportsView(APIView):
    def get(self, request):
        require_reports(request.user)
        if request.query_params.get('view'):
            from .services.attention import projection

            return Response(projection(request.query_params))
        if request.query_params.get('file_format'):
            data = summary(request.query_params, export=True)
            rows = [{'record_type': '项目', **row} for row in data['results']]
            rows.append(
                {
                    'record_type': '合计',
                    'name': '当前筛选全部项目',
                    **{
                        key: value
                        for key, value in data['summary'].items()
                        if key
                        in {
                            'contract_amount',
                            'actual_cost',
                            'committed_cost',
                            'receivable',
                            'payable',
                            'overdue_receivable',
                            'overdue_payable',
                            'refund_out',
                            'refund_in',
                        }
                    },
                }
            )
            return export_rows(
                'reports',
                rows,
                request.query_params['file_format'],
                ['code', 'name', 'contract_amount', 'actual_cost'],
            )
        from .models import Project

        data = summary(request.query_params)
        permitted = set(
            projects_for(
                request.user, Project.objects.filter(pk__in=[row['id'] for row in data['results']])
            ).values_list('pk', flat=True)
        )
        for row in data['results']:
            row['can_open'] = row['id'] in permitted
        return Response(data)
