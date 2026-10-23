import logging
from math import ceil

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.exceptions import APIException, ErrorDetail, Throttled
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import exception_handler as drf_exception_handler

from .error_messages import localize_detail, validation_detail
from .request_id import request_id

logger = logging.getLogger(__name__)


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
    cause = exc.__cause__
    sqlstate = getattr(cause, 'sqlstate', None) or getattr(cause, 'pgcode', None)
    if isinstance(exc, IntegrityError) and sqlstate == '23505':
        # 只识别 PostgreSQL 的真实唯一冲突；外键、非空、CHECK 等错误保留 500 与原始排障日志。
        logger.warning('数据库唯一约束冲突已转为 409', exc_info=exc)
        exc = Conflict()
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = localize_detail(response.data)
        if isinstance(exc, Throttled):
            wait = f'请在 {ceil(exc.wait)} 秒后重试。' if exc.wait is not None else '请稍后再试。'
            response.data['detail'] = ErrorDetail(f'操作过于频繁（请求限流），{wait}', code='throttled')
        if response.status_code >= 500:
            # 接口主动返回的 5xx 不经过 django.request 的异常堆栈，这里补记，并把编号交给员工报给管理员。
            logger.error('接口返回服务器错误', exc_info=exc)
            value = request_id(context.get('request'))
            if value and isinstance(response.data, dict):
                response.data['request_id'] = value
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
