"""请求编号：员工报出的错误编号与 Nginx 访问日志、后端异常日志对应同一请求。

只记录编号与已认证用户 ID，不读取 Authorization、Cookie、请求体或密码。
"""

import logging
import re
import uuid
from contextvars import ContextVar

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import JsonResponse

HEADER = 'X-Request-ID'
SERVER_ERROR = '服务器处理失败，请稍后重试或联系管理员。'
# 与 Nginx 的 map 保持一致：只接受安全字符且不超过 64 位，杜绝借编号伪造日志行。
SAFE_ID = re.compile(r'[A-Za-z0-9._-]{1,64}')
_current = ContextVar('lean_erp_request', default=None)


def clean(value):
    return value if isinstance(value, str) and SAFE_ID.fullmatch(value) else uuid.uuid4().hex


def request_id(request=None):
    """返回请求编号；request 可以是 Django 或 DRF 请求，缺省时取当前请求。"""
    request = getattr(request, '_request', request) or _current.get()
    return getattr(request, 'request_id', None)


class RequestIDMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def __call__(self, request):
        if iscoroutinefunction(self):
            return self.__acall__(request)
        token = self.start(request)
        try:
            response = self.get_response(request)
        finally:
            _current.reset(token)
        return self.finish(request, response)

    async def __acall__(self, request):
        token = self.start(request)
        try:
            response = await self.get_response(request)
        finally:
            _current.reset(token)
        return self.finish(request, response)

    @staticmethod
    def start(request):
        request.request_id = clean(request.META.get('HTTP_X_REQUEST_ID'))
        return _current.set(request)

    @staticmethod
    def finish(request, response):
        response[HEADER] = request.request_id
        return response


class RequestContextFilter(logging.Filter):
    """给每条日志补 request_id 与 user_id；不在请求内或未登录时为 '-'。"""

    def filter(self, record):
        # django.request 的 4xx/5xx 记录在中间件返回后才写，随记录带着原请求。
        request = getattr(record, 'request', None)
        request = getattr(request, '_request', request)
        if not hasattr(request, 'META'):
            request = _current.get()
        user = getattr(request, 'user', None)
        if not hasattr(record, 'request_id'):
            record.request_id = getattr(request, 'request_id', None) or '-'
        if not hasattr(record, 'user_id'):
            record.user_id = user.pk if getattr(user, 'is_authenticated', False) else '-'
        return True


def server_error(request):
    """未捕获异常的 500 响应；堆栈由 django.request 以 ERROR 记录，同带编号。"""
    value = request_id(request) or clean(None)
    response = JsonResponse({'detail': SERVER_ERROR, 'request_id': value}, status=500)
    response[HEADER] = value
    return response
