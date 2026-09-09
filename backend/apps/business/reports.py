from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import require_reports

from .services.reports import summary
from .services.tabular import export_rows


class ReportsView(APIView):
    def get(self, request):
        require_reports(request.user)
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
        return Response(summary(request.query_params))
