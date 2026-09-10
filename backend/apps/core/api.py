from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = '记录已发生变化，请刷新后重试。'


class Pagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 200


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        from rest_framework.exceptions import ValidationError

        exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
    response = drf_exception_handler(exc, context)
    if response is not None and response.status_code == 409 and isinstance(response.data, dict):
        view = context.get('view')
        pk = getattr(view, 'kwargs', {}).get('pk')
        resource = getattr(view, 'basename', '')
        paths = {
            'purchaseorder': '/purchases',
            'entry': '/finance',
            'reconciliation': '/finance',
            'project': '/projects',
        }
        if pk and resource in paths:
            resources = {
                'purchaseorder': 'purchases',
                'entry': 'entries',
                'reconciliation': 'reconciliations',
                'project': 'projects',
            }
            target = (
                f'/projects/{pk}'
                if resource == 'project'
                else f'{paths[resource]}?resource={resources[resource]}&focus={pk}'
            )
            response.data['actions'] = [{'label': '打开原单据核对并处理', 'path': target}]
    return response
