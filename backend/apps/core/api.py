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
    return drf_exception_handler(exc, context)
