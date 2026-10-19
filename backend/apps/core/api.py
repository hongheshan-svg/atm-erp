from math import ceil

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import APIException, ErrorDetail, Throttled
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import exception_handler as drf_exception_handler

from .error_messages import localize_detail, validation_detail


class Conflict(APIException):
    status_code = 409
    default_detail = '记录已发生变化，请刷新后重试。'


class Pagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 200


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        from rest_framework.exceptions import ValidationError

        exc = ValidationError(validation_detail(exc))
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = localize_detail(response.data)
        if isinstance(exc, Throttled):
            wait = f'请在 {ceil(exc.wait)} 秒后重试。' if exc.wait is not None else '请稍后再试。'
            response.data['detail'] = ErrorDetail(f'操作过于频繁（请求限流），{wait}', code='throttled')
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
